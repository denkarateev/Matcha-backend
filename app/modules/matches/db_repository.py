"""
PostgreSQL-backed repositories for Swipe and Match entities.

Two flavours:
  - ``SwipeRepository`` / ``MatchRepository``  — async
  - ``SyncDBMatchRepository`` — sync, implements ``MatchRepository``
    Protocol (combines swipe + match ops) for the synchronous service layer.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import Match as MatchORM
from app.database.models import Swipe as SwipeORM
from app.modules.matches.domain.models import Match, MatchSource, Swipe, SwipeDirection


def _swipe_orm_to_domain(row: SwipeORM) -> Swipe:
    return Swipe(
        id=row.id,
        actor_id=row.swiper_id,
        target_id=row.swiped_id,
        direction=SwipeDirection(row.direction),
        delivered=row.delivered,
        created_at=row.created_at,
    )


def _match_orm_to_domain(row: MatchORM) -> Match:
    return Match(
        id=row.id,
        user_ids=(row.user1_id, row.user2_id),
        source=MatchSource(row.source),
        first_message_by=row.first_message_by,
        created_at=row.created_at,
    )


class SwipeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_swipe(self, swipe: Swipe) -> Swipe:
        row = SwipeORM(
            id=swipe.id,
            swiper_id=swipe.actor_id,
            swiped_id=swipe.target_id,
            direction=swipe.direction.value,
            delivered=swipe.delivered,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _swipe_orm_to_domain(row)

    async def get_latest_swipe(self, actor_id: str, target_id: str) -> Swipe | None:
        stmt = (
            select(SwipeORM)
            .where(SwipeORM.swiper_id == actor_id, SwipeORM.swiped_id == target_id)
            .order_by(SwipeORM.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _swipe_orm_to_domain(row) if row else None

    async def count_pending_positive_swipes(self, actor_id: str) -> int:
        stmt = select(func.count()).where(
            SwipeORM.swiper_id == actor_id,
            SwipeORM.delivered.is_(False),
            SwipeORM.direction.in_(["right", "super"]),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one() or 0

    async def activate_pending_swipes(self, actor_id: str) -> list[Swipe]:
        stmt = select(SwipeORM).where(
            SwipeORM.swiper_id == actor_id,
            SwipeORM.delivered.is_(False),
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        activated: list[Swipe] = []
        for row in rows:
            row.delivered = True
            activated.append(_swipe_orm_to_domain(row))
        await self._session.flush()
        return activated

    async def list_swiped_ids(self, actor_id: str) -> list[str]:
        """Return all target user IDs that actor has swiped (any direction)."""
        stmt = select(SwipeORM.swiped_id).where(SwipeORM.swiper_id == actor_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class MatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_match(self, match: Match) -> Match:
        u1, u2 = sorted(match.user_ids)
        row = MatchORM(
            id=match.id,
            user1_id=u1,
            user2_id=u2,
            source=match.source.value,
            first_message_by=match.first_message_by,
            is_active=True,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _match_orm_to_domain(row)

    async def get_match_by_pair(self, user_a_id: str, user_b_id: str) -> Match | None:
        u1, u2 = sorted((user_a_id, user_b_id))
        stmt = select(MatchORM).where(
            MatchORM.user1_id == u1,
            MatchORM.user2_id == u2,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _match_orm_to_domain(row) if row else None

    async def list_matches_for_user(self, user_id: str) -> list[Match]:
        stmt = (
            select(MatchORM)
            .where(
                or_(MatchORM.user1_id == user_id, MatchORM.user2_id == user_id),
                MatchORM.is_active.is_(True),
            )
            .order_by(MatchORM.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [_match_orm_to_domain(row) for row in result.scalars().all()]


# ---------------------------------------------------------------------------
# Sync repository  — implements MatchRepository Protocol
# (combines swipe + match operations in one class)
# ---------------------------------------------------------------------------

class SyncDBMatchRepository:
    """
    Synchronous PostgreSQL repository for Swipe + Match entities.

    Implements the ``MatchRepository`` Protocol used by ``MatchService``.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sf = session_factory

    # -- Swipe operations ----------------------------------------------------

    def add_swipe(self, swipe: Swipe) -> Swipe:
        with self._sf() as session:
            row = SwipeORM(
                id=swipe.id,
                swiper_id=swipe.actor_id,
                swiped_id=swipe.target_id,
                direction=swipe.direction.value,
                delivered=swipe.delivered,
            )
            session.add(row)
            session.flush()
            session.refresh(row)
            result = _swipe_orm_to_domain(row)
            session.commit()
            return result

    def get_latest_swipe(self, actor_id: str, target_id: str) -> Swipe | None:
        with self._sf() as session:
            stmt = (
                select(SwipeORM)
                .where(SwipeORM.swiper_id == actor_id, SwipeORM.swiped_id == target_id)
                .order_by(SwipeORM.created_at.desc())
                .limit(1)
            )
            row = session.execute(stmt).scalar_one_or_none()
            return _swipe_orm_to_domain(row) if row else None

    def count_pending_positive_swipes(self, actor_id: str) -> int:
        with self._sf() as session:
            stmt = select(func.count()).where(
                SwipeORM.swiper_id == actor_id,
                SwipeORM.delivered.is_(False),
                SwipeORM.direction.in_(["right", "super"]),
            )
            return session.execute(stmt).scalar_one() or 0

    def activate_pending_swipes(self, actor_id: str) -> list[Swipe]:
        with self._sf() as session:
            stmt = select(SwipeORM).where(
                SwipeORM.swiper_id == actor_id,
                SwipeORM.delivered.is_(False),
            )
            rows = session.execute(stmt).scalars().all()
            activated: list[Swipe] = []
            for row in rows:
                row.delivered = True
                activated.append(_swipe_orm_to_domain(row))
            session.commit()
            return activated

    # -- Match operations ----------------------------------------------------

    def add_match(self, match: Match) -> Match:
        with self._sf() as session:
            u1, u2 = sorted(match.user_ids)
            row = MatchORM(
                id=match.id,
                user1_id=u1,
                user2_id=u2,
                source=match.source.value,
                first_message_by=match.first_message_by,
                is_active=True,
            )
            session.add(row)
            session.flush()
            session.refresh(row)
            result = _match_orm_to_domain(row)
            session.commit()
            return result

    def get_match_by_pair(self, user_a_id: str, user_b_id: str) -> Match | None:
        with self._sf() as session:
            u1, u2 = sorted((user_a_id, user_b_id))
            stmt = select(MatchORM).where(
                MatchORM.user1_id == u1,
                MatchORM.user2_id == u2,
            )
            row = session.execute(stmt).scalar_one_or_none()
            return _match_orm_to_domain(row) if row else None

    def list_matches_for_user(self, user_id: str) -> list[Match]:
        with self._sf() as session:
            stmt = (
                select(MatchORM)
                .where(
                    or_(MatchORM.user1_id == user_id, MatchORM.user2_id == user_id),
                    MatchORM.is_active.is_(True),
                )
                .order_by(MatchORM.created_at.desc())
            )
            return [_match_orm_to_domain(row) for row in session.execute(stmt).scalars().all()]

    def delete_match(self, match_id: str) -> None:
        with self._sf() as session:
            row = session.get(MatchORM, match_id)
            if row is not None:
                session.delete(row)
                session.commit()
