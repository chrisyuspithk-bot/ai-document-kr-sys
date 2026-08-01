"""Document parsers: bytes -> page-oriented plain text.

Supported formats (v1): plain text, CSV, HTML, PDF (pypdf), Word .docx.
Excel/PPT/image-OCR formats are detected but require a downstream OCR/table
worker; processing fails fast with a clear message until those are wired.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class UnsupportedDocumentError(RuntimeError):
    pass


@dataclass
class ParsedDocument:
    pages: list[str]


SUPPORTED_MIME_TYPES: dict[str, str] = {
    "text/plain": "text",
    "text/csv": "csv",
    "text/html": "html",
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "unsupported-word",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "unsupported-xlsx",
    "application/vnd.ms-excel": "unsupported-xls",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "unsupported-pptx",
    "application/vnd.ms-powerpoint": "unsupported-ppt",
    "image/png": "unsupported-image",
    "image/jpeg": "unsupported-image",
    "image/tiff": "unsupported-image",
}

# Fallbacks for mislabelled uploads (Windows often reports octet-stream).
_MIME_BY_EXTENSION: dict[str, str] = {
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".html": "text/html",
    ".htm": "text/html",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def resolve_mime_type(filename: str, declared: str) -> str:
    if declared == "application/octet-stream" or not declared:
        return _MIME_BY_EXTENSION.get(Path(filename).suffix.lower(), declared)
    return declared


def parse_file(filename: str, mime_type: str, data: bytes) -> ParsedDocument:
    mime_type = resolve_mime_type(filename, mime_type)
    kind = SUPPORTED_MIME_TYPES.get(mime_type, "unknown")
    if kind.startswith("unsupported"):
        raise UnsupportedDocumentError(
            f"Format not yet supported by the parsing pipeline: {mime_type}"
        )

    if kind == "text":
        return ParsedDocument(pages=[_decode(data)])
    if kind == "csv":
        return ParsedDocument(pages=[_parse_csv(data)])
    if kind == "html":
        return ParsedDocument(pages=[_parse_html(data)])
    if kind == "pdf":
        return ParsedDocument(pages=_parse_pdf(data))
    if kind == "docx":
        return ParsedDocument(pages=[_parse_docx(data)])
    raise UnsupportedDocumentError(f"Unsupported MIME type: {mime_type}")


def _decode(data: bytes) -> str:
    for encoding in ("utf-8", "big5", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _parse_csv(data: bytes) -> str:
    text = _decode(data)
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return ""
    # Render rows as tab-separated lines so table structure survives chunking.
    return "\n".join("\t".join(cell for cell in row) for row in rows)


def _parse_html(data: bytes) -> str:
    soup = BeautifulSoup(_decode(data), "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text("\n")
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _parse_pdf(data: bytes) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise UnsupportedDocumentError("pypdf is not installed") from exc

    reader = PdfReader(io.BytesIO(data))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text.strip())
    return pages


def _parse_docx(data: bytes) -> str:
    try:
        from docx import Document as DocxDocument
    except ImportError as exc:  # pragma: no cover
        raise UnsupportedDocumentError("python-docx is not installed") from exc

    document = DocxDocument(io.BytesIO(data))
    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            paragraphs.append("\t".join(cells))
    return "\n".join(paragraphs)
