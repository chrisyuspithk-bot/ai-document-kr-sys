# AIDG & KR System — Architecture

**Client:** Yan Oi Tong Limited (YOT) – Social Services Division
**Reference:** TEN-IT-26-0167
**Status:** v0.3 — Architecture (all key decisions confirmed)

This document is the **living architecture record** for the AI-Enabled Document Generation
and Knowledge Retrieval (AIDG & KR) System. It is updated as the system evolves.

---

## 1. Overview

A secure, multi-tenant-capable, AI-powered internal platform that lets authorized YOT staff:

1. Query internal knowledge using natural language (RAG)
2. Generate business documents (proposals, reports, minutes, approvals, …)
3. Transcribe and organize meeting recordings (Cantonese + Traditional Chinese + English)
4. Manage knowledge bases, AI assistants, workflows, and permissions (admin console)
5. Review & approve AI outputs (human-in-the-loop)
6. Integrate with the YOT intranet and future systems via APIs

**Primary language:** Traditional Chinese (zh-Hant), full English (en) support.
**SSO:** Microsoft (Microsoft Entra ID / M365) first.

---

## 2. Confirmed Decisions (from client)

| # | Decision | Detail |
|---|----------|--------|
| D-01 | **SSO = Microsoft first** | Microsoft Entra ID (OIDC) as the primary identity provider; MFA for privileged users via Entra Conditional Access. Local "demo" provider only for development/seed. |
| D-02 | **Production hosting = Alibaba Cloud (HK region)** | Kubernetes on Alibaba ACK (or managed VMs) in HK; object storage = Alibaba OSS (HK); KMS for keys. |
| D-03 | **No GPU available** | No self-hosted models. All AI models (LLM, embeddings, reranker, ASR) are consumed via **managed APIs**. Self-hosting is a documented future option only. |
| D-04 | **Embeddings = Jina AI** (`jina-embeddings-v3`) | Client-provided Jina API key; multilingual (zh-Hant/en/mixed) at 1024 dims; configurable endpoint reduces data-residency concerns vs mainland-CN hosting. |
| D-05 | **Workflow engine = Dify** (self-hosted, open-source) | Dify is our visual workflow / AI orchestration engine, integrated via its Service API. Our FastAPI backend remains the security & governance boundary. Dify is **not** used for core RAG/chat (confirmed). |
| D-06 | **Auth = local provider now, OIDC-ready** | Build against the local identity provider (username/password + JWT) immediately; Microsoft Entra OIDC wired via config (no dev block). |
| D-07 | **UI language = zh-Hant default, en toggle** | Confirmed. |
| D-08 | **LLM keys:** DeepSeek key available (env); **OpenRouter key provided** | DeepSeek integrated behind config now. STT first via **OpenRouter** (audio-capable model, e.g. `mistralai/voxtral-small-24b-2507`); **Qwen ASR (DashScope)** becomes primary when its key arrives. |
| D-09 | **STT = OpenRouter first** | User chose OpenRouter for ASR. Note: **Qwen text models on OpenRouter (e.g. `qwen3.7-flash`) do not accept audio input** (HTTP 404) — a verified audio-capable model is the default; model is configurable via `AIDG_OPENROUTER_ASR_MODEL`. |

**Implication of D-03/D-04/D-05:** the "self-hosted model nodes (vLLM)" idea is dropped.
All model traffic goes to managed APIs (DeepSeek, OpenRouter, Alibaba Cloud, optionally Azure Speech as STT fallback).
→ Data-residency & zero-training-terms must be confirmed with each provider (see §12).

---

## 3. Guiding Principles & Key Decisions (ADRs)

