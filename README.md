# AIDG & KR System

**AI-Enabled Document Generation & Knowledge Retrieval System**

A secure, multi-tenant-capable, AI-powered internal platform

1. Query internal knowledge with natural language (RAG)
2. Generate business documents (proposals, reports, meeting minutes, approvals)
3. Transcribe and organize meeting recordings (Cantonese + Traditional Chinese + English)
4. Manage knowledge bases, AI assistants, workflows, and permissions from an admin console
5. Review & approve AI outputs (human-in-the-loop)
6. Integrate with the intranet and/or future systems via APIs

Primary UI language: **Traditional Chinese (zh-Hant)** with full English support.

## Monorepo layout

```
apps/
  api/    FastAPI + SQLAlchemy 2.x (async) + Alembic + PostgreSQL/pgvector
  web/    Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui
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

## Quick start (frontend)

Prerequisites: Node.js 20+, npm.

```bash
cd apps/web
cp .env.example .env.local       # configure NEXT_PUBLIC_API_URL (default: http://localhost:8000)
npm install
npm run dev                       # http://localhost:3000
```

Build: `npm run build` (16 routes, zero errors).

## Demo users (after seeding)

| Username    | Password       | Role         |
|-------------|----------------|--------------|
| `admin`     | `admin1234!`   | system_admin |
| `poweruser` | `admin1234!`   | power_user   |
| `staff`     | `admin1234!`   | staff        |
| `approver`  | `admin1234!`   | approver     |
| `auditor`   | `admin1234!`   | auditor      |

> Override the default password via `AIDG_SEED_ADMIN_PASSWORD` and rotate before any
> non-local deployment.

## Testing & linting

```bash
# Backend
cd apps/api
uv run pytest -q                     # 146 tests
uv run ruff check app tests
uv run ruff format --check app tests

# Frontend
cd apps/web
npm run build                        # 16 routes, verified
```

## Epic implementation status

| Epic | Module | Status |
|------|--------|--------|
| 0/1  | Foundation (auth, RBAC, orgs, audit, multi-tenancy) | ✅ done |
| 2    | Knowledge Base & Document Processing | ✅ done |
| 3    | RAG & Answer Generation Engine | ✅ done |
| 4    | Document Generation Engine | ✅ done |
| 5    | Speech-to-Text & Meeting Intelligence | ✅ done |
| 6    | Workflow Automation | ✅ done |
| 7    | Integration & API Layer | ✅ done |
| 8    | Frontend Portal (Modules A & B) | ✅ done |
| 9    | Admin Console (assistants, analytics, model mgmt) | ✅ done |

See `docs/ARCHITECTURE.md` for the full architecture and decisions.
