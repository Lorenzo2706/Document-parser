"""Typer CLI entry-point: ``document-parser``."""

from __future__ import annotations

import shutil
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import typer
from rich.console import Console

from document_parser.core import ParseResult, parse
from document_parser.excel_backend import ExcelResult, convert_excel
from document_parser.utils import doc_stem

SLIDE_EXTS = {".pdf", ".pptx"}
EXCEL_EXTS = {".xlsx", ".xlsm", ".xls"}
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


def _process_excel(
    input_path: Path,
    out_dir: Path,
    *,
    sep: str,
) -> tuple[Path, ExcelResult | Exception]:
    try:
        return input_path, convert_excel(input_path, out_dir=out_dir, sep=sep)
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


@app.command("excel")
def excel_cmd(
    inputs: list[Path] = typer.Argument(
        ..., exists=True, readable=True, help="One or more .xlsx / .xlsm / .xls files."
    ),
    out_dir: Path = typer.Option(
        Path("./out"), "--out", "-o", help="Output directory for the CSV subfolders."
    ),
    sep: str = typer.Option(",", "--sep", help="CSV field separator."),
    workers: int = typer.Option(
        1, "--workers", "-j", min=1, help="Parallel workers for batch conversion."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Convert each workbook in INPUTS to CSVs (one per sheet) under --out/<stem>/."""
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        console.print(
            f"[dim]converting {len(inputs)} workbook(s) -> {out_dir} "
            f"(sep={sep!r}, workers={workers})[/dim]"
        )

    failures = 0

    if workers == 1:
        for path in inputs:
            _, res = _process_excel(path, out_dir, sep=sep)
            failures += _report_excel(path, res)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_process_excel, path, out_dir, sep=sep): path for path in inputs
            }
            for fut in as_completed(futures):
                path, res = fut.result()
                failures += _report_excel(path, res)

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

    counts = {"parsed": 0, "excel": 0, "copied": 0, "skipped": 0, "ignored": 0, "failed": 0}

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
        elif ext in EXCEL_EXTS:
            subdir = mirrored.parent / doc_stem(entry)
            newest = _newest_mtime(subdir, "*.csv")
            if newest is not None and newest >= entry.stat().st_mtime:
                if verbose:
                    console.print(f"[dim]= {rel} (up-to-date)[/dim]")
                counts["skipped"] += 1
                continue
            _, res = _process_excel(entry, mirrored.parent, sep=",")
            if isinstance(res, Exception):
                err_console.print(f"[red]FAIL {rel}: {res}[/red]")
                counts["failed"] += 1
            else:
                console.print(
                    f"[green]OK[/green] {rel} -> {res.out_subdir.relative_to(dst)} "
                    f"[dim]({res.n_sheets} sheets)[/dim]"
                )
                counts["excel"] += 1
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
        f"[bold]Done.[/bold] parsed={counts['parsed']} excel={counts['excel']} "
        f"copied={counts['copied']} skipped={counts['skipped']} "
        f"ignored={counts['ignored']} failed={counts['failed']}"
    )
    if counts["failed"]:
        raise typer.Exit(code=1)


@app.command("zip")
def zip_cmd(
    folder: Path = typer.Argument(
        ..., exists=True, file_okay=False, dir_okay=True, readable=True,
        help="Folder to archive (e.g. a conversion output tree).",
    ),
    out: Path = typer.Option(
        None, "--out", "-o", help="Archive path. Default: <folder>.zip alongside it."
    ),
    keep: bool = typer.Option(
        False, "--keep/--delete", help="Keep the source folder. Default: delete after archiving."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Archive FOLDER into a .zip, writing a .log of every file added; delete it unless --keep."""
    folder = folder.resolve()
    archive = (out.resolve() if out else folder.with_suffix(folder.suffix + ".zip"))
    archive.parent.mkdir(parents=True, exist_ok=True)
    log_path = archive.with_name(archive.name + ".log")

    lines = [f"source: {folder}", f"archive: {archive}", ""]
    added = 0
    errors = 0
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for entry in sorted(folder.rglob("*")):
            if not entry.is_file():
                continue
            rel = entry.relative_to(folder.parent).as_posix()
            try:
                zf.write(entry, arcname=rel)
                lines.append(f"ADDED {rel}")
                added += 1
                if verbose:
                    console.print(f"[cyan]+[/cyan] {rel}")
            except Exception as exc:
                lines.append(f"ERROR {rel}: {exc}")
                errors += 1
                err_console.print(f"[red]FAIL {rel}: {exc}[/red]")

    lines.append("")
    lines.append(f"summary: files={added} errors={errors}")

    deleted = False
    if errors == 0 and not keep:
        try:
            shutil.rmtree(folder)
            deleted = True
            lines.append(f"DELETED {folder}")
        except Exception as exc:
            lines.append(f"ERROR deleting {folder}: {exc}")
            err_console.print(f"[red]FAIL deleting {folder}: {exc}[/red]")
            errors += 1
    else:
        lines.append(f"KEPT {folder}")

    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    status = "deleted source" if deleted else ("kept source" if keep else "kept source (errors)")
    console.print(
        f"[green]OK[/green] {folder.name} -> {archive} "
        f"[dim]({added} files, {status}, log: {log_path.name})[/dim]"
    )
    if errors:
        raise typer.Exit(code=1)


def _newest_mtime(directory: Path, pattern: str = "*") -> float | None:
    """Most-recent mtime among files matching ``pattern`` in ``directory``, or None if none."""
    if not directory.is_dir():
        return None
    mtimes = [p.stat().st_mtime for p in directory.glob(pattern) if p.is_file()]
    return max(mtimes) if mtimes else None


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


def _report_excel(path: Path, res: ExcelResult | Exception) -> int:
    if isinstance(res, Exception):
        err_console.print(f"[red]FAIL {path}: {res}[/red]")
        return 1
    console.print(
        f"[green]OK[/green] {path.name} -> {res.out_subdir} "
        f"[dim]({res.n_sheets} sheets)[/dim]"
    )
    return 0


if __name__ == "__main__":
    app()