| # | Decision | Rationale |
|---|----------|-----------|
| ADR-01 | **Python-first backend (FastAPI)**, single modular monolith for the API; Node/TS only in the frontend | All AI-heavy work lives in the Python ecosystem. One backend language = one domain model, one migration toolchain, one hiring profile. TypeScript remains in the Next.js frontend. |
| ADR-02 | **PostgreSQL 16 + pgvector + pg_trgm** as the primary store (relational + vectors) | One database: transactional data, RBAC, audit, and embeddings. pgvector HNSW + pg_trgm enable hybrid search in-place. Vector store abstracted behind an interface. |
| ADR-03 | **Custom retrieval pipeline** (not a black-box RAG framework) | Full control over chunking, metadata, permission-scoped filtering, citation granularity, and audit. This stays in OUR platform even though Dify owns workflows. |
| ADR-04 | **LLM provider abstraction layer** (OpenAI-compatible protocol) | DeepSeek, Qwen (DashScope), and others expose OpenAI-compatible APIs. One adapter serves all providers; models are DB-registered and config-driven. No vendor lock-in. |
| ADR-05 | **All AI via managed APIs (no self-hosted models)** | No GPU on premise (D-03). Embeddings = Jina AI; rerank = Jina reranker (same key/endpoint family); STT = OpenRouter audio model first (key provided), Qwen ASR API primary later; LLMs = DeepSeek per priority list. |
| ADR-06 | **Dify (self-hosted) as the workflow/AI-orchestration engine; our backend stays the governance boundary** | Visual, low-code workflow building (Module G) comes out of the box. Identity, RBAC, audit, approvals, and domain actions (generate doc, send for approval) remain in our platform; Dify is called through its Service API and reached through our permission-checked endpoints. A thin adapter maps our approval tasks to Dify workflow segments (HITL). |
| ADR-07 | **SSE (Server-Sent Events)** for chat/generation streaming | Simpler than WebSockets, proxy/ingress-friendly, one-directional — all streaming LLM output needs. |
| ADR-08 | **S3-compatible object storage (Alibaba OSS in prod; MinIO in dev)** | Portable across OSS/Azure Blob/S3. Bytes stay out of the database. |
| ADR-09 | **Multi-tenancy via organization (service unit) scoping**, enforced server-side on every query | Each of the 167 service units can own KBs, assistants, meetings, members. Tenant isolation is structural (org_id on every row + required-filter middleware), never UI-only. |
| ADR-10 | **JWT (short-lived) + OIDC (Microsoft Entra ID SSO)**; MFA via Entra Conditional Access; local provider for dev/demo | Enterprise-standard SSO/MFA without building MFA ourselves. JWKS-validated server-side. |
| ADR-11 | **Append-only audit log + retrieval event log** | Every security-sensitive action and every RAG retrieval/generation is recorded. PDPO compliance and incident investigation are first-class features. |
| ADR-12 | **Data-residency & zero-training agreements tracked per provider** | Managed APIs process content off-site; we record per-provider region + data-retention/training terms, and keep a compliance register (see §12 risks). |

---

## 4. High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        Users / Browsers (HTTPS/TLS 1.2+)                    │
│   Staff — Unified AI Portal          Admins — Admin Console                 │
└───────────────────────────┬──────────────────────────┬──────────────────────┘
                            │                          │
┌───────────────────────────▼──────────────────────────▼──────────────────────┐
│                    Next.js 15 (apps/web) — TypeScript + Tailwind + shadcn   │
│   Portal: chat(SSE), docgen, meetings, approvals, feedback                  │
│   Admin:  RBAC, KB mgmt, assistants, models/quotas, audit viewer, dashboards│
│   Auth: NextAuth v5 (Microsoft Entra ID OIDC · local dev provider)          │
└───────────────────────────┬─────────────────────────────────────────────────┘
                            │ REST (OpenAPI) + SSE streaming
