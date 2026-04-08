"""
PostgreSQL-backed repositories for Offer and OfferResponse entities.

Two flavours:
  - ``OfferRepository`` / ``OfferResponseRepository``  — async
  - ``SyncDBOfferRepository`` — sync, implements ``OfferRepository``
    Protocol (combines offer + response ops) for the synchronous service layer.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import Offer as OfferORM
from app.database.models import OfferResponse as OfferResponseORM
from app.modules.offers.domain.models import (
    Offer,
    OfferResponse,
    OfferResponseStatus,
    OfferStatus,
    OfferType,
)


def _offer_orm_to_domain(row: OfferORM) -> Offer:
    return Offer(
        id=row.id,
        business_id=row.business_id,
        title=row.title,
        type=OfferType(row.type),
        blogger_receives=row.blogger_receives,
        business_receives=row.business_receives,
        slots_total=row.slots_total,
        slots_remaining=row.slots_remaining,
        photo_url=row.photo_url,
        expires_at=row.expires_at,
        preferred_blogger_niche=row.preferred_blogger_niche,
        min_audience=row.min_audience,
        guests=row.guests,
        special_conditions=row.special_conditions,
        is_last_minute=row.is_last_minute,
        status=OfferStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _offer_response_orm_to_domain(row: OfferResponseORM) -> OfferResponse:
    return OfferResponse(
        id=row.id,
        offer_id=row.offer_id,
        business_id=row.business_id,
        blogger_id=row.blogger_id,
        status=OfferResponseStatus(row.status),
        message=row.message,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class OfferRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_offer(self, offer: Offer) -> Offer:
        row = OfferORM(
            id=offer.id,
            business_id=offer.business_id,
            title=offer.title,
            type=offer.type.value,
            blogger_receives=offer.blogger_receives,
            business_receives=offer.business_receives,
            slots_total=offer.slots_total,
            slots_remaining=offer.slots_remaining,
            photo_url=offer.photo_url,
            expires_at=offer.expires_at,
            preferred_blogger_niche=offer.preferred_blogger_niche,
            min_audience=offer.min_audience,
            guests=offer.guests,
            special_conditions=offer.special_conditions,
            is_last_minute=offer.is_last_minute,
            status=offer.status.value,
            is_active=offer.status == OfferStatus.ACTIVE,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _offer_orm_to_domain(row)

    async def update_offer(self, offer: Offer) -> Offer:
        row = await self._session.get(OfferORM, offer.id)
        if row is None:
            raise ValueError(f"Offer {offer.id!r} not found for update.")
        row.title = offer.title
        row.blogger_receives = offer.blogger_receives
        row.business_receives = offer.business_receives
        row.slots_total = offer.slots_total
        row.slots_remaining = offer.slots_remaining
        row.status = offer.status.value
        row.is_active = offer.status == OfferStatus.ACTIVE
        row.expires_at = offer.expires_at
        await self._session.flush()
        await self._session.refresh(row)
        return _offer_orm_to_domain(row)

    async def get_offer(self, offer_id: str) -> Offer | None:
        row = await self._session.get(OfferORM, offer_id)
        return _offer_orm_to_domain(row) if row else None

    async def list_offers(
        self,
        *,
        type: OfferType | None = None,
        niche: str | None = None,
        last_minute_only: bool = False,
        active_only: bool = True,
    ) -> list[Offer]:
        stmt = select(OfferORM)
        if active_only:
            stmt = stmt.where(OfferORM.is_active.is_(True))
        if type is not None:
            stmt = stmt.where(OfferORM.type == type.value)
        if niche is not None:
            stmt = stmt.where(OfferORM.preferred_blogger_niche == niche)
        if last_minute_only:
            stmt = stmt.where(OfferORM.is_last_minute.is_(True))
        stmt = stmt.order_by(OfferORM.created_at.desc())
        result = await self._session.execute(stmt)
        return [_offer_orm_to_domain(row) for row in result.scalars().all()]


class OfferResponseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_response(self, response: OfferResponse) -> OfferResponse:
        row = OfferResponseORM(
            id=response.id,
            offer_id=response.offer_id,
            business_id=response.business_id,
            blogger_id=response.blogger_id,
            status=response.status.value,
            message=response.message,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _offer_response_orm_to_domain(row)

    async def update_response(self, response: OfferResponse) -> OfferResponse:
        row = await self._session.get(OfferResponseORM, response.id)
        if row is None:
            raise ValueError(f"OfferResponse {response.id!r} not found for update.")
        row.status = response.status.value
        row.message = response.message
        await self._session.flush()
        await self._session.refresh(row)
        return _offer_response_orm_to_domain(row)

    async def get_response(self, response_id: str) -> OfferResponse | None:
        row = await self._session.get(OfferResponseORM, response_id)
        return _offer_response_orm_to_domain(row) if row else None

    async def get_response_for_offer_and_blogger(
        self, offer_id: str, blogger_id: str
    ) -> OfferResponse | None:
        stmt = select(OfferResponseORM).where(
            OfferResponseORM.offer_id == offer_id,
            OfferResponseORM.blogger_id == blogger_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _offer_response_orm_to_domain(row) if row else None

    async def list_responses_for_business(self, business_id: str) -> list[OfferResponse]:
        stmt = (
            select(OfferResponseORM)
            .where(OfferResponseORM.business_id == business_id)
            .order_by(OfferResponseORM.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [_offer_response_orm_to_domain(row) for row in result.scalars().all()]

    async def count_blogger_responses_on_date(
        self, blogger_id: str, day: date
    ) -> int:
        """Count responses created by blogger on a given WITA calendar day."""
        # We store UTC; compare by casting to date in the application for simplicity.
        # For scale, use a DB-side date_trunc query.
        stmt = select(func.count()).where(
            OfferResponseORM.blogger_id == blogger_id,
            func.date(OfferResponseORM.created_at) == day,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one() or 0


# ---------------------------------------------------------------------------
# Sync repository  — implements OfferRepository Protocol
# (combines offer + response operations in one class)
# ---------------------------------------------------------------------------

class SyncDBOfferRepository:
    """
    Synchronous PostgreSQL repository for Offer + OfferResponse entities.

    Implements the ``OfferRepository`` Protocol used by ``OfferService``.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sf = session_factory

    # -- Offer operations ----------------------------------------------------

    def add_offer(self, offer: Offer) -> Offer:
        with self._sf() as session:
            row = OfferORM(
                id=offer.id,
                business_id=offer.business_id,
                title=offer.title,
                type=offer.type.value,
                blogger_receives=offer.blogger_receives,
                business_receives=offer.business_receives,
                slots_total=offer.slots_total,
                slots_remaining=offer.slots_remaining,
                photo_url=offer.photo_url,
                expires_at=offer.expires_at,
                preferred_blogger_niche=offer.preferred_blogger_niche,
                min_audience=offer.min_audience,
                guests=offer.guests,
                special_conditions=offer.special_conditions,
                is_last_minute=offer.is_last_minute,
                status=offer.status.value,
                is_active=offer.status == OfferStatus.ACTIVE,
            )
            session.add(row)
            session.flush()
            session.refresh(row)
            result = _offer_orm_to_domain(row)
            session.commit()
            return result

    def update_offer(self, offer: Offer) -> Offer:
        with self._sf() as session:
            row = session.get(OfferORM, offer.id)
            if row is None:
                raise ValueError(f"Offer {offer.id!r} not found for update.")
            row.title = offer.title
            row.blogger_receives = offer.blogger_receives
            row.business_receives = offer.business_receives
            row.slots_total = offer.slots_total
            row.slots_remaining = offer.slots_remaining
            row.status = offer.status.value
            row.is_active = offer.status == OfferStatus.ACTIVE
            row.expires_at = offer.expires_at
            session.flush()
            session.refresh(row)
            result = _offer_orm_to_domain(row)
            session.commit()
            return result

    def get_offer(self, offer_id: str) -> Offer | None:
        with self._sf() as session:
            row = session.get(OfferORM, offer_id)
            return _offer_orm_to_domain(row) if row else None

    def list_offers(self) -> list[Offer]:
        with self._sf() as session:
            stmt = select(OfferORM).order_by(OfferORM.created_at.desc())
            return [_offer_orm_to_domain(row) for row in session.execute(stmt).scalars().all()]

    # -- OfferResponse operations --------------------------------------------

    def add_response(self, response: OfferResponse) -> OfferResponse:
        with self._sf() as session:
            row = OfferResponseORM(
                id=response.id,
                offer_id=response.offer_id,
                business_id=response.business_id,
                blogger_id=response.blogger_id,
                status=response.status.value,
                message=response.message,
            )
            session.add(row)
            session.flush()
            session.refresh(row)
            result = _offer_response_orm_to_domain(row)
            session.commit()
            return result

    def update_response(self, response: OfferResponse) -> OfferResponse:
        with self._sf() as session:
            row = session.get(OfferResponseORM, response.id)
            if row is None:
                raise ValueError(f"OfferResponse {response.id!r} not found for update.")
            row.status = response.status.value
            row.message = response.message
            session.flush()
            session.refresh(row)
            result = _offer_response_orm_to_domain(row)
            session.commit()
            return result

    def get_response(self, response_id: str) -> OfferResponse | None:
        with self._sf() as session:
            row = session.get(OfferResponseORM, response_id)
            return _offer_response_orm_to_domain(row) if row else None

    def get_response_for_offer_and_blogger(
        self,
        offer_id: str,
        blogger_id: str,
    ) -> OfferResponse | None:
        with self._sf() as session:
            stmt = select(OfferResponseORM).where(
                OfferResponseORM.offer_id == offer_id,
                OfferResponseORM.blogger_id == blogger_id,
            )
            row = session.execute(stmt).scalar_one_or_none()
            return _offer_response_orm_to_domain(row) if row else None

    def list_responses_for_business(self, business_id: str) -> list[OfferResponse]:
        with self._sf() as session:
            stmt = (
                select(OfferResponseORM)
                .where(OfferResponseORM.business_id == business_id)
                .order_by(OfferResponseORM.created_at.desc())
            )
            return [
                _offer_response_orm_to_domain(row)
                for row in session.execute(stmt).scalars().all()
            ]

    def count_blogger_responses_on_date(self, blogger_id: str, day: date) -> int:
        with self._sf() as session:
            stmt = select(func.count()).where(
                OfferResponseORM.blogger_id == blogger_id,
                func.date(OfferResponseORM.created_at) == day,
            )
            return session.execute(stmt).scalar_one() or 0
