# API Reference — AIDG & KR System

Base path: `/api/v1` (configurable via `AIDG_API_V1_PREFIX`).

All endpoints return JSON. Errors follow the standard shape
`{"detail": string | object}`. Interactive docs (`/docs`) are exposed in
`AIDG_DEBUG=true` only.

## Authentication

Token-based auth. Login returns an **access token** (short-lived JWT, default
30 min) plus a **refresh token** (opaque, one-time use, default 7 days).
Send `Authorization: Bearer <access_token>` on protected routes.

| Method | Path                          | Description |
|--------|-------------------------------|-------------|
| POST   | `/auth/login`                 | Password login → `{access_token, refresh_token}` |
| POST   | `/auth/refresh`               | Rotate a refresh token → new pair (old token invalidated) |
| POST   | `/auth/logout`                | Revoke a refresh token (204) |
| POST   | `/auth/change-password`       | Change own password (204) |
| POST   | `/auth/oidc/token`            | Exchange an OIDC ID token (Microsoft Entra ID) for a session — enabled when `AIDG_OIDC_ENABLED=true` |
| GET    | `/auth/me`                    | Current user profile + roles/permissions |

### Login request

```json
{ "username": "admin", "password": "admin1234!" }
```

### Login response

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<opaque>",
  "token_type": "bearer",
  "expires_in": 1800
}
```

## RBAC model

- **Permission** — granular capability string (`kb:read`, `user:write`, …).
- **Role** — a named set of permissions (`staff`, `power_user`, `org_admin`,
  `approver`, `auditor`, `system_admin`).
- **User ↔ Role** assignments are optionally **org-scoped** (scoped roles apply
  only within an organization/service unit).
- Superusers bypass scoping checks and see all data.

Every protected endpoint enforces `require_permission(<code>)`. Unauthorized
(no/invalid token) → `401`; authenticated but missing permission → `403`.

## Endpoints

### Users

| Method | Path            | Permission | Description |
|--------|-----------------|------------|-------------|
| GET    | `/users`        | `user:read` | List users (`?q=&org_id=`) |
| POST   | `/users`        | `user:write`| Create user |
| GET    | `/users/{id}`   | `user:read` | Get user |
| PATCH  | `/users/{id}`   | `user:write`| Update user (deactivate, rename, roles, …) |

### Roles & permissions

| Method | Path             | Permission  | Description |
|--------|------------------|-------------|-------------|
| GET    | `/roles`         | `user:write`| List roles with permission codes |
| GET    | `/permissions`   | `user:write`| List permission catalog |
| POST   | `/roles/assign`  | `user:write`| Assign a role to a user (optional org scope) |
| POST   | `/roles/revoke`  | `user:write`| Revoke a role from a user |

### Groups

| Method | Path                              | Permission   | Description |
|--------|-----------------------------------|--------------|-------------|
| GET    | `/groups`                         | `group:read` | List groups (org-scoped for non-superusers) |
| POST   | `/groups`                         | `group:write`| Create group |
| DELETE | `/groups/{id}`                    | `group:write`| Delete group |
| POST   | `/groups/{id}/members`            | `group:write`| Add member |
| DELETE | `/groups/{id}/members/{userId}`   | `group:write`| Remove member |

### Organizations (tenants / service units)

| Method | Path                 | Permission | Description |
|--------|----------------------|------------|-------------|
| GET    | `/organizations`     | `org:read` | List organizations |
| POST   | `/organizations`     | `org:write`| Create organization |
| PATCH  | `/organizations/{id}`| `org:write`| Update organization |

### Audit logs

| Method | Path                   | Permission   | Description |
|--------|------------------------|--------------|-------------|
| GET    | `/audit-logs`          | `audit:read` | Paginated query (`?action=&actor_email=&org_id=&page=&size=`) |
| GET    | `/audit-logs/export`   | `audit:export` | CSV export |

### Health

| Method | Path       | Description |
|--------|------------|-------------|
| GET    | `/healthz` | Liveness → `{"status":"ok"}` |
| GET    | `/readyz`  | Readiness (db + redis) → 200 / 503 with per-check detail |

## Knowledge Bases & Documents (Epic 2)

All knowledge endpoints are permission-scoped: non-superusers only see the
knowledge bases of their own organisation. `kb:read` / `kb:write` / `kb:delete`
govern KB operations; `document:read` / `document:write` govern documents.

### Knowledge bases

| Method | Path                          | Permission   | Description |
|--------|-------------------------------|--------------|-------------|
| GET    | `/knowledge-bases`            | `kb:read`    | List KBs (org-scoped) |
| POST   | `/knowledge-bases`            | `kb:write`   | Create KB — body `{name, description?, is_active?, org_id?}` (`org_id` superuser-only) |
| GET    | `/knowledge-bases/{kbId}`     | `kb:read`    | Get KB |
| PATCH  | `/knowledge-bases/{kbId}`     | `kb:write`   | Update KB (`name`, `description`, `is_active`) |
| DELETE | `/knowledge-bases/{kbId}`     | `kb:delete`  | Delete KB + documents + chunks (204) |

### Documents

| Method | Path                                      | Permission      | Description |
|--------|-------------------------------------------|-----------------|-------------|
| GET    | `/knowledge-bases/{kbId}/documents`       | `document:read` | List documents (`?status=`) |
| POST   | `/knowledge-bases/{kbId}/documents`       | `document:write`| Upload (multipart `file`, optional `title`, `document_id` for new version, `process_sync`) |
| GET    | `/documents/{docId}`                      | `document:read` | Get document (+ `chunk_count`, `error_message`) |
| PATCH  | `/documents/{docId}`                      | `document:write`| Update title / `is_approved` (sets `approved_at`) |
| POST   | `/documents/{docId}/reindex`              | `document:write`| Re-run indexing for latest version (`?process_sync=true`) |
| GET    | `/documents/{docId}/versions`             | `document:read` | Version history (newest first) |
| GET    | `/documents/{docId}/chunks`               | `document:read` | Chunks of the current version (with `metadata.page`) |

**Upload request** (multipart/form-data):

```
file          : required  — the binary file
title         : optional  — display title (defaults to filename)
document_id   : optional  — upload a new version of this document
process_sync  : optional  — "true" processes+indexes inline; default queues a job
```

**Upload response** (`DocumentRead`):

```json
{
  "id": "<uuid>",
  "kb_id": "<uuid>",
  "title": "長者服務中心指引",
  "filename": "service_guide.txt",
  "status": "indexed",
  "version_number": 1,
  "is_approved": false,
  "chunk_count": 6,
  "error_message": null,
  "created_at": "…"
}
```

`status` values: `draft` → `processing` → `indexed` | `failed`.

### Retrieval (RAG foundation)

| Method | Path                | Permission | Description |
|--------|---------------------|------------|-------------|
| POST   | `/retrieval/search` | `kb:read`  | Hybrid (vector + keyword) search across KBs within the caller's permission scope |

**Request:**

```json
{
  "query": "長者申請資格門檻",
  "kb_ids": ["<uuid>", "<uuid>"],
  "top_k": 10,
  "min_score": 0.0
}
```

- `kb_ids` optional — omitting it searches all visible KBs.
- Requesting a KB outside your org → `403`; a non-existent id → `400`.

**Response** — ranked results, best first:

```json
[
  {
    "chunk_id": "<uuid>",
    "document_id": "<uuid>",
    "kb_id": "<uuid>",
    "document_title": "長者服務中心指引2025",
    "content": "第三章 申請資格\n申請人須年滿六十歲…",
    "page": 1,
    "score": 0.4181,
    "vector_score": 0.71,
    "keyword_score": 0.22
  }
]
```

`score` is an RRF-weighted blend (`0.6 × vector + 0.4 × keyword`) with negative
vector similarity clamped to zero. Retrieval attempts are written to the audit
log (`retrieval.search`).

Every retrieval and generation is audit-logged with the query, scope, model and
result count (see `audit:read`).

## Pagination

`/audit-logs` returns:

```json
{ "items": [...], "total": 123, "page": 1, "size": 20 }
```

## Upcoming modules (Epics 3–7)

AI assistants, chat/SSE answer generation, document generation, meetings/STT
endpoints, workflows, and integration APIs will be added under the same
`/api/v1` prefix with identical auth/permission conventions.
