"""
FastAPI dependency providers.

Architecture note
-----------------
During the transition from in-memory to PostgreSQL the app runs in a
"dual-mode" setup:

  - Synchronous in-memory services (AuthService, MatchService, …)
    are still used for the main request flow.

  - Async DB session (get_db_session) is used by new DB-backed
    repositories (db_repository.py files) injected into specific async
    endpoints (e.g. the discovery feed).

Once the full migration is complete the in-memory services will be
replaced and this file will be simplified.
"""
from __future__ import annotations

from fastapi import Depends, Request

from app.core.container import AppContainer
from app.core.exceptions import NotFoundError, UnauthorizedError
from app.core.security import get_current_user_id as _jwt_extract_user_id


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------

def get_container(request: Request) -> AppContainer:
    """Return the app-level service container from request state."""
    return request.app.state.container


# ---------------------------------------------------------------------------
# Current user (JWT → validated user)
# ---------------------------------------------------------------------------

async def get_current_user_id(
    user_id: str = Depends(_jwt_extract_user_id),
    container: AppContainer = Depends(get_container),
) -> str:
    """
    Validate the JWT-decoded user_id against the active store.

    Raises UnauthorizedError if the user does not exist or is inactive.
    Returns the validated user_id string.
    """
    try:
        user = container.auth_service.get_user(user_id)
    except NotFoundError:
        raise UnauthorizedError("User not found.")
    if not user.is_active:
        raise UnauthorizedError("User account is inactive.")
    return user_id


# ---------------------------------------------------------------------------
# DB session (lazy import to avoid hard SQLAlchemy dependency at import time)
# ---------------------------------------------------------------------------

async def get_db_session():
    """
    FastAPI dependency: async SQLAlchemy session.

    Lazily imports database.session to avoid failing in environments
    where asyncpg/sqlalchemy are not yet installed.
    """
    from app.database.session import get_db_session as _get_db
    async for session in _get_db():
        yield session


__all__ = [
    "get_container",
    "get_current_user_id",
    "get_db_session",
]
