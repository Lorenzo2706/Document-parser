"""Serialize a DoclingDocument to a per-slide Markdown file + assets/ directory.

Strategy (works around two Docling quirks):

1. Docling's ``page_break_placeholder`` is only emitted at the very end of
   the document, so we cannot rely on it to split slides. Instead we iterate
   ``doc.pages`` and call ``export_to_markdown(page_no=N)`` per page.
2. Docling's ``save_as_markdown`` writes absolute paths into the saved
   Markdown for image references. We extract pictures ourselves with
   ``picture.get_image(doc)``, write them under ``<stem>/assets/`` with a
   content-hash filename, and replace the ``<!-- image -->`` placeholders
   in the per-page markdown in document order.
"""

from __future__ import annotations

import hashlib
import io
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml
from docling_core.types.doc import DoclingDocument, ImageRefMode

from document_parser import ocr
from document_parser.utils import ensure_dir

IMAGE_PLACEHOLDER = "<!-- image -->"


@dataclass(slots=True)
class WriteResult:
    markdown_path: Path
    assets_dir: Path
    n_slides: int


def _build_frontmatter(meta: dict) -> str:
    body = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{body}\n---\n\n"


def _format_notes_block(text: str) -> str:
    quoted = "\n".join(f"> {line}" if line else ">" for line in text.splitlines())
    return f"\n\n> **Speaker notes:**\n{quoted}\n"


def _save_pictures(
    doc: DoclingDocument, assets_dir: Path, rel_prefix: str
) -> dict[int, list[str]]:
    """Save every picture to ``assets_dir`` and return ``{page: [relpath, ...]}``.

    Order within each page mirrors ``doc.pictures``, which itself follows
    document order, so it lines up with the placeholder positions emitted by
    ``export_to_markdown``.
    """
    ensure_dir(assets_dir)
    by_page: dict[int, list[str]] = defaultdict(list)
    for pic in doc.pictures:
        page = pic.prov[0].page_no if pic.prov else 1
        try:
            pil = pic.get_image(doc)
        except Exception:
            pil = None
        if pil is None:
            continue
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        data = buf.getvalue()
        digest = hashlib.sha1(data).hexdigest()[:12]
        idx_on_page = len(by_page[page]) + 1
        fname = f"slide-{page:03d}-{idx_on_page:02d}-{digest}.png"
        (assets_dir / fname).write_bytes(data)
        by_page[page].append(f"{rel_prefix}{fname}")
    return by_page


def _ocr_pictures(doc: DoclingDocument, lang: str) -> dict[int, list[str]]:
    """OCR every picture and return ``{page: [text, ...]}``.

    Emits one slot per picture (empty string when the image yields no text or
    cannot be loaded) in the same order as ``_save_pictures`` and the
    ``<!-- image -->`` placeholders, so substitution stays aligned.
    """
    by_page: dict[int, list[str]] = defaultdict(list)
    for pic in doc.pictures:
        page = pic.prov[0].page_no if pic.prov else 1
        try:
            pil = pic.get_image(doc)
        except Exception:
            pil = None
        text = ocr.ocr_image(pil, lang) if pil is not None else ""
        by_page[page].append(text)
    return by_page


def _replace_placeholders(markdown: str, replacements: list[str]) -> str:
    """Replace ``IMAGE_PLACEHOLDER`` markers in order with ``replacements``.

    An empty replacement string drops that placeholder (used for OCR'd images
    with no recognized text).
    """
    out = markdown
    for repl in replacements:
        out = out.replace(IMAGE_PLACEHOLDER, repl, 1)
    return out


def _placeholder_replacements(
    page_no: int,
    images_by_page: dict[int, list[str]],
    ocr_text_by_page: dict[int, list[str]],
    with_images: bool,
    ocr_images: bool,
) -> list[str]:
    """Build the ordered per-placeholder replacement strings for one page."""
    imgs = images_by_page.get(page_no, []) if with_images else []
    texts = ocr_text_by_page.get(page_no, []) if ocr_images else []
    count = max(len(imgs), len(texts))
    out: list[str] = []
    for i in range(count):
        parts: list[str] = []
        if ocr_images and i < len(texts) and texts[i]:
            parts.append(texts[i])
        if with_images and i < len(imgs):
            parts.append(f"![Image]({imgs[i]})")
        out.append("\n\n".join(parts))
    return out


def _cleanup(body: str) -> str:
    """Drop any leftover image placeholders and collapse blank-line runs."""
    body = body.replace(IMAGE_PLACEHOLDER, "")
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def _assemble(
    doc: DoclingDocument,
    images_by_page: dict[int, list[str]],
    ocr_text_by_page: dict[int, list[str]],
    notes_by_slide: dict[int, str] | None,
    with_images: bool,
    ocr_images: bool,
) -> tuple[str, int]:
    pages = sorted(doc.pages.keys()) if doc.pages else [1]
    chunks: list[str] = []
    for slide_idx, page_no in enumerate(pages, start=1):
        body = doc.export_to_markdown(
            page_no=page_no, image_mode=ImageRefMode.PLACEHOLDER
        ).strip()
        if with_images or ocr_images:
            replacements = _placeholder_replacements(
                page_no, images_by_page, ocr_text_by_page, with_images, ocr_images
            )
            body = _replace_placeholders(body, replacements)
        body = _cleanup(body)
        chunk = f"## Slide {slide_idx}\n\n{body}".rstrip()
        if notes_by_slide and slide_idx in notes_by_slide:
            chunk += _format_notes_block(notes_by_slide[slide_idx])
        chunks.append(chunk)
    return "\n\n".join(chunks).rstrip() + "\n", len(pages)


def write_markdown(
    doc: DoclingDocument,
    *,
    out_dir: Path,
    stem: str,
    source: str,
    ocr_enabled: bool,
    lang: str,
    notes_by_slide: dict[int, str] | None = None,
    with_images: bool = True,
    ocr_images: bool = False,
) -> WriteResult:
    ensure_dir(out_dir)
    md_path = out_dir / f"{stem}.md"
    assets_dir = out_dir / stem / "assets"
    rel_prefix = f"{stem}/assets/"

    images_by_page: dict[int, list[str]] = {}
    if with_images:
        images_by_page = _save_pictures(doc, assets_dir, rel_prefix)

    ocr_text_by_page: dict[int, list[str]] = {}
    if ocr_images:
        ocr_text_by_page = _ocr_pictures(doc, lang)

    body, n_slides = _assemble(
        doc, images_by_page, ocr_text_by_page, notes_by_slide, with_images, ocr_images
    )

    frontmatter = _build_frontmatter(
        {
            "source": source,
            "n_slides": n_slides,
            "parsed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ocr_enabled": ocr_enabled,
            "ocr_lang": lang,
            "generator": "document-parser",
        }
    )
    md_path.write_text(frontmatter + body, encoding="utf-8")
    return WriteResult(markdown_path=md_path, assets_dir=assets_dir, n_slides=n_slides)
