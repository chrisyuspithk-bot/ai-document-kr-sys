"""Live smoke test for Epic 2 against Postgres (vector + pg_trgm).

Requires the live database (see DEPLOYMENT.md) and applied migrations. Uses the
mock embedding provider so no external embedding API is called; re-run with
AIDG_JINA_API_KEY set to exercise the real Jina provider.
"""

from __future__ import annotations

import asyncio
import os

os.environ["AIDG_STORAGE_BACKEND"] = "local"
os.environ["AIDG_LOCAL_STORAGE_ROOT"] = "data/uploads-live"
os.environ["AIDG_JINA_API_KEY"] = os.environ.get("AIDG_JINA_API_KEY", "")

import httpx  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402

DOC_TEXT = """仁愛堂長者服務中心服務指引（2025年版）

第一章 總則
本指引適用於仁愛堂社會服務部轄下所有長者服務中心。

第二章 服務目標
中心旨在為社區長者提供日間照顧、健康管理及復康訓練等綜合服務，並支援照顧者。

第三章 申請資格
申請人須年滿六十歲，並為本區居民，或經社會福利署轉介。
申請時須提交身分證明文件副本及住址證明。

第四章 收費標準
日間照顧服務每日收費為港幣五十元，經濟困難者可申請減免。
復康訓練按節收費，每節港幣二十元。

第五章 服務時間
星期一至六上午九時至下午五時，公眾假期休息。
緊急支援熱線於辦公時間外維持運作。

第六章 投訴機制
服務使用者或其家屬可向中心主任提出投訴，中心須於十個工作天內回覆。
"""


async def main() -> None:
    settings = get_settings()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": settings.seed_admin_password},
        )
        assert login.status_code == 200, f"login failed: {login.text}"
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        kb = await client.post(
            "/api/v1/knowledge-bases",
            json={"name": "實況測試庫-長者服務"},
            headers=headers,
        )
        assert kb.status_code == 201, kb.text
        kb_id = kb.json()["id"]
        print(f"[ok] created KB {kb_id}")

        upload = await client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents",
            files={"file": ("service_guide_2025.txt", DOC_TEXT.encode("utf-8"), "text/plain")},
            data={"title": "長者服務中心指引2025", "process_sync": "true"},
            headers=headers,
        )
        assert upload.status_code == 201, upload.text
        doc = upload.json()
        print(
            f"[ok] upload processed: status={doc['status']} chunks={doc['chunk_count']}"
        )

        search = await client.post(
            "/api/v1/retrieval/search",
            json={"query": "長者申請資格門檻", "kb_ids": [kb_id], "top_k": 5},
            headers=headers,
        )
        assert search.status_code == 200, search.text
        results = search.json()
        print(f"[ok] fuzzy phrase search returned {len(results)} result(s)")
        for r in results[:3]:
            snippet = r["content"].replace("\n", " ")[:60]
            print(f"      score={r['score']} :: {snippet}")
        assert results, "expected at least one result from pg_trgm/vector search"

        exact = await client.post(
            "/api/v1/retrieval/search",
            json={"query": "收費標準", "kb_ids": [kb_id], "top_k": 3},
            headers=headers,
        )
        assert exact.status_code == 200
        print(
            f"[ok] exact search returned {len(exact.json())} result(s) "
            f"(first score={exact.json()[0]['score'] if exact.json() else None})"
        )

        chunks = await client.get(
            f"/api/v1/documents/{doc['id']}/chunks", headers=headers
        )
        assert chunks.status_code == 200, chunks.text
        print(f"[ok] document chunks: {len(chunks.json())}")

        print("\nSMOKE TEST PASSED (Postgres / pgvector / pg_trgm)")


if __name__ == "__main__":
    asyncio.run(main())
