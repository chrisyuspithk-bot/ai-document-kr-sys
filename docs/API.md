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

## Pagination

`/audit-logs` returns:

```json
{ "items": [...], "total": 123, "page": 1, "size": 20 }
```

## Upcoming modules (Epics 2–7)

Knowledge bases, documents, assistants, chat/SSE, generation, meetings/STT,
workflows, and integration APIs will be added under the same `/api/v1` prefix
with identical auth/permission conventions.
