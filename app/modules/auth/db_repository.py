"""
PostgreSQL-backed repositories for User entities.

Maps between the SQLAlchemy ORM model (database.models.User) and the
domain dataclass (modules.auth.domain.models.User) so the service layer
remains database-agnostic.

Two flavours are provided:
  - ``UserRepository``  — async (for future async endpoints / Alembic)
  - ``SyncDBAuthRepository`` — sync, implements the ``AuthRepository``
    Protocol so it can be plugged into the synchronous service layer
    via ``build_container``.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import User as UserORM
from app.modules.auth.domain.models import PlanTier, User, UserRole, VerificationLevel


def _orm_to_domain(row: UserORM) -> User:
    return User(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        role=UserRole(row.role),
        full_name=row.full_name,
        is_active=row.is_active,
        verification_level=VerificationLevel(row.verification_level),
        plan_tier=PlanTier(row.plan_tier),
        offer_credits=row.offer_credits,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _domain_to_orm(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "password_hash": user.password_hash,
        "role": user.role.value,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "verification_level": int(user.verification_level),
        "plan_tier": user.plan_tier.value,
        "offer_credits": user.offer_credits,
    }


# ---------------------------------------------------------------------------
# Async repository (kept for Alembic / future async endpoints)
# ---------------------------------------------------------------------------

class UserRepository:
    """Async SQLAlchemy repository — replaces InMemoryAuthRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user: User) -> User:
        row = UserORM(**_domain_to_orm(user))
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _orm_to_domain(row)

    async def get_by_id(self, user_id: str) -> User | None:
        row = await self._session.get(UserORM, user_id)
        return _orm_to_domain(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserORM).where(UserORM.email == email)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _orm_to_domain(row) if row else None

    async def update(self, user: User) -> User:
        row = await self._session.get(UserORM, user.id)
        if row is None:
            raise ValueError(f"User {user.id!r} not found for update.")
        data = _domain_to_orm(user)
        for key, value in data.items():
            setattr(row, key, value)
        await self._session.flush()
        await self._session.refresh(row)
        return _orm_to_domain(row)


# ---------------------------------------------------------------------------
# Sync repository  — implements AuthRepository Protocol
# ---------------------------------------------------------------------------

class SyncDBAuthRepository:
    """
    Synchronous PostgreSQL repository for User entities.

    Each public method opens its own session (auto-commit on success,
    rollback on error) so it is safe to call from the sync service layer.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sf = session_factory

    # -- AuthRepository Protocol ---------------------------------------------

    def add(self, user: User) -> User:
        with self._sf() as session:
            row = UserORM(**_domain_to_orm(user))
            session.add(row)
            session.flush()
            session.refresh(row)
            result = _orm_to_domain(row)
            session.commit()
            return result

    def get_by_id(self, user_id: str) -> User | None:
        with self._sf() as session:
            row = session.get(UserORM, user_id)
            return _orm_to_domain(row) if row else None

    def get_by_email(self, email: str) -> User | None:
        with self._sf() as session:
            stmt = select(UserORM).where(UserORM.email == email)
            row = session.execute(stmt).scalar_one_or_none()
            return _orm_to_domain(row) if row else None

    def update(self, user: User) -> User:
        with self._sf() as session:
            row = session.get(UserORM, user.id)
            if row is None:
                raise ValueError(f"User {user.id!r} not found for update.")
            data = _domain_to_orm(user)
            for key, value in data.items():
                setattr(row, key, value)
            session.flush()
            session.refresh(row)
            result = _orm_to_domain(row)
            session.commit()
            return result

    def delete(self, user_id: str) -> None:
        with self._sf() as session:
            row = session.get(UserORM, user_id)
            if row is not None:
                session.delete(row)
                session.commit()
