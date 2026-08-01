"""Speech-to-text provider factory."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.services.stt.base import (
    STTError,
    STTProvider,
    TranscriptionResult,
    TranscriptionSegment,
    UnsupportedAudioFormatError,
)
from app.services.stt.mock import MockSTTProvider
from app.services.stt.openrouter import OpenRouterSTTProvider

__all__ = [
    "STTError",
    "STTProvider",
    "TranscriptionResult",
    "TranscriptionSegment",
    "UnsupportedAudioFormatError",
    "get_stt_provider",
]


def get_stt_provider(settings: Settings | None = None) -> STTProvider:
    """Return the configured STT provider."""
    settings = settings or get_settings()
    provider = settings.stt_provider.lower()

    if provider == "mock":
        return MockSTTProvider()

    if provider == "openrouter":
        if not settings.openrouter_api_key:
            raise STTError(
                "OpenRouter STT selected but AIDG_OPENROUTER_API_KEY is not set"
            )
        return OpenRouterSTTProvider(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            model=settings.openrouter_asr_model,
        )

    if provider == "qwen_asr":
        raise STTError(
            "Qwen ASR (DashScope) is not configured yet — "
            "set AIDG_QWEN_ASR_API_KEY or switch to AIDG_STT_PROVIDER=openrouter"
        )

    raise STTError(f"Unknown STT provider: {settings.stt_provider}")
