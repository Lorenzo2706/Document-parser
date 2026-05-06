"""PPTX → DoclingDocument via Docling's default PPTX backend."""

from __future__ import annotations

from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter
from docling_core.types.doc import DoclingDocument


def build_pptx_converter() -> DocumentConverter:
    return DocumentConverter(allowed_formats=[InputFormat.PPTX])


def convert_pptx(path: Path) -> DoclingDocument:
    converter = build_pptx_converter()
    result = converter.convert(str(path))
    return result.document
