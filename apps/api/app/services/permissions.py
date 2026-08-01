"""Permission catalog and default role definitions (seed source of truth)."""

from __future__ import annotations

USER_READ = "user:read"
USER_WRITE = "user:write"
ORG_READ = "org:read"
ORG_WRITE = "org:write"
GROUP_READ = "group:read"
GROUP_WRITE = "group:write"
KB_READ = "kb:read"
KB_WRITE = "kb:write"
KB_DELETE = "kb:delete"
DOCUMENT_READ = "document:read"
DOCUMENT_WRITE = "document:write"
DOCUMENT_DELETE = "document:delete"
ASSISTANT_READ = "assistant:read"
ASSISTANT_WRITE = "assistant:write"
CHAT_USE = "chat:use"
GENERATION_CREATE = "generation:create"
GENERATION_APPROVE = "generation:approve"
MEETING_READ = "meeting:read"
MEETING_WRITE = "meeting:write"
WORKFLOW_MANAGE = "workflow:manage"
MODEL_MANAGE = "model:manage"
AUDIT_READ = "audit:read"
AUDIT_EXPORT = "audit:export"
ANALYTICS_READ = "analytics:read"

PERMISSION_CATALOG: tuple[tuple[str, str], ...] = (
    (USER_READ, "View users"),
    (USER_WRITE, "Create / update / deactivate users"),
    (ORG_READ, "View organizations"),
    (ORG_WRITE, "Create / update organizations"),
    (GROUP_READ, "View groups"),
    (GROUP_WRITE, "Manage groups and members"),
    (KB_READ, "View and query knowledge bases"),
    (KB_WRITE, "Create / update knowledge bases and documents"),
    (KB_DELETE, "Delete knowledge bases"),
    (DOCUMENT_READ, "Read documents"),
    (DOCUMENT_WRITE, "Upload / update documents"),
    (DOCUMENT_DELETE, "Delete documents"),
    (ASSISTANT_READ, "View AI assistants"),
    (ASSISTANT_WRITE, "Create / configure AI assistants"),
    (CHAT_USE, "Use chat assistants"),
    (GENERATION_CREATE, "Create document generation requests"),
    (GENERATION_APPROVE, "Approve / reject AI-generated documents"),
    (MEETING_READ, "Read meeting transcripts and summaries"),
    (MEETING_WRITE, "Upload / manage meeting recordings"),
    (WORKFLOW_MANAGE, "Design and manage workflows"),
    (MODEL_MANAGE, "Manage models, quotas and token usage"),
    (AUDIT_READ, "View audit logs"),
    (AUDIT_EXPORT, "Export audit logs"),
    (ANALYTICS_READ, "View system usage dashboards"),
)

ALL_PERMISSION_CODES: frozenset[str] = frozenset(code for code, _ in PERMISSION_CATALOG)

ROLE_SYSTEM_ADMIN = "system_admin"
ROLE_ORG_ADMIN = "org_admin"
ROLE_POWER_USER = "power_user"
ROLE_STAFF = "staff"
ROLE_APPROVER = "approver"
ROLE_AUDITOR = "auditor"

ROLE_DEFINITIONS: dict[str, set[str]] = {
    ROLE_SYSTEM_ADMIN: set(ALL_PERMISSION_CODES),
    ROLE_ORG_ADMIN: {
        USER_READ,
        USER_WRITE,
        ORG_READ,
        ORG_WRITE,
        GROUP_READ,
        GROUP_WRITE,
        KB_READ,
        KB_WRITE,
        KB_DELETE,
        DOCUMENT_READ,
        DOCUMENT_WRITE,
        DOCUMENT_DELETE,
        ASSISTANT_READ,
        ASSISTANT_WRITE,
        CHAT_USE,
        GENERATION_CREATE,
        GENERATION_APPROVE,
        MEETING_READ,
        MEETING_WRITE,
        WORKFLOW_MANAGE,
        MODEL_MANAGE,
        AUDIT_READ,
        ANALYTICS_READ,
    },
    ROLE_POWER_USER: {
        USER_READ,
        ORG_READ,
        GROUP_READ,
        KB_READ,
        KB_WRITE,
        DOCUMENT_READ,
        DOCUMENT_WRITE,
        ASSISTANT_READ,
        CHAT_USE,
        GENERATION_CREATE,
        MEETING_READ,
        MEETING_WRITE,
        AUDIT_READ,
    },
    ROLE_STAFF: {
        ORG_READ,
        KB_READ,
        DOCUMENT_READ,
        ASSISTANT_READ,
        CHAT_USE,
        GENERATION_CREATE,
        MEETING_READ,
    },
    ROLE_APPROVER: {KB_READ, DOCUMENT_READ, GENERATION_APPROVE, CHAT_USE},
    ROLE_AUDITOR: {AUDIT_READ, AUDIT_EXPORT, KB_READ, DOCUMENT_READ, ORG_READ},
}
