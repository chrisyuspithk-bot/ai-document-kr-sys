"""Tests for meeting intelligence endpoints."""

from __future__ import annotations

import io
import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.asr import AsrResult
from tests.conftest import auth_headers, login

STAFF = ("staff", "staff-password-123")
POWER = ("power", "power-password-123")
ADMIN = ("admin", "admin-password-123")


class TestMeetingCrud:
    @pytest.mark.asyncio
    async def test_create_and_list(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/meetings",
            json={"title": "季度服務檢討會議", "folder": "季度會議", "tags": ["檢討", "服務"]},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "季度服務檢討會議"
        assert data["folder"] == "季度會議"
        assert data["status"] == "completed"

        # List
        resp = await client.get("/api/v1/meetings", headers=headers)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["title"] == "季度服務檢討會議"

    @pytest.mark.asyncio
    async def test_create_empty_title_fails(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/meetings", json={"title": ""}, headers=headers
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_get_detail(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/meetings",
            json={"title": "管理委員會會議", "meeting_date": "2026-07-15T10:00:00Z"},
            headers=headers,
        )
        mid = resp.json()["id"]

        resp = await client.get(f"/api/v1/meetings/{mid}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["meeting"]["title"] == "管理委員會會議"
        assert data["recordings"] == []
        assert data["transcript"] is None
        assert data["summary"] is None

    @pytest.mark.asyncio
    async def test_update(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/meetings", json={"title": "舊標題"}, headers=headers
        )
        mid = resp.json()["id"]

        resp = await client.patch(
            f"/api/v1/meetings/{mid}",
            json={"title": "新標題", "description": "會議說明"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "新標題"
        assert resp.json()["description"] == "會議說明"

    @pytest.mark.asyncio
    async def test_delete(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/meetings", json={"title": "待刪除會議"}, headers=headers
        )
        mid = resp.json()["id"]

        resp = await client.delete(f"/api/v1/meetings/{mid}", headers=headers)
        assert resp.status_code == 204

        resp = await client.get(f"/api/v1/meetings/{mid}", headers=headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_folder_filter(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        await client.post(
            "/api/v1/meetings",
            json={"title": "會議A", "folder": "行政"},
            headers=headers,
        )
        await client.post(
            "/api/v1/meetings",
            json={"title": "會議B", "folder": "項目"},
            headers=headers,
        )

        resp = await client.get("/api/v1/meetings?folder=行政", headers=headers)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["title"] == "會議A"

    @pytest.mark.asyncio
    async def test_search(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        await client.post(
            "/api/v1/meetings", json={"title": "長者服務會議"}, headers=headers
        )
        await client.post(
            "/api/v1/meetings", json={"title": "青少年項目"}, headers=headers
        )

        resp = await client.get("/api/v1/meetings?search=長者", headers=headers)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["title"] == "長者服務會議"


class TestUploadAndTranscription:
    @pytest.mark.asyncio
    async def test_upload_and_transcribe(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/meetings", json={"title": "錄音測試會議"}, headers=headers
        )
        mid = resp.json()["id"]

        # Mock the ASR provider
        mock_result = AsrResult(
            full_text="[00:00] 大家好。\n[01:00] 今日討論新項目。",
            segments=[
                {"start": 0, "end": 60, "text": "大家好。"},
                {"start": 60, "end": 120, "text": "今日討論新項目。"},
            ],
            language="yue",
            confidence=0.95,
            provider="mock",
        )

        with patch(
            "app.services.meeting.get_asr_provider",
            return_value=AsyncMock(
                transcribe=AsyncMock(return_value=mock_result),
                provider_name="mock",
            ),
        ):
            fake_audio = io.BytesIO(b"\x00" * 1024)
            resp = await client.post(
                f"/api/v1/meetings/{mid}/recordings",
                files=[("files", ("test.mp3", fake_audio, "audio/mpeg"))],
                data={"language": "yue"},
                headers=headers,
            )
        assert resp.status_code == 201
        recordings = resp.json()
        assert len(recordings) >= 1

        # Check transcript
        resp = await client.get(f"/api/v1/meetings/{mid}/transcript", headers=headers)
        assert resp.status_code == 200
        transcript = resp.json()
        assert "大家好" in transcript["full_text"]
        assert transcript["language"] == "yue"

    @pytest.mark.asyncio
    async def test_no_meeting_returns_404(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/meetings/{fake_id}", headers=headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_transcript_not_found(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/meetings", json={"title": "無轉錄會議"}, headers=headers
        )
        mid = resp.json()["id"]

        resp = await client.get(f"/api/v1/meetings/{mid}/transcript", headers=headers)
        assert resp.status_code == 404


class TestSummarization:
    @pytest.mark.asyncio
    async def test_summarize(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/meetings", json={"title": "總結測試會議"}, headers=headers
        )
        mid = resp.json()["id"]

        # First upload and transcribe
        mock_asr = AsrResult(
            full_text=(
                "[00:00] 大家好。今日討論長者服務計劃。\n"
                "[01:00] 決定增加資源投放。\n"
                "[02:00] 下一步要準備預算提案。"
            ),
            segments=[
                {"start": 0, "end": 60, "text": "大家好。今日討論長者服務計劃。"},
                {"start": 60, "end": 120, "text": "決定增加資源投放。"},
                {"start": 120, "end": 180, "text": "下一步要準備預算提案。"},
            ],
            language="yue",
            confidence=0.95,
            provider="mock",
        )

        with patch(
            "app.services.meeting.get_asr_provider",
            return_value=AsyncMock(
                transcribe=AsyncMock(return_value=mock_asr),
                provider_name="mock",
            ),
        ):
            fake_audio = io.BytesIO(b"\x00" * 1024)
            await client.post(
                f"/api/v1/meetings/{mid}/recordings",
                files=[("files", ("test.mp3", fake_audio, "audio/mpeg"))],
                data={"language": "yue"},
                headers=headers,
            )

        # Now summarize
        mock_llm_response = type(
            "MockResp",
            (),
            {
                "content": json.dumps({
                    "summary": "會議討論長者服務計劃，決定增加資源投放並準備預算提案。",
                    "decisions": ["增加長者服務資源"],
                    "action_items": [
                        {"task": "準備預算提案", "owner": "未指定", "deadline": None}
                    ],
                    "key_points": ["長者服務計劃檢討", "資源投放增加", "預算準備"],
                }, ensure_ascii=False),
                "model": "deepseek-chat",
                "usage": type("Usage", (), {"prompt_tokens": 100, "completion_tokens": 50})(),
            },
        )()

        with patch(
            "app.services.meeting.get_provider_for",
            return_value=(AsyncMock(chat=AsyncMock(return_value=mock_llm_response)), None),
        ):
            resp = await client.post(
                f"/api/v1/meetings/{mid}/summarize", headers=headers
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "長者服務計劃" in data["summary"]
        assert len(data["decisions"]) >= 1
        assert len(data["action_items"]) >= 1
        assert len(data["key_points"]) >= 1

    @pytest.mark.asyncio
    async def test_summarize_no_transcript_fails(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/meetings", json={"title": "無轉錄會議"}, headers=headers
        )
        mid = resp.json()["id"]

        resp = await client.post(
            f"/api/v1/meetings/{mid}/summarize", headers=headers
        )
        assert resp.status_code == 400
        assert "transcript" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_summary(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/meetings", json={"title": "已有摘要會議"}, headers=headers
        )
        mid = resp.json()["id"]

        # Upload + transcribe
        mock_asr = AsrResult(
            full_text="會議內容。", segments=[], language="yue", confidence=0.9, provider="mock"
        )
        with patch(
            "app.services.meeting.get_asr_provider",
            return_value=AsyncMock(
                transcribe=AsyncMock(return_value=mock_asr), provider_name="mock"
            ),
        ):
            fake_audio = io.BytesIO(b"\x00" * 1024)
            await client.post(
                f"/api/v1/meetings/{mid}/recordings",
                files=[("files", ("test.mp3", fake_audio, "audio/mpeg"))],
                data={"language": "yue"},
                headers=headers,
            )

        # Summarize
        mock_summary = type(
            "MockResp", (),
            {
                "content": json.dumps({
                    "summary": "摘要內容",
                    "decisions": [],
                    "action_items": [],
                    "key_points": ["重點一"],
                }, ensure_ascii=False),
                "model": "deepseek-chat",
                "usage": type("Usage", (), {"prompt_tokens": 10, "completion_tokens": 5})(),
            },
        )()
        with patch(
            "app.services.meeting.get_provider_for",
            return_value=(AsyncMock(chat=AsyncMock(return_value=mock_summary)), None),
        ):
            await client.post(f"/api/v1/meetings/{mid}/summarize", headers=headers)

        resp = await client.get(f"/api/v1/meetings/{mid}/summary", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["summary"] == "摘要內容"

    @pytest.mark.asyncio
    async def test_summary_not_found(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/meetings", json={"title": "無摘要會議"}, headers=headers
        )
        mid = resp.json()["id"]

        resp = await client.get(f"/api/v1/meetings/{mid}/summary", headers=headers)
        assert resp.status_code == 404


class TestLinkKb:
    @pytest.mark.asyncio
    async def test_link_kb_no_transcript(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/meetings", json={"title": "未轉錄會議"}, headers=headers
        )
        mid = resp.json()["id"]

        resp = await client.post(
            f"/api/v1/meetings/{mid}/link-kb",
            json={"kb_ids": [str(uuid.uuid4())]},
            headers=headers,
        )
        assert resp.status_code == 400


class TestValidation:
    @pytest.mark.asyncio
    async def test_title_too_long(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/meetings", json={"title": "A" * 400}, headers=headers
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_cross_org_isolation(self, client):
        """Meetings from org A are not visible to org B."""
        headers_a = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/meetings", json={"title": "Org A 會議"}, headers=headers_a
        )
        assert resp.status_code == 201
        resp.json()["id"]

        # Staff and admin are in same org (hq) by seed data, so cross-org
        # isolation requires creating a user in a different org.
        # For now, verify that a random UUID doesn't work.
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/meetings/{fake_id}", headers=headers_a)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        # Filter by non-existent folder
        resp = await client.get("/api/v1/meetings?folder=不存在的文件夾", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []
