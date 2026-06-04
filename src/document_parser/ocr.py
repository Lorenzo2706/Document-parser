"""OCR configuration helpers (Tesseract backend).

Two distinct OCR paths live here:

* ``build_ocr_options`` configures Docling's *PDF* pipeline, which OCRs pages
  natively and merges the recognized text into the document body.
* ``ocr_image`` runs Tesseract directly (via ``pytesseract``) on a single PIL
  image. Docling's *PPTX* pipeline (``SimplePipeline``) does no OCR, so for
  PowerPoint we extract each embedded picture and OCR it ourselves.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from docling.datamodel.pipeline_options import TesseractCliOcrOptions as TesseractOcrOptions

if TYPE_CHECKING:
    from PIL.Image import Image


class OcrError(RuntimeError):
    """Raised when direct image OCR fails (e.g. Tesseract binary missing)."""


def parse_lang_spec(spec: str | Iterable[str]) -> list[str]:
    """Accept "eng+ita" or ["eng","ita"] → list of 3-letter codes for Tesseract."""
    if isinstance(spec, str):
        parts = [p.strip() for p in spec.replace(",", "+").split("+")]
    else:
        parts = list(spec)
    langs = [p for p in parts if p]
    if not langs:
        langs = ["eng"]
    return langs


def tesseract_lang(spec: str | Iterable[str] = "eng") -> str:
    """Normalize a language spec to the ``"ita+eng"`` string pytesseract expects."""
    return "+".join(parse_lang_spec(spec))


def build_ocr_options(lang: str | Iterable[str] = "eng") -> TesseractOcrOptions:
    """Build a TesseractOcrOptions object from a language spec."""
    return TesseractOcrOptions(lang=parse_lang_spec(lang))


def ocr_image(image: Image, lang: str | Iterable[str] = "eng", *, min_chars: int = 3) -> str:
    """Run Tesseract on a single PIL image and return the recognized text.

    Returns ``""`` when the result is shorter than ``min_chars`` (so purely
    decorative or text-free images are effectively dropped by callers). Raises
    :class:`OcrError` if Tesseract is unavailable.
    """
    import pytesseract

    try:
        text = pytesseract.image_to_string(image, lang=tesseract_lang(lang))
    except (pytesseract.TesseractError, OSError) as exc:  # binary missing / lang data missing
        raise OcrError(f"Tesseract OCR failed: {exc}") from exc
    text = text.strip()
    return text if len(text) >= min_chars else ""
