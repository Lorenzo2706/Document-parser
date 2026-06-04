"""Document-parser: PDF/PPTX → Markdown for LLM ingestion with zero data loss."""

from document_parser.core import ParseResult, parse, parse_pdf, parse_pptx
from document_parser.excel_backend import ExcelResult, convert_excel

__all__ = ["parse", "parse_pdf", "parse_pptx", "ParseResult", "convert_excel", "ExcelResult"]
__version__ = "0.1.0"
