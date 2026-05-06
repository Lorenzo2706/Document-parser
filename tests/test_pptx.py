from __future__ import annotations

from pathlib import Path

from slide_parser import parse


def test_pptx_end_to_end(tmp_path: Path, sample_pptx: Path) -> None:
    res = parse(sample_pptx, out_dir=tmp_path, ocr=False)
    md = res.markdown_path.read_text(encoding="utf-8")

    assert res.n_slides == 2
    assert res.has_notes is True
    assert res.markdown_path.exists()

    # Front-matter present and well-formed.
    assert md.startswith("---\n")
    assert "generator: slide-parser" in md
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
