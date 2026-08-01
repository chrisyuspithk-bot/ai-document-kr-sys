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
    KB_GROUP_PERM_APPROVE,
    KB_GROUP_PERM_READ,
    KB_GROUP_PERM_WRITE,
    Document,
    DocumentChunk,
    DocumentVersion,
    KnowledgeBase,
    KnowledgeBaseGroupPermission,
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
    "KB_GROUP_PERM_APPROVE",
    "KB_GROUP_PERM_READ",
    "KB_GROUP_PERM_WRITE",
    "KnowledgeBase",
    "KnowledgeBaseGroupPermission",
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
