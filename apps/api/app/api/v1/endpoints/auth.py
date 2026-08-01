"""Authentication endpoints: local login, refresh, logout, OIDC, profile."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request, status
from sqlalchemy import update

from app.core import security
from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import bad_request
from app.models.refresh_token import RefreshToken
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    OIDCExchangeRequest,
    RefreshRequest,
    TokenPair,
)
from app.schemas.user import UserRead
from app.services import auth_service
from app.services.audit_service import write_audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, request: Request, db: DbSession) -> TokenPair:
    user = await auth_service.authenticate_local(db, payload.username, payload.password)
    if user is None:
        await write_audit(
            db,
            action=auth_service.AUDIT_LOGIN_FAILED,
            request=request,
            detail=f"Failed login for '{payload.username}'",
        )
        await db.commit()
        raise bad_request("Invalid credentials")
    return TokenPair(**await auth_service.issue_token_pair(db, user, request))


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, request: Request, db: DbSession) -> TokenPair:
    return TokenPair(**await auth_service.rotate_refresh_token(db, payload.refresh_token, request))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest, request: Request, db: DbSession) -> None:
    await auth_service.revoke_refresh_token(db, payload.refresh_token, request)


@router.post("/oidc/token", response_model=TokenPair)
async def oidc_token(payload: OIDCExchangeRequest, request: Request, db: DbSession) -> TokenPair:
    return TokenPair(**await auth_service.exchange_oidc_token(db, payload.id_token, request))


@router.get("/me", response_model=UserRead)
async def me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    if not current_user.password_hash or not security.verify_password(
        payload.old_password, current_user.password_hash
    ):
        raise bad_request("Current password is incorrect")
    current_user.password_hash = security.hash_password(payload.new_password)
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    await write_audit(
        db,
        action="auth.change_password",
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        org_id=current_user.org_id,
        request=request,
    )
    await db.commit()
