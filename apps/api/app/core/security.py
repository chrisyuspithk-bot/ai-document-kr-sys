"""Password hashing and JWT token helpers.

Local auth uses argon2id password hashing and short-lived HS256 access tokens
with rotating refresh tokens (refresh token hashes stored in the database).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status
from pwdlib import PasswordHash

from app.core.config import get_settings

_password_hasher = PasswordHash.recommended()

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


# --- Passwords -----------------------------------------------------------------


def hash_password(plain: str) -> str:
    return _password_hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _password_hasher.verify(plain, hashed)
    except Exception:
        return False


# --- Tokens --------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def create_access_token(subject: str, extra_claims: dict | None = None) -> str:
    settings = get_settings()
    payload: dict = {
        "sub": subject,
        "iat": _now(),
        "exp": _now() + timedelta(minutes=settings.access_token_expire_minutes),
        "jti": str(uuid.uuid4()),
        "type": TOKEN_TYPE_ACCESS,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> tuple[str, uuid.UUID, datetime]:
    """Returns ``(token, jti, expires_at)``. The caller persists the token hash."""
    settings = get_settings()
    expires_at = _now() + timedelta(days=settings.refresh_token_expire_days)
    jti = uuid.uuid4()
    payload = {
        "sub": subject,
        "iat": _now(),
        "exp": expires_at,
        "jti": str(jti),
        "type": TOKEN_TYPE_REFRESH,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def decode_token(token: str, expected_type: str | None = None) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if expected_type is not None and payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def token_sha256(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
