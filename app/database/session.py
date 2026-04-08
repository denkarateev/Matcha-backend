"""
Async AND sync SQLAlchemy engine and session factories.

The engines are created lazily on first access so that the module can be
imported in test/dev environments where asyncpg may not yet be installed
(e.g. when running with the default SQLite-based test fixture).

Sync support (psycopg2) is used by the DB-backed repositories that are
called from the synchronous service layer.  The async engine remains
available for Alembic migrations and any future async endpoints.
"""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy import create_engine as _create_sync_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

# ---------------------------------------------------------------------------
# Async engine / factory  (asyncpg)
# ---------------------------------------------------------------------------

_engine: AsyncEngine | None = None
_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return (or create) the singleton async engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.env == "development",
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return (or create) the singleton session factory."""
    global _factory
    if _factory is None:
        _factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency: yields an async session, commits on success,
    rolls back on error, and always closes.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Sync engine / factory  (psycopg2)
# ---------------------------------------------------------------------------

_sync_engine: Engine | None = None
_sync_factory: sessionmaker[Session] | None = None


def _async_url_to_sync(url: str) -> str:
    """Convert ``postgresql+asyncpg://`` to ``postgresql+psycopg2://``."""
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)


def get_sync_engine() -> Engine:
    """Return (or create) the singleton *sync* engine (psycopg2 driver)."""
    global _sync_engine
    if _sync_engine is None:
        settings = get_settings()
        _sync_engine = _create_sync_engine(
            _async_url_to_sync(settings.database_url),
            echo=settings.env == "development",
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
    return _sync_engine


def get_sync_session_factory() -> sessionmaker[Session]:
    """Return (or create) the singleton *sync* session factory."""
    global _sync_factory
    if _sync_factory is None:
        _sync_factory = sessionmaker(
            bind=get_sync_engine(),
            class_=Session,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _sync_factory


# Module-level aliases kept for Alembic env.py compatibility.
# Access via the getter functions above whenever possible.
engine = get_engine
async_session_factory = get_session_factory
