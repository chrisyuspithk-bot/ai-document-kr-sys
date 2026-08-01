"""Minimal OIDC ID-token verification (Microsoft Entra ID ready).

The frontend (NextAuth) performs the browser redirect flows; this backend
endpoint verifies the resulting ID token using the issuer's JWKS.
"""

from __future__ import annotations

import httpx
import jwt
from jwt import PyJWKClient

from app.core.config import Settings


class OIDCProvider:
    def __init__(self, settings: Settings) -> None:
        if not settings.oidc_issuer:
            raise ValueError("AIDG_OIDC_ISSUER is required when OIDC is enabled")
        self.issuer = settings.oidc_issuer.rstrip("/")
        self.audience = settings.oidc_audience or settings.oidc_client_id
        self._jwks_client: PyJWKClient | None = None

    async def _discover_jwks_uri(self) -> str:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self.issuer}/.well-known/openid-configuration")
            resp.raise_for_status()
            return resp.json()["jwks_uri"]

    async def verify_id_token(self, id_token: str) -> dict:
        if not self.audience:
            raise ValueError("AIDG_OIDC_CLIENT_ID (or AIDG_OIDC_AUDIENCE) is required")
        if self._jwks_client is None:
            jwks_uri = await self._discover_jwks_uri()
            self._jwks_client = PyJWKClient(jwks_uri)
        signing_key = self._jwks_client.get_signing_key_from_jwt(id_token)
        return jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=self.audience,
            issuer=self.issuer,
            options={"require": ["exp", "iss", "aud"]},
        )
