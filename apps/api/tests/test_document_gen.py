"""Tests for document generation endpoints: templates, generate, revise, approve, export."""



from __future__ import annotations

import uuid
from unittest.mock import patch

import jinja2
import pytest

from app.models.document_gen import DOCGEN_STATUS_DRAFT
from app.services.llm import LlmResponse, LlmUsage
from tests.conftest import auth_headers, login

STAFF = ("staff", "staff-password-123")
ADMIN = ("admin", "admin-password-123")
POWER = ("power", "power-password-123")

SAMPLE_TEMPLATE_CONTENT = """# {{title}}

## {{section_title}}

{{body}}

呈報人：{{reporter}}
日期：{{date}}
"""


#  ---------------------------------------------------------------------------
#  Template CRUD tests
#  ---------------------------------------------------------------------------


class TestTemplateCrud:
    @pytest.mark.asyncio
    async def test_create_template(self, client):
        headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.post(
            "/api/v1/templates",
            json={
                "name": "Test Proposal Template",
                "description": "A test template",
                "category": "proposal",
                "content": SAMPLE_TEMPLATE_CONTENT,
                "variables": {
                    "title": "Document title",
                    "section_title": "Section heading",
                    "body": "Main body text",
                    "reporter": "Who submitted",
                    "date": "Submission date",
                },
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Proposal Template"
        assert data["category"] == "proposal"
        assert data["variables"]["title"] == "Document title"
        assert data["version"] == 1
        return data

    @pytest.mark.asyncio
    async def test_list_templates(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])
        # Create one first
        await client.post(
            "/api/v1/templates",
            json={"name": "T1", "category": "proposal"},
            headers=auth_headers((await login(client, *POWER))["access_token"]),
        )
        resp = await client.get("/api/v1/templates", headers=headers)
        assert resp.status_code == 200
        items = resp.json()
        assert isinstance(items, list)

    @pytest.mark.asyncio
    async def test_get_template(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])
        # Create first
        create_resp = await client.post(
            "/api/v1/templates",
            json={"name": "T2", "category": "report"},
            headers=auth_headers((await login(client, *POWER))["access_token"]),
        )
        tmpl_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/templates/{tmpl_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "T2"

    @pytest.mark.asyncio
    async def test_get_nonexistent_template(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])
        resp = await client.get(f"/api/v1/templates/{uuid.uuid4()}", headers=headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_template(self, client):
        # Create
        power_headers = auth_headers((await login(client, *POWER))["access_token"])
        create_resp = await client.post(
            "/api/v1/templates",
            json={"name": "T3", "category": "minutes", "content": "original"},
            headers=power_headers,
        )
        tmpl_id = create_resp.json()["id"]

        # Update
        resp = await client.patch(
            f"/api/v1/templates/{tmpl_id}",
            json={"name": "T3 Updated", "content": "updated"},
            headers=power_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "T3 Updated"
        assert data["content"] == "updated"
        assert data["version"] == 2

    @pytest.mark.asyncio
    async def test_delete_template(self, client):
        power_headers = auth_headers((await login(client, *POWER))["access_token"])
        create_resp = await client.post(
            "/api/v1/templates",
            json={"name": "T4", "category": "memo"},
            headers=power_headers,
        )
        tmpl_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/templates/{tmpl_id}", headers=power_headers)
        assert resp.status_code == 204

        # Should not appear in active list
        staff_headers = auth_headers((await login(client, *STAFF))["access_token"])
        list_resp = await client.get("/api/v1/templates", headers=staff_headers)
        ids = [t["id"] for t in list_resp.json()]
        assert tmpl_id not in ids

    @pytest.mark.asyncio
    async def test_filter_by_category(self, client):
        power_headers = auth_headers((await login(client, *POWER))["access_token"])
        await client.post(
            "/api/v1/templates",
            json={"name": "Cat1", "category": "proposal"},
            headers=power_headers,
        )
        await client.post(
            "/api/v1/templates",
            json={"name": "Cat2", "category": "report"},
            headers=power_headers,
        )

        staff_headers = auth_headers((await login(client, *STAFF))["access_token"])
        resp = await client.get(
            "/api/v1/templates", params={"category": "proposal"}, headers=staff_headers
        )
        assert resp.status_code == 200
        for item in resp.json():
            assert item["category"] == "proposal"


#  ---------------------------------------------------------------------------
#  Document generation tests
#  ---------------------------------------------------------------------------


class TestDocumentGeneration:
    @pytest.mark.asyncio
    async def test_generate_basic(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])

        with patch("app.services.llm.DeepSeekProvider.chat") as mock_llm:
            mock_llm.return_value = LlmResponse(
                content="# 測試提案\n\n這是一份測試文件。\n\n呈報人：測試員",
                usage=LlmUsage(prompt_tokens=50, completion_tokens=30),
                model="deepseek-chat",
            )
            resp = await client.post(
                "/api/v1/generate",
                json={"prompt": "寫一份關於長者服務的提案", "title": "長者服務計劃提案"},
                headers=headers,
            )
            assert resp.status_code == 201, resp.text
            data = resp.json()
            assert data["title"] == "長者服務計劃提案"
            assert "測試提案" in data["content"]
            assert data["status"] == DOCGEN_STATUS_DRAFT
            assert data["model"] == "deepseek-v4-flash"
            return data

    @pytest.mark.asyncio
    async def test_generate_with_template(self, client):
        power_headers = auth_headers((await login(client, *POWER))["access_token"])
        # Create template
        tmpl_resp = await client.post(
            "/api/v1/templates",
            json={
                "name": "Proposal Template",
                "category": "proposal",
                "content": SAMPLE_TEMPLATE_CONTENT,
                "variables": {
                    "title": "Title",
                    "section_title": "Section",
                    "body": "Body",
                    "reporter": "Reporter",
                    "date": "Date",
                },
            },
            headers=power_headers,
        )
        tmpl_id = tmpl_resp.json()["id"]

        staff_headers = auth_headers((await login(client, *STAFF))["access_token"])
        with patch("app.services.llm.DeepSeekProvider.chat") as mock_llm:
            mock_llm.return_value = LlmResponse(
                content="# 服務評估報告\n\n## 評估結果\n\n服務成效良好。",
                usage=LlmUsage(prompt_tokens=60, completion_tokens=25),
                model="deepseek-chat",
            )
            resp = await client.post(
                "/api/v1/generate",
                json={
                    "prompt": "撰寫長者服務評估報告",
                    "template_id": tmpl_id,
                    "fill_values": {
                        "title": "長者服務評估",
                        "section_title": "綜合評估",
                        "body": "服務成效良好",
                        "reporter": "陳社工",
                        "date": "2026-08-01",
                    },
                },
                headers=staff_headers,
            )
            assert resp.status_code == 201, resp.text
            data = resp.json()
            assert data["content"]  # content was generated

    @pytest.mark.asyncio
    async def test_generate_empty_prompt_rejected(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])
        resp = await client.post(
            "/api/v1/generate",
            json={"prompt": ""},
            headers=headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_generate_invalid_model(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])
        resp = await client.post(
            "/api/v1/generate",
            json={"prompt": "測試", "model": "no-such-model"},
            headers=headers,
        )
        assert resp.status_code == 400


