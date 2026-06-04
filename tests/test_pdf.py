from __future__ import annotations

from pathlib import Path

from conftest import pdf_pipeline_available  # noqa: E402  (added by pytest's rootdir)

from document_parser import parse


@pdf_pipeline_available
def test_pdf_end_to_end(tmp_path: Path, sample_pdf: Path) -> None:
    res = parse(sample_pdf, out_dir=tmp_path, ocr=False)
    md = res.markdown_path.read_text(encoding="utf-8")

    assert res.n_slides == 2
    assert res.has_notes is False

    # Slide headings match the page count.
    assert md.count("## Slide ") == 2
    assert "## Slide 1" in md
    assert "## Slide 2" in md

    # Front-matter sanity.
    assert md.startswith("---\n")
    assert "n_slides: 2" in md

    # Document content was preserved.
    for token in ("Q1 Roadmap", "Ship parser MVP", "Metrics", "12,400"):
        assert token in md, f"missing token: {token!r}"

    # No speaker notes block for PDF input.
    assert "**Speaker notes:**" not in md
