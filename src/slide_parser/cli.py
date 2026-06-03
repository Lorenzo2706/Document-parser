"""Typer CLI entry-point: ``slide-parser``."""

from __future__ import annotations

import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import typer
from rich.console import Console

from slide_parser.core import ParseResult, parse
from slide_parser.utils import doc_stem

SLIDE_EXTS = {".pdf", ".pptx"}
COPY_EXTS = {".docx", ".doc", ".html", ".htm", ".txt"}

app = typer.Typer(
    add_completion=False,
    help="Convert PDF/PPTX slide decks to LLM-ready Markdown with zero data loss.",
    no_args_is_help=True,
)
console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)


def _process_one(
    input_path: Path,
    out_dir: Path,
    *,
    ocr: bool,
    lang: str,
    with_images: bool | None,
) -> tuple[Path, ParseResult | Exception]:
    try:
        result = parse(
            input_path,
            out_dir=out_dir,
            ocr=ocr,
            lang=lang,
            with_images=with_images,
        )
        return input_path, result
    except Exception as exc:  # surface, do not abort the whole batch
        return input_path, exc


@app.command("parse")
def parse_cmd(
    inputs: list[Path] = typer.Argument(
        ..., exists=True, readable=True, help="One or more .pdf / .pptx files."
    ),
    out_dir: Path = typer.Option(
        Path("./out"), "--out", "-o", help="Output directory for Markdown + assets."
    ),
    ocr: bool = typer.Option(
        True, "--ocr/--no-ocr", help="Enable Tesseract OCR (PDF + PPTX)."
    ),
    lang: str = typer.Option(
        "eng",
        "--lang",
        "-l",
        help="Tesseract language(s) — '+' or ',' separated, e.g. 'ita+eng'.",
    ),
    with_images: bool | None = typer.Option(
        None,
        "--images/--no-images",
        help="Embed images into <stem>/assets/. Default: off with --ocr, on with --no-ocr.",
    ),
    workers: int = typer.Option(
        1, "--workers", "-j", min=1, help="Parallel workers for batch parsing."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Parse INPUTS and write one Markdown file per document to --out."""
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        images_eff = with_images if with_images is not None else (not ocr)
        console.print(
            f"[dim]parsing {len(inputs)} file(s) → {out_dir} (ocr={ocr}, lang={lang}, "
            f"images={images_eff}, workers={workers})[/dim]"
        )

    failures = 0

    if workers == 1:
        for path in inputs:
            _, res = _process_one(
                path, out_dir, ocr=ocr, lang=lang, with_images=with_images
            )
            failures += _report(path, res)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    _process_one, path, out_dir, ocr=ocr, lang=lang, with_images=with_images
                ): path
                for path in inputs
            }
            for fut in as_completed(futures):
                path, res = fut.result()
                failures += _report(path, res)

    if failures:
        raise typer.Exit(code=1)


@app.command("mirror")
def mirror_cmd(
    src: Path = typer.Argument(
        ..., exists=True, file_okay=False, dir_okay=True, readable=True,
        help="Source folder to scan recursively.",
    ),
    dst: Path = typer.Argument(..., help="Destination folder (created if missing)."),
    ocr: bool = typer.Option(True, "--ocr/--no-ocr"),
    lang: str = typer.Option("eng", "--lang", "-l"),
    with_images: bool | None = typer.Option(
        None,
        "--images/--no-images",
        help="Embed images. Default: off with --ocr, on with --no-ocr.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Mirror SRC tree into DST, parsing slides and copying documents."""
    src = src.resolve()
    dst = dst.resolve()
    dst.mkdir(parents=True, exist_ok=True)

    counts = {"parsed": 0, "copied": 0, "skipped": 0, "ignored": 0, "failed": 0}

    for entry in sorted(src.rglob("*")):
        rel = entry.relative_to(src)
        mirrored = dst / rel
        if entry.is_dir():
            mirrored.mkdir(parents=True, exist_ok=True)
            continue
        if not entry.is_file():
            continue

        ext = entry.suffix.lower()
        mirrored.parent.mkdir(parents=True, exist_ok=True)

        if ext in SLIDE_EXTS:
            target = mirrored.parent / f"{doc_stem(entry)}.md"
            if target.exists() and target.stat().st_mtime >= entry.stat().st_mtime:
                if verbose:
                    console.print(f"[dim]= {rel} (up-to-date)[/dim]")
                counts["skipped"] += 1
                continue
            _, res = _process_one(
                entry, mirrored.parent, ocr=ocr, lang=lang, with_images=with_images
            )
            if isinstance(res, Exception):
                err_console.print(f"[red]FAIL {rel}: {res}[/red]")
                counts["failed"] += 1
            else:
                notes = " (notes)" if res.has_notes else ""
                console.print(
                    f"[green]OK[/green] {rel} -> {res.markdown_path.relative_to(dst)} "
                    f"[dim]({res.n_slides} slides{notes})[/dim]"
                )
                counts["parsed"] += 1
        elif ext in COPY_EXTS:
            if mirrored.exists() and mirrored.stat().st_mtime >= entry.stat().st_mtime:
                if verbose:
                    console.print(f"[dim]= {rel} (up-to-date)[/dim]")
                counts["skipped"] += 1
                continue
            try:
                shutil.copy2(entry, mirrored)
                console.print(f"[cyan]->[/cyan] {rel} [dim](copied)[/dim]")
                counts["copied"] += 1
            except Exception as exc:
                err_console.print(f"[red]FAIL {rel}: {exc}[/red]")
                counts["failed"] += 1
        else:
            if verbose:
                console.print(f"[dim]· {rel} (ignored)[/dim]")
            counts["ignored"] += 1

    console.print(
        f"[bold]Done.[/bold] parsed={counts['parsed']} copied={counts['copied']} "
        f"skipped={counts['skipped']} ignored={counts['ignored']} failed={counts['failed']}"
    )
    if counts["failed"]:
        raise typer.Exit(code=1)


def _report(path: Path, res: ParseResult | Exception) -> int:
    if isinstance(res, Exception):
        err_console.print(f"[red]FAIL {path}: {res}[/red]")
        return 1
    notes_flag = " (notes)" if res.has_notes else ""
    console.print(
        f"[green]OK[/green] {path.name} -> {res.markdown_path} "
        f"[dim]({res.n_slides} slides{notes_flag})[/dim]"
    )
    return 0


if __name__ == "__main__":
    app()
