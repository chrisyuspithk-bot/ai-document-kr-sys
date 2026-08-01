# Deployment Guide — AIDG & KR System

Covers local development, staging, and the target production topology
(**Alibaba Cloud Hong Kong region**). Kubernetes manifests and Terraform
modules will land with later epics; the compose file below is the source of
truth for local runs and a reference topology.

## Environments

| Environment | Purpose | Region |
|-------------|---------|--------|
| `development` | local docker-compose + `uvicorn --reload` | local |
| `staging`     | pre-production validation (isolated data) | HK (or SG by approval) |
| `production`  | live service, ~600 users / 167 service units | HK |

Production and testing environments are **fully separated** (separate
Postgres, Redis, object storage, secrets, and DNS). No production data ever
flows into staging/testing.

## Configuration

All settings are environment variables (prefix `AIDG_`, see
[`apps/api/app/core/config.py`](../apps/api/app/core/config.py)). Copy
`.env.example` → `.env` for local development. **Never commit `.env`.**

Security-relevant variables that must differ per environment:

| Variable | Notes |
|----------|-------|
| `AIDG_JWT_SECRET` | ≥ 32 random bytes; rotate on compromise |
| `AIDG_SEED_ADMIN_PASSWORD` | change from the dev default before any real deployment |
| `AIDG_DATABASE_URL` | `postgresql+asyncpg://…` |
| `AIDG_REDIS_URL` | `redis://…` |
| `AIDG_S3_*` | S3-compatible endpoint, keys, bucket |
| `AIDG_OIDC_*` | Microsoft Entra ID tenant/client settings |
| `AIDG_JINA_API_KEY` | embeddings (`jina-embeddings-v3`); leave empty to use the deterministic mock |
| `AIDG_STORAGE_BACKEND` | `auto` → S3/MinIO when `AIDG_S3_ENDPOINT` is set, else local disk; `local` forces local disk (`AIDG_LOCAL_STORAGE_ROOT`) |
| `AIDG_STT_PROVIDER` / `AIDG_OPENROUTER_*` | speech-to-text (OpenRouter default; `mock` for dev) |

## Object storage

Documents are stored via `app/services/storage.py` — a thin abstraction over
S3-compatible storage with a local-disk fallback (`AIDG_STORAGE_BACKEND=local`).
In production use **Alibaba Cloud OSS (HK)** with `AIDG_S3_ENDPOINT=https://oss-cn-hongkong.aliyuncs.com`
and the appropriate bucket/keys. Object keys are `docs/{kb_id}/{random}_{filename}`;
versions are immutable blobs referenced by `document_versions.storage_key`.

## Local development

```bash
docker compose up -d db redis minio        # infra only
cd apps/api
uv venv && uv pip install -e ".[dev]"
uv run alembic upgrade head
uv run python -m app.db.seed
uv run uvicorn app.main:app --reload --port 8000
```

`docker compose up --build` runs the full API container
(migrate → seed → uvicorn) against the same infra.

## Database migrations

Migrations live in `apps/api/alembic/versions/`. They are generated against
PostgreSQL and must be applied before deploying a new API version:

```bash
uv run alembic upgrade head     # apply
uv run alembic downgrade -1     # roll back one step (dev only)
```

### Required PostgreSQL extensions (Epic 2)

The schema uses two extensions, created by the `3f8c2625f16e` migration
(`epic_2_knowledge_bases_documents_chunks`) — or manually on managed Postgres
that forbids superuser DDL:

```sql
CREATE EXTENSION IF NOT EXISTS vector;    -- pgvector (embedding column, HNSW index)
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- word_similarity keyword search, GIN index
```

Both extensions ship in the `pgvector/pgvector` Docker image used by
`docker-compose.yml`. On Alibaba Cloud RDS/ApsaraDB for PostgreSQL, enable the
`vector` (rds_pgvector) and `pg_trgm` plugins via the console before running
migrations. Verify with:

```sql
SELECT extname FROM pg_extension WHERE extname IN ('vector','pg_trgm');
SELECT indexname FROM pg_indexes WHERE indexname LIKE 'ix_document_chunks%';
```

## Backups & data portability

- Postgres: scheduled `pg_dump`; verified restore drill.
- Object storage: bucket replication within the HK region.
- Vendor lock-in avoidance: all data (documents, vectors, configs,
  conversations) is stored in open formats on owned infrastructure; the LLM
  layer is provider-swappable behind a thin adapter (see ARCHITECTURE.md).

## Security checklist (non-exhaustive)

- [ ] TLS everywhere (in transit), KMS/encrypted volumes at rest
- [ ] Microsoft Entra ID SSO + MFA enforced for privileged users
- [ ] MFA for all admin console users
- [ ] Least-privilege RBAC; admin sessions audited
- [ ] Secrets in a secrets manager, never in env of long-lived instances only
- [ ] Full audit logging enabled; export restricted to `audit:export`
- [ ] Privacy-by-design review vs. PDPO requirements before go-live

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs lint + tests on every push/PR.
Deployment automation (build image → push to Alibaba ACR → rollout on ACK) is
planned as a separate workflow once the target environment is provisioned.
