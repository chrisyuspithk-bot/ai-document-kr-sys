"""OpenRouter-backed speech-to-text via audio-capable chat models.

Uses the OpenAI-compatible chat completions API with an ``input_audio``
content part. Only models that advertise audio input work (e.g.
``mistralai/voxtral-small-24b-2507``, ``xiaomi/mimo-v2.5``). Pure-text Qwen
models (e.g. ``qwen/qwen3.7-flash``) reject audio with HTTP 404.
"""

from __future__ import annotations

import base64
import logging

import httpx

from app.services.stt.base import (
    SUPPORTED_AUDIO_FORMATS,
    STTError,
    STTProvider,
    TranscriptionResult,
    UnsupportedAudioFormatError,
)

logger = logging.getLogger(__name__)

ASR_SYSTEM_PROMPT = (
    "You are a professional transcription engine. Transcribe the spoken audio "
    "verbatim. Preserve the original language; transcribe Cantonese and "
    "Mandarin using Traditional Chinese characters. Never summarize, translate, "
    "or add content that was not spoken. If there is no audible speech, reply "
    "with an empty string. Output only the transcript text."
)

DEFAULT_TIMEOUT = httpx.Timeout(connect=15.0, read=300.0, write=60.0, pool=15.0)


class OpenRouterSTTProvider(STTProvider):
    name = "openrouter"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        model: str = "mistralai/voxtral-small-24b-2507",
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    ) -> None:
        self._model = model
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def transcribe(
        self,
        audio: bytes,
        mime_type: str,
        language_hint: str | None = None,
    ) -> TranscriptionResult:
        audio_format = SUPPORTED_AUDIO_FORMATS.get(mime_type)
        if audio_format is None:
            raise UnsupportedAudioFormatError(
                f"Unsupported audio format: {mime_type}. "
                f"Supported: {', '.join(sorted(SUPPORTED_AUDIO_FORMATS))}"
            )

        prompt = ASR_SYSTEM_PROMPT
        if language_hint:
            prompt = f"{prompt}\nExpected spoken language: {language_hint}."

        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": base64.b64encode(audio).decode("ascii"),
                                "format": audio_format,
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 4096,
        }

        try:
            response = await self._client.post("/chat/completions", json=payload)
        except httpx.HTTPError as exc:
            logger.warning("OpenRouter STT request failed: %s", exc)
            raise STTError(f"OpenRouter STT request failed: {exc}") from exc

        if response.status_code != 200:
            body = response.text[:500]
            logger.warning(
                "OpenRouter STT returned %s: %s", response.status_code, body
            )
            raise STTError(
                f"OpenRouter STT failed with HTTP {response.status_code}: {body}"
            )

        try:
            data = response.json()
            text = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning("Malformed OpenRouter STT response: %s", exc)
            raise STTError("Malformed OpenRouter STT response") from exc

        return TranscriptionResult(
            text=text,
            provider=self.name,
            model=self._model,
            language=language_hint,
        )
