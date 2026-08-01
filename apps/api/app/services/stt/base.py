"""Speech-to-text provider interface and shared types."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field


class STTError(Exception):
    """Raised when transcription fails."""


class UnsupportedAudioFormatError(STTError):
    """Raised when the audio MIME type cannot be transcribed."""


# Formats accepted by the OpenRouter input_audio content part.
SUPPORTED_AUDIO_FORMATS: dict[str, str] = {
    "audio/wav": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "mp4",
    "audio/x-m4a": "m4a",
    "audio/m4a": "m4a",
    "audio/aac": "aac",
    "audio/ogg": "ogg",
    "audio/webm": "webm",
    "audio/flac": "flac",
    "audio/x-wav": "wav",
}

SUPPORTED_MIME_TYPES = frozenset(SUPPORTED_AUDIO_FORMATS)


@dataclass
class TranscriptionSegment:
    start: float
    end: float
    text: str
    speaker: str | None = None


@dataclass
class TranscriptionResult:
    text: str
    provider: str
    model: str | None = None
    language: str | None = None
    segments: list[TranscriptionSegment] = field(default_factory=list)
    duration_ms: int | None = None


class STTProvider(abc.ABC):
    """Base class for speech-to-text providers."""

    name: str = "abstract"

    @abc.abstractmethod
    async def transcribe(
        self,
        audio: bytes,
        mime_type: str,
        language_hint: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe audio bytes into text."""
        raise NotImplementedError
