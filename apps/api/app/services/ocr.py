"""OCR service: Traditional Chinese + English using EasyOCR.

Lazy-loads the reader so imports stay cheap when OCR is not needed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)

_READER: EasyOcrProvider | None = None


def _import_easyocr():
    import easyocr

    return easyocr


class EasyOcrProvider:
    """Thin wrapper around EasyOCR with zh-Hant + English support."""

    def __init__(self, gpu: bool = False) -> None:
        easyocr = _import_easyocr()
        self._reader = easyocr.Reader(["ch_tra", "en"], gpu=gpu)

    def readtext(self, image: bytes | np.ndarray) -> str:
        """OCR a single image and return concatenated text."""
        results = self._reader.readtext(image)
        if not results:
            return ""
        lines: list[str] = []
        for _bbox, text, _conf in results:
            stripped = text.strip()
            if stripped:
                lines.append(stripped)
        return "\n".join(lines)


def _get_reader() -> EasyOcrProvider:
    global _READER
    if _READER is None:
        _READER = EasyOcrProvider(gpu=False)
    return _READER


def ocr_bytes(image_bytes: bytes) -> str:
    """OCR raw image bytes (PNG, JPEG, etc.) and return recognised text."""
    try:
        reader = _get_reader()
        return reader.readtext(image_bytes)
    except Exception:
        logger.exception("OCR failed on %d-byte image", len(image_bytes))
        return ""


def ocr_pages(page_images: list[bytes]) -> list[str]:
    """OCR a list of page images (one per page). Returns one string per page."""
    return [ocr_bytes(img) for img in page_images]
