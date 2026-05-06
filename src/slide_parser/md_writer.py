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
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml
from docling_core.types.doc import DoclingDocument, ImageRefMode

from slide_parser.utils import ensure_dir

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


def _replace_placeholders(markdown: str, links: list[str]) -> str:
    out = markdown
    for link in links:
        repl = f"![Image]({link})"
        out = out.replace(IMAGE_PLACEHOLDER, repl, 1)
    return out


def _assemble(
    doc: DoclingDocument,
    images_by_page: dict[int, list[str]],
    notes_by_slide: dict[int, str] | None,
    with_images: bool,
) -> tuple[str, int]:
    pages = sorted(doc.pages.keys()) if doc.pages else [1]
    chunks: list[str] = []
    for slide_idx, page_no in enumerate(pages, start=1):
        body = doc.export_to_markdown(
            page_no=page_no, image_mode=ImageRefMode.PLACEHOLDER
        ).strip()
        if with_images and images_by_page.get(page_no):
            body = _replace_placeholders(body, images_by_page[page_no])
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
) -> WriteResult:
    ensure_dir(out_dir)
    md_path = out_dir / f"{stem}.md"
    assets_dir = out_dir / stem / "assets"
    rel_prefix = f"{stem}/assets/"

    images_by_page: dict[int, list[str]] = {}
    if with_images:
        images_by_page = _save_pictures(doc, assets_dir, rel_prefix)

    body, n_slides = _assemble(doc, images_by_page, notes_by_slide, with_images)

    frontmatter = _build_frontmatter(
        {
            "source": source,
            "n_slides": n_slides,
            "parsed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ocr_enabled": ocr_enabled,
            "ocr_lang": lang,
            "generator": "slide-parser",
        }
    )
    md_path.write_text(frontmatter + body, encoding="utf-8")
    return WriteResult(markdown_path=md_path, assets_dir=assets_dir, n_slides=n_slides)