#  ---------------------------------------------------------------------------
#  Document revision tests
#  ---------------------------------------------------------------------------


class TestDocumentRevision:
    @pytest.mark.asyncio
    async def test_revise_document(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])

        with patch("app.services.llm.DeepSeekProvider.chat") as mock_llm:
            mock_llm.return_value = LlmResponse(
                content="# Draft\n\nOriginal content.",
                usage=LlmUsage(prompt_tokens=10, completion_tokens=5),
                model="deepseek-chat",
            )
            gen_resp = await client.post(
                "/api/v1/generate",
                json={"prompt": "Create a draft"},
                headers=headers,
            )
            doc_id = gen_resp.json()["id"]

            # Update mock for revision
            mock_llm.return_value = LlmResponse(
                content="# Draft\n\nRevised content with changes.",
                usage=LlmUsage(prompt_tokens=15, completion_tokens=8),
                model="deepseek-chat",
            )
            rev_resp = await client.post(
                f"/api/v1/gen-documents/{doc_id}/revise",
                json={"prompt": "Make it more formal"},
                headers=headers,
            )
            assert rev_resp.status_code == 200
            data = rev_resp.json()
            assert "Revised" in data["content"]

    @pytest.mark.asyncio
    async def test_revise_nonexistent_document(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])
        resp = await client.post(
            f"/api/v1/gen-documents/{uuid.uuid4()}/revise",
            json={"prompt": "Fix it"},
            headers=headers,
        )
        assert resp.status_code == 404


#  ---------------------------------------------------------------------------
#  Approval workflow tests
#  ---------------------------------------------------------------------------


