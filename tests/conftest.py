"""Pytest fixtures: regenerate sample.pptx / sample.pdf if missing."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def _ensure_fixtures() -> None:
    if (FIXTURES / "sample.pptx").exists() and (FIXTURES / "sample.pdf").exists():
        return
    sys.path.insert(0, str(FIXTURES))
    try:
        from build_fixtures import build_pdf, build_pptx  # type: ignore
    finally:
        sys.path.pop(0)
    build_pptx(FIXTURES / "sample.pptx")
    build_pdf(FIXTURES / "sample.pdf")


@pytest.fixture(scope="session", autouse=True)
def _fixtures_ready() -> None:
    _ensure_fixtures()


@pytest.fixture
def sample_pptx() -> Path:
    return FIXTURES / "sample.pptx"


@pytest.fixture
def sample_pdf() -> Path:
    return FIXTURES / "sample.pdf"


def _docling_pdf_available() -> bool:
    """True iff the Docling PDF pipeline can run end-to-end.

    The PDF pipeline downloads layout / table-structure model weights from
    Hugging Face on first use. Skip integration tests when the download
    fails (e.g. sandboxed CI without internet). We force pipeline init
    via a real ``.convert()`` call on the sample because converter
    construction is lazy.
    """
    try:
        from slide_parser.pdf_backend import build_pdf_converter

        _ensure_fixtures()
        converter = build_pdf_converter(ocr=False, lang="eng", with_images=False)
        converter.convert(str(FIXTURES / "sample.pdf"))
        return True
    except Exception:
        return False


pdf_pipeline_available = pytest.mark.skipif(
    not _docling_pdf_available(),
    reason="Docling PDF pipeline models not available (offline environment).",
)
