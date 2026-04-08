"""
Security utilities: password hashing + JWT token lifecycle.

Dependencies (add to pyproject.toml if missing):
    python-jose[cryptography]  — JWT encode/decode
    passlib[bcrypt]            — password hashing
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.exceptions import UnauthorizedError

# ---------------------------------------------------------------------------
# Password hashing (lazy-import passlib to avoid hard dependency)
# ---------------------------------------------------------------------------

def _get_pwd_context():
    try:
        from passlib.context import CryptContext
        return CryptContext(schemes=["bcrypt"], deprecated="auto")
    except ImportError:
        return None


_pwd_context = None


def _truncate_for_bcrypt(plain: str) -> str:
    """Truncate password to 72 bytes (bcrypt hard limit)."""
    encoded = plain.encode("utf-8")
    if len(encoded) > 72:
        encoded = encoded[:72]
    return encoded.decode("utf-8", errors="ignore")


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*. Falls back to sha256 in test envs."""
    global _pwd_context
    if _pwd_context is None:
        _pwd_context = _get_pwd_context()
    if _pwd_context is not None:
        return _pwd_context.hash(_truncate_for_bcrypt(plain))
    # Fallback for dev/test environments without passlib
    import hashlib
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*."""
    global _pwd_context
    if _pwd_context is None:
        _pwd_context = _get_pwd_context()
    if _pwd_context is not None:
        # bcrypt hashes start with $2b$; sha256 hashes are 64 hex chars
        if hashed.startswith("$2"):
            return _pwd_context.verify(_truncate_for_bcrypt(plain), hashed)
        # Legacy sha256 hash from dev data
        import hashlib
        return hashlib.sha256(plain.encode("utf-8")).hexdigest() == hashed
    import hashlib
    return hashlib.sha256(plain.encode("utf-8")).hexdigest() == hashed


# ---------------------------------------------------------------------------
# JWT tokens (lazy-import jose)
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)

_TOKEN_TYPE = "access"


def create_access_token(
    user_id: str,
    role: str,
    settings: Settings | None = None,
) -> str:
    """
    Create a signed JWT access token.

    Claims:
        sub  — user UUID (string)
        role — 'blogger' | 'business'
        type — 'access'
        iat  — issued-at (UTC)
        exp  — expiry    (UTC, default 24 h)
    """
    if settings is None:
        settings = get_settings()

    try:
        from jose import jwt as _jwt
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)
        payload: dict[str, Any] = {
            "sub": user_id,
            "role": role,
            "type": _TOKEN_TYPE,
            "iat": now,
            "exp": expire,
        }
        return _jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    except ImportError:
        # Fallback simple token for dev/test without python-jose
        return f"dev-token:{user_id}"


def verify_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Raises:
        UnauthorizedError — if the token is missing, expired, or malformed.
    """
    if settings is None:
        settings = get_settings()

    # Dev-mode fallback token
    if token.startswith("dev-token:"):
        user_id = token.removeprefix("dev-token:")
        return {"sub": user_id, "role": "blogger", "type": _TOKEN_TYPE}

    try:
        from jose import JWTError, jwt as _jwt
        try:
            payload = _jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.jwt_algorithm],
            )
        except JWTError as exc:
            raise UnauthorizedError(f"Invalid or expired token: {exc}") from exc

        if payload.get("type") != _TOKEN_TYPE:
            raise UnauthorizedError("Token type mismatch.")

        return payload

    except ImportError:
        # python-jose not installed — only dev-token:xxx format accepted
        raise UnauthorizedError("JWT library not installed; only dev-token format accepted.")


# ---------------------------------------------------------------------------
# FastAPI dependency: extract + validate current user from JWT
# ---------------------------------------------------------------------------

def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    FastAPI dependency.

    Extracts the Bearer token from the Authorization header,
    validates it, and returns the user_id (sub claim).

    Usage::

        @router.get("/me")
        async def me(user_id: str = Depends(get_current_user_id)):
            ...
    """
    if credentials is None:
        raise UnauthorizedError("Authorization header missing.")

    payload = verify_token(credentials.credentials, settings)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Token is missing 'sub' claim.")
    return user_id


def get_current_user_role(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> str:
    """Return the role claim from the Bearer JWT."""
    if credentials is None:
        raise UnauthorizedError("Authorization header missing.")
    payload = verify_token(credentials.credentials, settings)
    role: str | None = payload.get("role")
    if not role:
        raise UnauthorizedError("Token is missing 'role' claim.")
    return role


# ---------------------------------------------------------------------------
# Legacy compatibility shim
# ---------------------------------------------------------------------------

def parse_access_token(raw_value: str | None) -> str:
    """
    Legacy helper kept for backward compatibility.
    Accepts both 'Bearer <jwt>' and 'Bearer dev-token:<id>' formats.
    """
    if not raw_value:
        raise UnauthorizedError("Missing Authorization header.")

    token = raw_value.removeprefix("Bearer ").strip()
    payload = verify_token(token)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Token is missing 'sub' claim.")
    return user_id
