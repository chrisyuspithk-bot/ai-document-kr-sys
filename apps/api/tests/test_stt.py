"""Speech-to-text provider tests (factory + OpenRouter request/response)."""

from __future__ import annotations

import httpx
import pytest

from app.core.config import Settings
from app.services.stt import (
    STTError,
    UnsupportedAudioFormatError,
    get_stt_provider,
)
from app.services.stt.openrouter import OpenRouterSTTProvider


def _settings(**overrides) -> Settings:
    defaults = {
        "stt_provider": "openrouter",
        "openrouter_api_key": "sk-or-test-key",
        "openrouter_base_url": "https://openrouter.ai/api/v1",
        "openrouter_asr_model": "mistralai/voxtral-small-24b-2507",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def test_factory_returns_mock() -> None:
    provider = get_stt_provider(_settings(stt_provider="mock"))
    assert provider.name == "mock"


def test_factory_openrouter_missing_key_raises() -> None:
    with pytest.raises(STTError, match="OPENROUTER_API_KEY"):
        get_stt_provider(_settings(openrouter_api_key=None))


def test_factory_unknown_provider_raises() -> None:
    with pytest.raises(STTError, match="Unknown STT provider"):
        get_stt_provider(_settings(stt_provider="nope"))


def test_factory_qwen_asr_pending_raises() -> None:
    with pytest.raises(STTError, match="Qwen ASR"):
        get_stt_provider(_settings(stt_provider="qwen_asr"))


def test_openrouter_provider_is_returned() -> None:
    provider = get_stt_provider(_settings())
    assert isinstance(provider, OpenRouterSTTProvider)
    assert provider._model == "mistralai/voxtral-small-24b-2507"


async def test_openrouter_transcribe_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/chat/completions"
        body = request.read()
        assert b"input_audio" in body
        assert b'"format":"wav"' in body
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "今日會議討論咗服務計劃嘅進度。"
                        }
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            },
        )

    transport = httpx.MockTransport(handler)
    provider = OpenRouterSTTProvider(
        api_key="sk-test",
        base_url="https://openrouter.ai/api/v1",
    )
    provider._client = httpx.AsyncClient(
        base_url="https://openrouter.ai/api/v1", transport=transport
    )

    result = await provider.transcribe(
        b"fake-audio-bytes", "audio/wav", language_hint="zh-yue"
    )
    assert result.text == "今日會議討論咗服務計劃嘅進度。"
    assert result.provider == "openrouter"
    assert result.model == "mistralai/voxtral-small-24b-2507"
    assert result.language == "zh-yue"
    await provider.aclose()


async def test_openrouter_unsupported_format() -> None:
    provider = OpenRouterSTTProvider(api_key="sk-test")
    with pytest.raises(UnsupportedAudioFormatError, match="Unsupported audio"):
        await provider.transcribe(b"data", "application/octet-stream")


async def test_openrouter_http_error_raises_stt_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"error": {"message": "No endpoints found that support input audio"}},
        )

    transport = httpx.MockTransport(handler)
    provider = OpenRouterSTTProvider(
        api_key="sk-test", base_url="https://openrouter.ai/api/v1"
    )
    provider._client = httpx.AsyncClient(
        base_url="https://openrouter.ai/api/v1", transport=transport
    )

    with pytest.raises(STTError, match="HTTP 404"):
        await provider.transcribe(b"audio", "audio/mpeg")
    await provider.aclose()


async def test_mock_provider_transcribes() -> None:
    provider = get_stt_provider(_settings(stt_provider="mock"))
    result = await provider.transcribe(b"", "audio/wav", language_hint="zh-Hant")
    assert result.text
    assert result.provider == "mock"
