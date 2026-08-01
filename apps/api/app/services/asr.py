"""Speech-to-text provider abstraction — Qwen-Audio primary, Whisper fallback."""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)

SUPPORTED_AUDIO_FORMATS = {
    ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".webm",
    ".mp4", ".aac", ".wma", ".opus", ".amr",
}
MAX_FILE_SIZE_MB = 500  # per file
AUDIO_UPLOAD_DIR = Path(os.getenv("AUDIO_UPLOAD_DIR", "/tmp/aidg-meetings"))


class AsrResult:
    """Normalised ASR result across providers."""

    def __init__(
        self,
        full_text: str,
        segments: list[dict] | None = None,
        language: str | None = None,
        confidence: float | None = None,
        duration_seconds: float | None = None,
        provider: str = "unknown",
    ):
        self.full_text = full_text
        self.segments = segments or []
        self.language = language
        self.confidence = confidence
        self.duration_seconds = duration_seconds
        self.provider = provider


class AsrProvider(Protocol):
    """Protocol for ASR providers."""

    async def transcribe(self, audio_path: str, language: str | None = None) -> AsrResult:
        ...

    @property
    def provider_name(self) -> str:
        ...


class WhisperAsrProvider:
    """OpenAI Whisper API provider (large-v3)."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.getenv("WHISPER_API_KEY", os.getenv("OPENAI_API_KEY", ""))
        self.base_url = (base_url or os.getenv("WHISPER_BASE_URL", "https://api.openai.com")).rstrip("/")

    @property
    def provider_name(self) -> str:
        return "whisper-large-v3"

    async def transcribe(self, audio_path: str, language: str | None = None) -> AsrResult:
        url = f"{self.base_url}/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data: dict = {"model": "whisper-1", "response_format": "verbose_json"}
        if language:
            data["language"] = language

        async with httpx.AsyncClient(timeout=300) as client:
            with open(audio_path, "rb") as f:
                files = {"file": (os.path.basename(audio_path), f)}
                resp = await client.post(url, headers=headers, data=data, files=files)
                resp.raise_for_status()
                result = resp.json()

        segments = [
            {"start": s["start"], "end": s["end"], "text": s["text"].strip()}
            for s in result.get("segments", [])
        ]
        return AsrResult(
            full_text=result["text"],
            segments=segments,
            language=result.get("language", language),
            confidence=result.get("confidence"),
            duration_seconds=result.get("duration"),
            provider=self.provider_name,
        )


class QwenAsrProvider:
    """Qwen-Audio provider — uses Qwen2-Audio / Qwen3-Audio via API.

    Environment variables:
        QWEN_ASR_API_KEY  – API key
        QWEN_ASR_BASE_URL – API endpoint base
        QWEN_ASR_MODEL    – model name (default: qwen2-audio)
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.getenv("QWEN_ASR_API_KEY", "")
        self.base_url = (base_url or os.getenv(
            "QWEN_ASR_BASE_URL", "https://dashscope-intl.aliyuncs.com"
        )).rstrip("/")
        self.model = os.getenv("QWEN_ASR_MODEL", "qwen2-audio-instruct")

    @property
    def provider_name(self) -> str:
        return f"qwen-audio({self.model})"

    async def transcribe(self, audio_path: str, language: str | None = None) -> AsrResult:
        """Call Qwen-Audio for transcription via OpenAI-compatible chat API.

        Sends the audio as a base64 data URI in the message content.
        """
        mime = _audio_mime(audio_path)
        data_uri = _file_to_data_uri(audio_path, mime)

        lang_instruction = ""
        if language in ("yue", "zh-yue"):
            lang_instruction = (
                "請將音頻轉寫為繁體中文。"
                "如果音頻中包含廣東話，請用口語化粵語文字轉寫。"
                "如果包含英文，保留英文原文。"
            )
        elif language in ("zh", "zh-tw", "zh-hant"):
            lang_instruction = "請將音頻轉寫為繁體中文。"
        elif language == "en":
            lang_instruction = "Transcribe the audio in English."

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"{lang_instruction}\n"
                            "請提供完整的逐字稿，分段標記時間。"
                        ),
                    },
                    {"type": "audio_url", "audio_url": {"url": data_uri}},
                ],
            }
        ]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 8000,
            "temperature": 0,
        }

        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            result = resp.json()

        full_text = result["choices"][0]["message"]["content"]
        return AsrResult(
            full_text=full_text,
            segments=_parse_segments_from_text(full_text),
            language=language,
            confidence=None,
            provider=self.provider_name,
        )


