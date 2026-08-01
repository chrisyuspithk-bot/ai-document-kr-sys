"""API v1 router aggregator."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    audit,
    auth,
    groups,
    health,
    organizations,
    rbac,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(rbac.router)
api_router.include_router(groups.router)
api_router.include_router(organizations.router)
api_router.include_router(audit.router)
