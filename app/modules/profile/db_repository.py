"""
PostgreSQL-backed repositories for Profile entities.

Two flavours:
  - ``ProfileRepository``  — async (Alembic / future async endpoints)
  - ``SyncDBProfileRepository`` — sync, implements ``ProfileRepository``
    Protocol for the synchronous service layer.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import Profile as ProfileORM
from app.modules.auth.domain.models import UserRole
from app.modules.profile.domain.models import Profile


def _orm_to_domain(row: ProfileORM) -> Profile:
    return Profile(
        user_id=row.user_id,
        display_name=row.display_name,
        photo_urls=list(row.photo_urls or []),
        primary_photo_url=row.primary_photo_url,
        bio=row.bio,
        description=row.description,
        what_we_offer=row.what_we_offer,
        niches=list(row.niches or []),
        audience_size=row.audience_size,
        district=row.location_district,
        country=row.country,
        instagram_handle=row.instagram_handle,
        tiktok_handle=row.tiktok_handle,
        website=row.website,
        category=row.category,
        languages=list(row.languages or []),
        collab_type=row.collab_type,
        badges=list(row.badges or []),
        verified_visits=row.verified_visits,
        rating=row.rating,
        review_count=row.review_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class ProfileRepository:
    """Async SQLAlchemy repository — replaces InMemoryProfileRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: str) -> Profile | None:
        row = await self._session.get(ProfileORM, user_id)
        return _orm_to_domain(row) if row else None

    async def upsert(self, profile: Profile) -> Profile:
        row = await self._session.get(ProfileORM, profile.user_id)
        if row is None:
            row = ProfileORM(user_id=profile.user_id)
            self._session.add(row)

        row.display_name = profile.display_name
        row.photo_urls = profile.photo_urls
        row.primary_photo_url = profile.primary_photo_url
        row.bio = profile.bio
        row.description = profile.description
        row.what_we_offer = profile.what_we_offer
        row.niches = profile.niches
        row.audience_size = profile.audience_size
        row.location_district = profile.district
        row.country = profile.country
        row.instagram_handle = profile.instagram_handle
        row.tiktok_handle = profile.tiktok_handle
        row.website = str(profile.website) if profile.website else None
        row.category = profile.category
        row.languages = profile.languages
        row.collab_type = profile.collab_type
        row.badges = profile.badges
        row.verified_visits = profile.verified_visits
        row.rating = profile.rating
        row.review_count = profile.review_count

        await self._session.flush()
        await self._session.refresh(row)
        return _orm_to_domain(row)

    async def increment_verified_visits(self, user_id: str) -> Profile:
        row = await self._session.get(ProfileORM, user_id)
        if row is None:
            raise ValueError(f"Profile for user {user_id!r} not found.")
        row.verified_visits = (row.verified_visits or 0) + 1
        await self._session.flush()
        await self._session.refresh(row)
        return _orm_to_domain(row)

    async def apply_review_score(self, user_id: str, score: float) -> Profile:
        row = await self._session.get(ProfileORM, user_id)
        if row is None:
            raise ValueError(f"Profile for user {user_id!r} not found.")
        total = (row.rating or 0.0) * (row.review_count or 0)
        row.review_count = (row.review_count or 0) + 1
        row.rating = round((total + score) / row.review_count, 2)
        await self._session.flush()
        await self._session.refresh(row)
        return _orm_to_domain(row)

    async def get_feed(
        self,
        viewer_id: str,
        viewer_role: str,
        already_swiped_ids: list[str],
        limit: int = 20,
        offset: int = 0,
    ) -> list[Profile]:
        """
        Return ranked profiles for the discovery feed.

        Ranking factors (descending priority):
            1. Opposite role only (Business sees Bloggers, Blogger sees Businesses)
            2. Exclude already-swiped profiles
            3. Exclude the viewer themselves
            4. Completeness: profiles with instagram_handle + bio rank higher
            5. Freshness: recently updated profiles rank higher
            6. Geographic affinity: same district ranks higher
        """
        from app.database.models import User as UserORM

        # Determine target role
        target_role = "blogger" if viewer_role == "business" else "business"

        # Base query: join Profile → User to filter by role
        stmt = (
            select(ProfileORM)
            .join(UserORM, UserORM.id == ProfileORM.user_id)
            .where(
                UserORM.role == target_role,
                UserORM.is_active.is_(True),
                ProfileORM.user_id != viewer_id,
            )
        )

        # Exclude already-swiped users
        if already_swiped_ids:
            stmt = stmt.where(ProfileORM.user_id.notin_(already_swiped_ids))

        # Ordering: completeness proxy + freshness
        # Profiles with instagram_handle come first (NULLS LAST), then by updated_at desc
        from sqlalchemy import case, nullslast, desc

        completeness_score = (
            case((ProfileORM.instagram_handle.isnot(None), 2), else_=0)
            + case((ProfileORM.bio.isnot(None), 1), else_=0)
            + case((ProfileORM.audience_size.isnot(None), 1), else_=0)
        )
        stmt = stmt.order_by(
            desc(completeness_score),
            desc(ProfileORM.updated_at),
        )

        stmt = stmt.offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [_orm_to_domain(row) for row in rows]


