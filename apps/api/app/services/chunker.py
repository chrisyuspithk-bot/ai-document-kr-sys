"""CJK-aware recursive text chunking with configurable size and overlap.

Splits on paragraph boundaries first, then on sentence/line breaks for long
segments. Operates on Python ``str`` (code points) so Chinese characters and
surrogate pairs are never split mid-character.
"""

from __future__ import annotations

import re

DEFAULT_CHUNK_SIZE = 800
DEFAULT_OVERLAP = 100

_SENTENCE_BOUNDARIES = ("\n", "。", "！", "？", "；", ".", "!", "?", ";", " ")
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[str]:
    """Split ``text`` into overlapping chunks, preserving paragraph flow."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    overlap = max(0, min(overlap, chunk_size // 2))

    paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT.split(text) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        if current:
            joined = "\n".join(current).strip()
            if joined:
                chunks.append(joined)
            current = []

    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            flush()
            chunks.extend(_split_long(paragraph, chunk_size, overlap))
            continue
        if sum(len(p) + 1 for p in current) + len(paragraph) > chunk_size:
            flush()
        current.append(paragraph)

    flush()
    return chunks


def _split_long(text: str, chunk_size: int, overlap: int) -> list[str]:
    out: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            for boundary in _SENTENCE_BOUNDARIES:
                index = text.rfind(boundary, max(start + chunk_size // 2, start + 1), end)
                if index != -1:
                    end = index + 1
                    break
        piece = text[start:end].strip()
        if piece:
            out.append(piece)
        if end >= length:
            break
        start = max(end - overlap, start + 1)
    return out