class MockAsrProvider:
    """Mock provider for testing — returns a fixed transcript."""

    @property
    def provider_name(self) -> str:
        return "mock"

    async def transcribe(self, audio_path: str, language: str | None = None) -> AsrResult:
        return AsrResult(
            full_text=(
                "[00:00] 大家好，歡迎參加今日會議。\n"
                "[01:30] 今日主要討論仁愛堂新年度服務計劃。\n"
                "[05:00] 決定增加長者社區支援服務的資源分配。"
            ),
            segments=[
                {"start": 0, "end": 90, "text": "大家好，歡迎參加今日會議。"},
                {"start": 90, "end": 300, "text": "今日主要討論仁愛堂新年度服務計劃。"},
                {"start": 300, "end": 400, "text": "決定增加長者社區支援服務的資源分配。"},
            ],
            language=language or "yue",
            confidence=0.95,
            duration_seconds=400,
            provider="mock",
        )


def get_asr_provider() -> AsrProvider:
    """Factory: returns the configured ASR provider.

    Priority: QWEN_ASR_API_KEY → WHISPER_API_KEY → OPENAI_API_KEY → mock (dev).
    """
    if os.getenv("QWEN_ASR_API_KEY"):
        logger.info("Using Qwen ASR provider")
        return QwenAsrProvider()
    if os.getenv("WHISPER_API_KEY") or os.getenv("OPENAI_API_KEY"):
        logger.info("Using Whisper ASR provider")
        return WhisperAsrProvider()
    logger.warning("No ASR credentials set — using mock provider")
    return MockAsrProvider()


# ── helpers ───────────────────────────────────────────────────────────

def _audio_mime(audio_path: str) -> str:
    ext = Path(audio_path).suffix.lower()
    return {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".webm": "audio/webm",
        ".mp4": "video/mp4",
        ".aac": "audio/aac",
    }.get(ext, "audio/mpeg")


def _file_to_data_uri(audio_path: str, mime: str) -> str:
    with open(audio_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _parse_segments_from_text(text: str) -> list[dict]:
    """Naive segment parser from timestamp-prefixed text like [MM:SS] text."""
    import re

    segments = []
    pattern = re.compile(r"\[(\d{1,3}):(\d{2})(?:[:.](\d{2}))?\]\s*(.*?)(?=\[\d|$)", re.DOTALL)
    for m in pattern.finditer(text):
        minutes = int(m.group(1))
        seconds = int(m.group(2))
        ms = int(m.group(3)) if m.group(3) else 0
        start = minutes * 60 + seconds + ms / 100
        content = m.group(4).strip()
        segments.append({"start": start, "end": start + len(content) / 15, "text": content})
    return segments


def validate_audio_file(filepath: str) -> None:
    """Validate audio file format and size."""
    ext = Path(filepath).suffix.lower()
    if ext not in SUPPORTED_AUDIO_FORMATS:
        raise ValueError(
            f"Unsupported audio format: {ext}. "
            f"Supported: {', '.join(sorted(SUPPORTED_AUDIO_FORMATS))}"
        )
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(
            f"File too large: {size_mb:.1f} MB. Maximum: {MAX_FILE_SIZE_MB} MB"
        )
