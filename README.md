# AIDG & KR System

**AI-Enabled Document Generation & Knowledge Retrieval System** 

A secure, multi-tenant-capable, AI-powered internal platform that :

1. Query internal knowledge with natural language (RAG)
2. Generate business documents (proposals, reports, meeting minutes, approvals)
3. Transcribe and organize meeting recordings (Cantonese + Traditional Chinese + English)
4. Manage knowledge bases, AI assistants, workflows, and permissions from an admin console
5. Review & approve AI outputs (human-in-the-loop)
6. Integrate with the intranet and / or future systems via APIs

Primary UI language: **Traditional Chinese (zh-Hant)** with full English support.

## Monorepo layout

```
apps/
  api/    FastAPI + SQLAlchemy 2.x (async) + Alembic + PostgreSQL/pgvector
  web/    Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui   [Module A — pending]
docs/
  ARCHITECTURE.md   Living architecture record (ADRs, decisions, model strategy)
  API.md            API contracts and endpoint reference
  DEPLOYMENT.md     Environment & deployment guide (staging + production)
.github/workflows/  CI pipeline
```

## Quick start (backend)

Prerequisites: Python 3.13, `uv`, Docker.

```bash
# 1. Configure environment
cp .env.example .env            # adjust as needed (dev defaults match docker-compose)

# 2. Start infrastructure (PostgreSQL/pgvector, Redis, MinIO S3)
docker compose up -d db redis minio

# 3. Run the API locally
cd apps/api
uv venv && uv pip install -e ".[dev]"
uv run alembic upgrade head      # apply migrations
uv run python -m app.db.seed     # seed orgs, roles, permissions, demo users
uv run uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs (dev only).
Health checks: `GET /api/v1/healthz` (liveness), `GET /api/v1/readyz` (db + redis).

### Demo users (after seeding)

| Username   | Password       | Role         |
|------------|----------------|--------------|
| `admin`    | `admin1234!`   | system_admin |
| `poweruser`| `admin1234!`   | power_user   |
| `staff`    | `admin1234!`   | staff        |
| `approver` | `admin1234!`   | approver     |
| `auditor`  | `admin1234!`   | auditor      |

> Override the default password via `AIDG_SEED_ADMIN_PASSWORD` and rotate before any
> non-local deployment.

## Testing & linting

```bash
cd apps/api
uv run pytest -q          # 64 tests: auth, RBAC, users, groups, orgs, audit, KBs, documents, retrieval, STT
uv run ruff check app tests
uv run ruff format --check app tests
```

Live smoke test (requires Postgres/pgvector up-to-date, mock embeddings by default):

```bash
cd apps/api
uv run python scripts/smoke_knowledge.py
```

## Module implementation status

| Module | Status |
|--------|--------|
| A — Unified AI Portal (frontend) | pending (next epic) |
| B — Backend Management Platform | in progress — auth/RBAC/users/groups/orgs/audit APIs done |
| C — Knowledge Base & Documents | **done (Epic 2)** — KBs, document upload/versioning, parsing (PDF/Word/Excel/PPT/TXT/HTML/CSV), chunking, embeddings, indexing pipeline, approval |
| D — RAG & Answer Generation | in progress — hybrid retrieval (pgvector + pg_trgm, RRF) done; LLM answer generation pending |
| E — Document Generation | pending |
| F — Speech-to-Text & Meetings | in progress — **OpenRouter ASR provider live** (verified), mock for dev; meeting endpoints pending |
| G — Workflow Automation | pending (Dify as external engine) |
| H — Integration & API Layer | foundation in place |

See `docs/ARCHITECTURE.md` for the full architecture and decisions.
