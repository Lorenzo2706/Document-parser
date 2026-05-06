"""OCR configuration helpers (Tesseract backend)."""

from __future__ import annotations

from collections.abc import Iterable

from docling.datamodel.pipeline_options import TesseractOcrOptions


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


def build_ocr_options(lang: str | Iterable[str] = "eng") -> TesseractOcrOptions:
    """Build a TesseractOcrOptions object from a language spec."""
    return TesseractOcrOptions(lang=parse_lang_spec(lang))
