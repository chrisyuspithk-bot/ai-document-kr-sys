"""Epic 2 API tests: KBs, document upload/processing, retrieval, permissions."""

from __future__ import annotations

import httpx

from tests.conftest import auth_headers, login

ADMIN = ("admin", "admin-password-123")
POWER = ("power", "power-password-123")
STAFF = ("staff", "staff-password-123")

SAMPLE_TXT = (
    "仁愛堂長者服務中心服務指引\n\n"
    "第一節：服務目標\n為社區長者提供日間照顧及復康服務。\n\n"
    "第二節：申請資格\n年滿六十歲並居住於本區之長者。\n\n"
    "第三節：收費標準\n每日收費為港幣五十元。\n"
).encode()


async def _login(client: httpx.AsyncClient, user: tuple[str, str]) -> dict:
    token = (await login(client, *user))["access_token"]
    return auth_headers(token)


async def _create_kb(client: httpx.AsyncClient, headers: dict, name: str, **extra) -> dict:
    resp = await client.post(
        "/api/v1/knowledge-bases", json={"name": name, **extra}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_kb_crud_and_org_scoping(client: httpx.AsyncClient) -> None:
    admin = await _login(client, ADMIN)
    power = await _login(client, POWER)

    # Admin creates a KB in their own org (hq).
    kb = await _create_kb(client, admin, "人力資源政策庫")
    kb_id = kb["id"]

    # Power user (same org) sees it.
    resp = await client.get("/api/v1/knowledge-bases", headers=power)
    assert resp.status_code == 200
    assert any(k["id"] == kb_id for k in resp.json())

    # Patch + get.
    resp = await client.patch(
        f"/api/v1/knowledge-bases/{kb_id}",
        json={"description": "更新後描述"},
        headers=admin,
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "更新後描述"

    # Second org KB is invisible to power user (org scoping).
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "YOT 新界區", "code": "YOT-NT"},
        headers=admin,
    )
    assert org_resp.status_code == 201, org_resp.text
    other_org_id = org_resp.json()["id"]
    other_kb = await _create_kb(client, admin, "其他分區內部庫", org_id=other_org_id)
    resp = await client.get("/api/v1/knowledge-bases", headers=power)
    assert other_kb["id"] not in {k["id"] for k in resp.json()}

    # Staff cannot create KBs.
    staff = await _login(client, STAFF)
    resp = await client.post("/api/v1/knowledge-bases", json={"name": "不應成功"}, headers=staff)
    assert resp.status_code == 403

    # Superuser can read the other-org KB directly.
    resp = await client.get(f"/api/v1/knowledge-bases/{other_kb['id']}", headers=admin)
    assert resp.status_code == 200

    # Delete KB (superuser).
    resp = await client.delete(f"/api/v1/knowledge-bases/{other_kb['id']}", headers=admin)
    assert resp.status_code == 204


async def test_upload_process_search_flow(client: httpx.AsyncClient) -> None:
    power = await _login(client, POWER)
    kb = await _create_kb(client, power, "長者服務知識庫")

    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        files={"file": ("service_guide.txt", SAMPLE_TXT, "text/plain")},
        data={"title": "長者服務中心指引", "process_sync": "true"},
        headers=power,
    )
    assert resp.status_code == 201, resp.text
    doc = resp.json()
    assert doc["status"] == "indexed"
    assert doc["chunk_count"] >= 1
    assert doc["version_number"] == 1

    # Retrieval finds the relevant chunk (verbatim term; fuzzy phrase matching
    # is exercised against Postgres/pg_trgm in the live smoke test).
    search = await client.post(
        "/api/v1/retrieval/search",
        json={"query": "申請資格", "kb_ids": [kb["id"]], "top_k": 5},
        headers=power,
    )
    assert search.status_code == 200, search.text
    results = search.json()
    assert results
    assert all(r["kb_id"] == kb["id"] for r in results)
    assert any("六十歲" in r["content"] for r in results)
    assert all(r["document_title"] == "長者服務中心指引" for r in results)

    # Chunks endpoint returns indexed chunks with page metadata.
    resp = await client.get(f"/api/v1/documents/{doc['id']}/chunks", headers=power)
    assert resp.status_code == 200
    chunks = resp.json()
    assert chunks
    assert all(c["metadata"]["page"] == 1 for c in chunks)

    # Approve flow.
    resp = await client.patch(
        f"/api/v1/documents/{doc['id']}",
        json={"is_approved": True},
        headers=power,
    )
    assert resp.status_code == 200
    assert resp.json()["is_approved"] is True
    assert resp.json()["approved_at"] is not None

    # Versioning: uploading again bumps the version.
    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        files={"file": ("service_guide_v2.txt", SAMPLE_TXT, "text/plain")},
        data={"document_id": doc["id"], "process_sync": "true"},
        headers=power,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["version_number"] == 2

    resp = await client.get(f"/api/v1/documents/{doc['id']}/versions", headers=power)
    assert resp.status_code == 200
    versions = resp.json()
    assert [v["version_number"] for v in versions] == [2, 1]


async def test_staff_cannot_upload(client: httpx.AsyncClient) -> None:
    staff = await _login(client, STAFF)
    power = await _login(client, POWER)
    kb = await _create_kb(client, power, "共用庫")
    resp = await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        files={"file": ("x.txt", b"data", "text/plain")},
        headers=staff,
    )
    assert resp.status_code == 403


async def test_retrieval_permission_scoping(client: httpx.AsyncClient) -> None:
    admin = await _login(client, ADMIN)
    power = await _login(client, POWER)

    # Admin creates a KB in a different org and indexes a doc there.
    org_resp = await client.post(
        "/api/v1/organizations",
        json={"name": "YOT 港島區", "code": "YOT-HI"},
        headers=admin,
    )
    assert org_resp.status_code == 201
    other_org_id = org_resp.json()["id"]
    other_kb = await _create_kb(client, admin, "港島內部政策", org_id=other_org_id)
    resp = await client.post(
        f"/api/v1/knowledge-bases/{other_kb['id']}/documents",
        files={"file": ("policy.txt", "機密內部政策內容".encode(), "text/plain")},
        data={"process_sync": "true"},
        headers=admin,
    )
    assert resp.status_code == 201, resp.text

    # Power user (different org) cannot retrieve from that KB.
    search = await client.post(
        "/api/v1/retrieval/search",
        json={"query": "機密內部政策", "kb_ids": [other_kb["id"]]},
        headers=power,
    )
    assert search.status_code == 403

    # Power user can search without kb_ids (org scoped) and sees no results.
    search = await client.post(
        "/api/v1/retrieval/search",
        json={"query": "機密內部政策"},
        headers=power,
    )
    assert search.status_code == 200
    assert search.json() == []


async def test_search_audited(client: httpx.AsyncClient) -> None:
    power = await _login(client, POWER)
    kb = await _create_kb(client, power, "審計測試庫")
    await client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        files={"file": ("a.txt", "測試文件內容".encode(), "text/plain")},
        data={"process_sync": "true"},
        headers=power,
    )
    await client.post(
        "/api/v1/retrieval/search",
        json={"query": "測試文件"},
        headers=power,
    )
    admin = await _login(client, ADMIN)
    resp = await client.get("/api/v1/audit-logs", headers=admin)
    assert resp.status_code == 200
    actions = [entry["action"] for entry in resp.json()["items"]]
    assert "retrieval.search" in actions
    assert "document.upload" in actions
