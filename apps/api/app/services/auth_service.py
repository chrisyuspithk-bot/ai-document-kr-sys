"""Authentication flows: local login, refresh rotation, logout, OIDC exchange."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.core.exceptions import bad_request, unauthorized
from app.models.organization import Organization
from app.models.rbac import Role, UserRole
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.audit_service import write_audit
from app.services.oidc_provider import OIDCProvider
from app.services.permissions import ROLE_STAFF

AUDIT_LOGIN = "auth.login"
AUDIT_LOGIN_FAILED = "auth.login_failed"
AUDIT_REFRESH = "auth.refresh"
AUDIT_LOGOUT = "auth.logout"
AUDIT_OIDC_LOGIN = "auth.oidc_login"


async def authenticate_local(
    session: AsyncSession, username_or_email: str, password: str
) -> User | None:
    result = await session.execute(
        select(User).where((User.username == username_or_email) | (User.email == username_or_email))
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or not user.password_hash:
        return None
    if not security.verify_password(password, user.password_hash):
        return None
    return user


def _token_payload(user: User) -> dict:
    return {"org": str(user.org_id) if user.org_id else None, "locale": user.locale}


async def issue_token_pair(session: AsyncSession, user: User, request: Request | None) -> dict:
    settings = get_settings()
    access_token = security.create_access_token(str(user.id), _token_payload(user))
    refresh_token, jti, expires_at = security.create_refresh_token(str(user.id))
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=security.token_sha256(refresh_token),
            expires_at=expires_at,
        )
    )
    user.last_login_at = datetime.now(UTC)
    await write_audit(
        session,
        action=AUDIT_LOGIN,
        actor_user_id=user.id,
        actor_email=user.email,
        org_id=user.org_id,
        request=request,
    )
    await session.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


async def rotate_refresh_token(
    session: AsyncSession, refresh_token: str, request: Request | None
) -> dict:
    security.decode_token(refresh_token, expected_type="refresh")
    token_hash = security.token_sha256(refresh_token)

    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    stored = result.scalar_one_or_none()
    if stored is None or stored.revoked_at is not None:
        raise unauthorized("Refresh token has been revoked")
    if stored.expires_at.tzinfo is None:
        stored.expires_at = stored.expires_at.replace(tzinfo=UTC)
    if stored.expires_at < datetime.now(UTC):
        raise unauthorized("Refresh token has expired")

    user = await session.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise unauthorized("User is not active")

    stored.revoked_at = datetime.now(UTC)
    new_access = security.create_access_token(str(user.id), _token_payload(user))
    new_refresh, jti, expires_at = security.create_refresh_token(str(user.id))
    stored.replaced_by = jti
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=security.token_sha256(new_refresh),
            expires_at=expires_at,
        )
    )
    await write_audit(
        session,
        action=AUDIT_REFRESH,
        actor_user_id=user.id,
        actor_email=user.email,
        org_id=user.org_id,
        request=request,
    )
    await session.commit()
    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": get_settings().access_token_expire_minutes * 60,
    }


async def revoke_refresh_token(
    session: AsyncSession, refresh_token: str, request: Request | None
) -> None:
    security.decode_token(refresh_token, expected_type="refresh")
    token_hash = security.token_sha256(refresh_token)
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    stored = result.scalar_one_or_none()
    if stored is None or stored.revoked_at is not None:
        return
    stored.revoked_at = datetime.now(UTC)
    user = await session.get(User, stored.user_id)
    await write_audit(
        session,
        action=AUDIT_LOGOUT,
        actor_user_id=stored.user_id,
        actor_email=user.email if user else None,
        org_id=user.org_id if user else None,
        request=request,
    )
    await session.commit()


async def _provision_default_role(session: AsyncSession, user: User) -> None:
    result = await session.execute(select(Role).where(Role.name == ROLE_STAFF))
    role = result.scalar_one_or_none()
    if role is None:
        return
    existing = await session.execute(
        select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
    )
    if existing.first() is None:
        session.add(UserRole(user_id=user.id, role_id=role.id, org_id=None))


async def exchange_oidc_token(
    session: AsyncSession, id_token: str, request: Request | None
) -> dict:
    settings = get_settings()
    if not settings.oidc_enabled:
        raise bad_request("OIDC is not enabled")
    provider = OIDCProvider(settings)
    claims = await provider.verify_id_token(id_token)

    sub = str(claims["sub"])
    email = (claims.get("email") or claims.get("preferred_username") or "").lower()

    result = await session.execute(select(User).where(User.oidc_sub == sub))
    user = result.scalar_one_or_none()
    if user is None and email:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is not None and user.oidc_sub is None:
            user.oidc_sub = sub
            user.oidc_issuer = str(claims.get("iss", ""))
            await session.flush()

    if user is None:
        org_result = await session.execute(
            select(Organization).where(Organization.org_type == "root")
        )
        root_org = org_result.scalars().first()
        username_base = (email.split("@")[0] if email else "oidc_user")[:40]
        user = User(
            email=email or f"{sub[:20]}@oidc.local",
            username=f"{username_base}_{sub[:6]}",
            full_name=str(claims.get("name") or claims.get("email") or "OIDC User"),
            oidc_sub=sub,
            oidc_issuer=str(claims.get("iss", "")),
            org_id=root_org.id if root_org else None,
            locale="zh-Hant",
            is_active=True,
        )
        session.add(user)
        await session.flush()
        await _provision_default_role(session, user)

    if user is None or not user.is_active:
        raise unauthorized("User is not active")

    await write_audit(
        session,
        action=AUDIT_OIDC_LOGIN,
        actor_user_id=user.id,
        actor_email=user.email,
        org_id=user.org_id,
        request=request,
        detail=f"OIDC issuer: {claims.get('iss')}",
    )
    return await issue_token_pair(session, user, request)
