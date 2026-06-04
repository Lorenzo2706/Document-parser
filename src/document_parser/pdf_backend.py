"""PDF → DoclingDocument via Docling's PDF pipeline."""

from __future__ import annotations

from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import DoclingDocument

from document_parser.ocr import build_ocr_options


def build_pdf_converter(*, ocr: bool, lang: str, with_images: bool) -> DocumentConverter:
    pipe = PdfPipelineOptions()
    pipe.do_ocr = ocr
    if ocr:
        pipe.ocr_options = build_ocr_options(lang)
    pipe.do_table_structure = True
    pipe.generate_picture_images = with_images
    pipe.images_scale = 2.0
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipe)}
    )


def convert_pdf(
    path: Path,
    *,
    ocr: bool = True,
    lang: str = "eng",
    with_images: bool = True,
) -> DoclingDocument:
    converter = build_pdf_converter(ocr=ocr, lang=lang, with_images=with_images)
    result = converter.convert(str(path))
    return result.document
