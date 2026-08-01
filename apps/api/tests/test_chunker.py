"""Chunker unit tests."""

from __future__ import annotations

from app.services.chunker import chunk_text


def test_single_short_paragraph_single_chunk() -> None:
    text = "仁愛堂社會服務部提供專業服務。"
    chunks = chunk_text(text)
    assert chunks == ["仁愛堂社會服務部提供專業服務。"]


def test_paragraphs_preserved_and_joined() -> None:
    text = "第一段內容。\n\n第二段內容。"
    chunks = chunk_text(text, chunk_size=1000)
    assert len(chunks) == 1
    assert "第一段內容。" in chunks[0]
    assert "第二段內容。" in chunks[0]


def test_long_text_splits_into_multiple_chunks() -> None:
    paragraph = "。".join(f"第{i}項服務內容說明文字" for i in range(200))
    chunks = chunk_text(paragraph, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)


def test_overlap_creates_shared_context() -> None:
    paragraph = "，".join(f"詞語{i}" for i in range(500))
    chunks = chunk_text(paragraph, chunk_size=60, overlap=20)
    assert len(chunks) > 2
    # Adjacent chunks share trailing/trailing content due to overlap.
    overlap_words = set(chunks[0].split("，")[-3:]) & set(chunks[1].split("，")[:3])
    assert overlap_words, "expected adjacent chunks to overlap"


def test_cjk_characters_not_split() -> None:
    text = "仁愛堂" * 500  # 1500 CJK code points, no boundaries
    chunks = chunk_text(text, chunk_size=100, overlap=10)
    for chunk in chunks:
        assert set(chunk) == {"仁", "愛", "堂"}


def test_empty_and_whitespace_input() -> None:
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []
    assert chunk_text("\n\n\n") == []


def test_invalid_chunk_size_raises() -> None:
    try:
        chunk_text("abc", chunk_size=0)
    except ValueError:
        return
    raise AssertionError("expected ValueError for chunk_size=0")
