"""API key generation and validation service."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import ApiKey

_KEY_PREFIX = "ak_"
_RAW_LENGTH = 48


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key pair.

    Returns (raw_key, key_prefix, key_hash).
    The raw_key is shown to the user once; the hash is stored.
    """
    raw = _KEY_PREFIX + secrets.token_urlsafe(_RAW_LENGTH)
    prefix = raw[: len(_KEY_PREFIX) + 6]
    key_hash = _hash_key(raw)
    return raw, prefix, key_hash


def verify_api_key(raw_key: str, key_hash: str) -> bool:
    """Constant-time comparison of a raw key against a stored hash."""
    return hmac.compare_digest(_hash_key(raw_key), key_hash)


async def create_api_key(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    name: str,
    created_by: uuid.UUID,
    permissions: list[str] | None = None,
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    """Create and persist a new API key. Returns (key_record, raw_key)."""
    raw, prefix, key_hash = generate_api_key()

    key = ApiKey(
        org_id=org_id,
        name=name,
        key_prefix=prefix,
        key_hash=key_hash,
        created_by=created_by,
        permissions=permissions,
        expires_at=expires_at,
    )
    session.add(key)
    await session.commit()
    await session.refresh(key)
    return key, raw


async def get_api_key_by_raw(
    session: AsyncSession,
    raw_key: str,
) -> ApiKey | None:
    """Look up an API key by its raw value.

    Since we store only hashes, we extract the prefix, find candidate keys,
    then do constant-time comparison.
    """
    prefix = raw_key[: len(_KEY_PREFIX) + 6]
    stmt = (
        select(ApiKey)
        .where(ApiKey.key_prefix == prefix, ApiKey.is_active.is_(True))
    )
    result = await session.execute(stmt)
    for key in result.scalars():
        if verify_api_key(raw_key, key.key_hash):
            # Check expiry
            if key.expires_at:
                expires = key.expires_at
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=UTC)
                if expires < datetime.now(tz=UTC):
                    return None
            # Update last_used_at
            await session.execute(
                update(ApiKey)
                .where(ApiKey.id == key.id)
                .values(last_used_at=func.now())
            )
            await session.commit()
            return key
    return None


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
