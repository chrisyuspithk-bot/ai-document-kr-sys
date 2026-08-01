"""LLM provider abstraction with DeepSeek as primary, OpenRouter fallback.

Supports streaming (SSE) and non-streaming completions.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum

import httpx

logger = logging.getLogger(__name__)

DEEPSEEK_BASE = "https://api.deepseek.com/v1"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

#  ---------------------------------------------------------------------------
#  Public types
#  ---------------------------------------------------------------------------


class LlmRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class LlmMessage:
    role: LlmRole
    content: str


@dataclass
class LlmUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class LlmResponse:
    content: str
    usage: LlmUsage = field(default_factory=LlmUsage)
    model: str = ""


@dataclass
class LlmStreamChunk:
    """A single token / fragment from a streaming completion."""

    delta: str
    finish_reason: str | None = None


#  ---------------------------------------------------------------------------
#  Provider (ABC)
#  ---------------------------------------------------------------------------


class LlmProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[LlmMessage],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs,
    ) -> LlmResponse: ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[LlmMessage],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[LlmStreamChunk]: ...


#  ---------------------------------------------------------------------------
#  DeepSeek provider
#  ---------------------------------------------------------------------------


class DeepSeekProvider(LlmProvider):
    """Calls DeepSeek's OpenAI-compatible API.

    Requires DEEPSEEK_API_KEY in the environment.
    """

    def __init__(self, base_url: str | None = None) -> None:
        self._base = (base_url or DEEPSEEK_BASE).rstrip("/")
        self._key = os.getenv("DEEPSEEK_API_KEY", "")

    async def chat(self, messages, *, model, temperature=0.3, max_tokens=4096, **kwargs):
        payload = _build_payload(messages, model, temperature, max_tokens, stream=False, **kwargs)
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self._base}/chat/completions",
                headers=_ds_headers(self._key),
                json=payload,
            )
        _raise_on_error(resp, "DeepSeek")
        body = resp.json()
        choice = body["choices"][0]
        usage = body.get("usage", {})
        return LlmResponse(
            content=choice["message"]["content"],
            usage=LlmUsage(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            ),
            model=body.get("model", model),
        )

    async def chat_stream(self, messages, *, model, temperature=0.3, max_tokens=4096, **kwargs):
        payload = _build_payload(messages, model, temperature, max_tokens, stream=True, **kwargs)
        async with (
            httpx.AsyncClient(timeout=120) as client,
            client.stream(
                "POST",
                f"{self._base}/chat/completions",
                headers=_ds_headers(self._key),
                json=payload,
            ) as resp,
        ):
            _raise_on_error(resp, "DeepSeek")
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                choice = data["choices"][0]
                yield LlmStreamChunk(
                    delta=choice.get("delta", {}).get("content", ""),
                    finish_reason=choice.get("finish_reason"),
                )


#  ---------------------------------------------------------------------------
#  OpenRouter provider (fallback / multi-model)
#  ---------------------------------------------------------------------------


class OpenRouterProvider(LlmProvider):
    """OpenRouter API — gives access to Qwen, Nemotron, etc."""

    def __init__(self, base_url: str | None = None) -> None:
        self._base = (base_url or OPENROUTER_BASE).rstrip("/")
        self._key = os.getenv("OPENROUTER_API_KEY", "")

    async def chat(self, messages, *, model, temperature=0.3, max_tokens=4096, **kwargs):
        payload = _build_payload(messages, model, temperature, max_tokens, stream=False, **kwargs)
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self._base}/chat/completions",
                headers=_or_headers(self._key),
                json=payload,
            )
        _raise_on_error(resp, "OpenRouter")
        body = resp.json()
        choice = body["choices"][0]
        usage = body.get("usage", {})
        return LlmResponse(
            content=choice["message"]["content"],
            usage=LlmUsage(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            ),
            model=body.get("model", model),
        )

    async def chat_stream(self, messages, *, model, temperature=0.3, max_tokens=4096, **kwargs):
        payload = _build_payload(messages, model, temperature, max_tokens, stream=True, **kwargs)
        async with (
            httpx.AsyncClient(timeout=120) as client,
            client.stream(
                "POST",
                f"{self._base}/chat/completions",
                headers=_or_headers(self._key),
                json=payload,
            ) as resp,
        ):
            _raise_on_error(resp, "OpenRouter")
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                choice = data["choices"][0]
                yield LlmStreamChunk(
                    delta=choice.get("delta", {}).get("content", ""),
                    finish_reason=choice.get("finish_reason"),
                )


#  ---------------------------------------------------------------------------
#  Model registry
#  ---------------------------------------------------------------------------


@dataclass
class ModelInfo:
    id: str
    provider: str  # "deepseek" | "openrouter"
    max_tokens: int
    description: str


MODELS: dict[str, ModelInfo] = {
    "deepseek-v4-flash": ModelInfo(
        id="deepseek-chat",
        provider="deepseek",
        max_tokens=8192,
        description="DeepSeek-V4-Flash: fast, cheap, high-volume Chinese QA",
    ),
    "deepseek-v4-pro": ModelInfo(
        id="deepseek-reasoner",
        provider="deepseek",
        max_tokens=8192,
        description="DeepSeek-V4-Pro: higher-quality reasoning & drafting",
    ),
    "qwen3.7-max": ModelInfo(
        id="qwen/qwen-max",
        provider="openrouter",
        max_tokens=32768,
        description="Qwen3.7 Max: best Traditional Chinese, 1M context",
    ),
    "nemotron-3-ultra": ModelInfo(
        id="nvidia/nemotron-3-ultra",
        provider="openrouter",
        max_tokens=8192,
        description="Nemotron 3 Ultra: agentic, complex multi-step drafting",
    ),
}


def get_provider_for(model_name: str) -> tuple[LlmProvider, ModelInfo]:
    info = MODELS.get(model_name)
    if not info:
        raise ValueError(f"Unknown model: {model_name}")

    if info.provider == "deepseek":
        return DeepSeekProvider(), info
    return OpenRouterProvider(), info


#  ---------------------------------------------------------------------------
#  Helpers
#  ---------------------------------------------------------------------------


def _build_payload(
    messages: list[LlmMessage],
    model: str,
    temperature: float,
    max_tokens: int,
    *,
    stream: bool,
    **kwargs,
) -> dict:
    payload: dict = {
        "model": model,
        "messages": [{"role": m.role.value, "content": m.content} for m in messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    payload.update(kwargs)
    return payload


def _ds_headers(key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _or_headers(key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://yot.aidg.internal",
        "X-Title": "YOT AIDG-KR",
    }


def _raise_on_error(resp: httpx.Response | httpx.AsyncResponse, provider: str) -> None:
    if resp.status_code < 400:
        return
    try:
        body = resp.json()
        msg = body.get("error", {}).get("message", resp.text)
    except Exception:
        msg = resp.text
    logger.error("%s API error %d: %s", provider, resp.status_code, msg)
    raise RuntimeError(f"{provider} API error {resp.status_code}: {msg}")
