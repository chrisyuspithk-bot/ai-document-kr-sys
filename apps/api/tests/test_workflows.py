"""Tests for Workflow Automation endpoints."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers, login

ADMIN = ("admin", "admin-password-123")
POWER = ("power", "power-password-123")
STAFF = ("staff", "staff-password-123")


class TestWorkflowCrud:
    @pytest.mark.asyncio
    async def test_create_and_list(self, client):
        headers = auth_headers((await login(client, *ADMIN))["access_token"])

        resp = await client.post(
            "/api/v1/workflows",
            json={
                "name": "文件審批流程",
                "description": "文件生成後的兩級審批流程",
                "trigger_type": "document.generated",
                "steps": [
                    {"name": "主管審核", "step_order": 0, "action": "approve"},
                    {"name": "總監審核", "step_order": 1, "action": "approve"},
                ],
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "文件審批流程"
        assert data["trigger_type"] == "document.generated"
        assert len(data["steps"]) == 2
        wf_id = data["id"]

        # List
        resp = await client.get("/api/v1/workflows", headers=headers)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["status"] == "draft"

        # Get
        resp = await client.get(f"/api/v1/workflows/{wf_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "文件審批流程"

    @pytest.mark.asyncio
    async def test_update_and_activate(self, client):
        headers = auth_headers((await login(client, *ADMIN))["access_token"])

        resp = await client.post(
            "/api/v1/workflows",
            json={"name": "測試流程", "steps": []},
            headers=headers,
        )
        wf_id = resp.json()["id"]

        resp = await client.patch(
            f"/api/v1/workflows/{wf_id}",
            json={"status": "active", "description": "已啟用的流程"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"
        assert resp.json()["description"] == "已啟用的流程"

    @pytest.mark.asyncio
    async def test_delete(self, client):
        headers = auth_headers((await login(client, *ADMIN))["access_token"])

        resp = await client.post(
            "/api/v1/workflows",
            json={"name": "待刪除流程"},
            headers=headers,
        )
        wf_id = resp.json()["id"]

        resp = await client.delete(f"/api/v1/workflows/{wf_id}", headers=headers)
        assert resp.status_code == 204

        resp = await client.get(f"/api/v1/workflows/{wf_id}", headers=headers)
        assert resp.status_code == 404


class TestWorkflowExecution:
    @pytest.mark.asyncio
    async def test_trigger_active_workflow(self, client):
        headers = auth_headers((await login(client, *ADMIN))["access_token"])

        # Create and activate workflow
        resp = await client.post(
            "/api/v1/workflows",
            json={
                "name": "單級審批",
                "trigger_type": "manual",
                "steps": [
                    {"name": "審批人審核", "step_order": 0, "action": "approve"}
                ],
            },
            headers=headers,
        )
        wf_id = resp.json()["id"]
        # Ensure active
        await client.patch(f"/api/v1/workflows/{wf_id}", json={"status": "active"}, headers=headers)

        # Trigger
        resp = await client.post(
            f"/api/v1/workflows/{wf_id}/trigger",
            json={"trigger_type": "manual", "trigger_context": {"doc_id": "test-123"}},
            headers=headers,
        )
        assert resp.status_code == 201
        run = resp.json()
        assert run["status"] == "waiting_approval"
        assert run["trigger_context"] == {"doc_id": "test-123"}
        assert len(run["approvals"]) == 1
        assert run["approvals"][0]["status"] == "pending"
        run_id = run["id"]

        # List runs
        resp = await client.get("/api/v1/workflows/runs", headers=headers)
        assert resp.status_code == 200
        runs = resp.json()
        assert len(runs) == 1

        # Get run detail
        resp = await client.get(f"/api/v1/workflows/runs/{run_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "waiting_approval"

    @pytest.mark.asyncio
    async def test_trigger_draft_workflow_fails(self, client):
        headers = auth_headers((await login(client, *ADMIN))["access_token"])

        resp = await client.post(
            "/api/v1/workflows",
            json={"name": "草稿流程", "steps": []},
            headers=headers,
        )
        wf_id = resp.json()["id"]

        resp = await client.post(f"/api/v1/workflows/{wf_id}/trigger", headers=headers)
        assert resp.status_code == 400  # draft workflow cannot be triggered

    @pytest.mark.asyncio
    async def test_workflow_without_steps_completes_immediately(self, client):
        headers = auth_headers((await login(client, *ADMIN))["access_token"])

        resp = await client.post(
            "/api/v1/workflows",
            json={"name": "無步驟流程", "steps": []},
            headers=headers,
        )
        wf_id = resp.json()["id"]
        await client.patch(f"/api/v1/workflows/{wf_id}", json={"status": "active"}, headers=headers)

        resp = await client.post(f"/api/v1/workflows/{wf_id}/trigger", headers=headers)
        assert resp.status_code == 201
        assert resp.json()["status"] == "completed"


class TestApprovalQueue:
    @pytest.mark.asyncio
    async def test_approve_step_and_complete_run(self, client):
        admin_headers = auth_headers((await login(client, *ADMIN))["access_token"])

        # Create workflow with one approval step
        resp = await client.post(
            "/api/v1/workflows",
            json={
                "name": "單級審批",
                "steps": [{"name": "審批", "step_order": 0, "action": "approve"}],
            },
            headers=admin_headers,
        )
        wf_id = resp.json()["id"]
        await client.patch(f"/api/v1/workflows/{wf_id}", json={"status": "active"}, headers=admin_headers)

        # Trigger
        resp = await client.post(f"/api/v1/workflows/{wf_id}/trigger", headers=admin_headers)
        run = resp.json()
        step_id = run["approvals"][0]["id"]

        # Approve the step
        resp = await client.post(
            f"/api/v1/workflows/approvals/{step_id}/approve",
            json={"comment": "已審核通過"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
        assert resp.json()["comment"] == "已審核通過"

        # Run should now be completed
        resp = await client.get(f"/api/v1/workflows/runs/{run['id']}", headers=admin_headers)
        assert resp.json()["status"] == "completed"

    @pytest.mark.asyncio
    async def test_reject_step_fails_run(self, client):
        admin_headers = auth_headers((await login(client, *ADMIN))["access_token"])

        resp = await client.post(
            "/api/v1/workflows",
            json={
                "name": "拒絕測試",
                "steps": [{"name": "審批", "step_order": 0, "action": "approve"}],
            },
            headers=admin_headers,
        )
        wf_id = resp.json()["id"]
        await client.patch(f"/api/v1/workflows/{wf_id}", json={"status": "active"}, headers=admin_headers)

        resp = await client.post(f"/api/v1/workflows/{wf_id}/trigger", headers=admin_headers)
        run = resp.json()
        step_id = run["approvals"][0]["id"]

        resp = await client.post(
            f"/api/v1/workflows/approvals/{step_id}/reject",
            json={"comment": "需要修改"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

        resp = await client.get(f"/api/v1/workflows/runs/{run['id']}", headers=admin_headers)
        assert resp.json()["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_double_approve_fails(self, client):
        admin_headers = auth_headers((await login(client, *ADMIN))["access_token"])

        resp = await client.post(
            "/api/v1/workflows",
            json={
                "name": "雙重審批測試",
                "steps": [{"name": "審批", "step_order": 0, "action": "approve"}],
            },
            headers=admin_headers,
        )
        wf_id = resp.json()["id"]
        await client.patch(f"/api/v1/workflows/{wf_id}", json={"status": "active"}, headers=admin_headers)

        resp = await client.post(f"/api/v1/workflows/{wf_id}/trigger", headers=admin_headers)
        step_id = resp.json()["approvals"][0]["id"]

        await client.post(f"/api/v1/workflows/approvals/{step_id}/approve", headers=admin_headers)
        resp = await client.post(f"/api/v1/workflows/approvals/{step_id}/approve", headers=admin_headers)
        assert resp.status_code == 400  # already decided

    @pytest.mark.asyncio
    async def test_pending_approvals_list(self, client):
        admin_headers = auth_headers((await login(client, *ADMIN))["access_token"])

        resp = await client.post(
            "/api/v1/workflows",
            json={
                "name": "審批隊列測試",
                "steps": [{"name": "審批", "step_order": 0, "action": "approve"}],
            },
            headers=admin_headers,
        )
        wf_id = resp.json()["id"]
        await client.patch(f"/api/v1/workflows/{wf_id}", json={"status": "active"}, headers=admin_headers)
        await client.post(f"/api/v1/workflows/{wf_id}/trigger", headers=admin_headers)

        resp = await client.get("/api/v1/workflows/approvals/all", headers=admin_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["status"] == "pending"


class TestAnalytics:
    @pytest.mark.asyncio
    async def test_overview(self, client):
        headers = auth_headers((await login(client, *ADMIN))["access_token"])

        resp = await client.get("/api/v1/analytics/overview", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert "knowledge_bases" in data
        assert "documents" in data

    @pytest.mark.asyncio
    async def test_token_usage(self, client):
        headers = auth_headers((await login(client, *ADMIN))["access_token"])

        resp = await client.get("/api/v1/analytics/token-usage?days=30", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["period_days"] == 30
        assert "total_prompt_tokens" in data
        assert "by_model" in data

    @pytest.mark.asyncio
    async def test_list_models(self, client):
        headers = auth_headers((await login(client, *ADMIN))["access_token"])

        resp = await client.get("/api/v1/models", headers=headers)
        assert resp.status_code == 200
        models = resp.json()
        assert len(models) >= 1
        assert any(m["provider"] == "deepseek" for m in models)
