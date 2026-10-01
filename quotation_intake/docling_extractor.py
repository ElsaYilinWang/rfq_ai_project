# quotation_intake/docling_extractor.py

"""
Wraps Docling's conversion step. Deterministic, no LLM involved --
turns a supplier document (PDF, DOCX, etc.) into raw markdown text.

Verified against a real exported PDF: field values (price, part
number, lead time) came through clean, but soft line breaks within a
paragraph collapse onto one line (e.g. "From: X Date: Y Re: Z" all
run together) -- confirmed real Docling/Markdown conversion behavior,
not a bug. This is exactly why the next step (analysis_core.py) uses
an LLM rather than line-based parsing: regex assuming "one field per
line" would silently break on this, and a real supplier document's
formatting will vary in ways no fixed regex could anticipate.
"""

from docling.document_converter import DocumentConverter

_converter = None  # lazy singleton, same pattern as
# retrieval/semantic_search.py's embedding model -- avoids paying any
# setup cost for anything that merely imports this module without
# actually calling extract_raw_text().


def _get_converter() -> DocumentConverter:
    global _converter
    if _converter is None:
        _converter = DocumentConverter()
    return _converter


def extract_raw_text(file_path: str) -> str:
    """
    Converts a supplier document at file_path into markdown text.
    Raises whatever Docling itself raises on a genuinely unreadable
    file -- the caller (the API route, once built) is responsible for
    turning that into a clean HTTP error, same pattern as every other
    extraction step in this project.
    """
    converter = _get_converter()
    result = converter.convert(file_path)
    return result.document.export_to_markdown()
