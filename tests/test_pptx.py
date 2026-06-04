from __future__ import annotations

from pathlib import Path

import pytest

from document_parser import parse


def _tesseract_available() -> bool:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


tesseract_available = pytest.mark.skipif(
    not _tesseract_available(),
    reason="Tesseract binary not available.",
)


def test_pptx_end_to_end(tmp_path: Path, sample_pptx: Path) -> None:
    res = parse(sample_pptx, out_dir=tmp_path, ocr=False)
    md = res.markdown_path.read_text(encoding="utf-8")

    assert res.n_slides == 2
    assert res.has_notes is True
    assert res.markdown_path.exists()

    # Front-matter present and well-formed.
    assert md.startswith("---\n")
    assert "generator: document-parser" in md
    assert "n_slides: 2" in md

    # Each slide has its heading.
    assert "## Slide 1" in md
    assert "## Slide 2" in md

    # Slide content was preserved.
    for token in (
        "Q1 Roadmap",
        "Ship parser MVP",
        "Onboard 3 design partners",
        "Cut infra cost 20%",
        "Metrics",
        "12,400",
        "Retention",
    ):
        assert token in md, f"missing token: {token!r}"

    # Speaker notes were merged in for both slides.
    assert md.count("**Speaker notes:**") == 2
    assert "design-partner pipeline" in md
    assert "Retention is the key narrative" in md

    # An image was extracted and referenced relatively.
    assert "![Image](sample/assets/" in md
    assets = list(res.assets_dir.glob("*.png"))
    assert len(assets) == 1


def test_pptx_no_images(tmp_path: Path, sample_pptx: Path) -> None:
    res = parse(sample_pptx, out_dir=tmp_path, ocr=False, with_images=False)
    md = res.markdown_path.read_text(encoding="utf-8")
    assert "![Image](" not in md
    # Speaker notes should still be merged.
    assert "**Speaker notes:**" in md


def test_pptx_ocr_inlines_text_no_images(
    tmp_path: Path, sample_pptx: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With OCR on, each image is replaced by recognized text — no image files."""
    import document_parser.ocr as ocr_mod

    monkeypatch.setattr(ocr_mod, "ocr_image", lambda img, lang="eng", **kw: "SENTINEL_OCR_TEXT")

    res = parse(sample_pptx, out_dir=tmp_path, ocr=True)
    md = res.markdown_path.read_text(encoding="utf-8")

    # OCR text inlined where the image was.
    assert "SENTINEL_OCR_TEXT" in md
    # No image links, no leftover placeholder comment, no PNG assets written.
    assert "![Image](" not in md
    assert "<!-- image -->" not in md
    assert not list(res.assets_dir.glob("*.png"))
    # Frontmatter records the OCR settings.
    assert "ocr_enabled: true" in md
    # Native slide text and notes are untouched.
    assert "Q1 Roadmap" in md
    assert "**Speaker notes:**" in md


def test_pptx_ocr_drops_image_when_no_text(
    tmp_path: Path, sample_pptx: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An image whose OCR yields no text leaves no residue in the Markdown."""
    import document_parser.ocr as ocr_mod

    monkeypatch.setattr(ocr_mod, "ocr_image", lambda img, lang="eng", **kw: "")

    res = parse(sample_pptx, out_dir=tmp_path, ocr=True)
    md = res.markdown_path.read_text(encoding="utf-8")

    assert "![Image](" not in md
    assert "<!-- image -->" not in md
    assert not list(res.assets_dir.glob("*.png"))


@tesseract_available
def test_pptx_real_ocr_reads_embedded_image(tmp_path: Path, sample_pptx: Path) -> None:
    """End-to-end: Tesseract recognizes the text baked into the slide image."""
    res = parse(sample_pptx, out_dir=tmp_path, ocr=True)
    md = res.markdown_path.read_text(encoding="utf-8")

    # The fixture image contains the text "OCR ME PLEASE".
    assert "OCR" in md.upper()
    assert "![Image](" not in md
    assert not list(res.assets_dir.glob("*.png"))


def test_pptx_ocr_with_images_override(
    tmp_path: Path, sample_pptx: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--ocr --images keeps both the inlined text and the embedded image."""
    import document_parser.ocr as ocr_mod

    monkeypatch.setattr(ocr_mod, "ocr_image", lambda img, lang="eng", **kw: "SENTINEL_OCR_TEXT")

    res = parse(sample_pptx, out_dir=tmp_path, ocr=True, with_images=True)
    md = res.markdown_path.read_text(encoding="utf-8")

    assert "SENTINEL_OCR_TEXT" in md
    assert "![Image](sample/assets/" in md
    assert list(res.assets_dir.glob("*.png"))
