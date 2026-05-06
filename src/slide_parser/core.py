"""High-level orchestration: dispatch by file type and produce Markdown."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from slide_parser.md_writer import WriteResult, write_markdown
from slide_parser.notes_extractor import extract_notes
from slide_parser.pdf_backend import convert_pdf
from slide_parser.pptx_backend import convert_pptx
from slide_parser.utils import doc_stem


@dataclass(slots=True)
class ParseResult:
    source: Path
    markdown_path: Path
    assets_dir: Path
    n_slides: int
    has_notes: bool
    warnings: list[str] = field(default_factory=list)


def _resolve_stem(input_path: Path) -> str:
    return doc_stem(input_path)


def parse_pdf(
    input_path: str | Path,
    *,
    out_dir: str | Path,
    ocr: bool = True,
    lang: str = "eng",
    with_images: bool = True,
) -> ParseResult:
    input_path = Path(input_path)
    out_dir = Path(out_dir)
    doc = convert_pdf(input_path, ocr=ocr, lang=lang, with_images=with_images)
    res: WriteResult = write_markdown(
        doc,
        out_dir=out_dir,
        stem=_resolve_stem(input_path),
        source=str(input_path),
        ocr_enabled=ocr,
        lang=lang,
        notes_by_slide=None,
        with_images=with_images,
    )
    return ParseResult(
        source=input_path,
        markdown_path=res.markdown_path,
        assets_dir=res.assets_dir,
        n_slides=res.n_slides,
        has_notes=False,
    )


def parse_pptx(
    input_path: str | Path,
    *,
    out_dir: str | Path,
    with_images: bool = True,
) -> ParseResult:
    input_path = Path(input_path)
    out_dir = Path(out_dir)
    doc = convert_pptx(input_path)
    notes = extract_notes(input_path)
    res: WriteResult = write_markdown(
        doc,
        out_dir=out_dir,
        stem=_resolve_stem(input_path),
        source=str(input_path),
        ocr_enabled=False,
        lang="n/a",
        notes_by_slide=notes,
        with_images=with_images,
    )
    return ParseResult(
        source=input_path,
        markdown_path=res.markdown_path,
        assets_dir=res.assets_dir,
        n_slides=res.n_slides,
        has_notes=bool(notes),
    )


def parse(
    input_path: str | Path,
    *,
    out_dir: str | Path,
    ocr: bool = True,
    lang: str = "eng",
    with_images: bool = True,
) -> ParseResult:
    """Dispatch by extension. Raises ``ValueError`` for unsupported formats."""
    input_path = Path(input_path)
    suffix = input_path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(
            input_path, out_dir=out_dir, ocr=ocr, lang=lang, with_images=with_images
        )
    if suffix == ".pptx":
        return parse_pptx(input_path, out_dir=out_dir, with_images=with_images)
    raise ValueError(
        f"Unsupported file type: {suffix!r}. Supported: .pdf, .pptx"
    )
