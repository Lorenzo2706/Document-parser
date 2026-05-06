"""Slide-parser: PDF/PPTX → Markdown for LLM ingestion with zero data loss."""

from slide_parser.core import ParseResult, parse, parse_pdf, parse_pptx

__all__ = ["parse", "parse_pdf", "parse_pptx", "ParseResult"]
__version__ = "0.1.0"
