"""Mock STT provider for development and tests (no network)."""

from __future__ import annotations

from app.services.stt.base import (
    STTProvider,
    TranscriptionResult,
    TranscriptionSegment,
)

MOCK_TRANSCRIPT = "這是會議錄音的模擬轉錄文字。請提供實際的語音轉錄服務設定。"


class MockSTTProvider(STTProvider):
    name = "mock"

    async def transcribe(
        self,
        audio: bytes,
        mime_type: str,
        language_hint: str | None = None,
    ) -> TranscriptionResult:
        return TranscriptionResult(
            text=MOCK_TRANSCRIPT,
            provider=self.name,
            model="mock",
            language=language_hint or "zh-Hant",
            segments=[TranscriptionSegment(start=0.0, end=2.0, text=MOCK_TRANSCRIPT)],
        )