class TestApprovalWorkflow:
    @pytest.mark.asyncio
    async def test_full_approval_flow(self, client):
        power_headers = auth_headers((await login(client, *POWER))["access_token"])
        admin_headers = auth_headers((await login(client, *ADMIN))["access_token"])

        # Power user generates a doc
        with patch("app.services.llm.DeepSeekProvider.chat") as mock_llm:
            mock_llm.return_value = LlmResponse(
                content="# Proposal\n\nContent for approval.",
                usage=LlmUsage(prompt_tokens=20, completion_tokens=10),
                model="deepseek-chat",
            )
            gen_resp = await client.post(
                "/api/v1/generate",
                json={"prompt": "Write a proposal"},
                headers=power_headers,
            )
        gen_data = gen_resp.json()
        doc_id = gen_data["id"]

        # Verify doc is visible immediately
        get_immediate = await client.get(f"/api/v1/gen-documents/{doc_id}", headers=power_headers)
        assert get_immediate.status_code == 200, f"Immediate GET failed: {get_immediate.text}"

        # Submit (as power user)
        submit_resp = await client.post(
            f"/api/v1/gen-documents/{doc_id}/submit", headers=power_headers
        )
        assert submit_resp.status_code == 200
        assert submit_resp.json()["status"] == "submitted"

        # Power user cannot approve own doc (even though they have WRITE permission)
        approve_self = await client.post(
            f"/api/v1/gen-documents/{doc_id}/approve",
            json={"comment": "self-approve"},
            headers=power_headers,
        )
        assert approve_self.status_code == 400

        # Admin (different user, superuser) approves
        approve_resp = await client.post(
            f"/api/v1/gen-documents/{doc_id}/approve",
            json={"comment": "Looks good"},
            headers=admin_headers,
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["status"] == "approved"

        # Verify document state (as power user, same org)
        get_resp = await client.get(f"/api/v1/gen-documents/{doc_id}", headers=power_headers)
        assert get_resp.status_code == 200, f"GET failed: {get_resp.text}"
        data = get_resp.json()
        assert data["status"] == "approved"
        assert data["review_comment"] == "Looks good"

    @pytest.mark.asyncio
    async def test_reject_flow(self, client):
        staff_headers = auth_headers((await login(client, *STAFF))["access_token"])
        power_headers = auth_headers((await login(client, *POWER))["access_token"])

        with patch("app.services.llm.DeepSeekProvider.chat") as mock_llm:
            mock_llm.return_value = LlmResponse(
                content="# Draft content",
                usage=LlmUsage(prompt_tokens=10, completion_tokens=5),
                model="deepseek-chat",
            )
            gen_resp = await client.post(
                "/api/v1/generate",
                json={"prompt": "Draft"},
                headers=staff_headers,
            )
        doc_id = gen_resp.json()["id"]

        # Submit
        await client.post(f"/api/v1/gen-documents/{doc_id}/submit", headers=staff_headers)

        # Reject
        reject_resp = await client.post(
            f"/api/v1/gen-documents/{doc_id}/reject",
            json={"comment": "Needs more details"},
            headers=power_headers,
        )
        assert reject_resp.status_code == 200
        assert reject_resp.json()["status"] == "rejected"

        # Can revise after rejection
        with patch("app.services.llm.DeepSeekProvider.chat") as mock_llm:
            mock_llm.return_value = LlmResponse(
                content="# Revised with more details",
                usage=LlmUsage(prompt_tokens=15, completion_tokens=8),
                model="deepseek-chat",
            )
            rev_resp = await client.post(
                f"/api/v1/gen-documents/{doc_id}/revise",
                json={"prompt": "Add more details"},
                headers=staff_headers,
            )
        assert rev_resp.status_code == 200
        assert rev_resp.json()["status"] == "draft"  # back to draft

    @pytest.mark.asyncio
    async def test_reject_without_comment_fails(self, client):
        staff_headers = auth_headers((await login(client, *STAFF))["access_token"])
        power_headers = auth_headers((await login(client, *POWER))["access_token"])

        with patch("app.services.llm.DeepSeekProvider.chat") as mock_llm:
            mock_llm.return_value = LlmResponse(
                content="# Draft",
                usage=LlmUsage(prompt_tokens=5, completion_tokens=3),
                model="deepseek-chat",
            )
            gen_resp = await client.post(
                "/api/v1/generate", json={"prompt": "Draft"}, headers=staff_headers
            )
        doc_id = gen_resp.json()["id"]
        await client.post(f"/api/v1/gen-documents/{doc_id}/submit", headers=staff_headers)

        # Reject without comment body — should be 422 (missing required field)
        resp = await client.post(
            f"/api/v1/gen-documents/{doc_id}/reject", headers=power_headers
        )
        assert resp.status_code == 422


#  ---------------------------------------------------------------------------
#  Document list + delete tests
#  ---------------------------------------------------------------------------


class TestDocumentList:
    @pytest.mark.asyncio
    async def test_list_documents(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])
        resp = await client.get("/api/v1/gen-documents", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_get_document(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])

        with patch("app.services.llm.DeepSeekProvider.chat") as mock_llm:
            mock_llm.return_value = LlmResponse(
                content="# Doc",
                usage=LlmUsage(prompt_tokens=5, completion_tokens=2),
                model="deepseek-chat",
            )
            gen_resp = await client.post(
                "/api/v1/generate",
                json={"prompt": "Write something"},
                headers=headers,
            )
        doc_id = gen_resp.json()["id"]

        resp = await client.get(f"/api/v1/gen-documents/{doc_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == doc_id

    @pytest.mark.asyncio
    async def test_delete_document(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])

        with patch("app.services.llm.DeepSeekProvider.chat") as mock_llm:
            mock_llm.return_value = LlmResponse(
                content="# To delete",
                usage=LlmUsage(prompt_tokens=5, completion_tokens=2),
                model="deepseek-chat",
            )
            gen_resp = await client.post(
                "/api/v1/generate", json={"prompt": "Delete me"}, headers=headers
            )
        doc_id = gen_resp.json()["id"]

        power_headers = auth_headers((await login(client, *POWER))["access_token"])
        resp = await client.delete(f"/api/v1/gen-documents/{doc_id}", headers=power_headers)
        assert resp.status_code == 204

        resp = await client.get(f"/api/v1/gen-documents/{doc_id}", headers=headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_document_history_preserves_prompt(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])

        with patch("app.services.llm.DeepSeekProvider.chat") as mock_llm:
            mock_llm.return_value = LlmResponse(
                content="# History test",
                usage=LlmUsage(prompt_tokens=10, completion_tokens=5),
                model="deepseek-chat",
            )
            gen_resp = await client.post(
                "/api/v1/generate",
                json={"prompt": "Write about history tracking"},
                headers=headers,
            )
        doc_id = gen_resp.json()["id"]

        resp = await client.get(f"/api/v1/gen-documents/{doc_id}", headers=headers)
        data = resp.json()
        assert data["prompt"] == "Write about history tracking"
        assert data["model"] == "deepseek-v4-flash"
        assert data["version"] == 1


