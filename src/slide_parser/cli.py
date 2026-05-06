"""Typer CLI entry-point: ``slide-parser``."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import typer
from rich.console import Console

from slide_parser.core import ParseResult, parse

app = typer.Typer(
    add_completion=False,
    help="Convert PDF/PPTX slide decks to LLM-ready Markdown with zero data loss.",
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)


def _process_one(
    input_path: Path,
    out_dir: Path,
    *,
    ocr: bool,
    lang: str,
    with_images: bool,
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


@app.command()
def main(
    inputs: list[Path] = typer.Argument(
        ..., exists=True, readable=True, help="One or more .pdf / .pptx files."
    ),
    out_dir: Path = typer.Option(
        Path("./out"), "--out", "-o", help="Output directory for Markdown + assets."
    ),
    ocr: bool = typer.Option(True, "--ocr/--no-ocr", help="Enable Tesseract OCR for PDF."),
    lang: str = typer.Option(
        "eng",
        "--lang",
        "-l",
        help="Tesseract language(s) — '+' or ',' separated, e.g. 'ita+eng'.",
    ),
    with_images: bool = typer.Option(
        True, "--images/--no-images", help="Extract images into <stem>/assets/."
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
        console.print(
            f"[dim]parsing {len(inputs)} file(s) → {out_dir} (ocr={ocr}, lang={lang}, "
            f"images={with_images}, workers={workers})[/dim]"
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


def _report(path: Path, res: ParseResult | Exception) -> int:
    if isinstance(res, Exception):
        err_console.print(f"[red]✗ {path}: {res}[/red]")
        return 1
    notes_flag = " (notes)" if res.has_notes else ""
    console.print(
        f"[green]✓[/green] {path.name} → {res.markdown_path} "
        f"[dim]({res.n_slides} slides{notes_flag})[/dim]"
    )
    return 0


if __name__ == "__main__":
    app()
