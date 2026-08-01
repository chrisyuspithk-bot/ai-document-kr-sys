"""Import all models so that ``Base.metadata`` is complete (Alembic autogenerate)."""

from app.models.audit_log import AuditLog
from app.models.base import Base
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
    "Group",
    "Organization",
    "Permission",
    "RefreshToken",
    "Role",
    "RolePermission",
    "SCOPE_GLOBAL",
    "SCOPE_ORG",
    "User",
    "UserGroup",
    "UserRole",
]