# ---------------------------------------------------------------------------
# Sync repository  — implements ProfileRepository Protocol
# ---------------------------------------------------------------------------

class SyncDBProfileRepository:
    """
    Synchronous PostgreSQL repository for Profile entities.

    Each public method opens its own session (auto-commit on success,
    rollback on error) so it is safe to call from the sync service layer.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sf = session_factory

    # -- ProfileRepository Protocol ------------------------------------------

    def get_by_user_id(self, user_id: str) -> Profile | None:
        with self._sf() as session:
            row = session.get(ProfileORM, user_id)
            return _orm_to_domain(row) if row else None

    def upsert(self, profile: Profile) -> Profile:
        with self._sf() as session:
            row = session.get(ProfileORM, profile.user_id)
            if row is None:
                row = ProfileORM(user_id=profile.user_id)
                session.add(row)

            row.display_name = profile.display_name
            row.photo_urls = profile.photo_urls
            row.primary_photo_url = profile.primary_photo_url
            row.bio = profile.bio
            row.description = profile.description
            row.what_we_offer = profile.what_we_offer
            row.niches = profile.niches
            row.audience_size = profile.audience_size
            row.location_district = profile.district
            row.country = profile.country
            row.instagram_handle = profile.instagram_handle
            row.tiktok_handle = profile.tiktok_handle
            row.website = str(profile.website) if profile.website else None
            row.category = profile.category
            row.languages = profile.languages
            row.collab_type = profile.collab_type
            row.badges = profile.badges
            row.verified_visits = profile.verified_visits
            row.rating = profile.rating
            row.review_count = profile.review_count

            session.flush()
            session.refresh(row)
            result = _orm_to_domain(row)
            session.commit()
            return result

    def increment_verified_visits(self, user_id: str) -> Profile:
        with self._sf() as session:
            row = session.get(ProfileORM, user_id)
            if row is None:
                raise ValueError(f"Profile for user {user_id!r} not found.")
            row.verified_visits = (row.verified_visits or 0) + 1
            session.flush()
            session.refresh(row)
            result = _orm_to_domain(row)
            session.commit()
            return result

    def apply_review_score(self, user_id: str, score: float) -> Profile:
        with self._sf() as session:
            row = session.get(ProfileORM, user_id)
            if row is None:
                raise ValueError(f"Profile for user {user_id!r} not found.")
            total = (row.rating or 0.0) * (row.review_count or 0)
            row.review_count = (row.review_count or 0) + 1
            row.rating = round((total + score) / row.review_count, 2)
            session.flush()
            session.refresh(row)
            result = _orm_to_domain(row)
            session.commit()
            return result

    def delete(self, user_id: str) -> None:
        with self._sf() as session:
            row = session.get(ProfileORM, user_id)
            if row is not None:
                session.delete(row)
                session.commit()
