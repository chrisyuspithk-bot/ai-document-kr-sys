"""Import all models so that ``Base.metadata`` is complete (Alembic autogenerate)."""

from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.knowledge import (
    DOC_STATUS_ARCHIVED,
    DOC_STATUS_DRAFT,
    DOC_STATUS_FAILED,
    DOC_STATUS_INDEXED,
    DOC_STATUS_PROCESSING,
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_STATUS_SUCCEEDED,
    Document,
    DocumentChunk,
    DocumentVersion,
    KnowledgeBase,
    ProcessingJob,
)
from app.models.organization import Organization
from app.models.rbac import (
    SCOPE_GLOBAL,
    SCOPE_ORG,
    Group,
    Permission,
    Role,
    RolePermission,
    UserGroup,
    UserRole,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User

__all__ = [
    "AuditLog",
    "Base",
    "DOC_STATUS_ARCHIVED",
    "DOC_STATUS_DRAFT",
    "DOC_STATUS_FAILED",
    "DOC_STATUS_INDEXED",
    "DOC_STATUS_PROCESSING",
    "Document",
    "DocumentChunk",
    "DocumentVersion",
    "Group",
    "JOB_STATUS_FAILED",
    "JOB_STATUS_PENDING",
    "JOB_STATUS_RUNNING",
    "JOB_STATUS_SUCCEEDED",
    "KnowledgeBase",
    "Organization",
    "Permission",
    "ProcessingJob",
    "RefreshToken",
    "Role",
    "RolePermission",
    "SCOPE_GLOBAL",
    "SCOPE_ORG",
    "User",
    "UserGroup",
    "UserRole",
]
