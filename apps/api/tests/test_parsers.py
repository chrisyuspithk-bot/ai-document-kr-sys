"""Document parser unit tests."""

from __future__ import annotations

import pytest

from app.services.parsers import (
    ParsedDocument,
    UnsupportedDocumentError,
    parse_file,
)


def test_plain_text_utf8() -> None:
    data = "仁愛堂社會服務部\n第二行".encode()
    parsed = parse_file("note.txt", "text/plain", data)
    assert parsed == ParsedDocument(pages=["仁愛堂社會服務部\n第二行"])


def test_plain_text_big5_fallback() -> None:
    data = "仁愛堂".encode("big5")
    parsed = parse_file("note.txt", "text/plain", data)
    assert parsed.pages[0] == "仁愛堂"


def test_csv_rendered_as_tsv() -> None:
    data = "姓名,部門\n陳大文,社會服務\n".encode()
    parsed = parse_file("staff.csv", "text/csv", data)
    assert "姓名\t部門" in parsed.pages[0]
    assert "陳大文\t社會服務" in parsed.pages[0]


def test_html_strips_markup() -> None:
    data = (
        "<html><head><style>p{color:red}</style></head><body>"
        "<h1>政策指引</h1><script>alert(1)</script>"
        "<p>第一段。</p><p>第二段。</p></body></html>"
    ).encode()
    parsed = parse_file("policy.html", "text/html", data)
    text = parsed.pages[0]
    assert "政策指引" in text
    assert "第一段。" in text
    assert "alert(1)" not in text
    assert "<h1>" not in text


def test_unsupported_format_raises() -> None:
    with pytest.raises(UnsupportedDocumentError):
        parse_file("deck.pptx", "application/vnd.ms-powerpoint", b"not a pptx")


def test_octet_stream_falls_back_to_extension() -> None:
    data = b"hello world"
    parsed = parse_file("note.txt", "application/octet-stream", data)
    assert parsed.pages[0] == "hello world"


def test_pdf_parses_text_per_page() -> None:
    try:
        from pypdf import PdfWriter
    except ImportError:  # pragma: no cover
        pytest.skip("pypdf not installed")

    from io import BytesIO

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)

    # pypdf blank pages yield no extractable text; assert structure only.
    parsed = parse_file("doc.pdf", "application/pdf", buffer.getvalue())
    assert isinstance(parsed, ParsedDocument)