┌───────────────────────────▼─────────────────────────────────────────────────┐
│                FastAPI (apps/api) — Python 3.12 modular monolith            │
│  ┌────────┬─────────┬──────────┬─────────┬────────┬────────┬───────┬─────┐  │
│  │ auth   │ users   │knowledge │retrieval│  chat  │genera- │meeting│work-│  │
│  │ (SSO,  │ (RBAC,  │(KB, docs,│(hybrid  │(convos,│tion    │(STT,  │flow │  │
│  │ tokens)│ groups, │ ingestion│ search, │ stream,│(docs,  │trans- │(defs│  │
│  │        │ roles)  │ versions)│ rerank) │ sources│ exports)│cripts)│,runs│  │
│  └────────┴─────────┴──────────┴─────────┴────────┴────────┴───────┴─────┘  │
│  + models | audit | integrations | LLM Provider abstraction (OpenAI-compat) │
│  + Dify adapter (workflow orchestration via Dify Service API)               │
│  Cross-cutting: tenant-scoping middleware · RBAC dependency · audit hooks   │
└───┬──────────────┬──────────────────┬──────────────────┬────────────────────┘
    │              │                  │                  │
┌───▼───────┐ ┌────▼──────┐ ┌────────▼──────┐ ┌──────────▼─────────┐
│ PostgreSQL│ │  Redis    │ │ OSS/MinIO     │ │ Celery/Redis Queue │
│ + pgvector│ │ cache/pub-│ │ (S3-compat)   │ │ workers:           │
│ + pg_trgm │ │ sub/queue │ │ docs, audio,  │ │ ingestion · stt ·  │
│ (source of│ │           │ │ exports       │ │ generation · index │
│  truth)   │ └───────────┘ └───────────────┘ └────────────────────┘
└───┬───────┘
    │
┌───▼────────────────────────────────────────────────────────────────────────┐
│  Dify (self-hosted, no GPU) — visual workflow / AI orchestration engine    │
│  • Visual workflow designer (Module G) · multi-step AI pipelines           │
│  • Reached ONLY via our FastAPI adapter (permission + audit at the edge)   │
│  • Human-in-the-loop steps mapped to our approval work queue               │
└───┬────────────────────────────────────────────────────────────────────────┘
    │
┌───▼────────────────────────────────────────────────────────────────────────┐
│  Managed AI APIs (no GPU — D-03)                                           │
│  • LLM: DeepSeek (V4-Flash/Pro) · Qwen3.7 Max (DashScope) · optional       │
│  • Embeddings: Qwen embedding API (DashScope)                              │
│  • Reranker: Alibaba GTE rerank API                                         │
│  • STT: Qwen/Paraformer ASR API (Cantonese+zh-Hant+en) · Azure Speech fallback│
│  • Zero-data-training agreements + provider region register                 │
└───┬────────────────────────────────────────────────────────────────────────┘
    │
┌───▼────────────────────────────────────────────────────────────────────────┐
│  External integrations (connectors, permission-enforced, audited)          │
│  Microsoft Entra ID (SSO/MFA) · Microsoft 365 / SharePoint / OneDrive      │
│  readiness · YOT intranet APIs                                             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Tech Stack

| Layer | Choice | Justification |
|---|---|---|
| Frontend | **Next.js 15 (App Router) + TypeScript + Tailwind CSS + shadcn/ui** | Modern, responsive; single app with `/portal` and `/admin` route groups. |
| UI libs | React Query + Zustand · SSE via `fetch` + ReadableStream | Caching, optimistic UI, native streaming. |
| Backend API | **FastAPI (Python 3.12)** | Async-native, OpenAPI out of the box, Pydantic validation, Python AI ecosystem. |
| Background jobs | **Celery + Redis** (or Arq) | Ingestion, transcription, generation, re-indexing are long-running → queue + workers, retries, idempotency. |
| Database | **PostgreSQL 16 + pgvector + pg_trgm** | Single source of truth; hybrid search in-place. |
| Cache/queue | **Redis 7** | Cache, rate limiting, Celery broker, pub/sub for progress events. |
| Object storage | **Alibaba OSS (HK) prod · MinIO dev** — S3 API | Portable; region-local (HK). |
| Auth | **NextAuth v5 + Microsoft Entra ID (OIDC)**; local provider for dev | Microsoft-first SSO + MFA via Conditional Access. |
| LLM orchestration | **LangGraph + custom retrieval pipeline** (our platform) | RAG/generation stay in-house for audit, permission scoping, citations. |
| Workflow | **Dify (self-hosted)** via Service API + thin adapter | Visual low-code workflow builder (Module G) with our governance at the edge. |
| Embeddings / rerank | **Jina AI `jina-embeddings-v3`** (1024 dims, zh-Hant/en/mixed) · **Jina reranker** for rerank | No GPU; client-provided key; configurable endpoint (D-04). |
| STT | **OpenRouter audio model** first (e.g. `mistralai/voxtral-small-24b-2507`) · **Qwen ASR (DashScope)** primary when key arrives · **Azure Speech** fallback | Cantonese + zh-Hant + EN + mixed; all managed APIs (no GPU). |
| Testing | pytest + httpx (API) · Vitest + Playwright (web) | Unit + integration + E2E for critical paths. |
| Observability | OpenTelemetry → Prometheus + Grafana · Loki · Sentry | Dashboards, health, audit. |
| Infra | Docker Compose (dev) · **Alibaba ACK K8s + Terraform (HK)** · GitHub Actions | Reproducible, portable, HK-region. |
| Secrets | KMS (Alibaba) / K8s Secrets / Vault; env in dev | No secrets in code or git. |

---

## 6. System Components (Modules A–H mapping)

| Module | Primary Components |
|---|---|
| A. Unified AI Portal | `apps/web` portal routes: chat (SSE), assistant launcher, docgen UI, meeting upload/folders, approval inbox, feedback. |
| B. Admin Console | `apps/web` admin routes + `apps/api` domains `users`, `knowledge`, `chat/assistants`, `models`, `workflow`, `audit`. |
| C. Knowledge Base & Processing | `knowledge` domain + `ingestion` worker: parsers (PDF/Word/Excel/PPT/TXT/HTML/image), OCR, layout/table extraction, chunking, metadata, versioning, re-index, bulk import. |
| D. RAG Engine | `retrieval` + `chat` domains: hybrid search, rerank, groundedness, confidence, citations, answer-format control, full retrieval/generation audit. |
| E. Document Generation | `generation` domain + workers: template + sample style transfer, preview→revise→regenerate→approve→export (Word/PDF). |
| F. STT & Meeting Intelligence | `meeting` domain + `stt` worker: ASR (OpenRouter audio model first; Qwen ASR/DashScope primary when key arrives; Azure Speech fallback), diarization, summary/decisions/action items, meeting folders, KB linkage. |
| G. Workflow Automation | **Dify** (self-hosted) + our `workflow` domain/adapter: visual builder, multi-level approval, human-in-the-loop, triggers (upload/generation/schedule/API), notifications, escalation, execution history. |
| H. Integration & API | `integrations` domain: API keys, M365/SharePoint/OneDrive readiness, intranet connectors, permission-enforced data access paths. |

---

## 7. Data Model (high level)

**Identity & access:** `organizations` (tenants/service units) · `users` · `groups` · `roles` ·
`role_assignments` · `permissions` · `api_keys`

**Knowledge:** `knowledge_bases` · `document_groups` · `documents` · `document_versions`
(content hash, effective date, approval status, lifecycle) · `chunks` (embedding vector) ·
`ingestion_jobs` · `meeting_folders`

**AI:** `assistants` · `assistant_versions` (prompt, model, knowledge scope, tools, mode) ·
`conversations` · `messages` (sources JSON) · `message_feedback` · `generation_requests` ·
`generation_versions` · `approvals` · `meetings` · `transcripts` · `transcript_segments` ·
`meeting_summaries`

**Ops:** `workflow_definitions` · `workflow_nodes` · `workflow_runs` · `workflow_run_steps`
(plus Dify workflow id mappings) · `llm_models` · `token_usage` · `quotas` · `audit_logs` ·
`retrieval_events` · `integrations`

Every row carries `org_id`; permission-scoped retrieval is enforced by tenant middleware + RBAC.

---

## 8. Cross-Cutting Concerns

- **Security:** TLS everywhere; JWT via JWKS (Microsoft Entra); MFA for privileged users (Entra Conditional Access); least-privilege RBAC; Pydantic validation on every endpoint; no secrets in code; KMS-managed keys; encryption at rest and in transit.
- **Privacy / PDPO:** privacy-by-design; data-minimized audit; export/delete user-data paths; **per-provider data-residency & zero-training register**; managed APIs reviewed for region + retention terms.
- **Multi-tenancy:** structural `org_id` scoping on all reads/writes; cross-KB search only within permitted scope.
- **Observability:** OTel traces across API + workers; Prometheus metrics; structured JSON logs; Sentry.
- **Vendor lock-in avoidance:** S3-compatible storage, OpenAI-compatible LLM adapter, open data model, export APIs for KBs/configs/documents. Dify workflows exportable as YAML (Dify native).

---

## 9. Model & AI Provider Strategy (all managed APIs — no GPU)

| Capability | Primary | Fallback / Notes |
|---|---|---|
| LLM — routine Q&A | DeepSeek-V4-Flash | default model |
| LLM — quality drafting | DeepSeek-V4-Pro | auto-upgrade by assistant config |
| LLM — critical / long ctx | Qwen3.7 Max (DashScope) | 1M context |
| LLM — agentic workflows | DeepSeek-V4-Pro / Qwen | used inside Dify workflows |
| Embeddings | **Jina AI** (`jina-embeddings-v3`) | dim 1024; DB-registered; key provided |
| Reranker | **Jina reranker** | quality threshold gate (key provided) |
| STT | **Qwen ASR API** | Cantonese + zh-Hant + en + mixed; **key pending — mocked behind ASRProvider** |
| STT fallback | **Azure Speech** | no-GPU cloud alternative; config-ready |

All adapters are OpenAI-compatible or wrapped behind our `LLMProvider` / `ASRProvider`
interfaces. Models are DB-registered rows; switching providers = config + key, no code change.

---

## 10. Epics & Prioritized User Stories

### Epic 0 — Foundation & Platform (P0)
- Monorepo + CI (lint, type-check, test, build, push); Docker Compose dev stack; config/secrets, logging, OpenAPI
- **US-0.1** As a developer, I can boot the full stack locally with one command.
- **US-0.2** As a developer, I get type-checked, linted, tested PRs in CI.

### Epic 1 — Auth, RBAC & Audit (P0)
- **Microsoft Entra ID OIDC** + local dev provider; JWT; MFA-ready (Conditional Access)
- Users/groups/roles/permissions; org (service-unit) scoping; append-only audit log
- **US-1.1** As a staff member, I sign in with my YOT Microsoft account (SSO).
- **US-1.2** As an admin, I create users/groups, assign roles/permissions per service unit.
- **US-1.3** As an auditor, I can view and export the audit trail.
- **US-1.4** As an admin, privileged actions require MFA (via Entra).

### Epic 2 — Knowledge Base & Document Processing (P0)
- KB/document-group CRUD; upload (multi-format + bulk); versioning; lifecycle/approval
- Ingestion pipeline: OCR, layout, tables, chunking, metadata, embedding (Qwen API), indexing status; re-index
- **US-2.1** As a user, I upload a PDF/Word/Excel/PPT/scan and see processing status.
- **US-2.2** As an admin, I control which groups can read which documents.
- **US-2.3** As an admin, I re-index a document after a new version is approved.
- **US-2.4** As an admin, I bulk-import a folder of documents.

### Epic 3 — RAG & Answer Engine (P0)
- Hybrid search (vector+BM25+metadata, RRF), rerank (GTE), top-k + score thresholds
- Source citations (document/page/paragraph), groundedness + confidence; answer formats; cross-KB within permission; full retrieval audit
- **US-3.1** As a staff member, I ask a question in Chinese and get a cited answer.
- **US-3.2** As a staff member, I see source snippets and can open the original document.
- **US-3.3** As an admin, I tune retrieval params and thresholds per assistant.
- **US-3.4** As an auditor, I can trace exactly which chunks and model produced every answer.

### Epic 4 — Unified AI Portal (P0)
- Assistant directory/launcher (permission-filtered); chat with streaming; conversation history; feedback; docgen UI; approval inbox
- **US-4.1** As a staff member, I launch an assistant and chat with streaming answers.
- **US-4.2** As a staff member, I review conversation history and rate answers.
- **US-4.3** As a staff member, I generate a document from a template + knowledge and preview it.
- **US-4.4** As an approver, I review and approve/reject an AI-generated document.

### Epic 5 — Document Generation Engine (P0)
- Templates + sample style transfer; preview→revise→regenerate→approve→export (Word/PDF); generation history
- **US-5.1** As a staff member, I generate a funding proposal from a YOT template.
- **US-5.2** As a staff member, I revise and regenerate, keeping version history.
- **US-5.3** As a staff member, I export the approved document to Word/PDF.

### Epic 6 — STT & Meeting Intelligence (P1)
- Upload audio/video; Cantonese/zh-Hant/en/mixed transcription (Qwen/Paraformer API, Azure fallback); diarization; auto summary/decisions/action items; meeting folders; KB linkage; permissions
- **US-6.1** As a user, I upload a Cantonese meeting recording and get a transcript + summary.
- **US-6.2** As a user, I organize meetings in folders and link a folder to an assistant.
- **US-6.3** As an admin, I control access to sensitive meeting content.

### Epic 7 — Admin Console & Model Governance (P1)
- Full RBAC/KB/assistant management UI; prompt versioning + rollback; model registry, token usage, quotas; health & usage dashboards
- **US-7.1** As an admin, I configure an assistant (prompt, model, KB scope, mode) and version it.
- **US-7.2** As an admin, I set model quotas and view token usage.
- **US-7.3** As an admin, I view system health and usage dashboards.
- **US-7.4** As an admin, I roll back an assistant prompt to a previous version.

### Epic 8 — Workflow Automation (P1) — via Dify
- Visual workflow designer (Dify UI, embedded/redirected); multi-level approval; human-in-the-loop; triggers (upload, generation, schedule, API); notifications/escalation; execution history; audit at the edge
- **US-8.1** As an admin, I design an approval workflow visually (Dify).
- **US-8.2** As a user, I complete my approval step in the work queue.
- **US-8.3** As an admin, I view execution history and audit every run.

### Epic 9 — Integration & API Layer (P1)
- Public/secure API with keys; intranet connectors; M365/SharePoint/OneDrive readiness
- **US-9.1** As a developer, I call the documented API with a scoped API key.
- **US-9.2** As an admin, I connect a KB to an approved intranet data source.
- **US-9.3** As a developer, I see a documented plan for SharePoint/OneDrive sync.

### Epic 10 — Hardening, Deployment & Docs (P2)
- Security hardening pass, load test (~600 users), export/backup, DR (Alibaba HK), Terraform + ACK manifests, DEPLOYMENT.md, API.md, seed data
- **US-10.1** As an operator, I deploy prod/test environments reproducibly in HK.
- **US-10.2** As an operator, I back up and restore the full system.
- **US-10.3** As a new engineer, I onboard using the docs and seed data.

---

## 11. Delivery Phases

| Phase | Scope | Exit criteria |
|---|---|---|
| **P0** | Epics 0–5 | E2E flow: upload → index → chat with sources → generate → approve → export |
| **P1** | Epics 6–9 | Meetings → transcript → summary → knowledge; admin governance; Dify workflows; APIs |
| **P2** | Epic 10 | Security/scale hardening, Alibaba HK production deployment, docs complete |

---

## 12. Open Decisions & Risks (need client confirmation)

### Decisions confirmed (v0.3)
1. **Auth:** build with local provider now + OIDC-ready config. ✅
2. **LLM keys:** DeepSeek key available (env). **Embeddings:** Jina AI key provided (`jina-embeddings-v3`). **STT:** **OpenRouter key provided** — audio-capable model wired now; Qwen ASR (DashScope) becomes primary when its key arrives. ✅
3. **UI language default:** zh-Hant default with English toggle. ✅
4. **Dify scope:** workflows only — **not** used for core RAG/chat (our pipeline owns RAG). ✅
5. **STT fallback:** Whisper needs GPU → Azure Speech as cloud fallback (config-ready). ✅
6. **OpenRouter ASR model:** Qwen text models on OpenRouter reject audio (HTTP 404); default verified audio model is `mistralai/voxtral-small-24b-2507` (configurable via `AIDG_OPENROUTER_ASR_MODEL`). ✅

### Remaining risks & notes
- **R-1 Data residency:** embeddings now via Jina (configurable endpoint). DeepSeek + OpenRouter ASR still process content off-site — confirm acceptable region/endpoint + retention terms with YOT.
- **R-2 Zero-training terms:** every provider (DeepSeek, Jina, OpenRouter, Alibaba, Azure) must confirm zero-data-retention & no-training-for-third-party terms. We keep a compliance register per provider/model.
- **R-3 Dependency on Dify:** Dify self-hosting is CPU-OK, but brings its own Postgres/Redis/vector store and upgrade cycle. Isolated behind our adapter.
- **R-4 Cost monitoring:** managed API costs need per-model quotas, dashboards, and alerting (covered by Epic 7).
- **R-5 Qwen ASR key pending:** STT now runs via OpenRouter (verified live). Qwen ASR (DashScope) remains the long-term primary for Cantonese quality; validate when its key arrives. Note that a pure-tone/no-speech clip can trigger model filler text — meeting pipeline should add VAD/no-speech detection (Epic 6).
