import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from fastapi import HTTPException, status
from joserfc import jwt
from joserfc.jwk import KeySet
from joserfc.jws import extract_compact

from src.common.application.logging import get_logger
from src.common.domain.entities.auth.google_login import GoogleAuthTokens, GoogleUser
from src.common.settings import settings

logger = get_logger(__name__)


async def get_google_tokens(code: str) -> GoogleAuthTokens:
    token_data = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "code": code,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(settings.GOOGLE_TOKEN_URL, data=token_data)
        try:
            response.raise_for_status()  # Lanza una excepción para errores HTTP
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error al obtener tokens de Google: {e.response.text}"
            )

        token_response = response.json()
        access_token = token_response.get("access_token")
        id_token = token_response.get("id_token")

        if not access_token or not id_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No se pudieron obtener tokens de Google válidos."
            )
    return GoogleAuthTokens(access_token=access_token, id_token=id_token)


# Google rotates its signing keys roughly daily and publishes them well in advance.
GOOGLE_JWKS_TTL_SECONDS = 60 * 60
GOOGLE_ISSUERS: list[str | int] = ["accounts.google.com", "https://accounts.google.com"]


@dataclass
class _JwksCache:
    key_set: KeySet | None = None
    fetched_at: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_jwks_cache = _JwksCache()


def clear_google_jwks_cache() -> None:
    _jwks_cache.key_set = None
    _jwks_cache.fetched_at = 0.0


async def _fetch_google_jwks() -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(settings.GOOGLE_CERTS_URL, timeout=5)
        response.raise_for_status()
        return response.json()


async def get_google_certs(force_refresh: bool = False) -> KeySet:
    async with _jwks_cache.lock:
        expired = time.monotonic() - _jwks_cache.fetched_at >= GOOGLE_JWKS_TTL_SECONDS
        if force_refresh or expired or _jwks_cache.key_set is None:
            _jwks_cache.key_set = KeySet.import_key_set(await _fetch_google_jwks())  # ty: ignore[invalid-argument-type]
            _jwks_cache.fetched_at = time.monotonic()
        return _jwks_cache.key_set


async def _decode_google_id_token(id_token: str) -> dict[str, Any]:
    if not settings.GOOGLE_CLIENT_ID:
        raise ValueError("GOOGLE_CLIENT_ID is not configured")
    key_set = await get_google_certs()
    kid = extract_compact(id_token.encode()).headers().get("kid")
    if kid and not any(key.kid == kid for key in key_set.keys):
        # Unknown key id: Google may have rotated before our cache expired.
        key_set = await get_google_certs(force_refresh=True)
    token = jwt.decode(id_token, key=key_set, algorithms=["RS256"])
    jwt.JWTClaimsRegistry(
        iss={"essential": True, "values": GOOGLE_ISSUERS},
        aud={"essential": True, "value": settings.GOOGLE_CLIENT_ID},
        exp={"essential": True},
    ).validate(token.claims)
    return token.claims


async def verify_google_id_token(id_token: str) -> GoogleUser | None:
    try:
        claims = await _decode_google_id_token(id_token)

        user_email = claims.get("email")
        user_given_name = claims.get("given_name", user_email)
        user_family_name = claims.get("family_name")
        user_picture = claims.get("picture")

        if not user_email:
            logger.error(
                "google.auth.token.invalid",
                reason="email_missing",
                error="ID Token does not contain email",
            )
            return None

        return GoogleUser(
            email=user_email, given_name=user_given_name, family_name=user_family_name, picture=user_picture
        )

    except Exception as e:
        logger.error(
            "google.auth.token.validation_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        return None