#  ---------------------------------------------------------------------------
#  Export tests
#  ---------------------------------------------------------------------------


class TestExport:
    @pytest.mark.asyncio
    async def test_export_unapproved_fails(self, client):
        headers = auth_headers((await login(client, *STAFF))["access_token"])

        with patch("app.services.llm.DeepSeekProvider.chat") as mock_llm:
            mock_llm.return_value = LlmResponse(
                content="# Draft only",
                usage=LlmUsage(prompt_tokens=5, completion_tokens=3),
                model="deepseek-chat",
            )
            gen_resp = await client.post(
                "/api/v1/generate", json={"prompt": "Draft"}, headers=headers
            )
        doc_id = gen_resp.json()["id"]

        resp = await client.post(f"/api/v1/gen-documents/{doc_id}/export", headers=headers)
        assert resp.status_code == 400  # not approved

    @pytest.mark.asyncio
    async def test_export_approved_docx(self, client):
        staff_headers = auth_headers((await login(client, *STAFF))["access_token"])
        power_headers = auth_headers((await login(client, *POWER))["access_token"])

        with patch("app.services.llm.DeepSeekProvider.chat") as mock_llm:
            mock_llm.return_value = LlmResponse(
                content="# Export Test\n\nThis document will be exported.",
                usage=LlmUsage(prompt_tokens=10, completion_tokens=8),
                model="deepseek-chat",
            )
            gen_resp = await client.post(
                "/api/v1/generate",
                json={"prompt": "Export test document"},
                headers=staff_headers,
            )
        doc_id = gen_resp.json()["id"]

        # Submit + approve
        await client.post(f"/api/v1/gen-documents/{doc_id}/submit", headers=staff_headers)
        await client.post(
            f"/api/v1/gen-documents/{doc_id}/approve",
            json={"comment": "ok"},
            headers=power_headers,
        )

        # Export
        resp = await client.post(
            f"/api/v1/gen-documents/{doc_id}/export?fmt=docx", headers=staff_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["docx"] is not None
        assert ".docx" in (data["docx"] or "")


#  ---------------------------------------------------------------------------
#  Template rendering unit test
#  ---------------------------------------------------------------------------


class TestTemplateRendering:
    def test_render_template(self):
        from app.services.document_gen import render_template

        result = render_template(
            SAMPLE_TEMPLATE_CONTENT,
            {
                "title": "年度報告",
                "section_title": "服務概覽",
                "body": "本年度服務人次顯著增加。",
                "reporter": "陳社工",
                "date": "2026-03-31",
            },
        )
        assert "年度報告" in result
        assert "服務概覽" in result
        assert "本年度服務人次顯著增加" in result
        assert "陳社工" in result
        assert "2026-03-31" in result

    def test_render_missing_variable_raises(self):
        from app.services.document_gen import render_template

        with pytest.raises(jinja2.TemplateError):
            render_template(SAMPLE_TEMPLATE_CONTENT, {"title": "Only title"})
