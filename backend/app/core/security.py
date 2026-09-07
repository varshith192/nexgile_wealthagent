"""Password hashing and JWT issue/verify.

Hashing uses PBKDF2-HMAC-SHA256 from the standard library so the backend has no
native build dependency. Supabase Auth handles credentials in the hosted
configuration; this path serves local development and the demo accounts.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import settings
from app.core.errors import UnauthorizedError

PBKDF2_ROUNDS = 240_000
SALT_BYTES = 16
ALGORITHM_TAG = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return f"{ALGORITHM_TAG}${PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        tag, rounds, salt_hex, digest_hex = encoded.split("$")
        if tag != ALGORITHM_TAG:
            return False
        expected = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(expected.hex(), digest_hex)


def create_access_token(
    *, subject: str, role: str, email: str, extra: dict[str, Any] | None = None, remember: bool = False
) -> tuple[str, datetime]:
    ttl = settings.remember_me_ttl_minutes if remember else settings.access_token_ttl_minutes
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl)
    payload: dict[str, Any] = {
        "sub": subject,
        "email": email,
        "role": role,
        "iss": "nexgile-wealthagent",
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int(expires_at.timestamp()),
        **(extra or {}),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_token(token: str) -> dict[str, Any]:
    """Verify a token issued by this API, or by Supabase Auth when configured."""
    secrets_to_try = [settings.jwt_secret]
    if settings.auth_provider == "supabase" and settings.supabase_jwt_secret:
        # Supabase signs access tokens with the project JWT secret.
        secrets_to_try.insert(0, settings.supabase_jwt_secret)

    last_error: Exception | None = None
    for secret in secrets_to_try:
        try:
            return jwt.decode(
                token,
                secret,
                algorithms=[settings.jwt_algorithm],
                options={"verify_aud": False},
            )
        except jwt.ExpiredSignatureError as exc:
            raise UnauthorizedError("Your session has expired. Please sign in again.", code="token_expired") from exc
        except jwt.InvalidTokenError as exc:
            last_error = exc
            continue

    raise UnauthorizedError("Could not validate credentials.", code="invalid_token") from last_error
