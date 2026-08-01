"""Tests for chat endpoints, RAG pipeline, and LLM provider."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.services.llm import LlmMessage, LlmResponse, LlmRole, LlmUsage, get_provider_for
from tests.conftest import auth_headers, login

STAFF = ("staff", "staff-password-123")
ADMIN = ("admin", "admin-password-123")


#  ---------------------------------------------------------------------------
#  LLM provider tests
#  ---------------------------------------------------------------------------
#  ---------------------------------------------------------------------------
class TestLlmProvider:
    def test_model_info_found(self):
        provider, info = get_provider_for("deepseek-v4-flash")
        assert info.id == "deepseek-chat"
        assert info.provider == "deepseek"

    def test_model_info_not_found(self):
        with pytest.raises(ValueError, match="Unknown model"):
            get_provider_for("no-such-model")

    @pytest.mark.asyncio
    async def test_mock_chat(self):
        """Verify the provider interface with a mock."""
        with patch("app.services.llm.DeepSeekProvider.chat") as mock_chat:
            mock_chat.return_value = LlmResponse(
                content="測試回應",
                usage=LlmUsage(prompt_tokens=10, completion_tokens=5),
                model="deepseek-chat",
            )
            provider, info = get_provider_for("deepseek-v4-flash")
            resp = await provider.chat(
                [LlmMessage(role=LlmRole.USER, content="你好")],
                model=info.id,
            )
            assert resp.content == "測試回應"


#  ---------------------------------------------------------------------------
#  RAG pipeline tests
#  ---------------------------------------------------------------------------
class TestRagPipeline:
    @pytest.mark.asyncio
    async def test_rag_pipeline_mocked(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])

        with patch("app.services.llm.DeepSeekProvider.chat") as mock_llm:
            mock_llm.return_value = LlmResponse(
                content="根據現有資料無法回答此問題",
                usage=LlmUsage(prompt_tokens=30, completion_tokens=10),
                model="deepseek-chat",
            )

            resp = await client.post(
                "/api/v1/chat",
                json={"query": "測試問題", "kb_ids": []},
                headers=headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "根據現有資料" in data["answer"]
            assert data["citations"] == []

    def test_format_instructions(self):
        from app.services.rag import _build_system_prompt

        prompt = _build_system_prompt("測試內容", "測試問題", "bullets")
        assert "要點" in prompt or "bullet" in prompt.lower()
        assert "測試內容" in prompt
        assert "測試問題" in prompt

        prompt_table = _build_system_prompt("內容", "問題", "table")
        assert "表格" in prompt_table


#  ---------------------------------------------------------------------------
#  Chat endpoint tests
#  ---------------------------------------------------------------------------
class TestChatEndpoints:
    @pytest.mark.asyncio
    async def test_chat_endpoint(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])

        with patch("app.services.llm.DeepSeekProvider.chat") as mock_llm:
            mock_llm.return_value = LlmResponse(
                content="這是測試的回應。",
                usage=LlmUsage(prompt_tokens=20, completion_tokens=5),
                model="deepseek-chat",
            )
            resp = await client.post(
                "/api/v1/chat",
                json={"query": "測試查詢", "kb_ids": []},
                headers=headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "answer" in data
            assert "conversation_id" in data

    @pytest.mark.asyncio
    async def test_chat_empty_query_rejected(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])

        resp = await client.post(
            "/api/v1/chat",
            json={"query": "", "kb_ids": []},
            headers=headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_stream_endpoint(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])

        with patch("app.services.llm.DeepSeekProvider.chat_stream") as mock_stream:

            async def _fake_stream(*args, **kwargs):
                from app.services.llm import LlmStreamChunk

                yield LlmStreamChunk(delta="測試")
                yield LlmStreamChunk(delta="回應")
                yield LlmStreamChunk(delta="", finish_reason="stop")

            mock_stream.side_effect = _fake_stream

            resp = await client.post(
                "/api/v1/chat/stream",
                json={"query": "測試", "kb_ids": []},
                headers=headers,
            )
            assert resp.status_code == 200
            body = resp.text
            assert "data:" in body
            assert "測試" in body
            assert "done" in body or "citations" in body

    @pytest.mark.asyncio
    async def test_list_conversations(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])

        resp = await client.get("/api/v1/conversations", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])

        fake_id = uuid.uuid4()
        resp = await client.get(f"/api/v1/conversations/{fake_id}", headers=headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_conversation(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])

        fake_id = uuid.uuid4()
        resp = await client.delete(f"/api/v1/conversations/{fake_id}", headers=headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_full_conversation_lifecycle(self, client):
        """Create → chat → retrieve → delete conversation."""
        headers = auth_headers((await login(client, *STAFF))["access_token"])

        with patch("app.services.llm.DeepSeekProvider.chat") as mock_llm:
            mock_llm.return_value = LlmResponse(
                content="這是人生哲理的回應。",
                usage=LlmUsage(prompt_tokens=10, completion_tokens=5),
                model="deepseek-chat",
            )

            # Create conversation via chat
            resp = await client.post(
                "/api/v1/chat",
                json={"query": "人生的意義是什麼？", "kb_ids": []},
                headers=headers,
            )
            assert resp.status_code == 200
            conv_id = resp.json()["conversation_id"]

            # Get conversation with messages
            resp = await client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["messages"]) == 2  # user + assistant

            # List should include it
            resp = await client.get("/api/v1/conversations", headers=headers)
            ids = [c["id"] for c in resp.json()]
            assert conv_id in ids

            # Delete
            resp = await client.delete(f"/api/v1/conversations/{conv_id}", headers=headers)
            assert resp.status_code == 204

            # Gone
            resp = await client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_chat_with_invalid_model(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])

        resp = await client.post(
            "/api/v1/chat",
            json={"query": "測試", "kb_ids": [], "model": "gpt-fake"},
            headers=headers,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_chat_with_format_option(self, client):
        """All format options should be accepted."""
        headers = auth_headers((await login(client, *STAFF))["access_token"])

        for fmt in ("default", "summary", "bullets", "table", "formal"):
            with patch("app.services.llm.DeepSeekProvider.chat") as mock_llm:
                mock_llm.return_value = LlmResponse(
                    content=f"回答（{fmt}格式）",
                    usage=LlmUsage(prompt_tokens=5, completion_tokens=3),
                    model="deepseek-chat",
                )
                resp = await client.post(
                    "/api/v1/chat",
                    json={"query": "測試", "kb_ids": [], "format": fmt},
                    headers=headers,
                )
                assert resp.status_code == 200, f"format={fmt} failed"

    @pytest.mark.asyncio
    async def test_chat_invalid_format_rejected(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])

        resp = await client.post(
            "/api/v1/chat",
            json={"query": "測試", "kb_ids": [], "format": "invalid-format"},
            headers=headers,
        )
        assert resp.status_code == 400


#  ---------------------------------------------------------------------------
#  LLM module unit tests (no network)
#  ---------------------------------------------------------------------------
class TestLlmModule:
    @pytest.mark.asyncio
    async def test_deepseek_provider_chat_mocked_http(self):
        import httpx

        from app.services.llm import DeepSeekProvider

        mock_resp = httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "你好"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

        with patch.object(httpx.AsyncClient, "post", return_value=mock_resp):
            provider = DeepSeekProvider()
            resp = await provider.chat(
                [LlmMessage(role=LlmRole.USER, content="hello")],
                model="deepseek-chat",
            )
            assert resp.content == "你好"
            assert resp.usage.prompt_tokens == 1

    @pytest.mark.asyncio
    async def test_openrouter_provider_chat_mocked_http(self):
        import httpx

        from app.services.llm import OpenRouterProvider

        mock_resp = httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "世界"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 2},
            },
        )

        with patch.object(httpx.AsyncClient, "post", return_value=mock_resp):
            provider = OpenRouterProvider()
            resp = await provider.chat(
                [LlmMessage(role=LlmRole.USER, content="hello")],
                model="qwen/qwen-max",
            )
            assert resp.content == "世界"
            assert resp.usage.prompt_tokens == 2

    def test_str_enum_membership(self):
        assert LlmRole.SYSTEM == "system"
        assert str(LlmRole.USER) == "user"

    def test_model_registry_completeness(self):
        from app.services.llm import MODELS

        required = {"deepseek-v4-flash", "deepseek-v4-pro", "qwen3.7-max", "nemotron-3-ultra"}
        assert set(MODELS) == required
        for info in MODELS.values():
            assert info.provider in ("deepseek", "openrouter")
            assert info.max_tokens > 0
            assert info.description
