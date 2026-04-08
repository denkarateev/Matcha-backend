"""
PostgreSQL-backed repositories for Deal and DealReview entities.

Two flavours:
  - ``DealRepository``  — async
  - ``SyncDBDealRepository`` — sync, implements ``DealRepository``
    Protocol for the synchronous service layer.
"""
from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.database.models import Deal as DealORM
from app.database.models import DealReview as DealReviewORM
from app.modules.deals.domain.models import Deal, DealReview, DealStatus
from app.modules.offers.domain.models import OfferType


def _deal_orm_to_domain(row: DealORM) -> Deal:
    reviews = [_review_orm_to_domain(r) for r in (row.reviews or [])]
    return Deal(
        id=row.id,
        chat_id=row.conversation_id or "",
        participant_ids=(row.influencer_id, row.business_id),
        initiator_id=row.initiator_id,
        type=OfferType(row.offer_type),
        offered_text=row.offered_text,
        requested_text=row.requested_text,
        place_name=row.place_name,
        guests=row.guests,
        scheduled_for=row.scheduled_for,
        content_deadline=row.content_deadline,
        status=DealStatus(row.status),
        cancellation_reason=row.cancellation_reason,
        reviews=reviews,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _review_orm_to_domain(row: DealReviewORM) -> DealReview:
    return DealReview(
        reviewer_id=row.reviewer_id,
        reviewee_id=row.reviewee_id,
        punctuality=row.punctuality,
        offer_match=row.offer_match,
        communication=row.communication,
        comment=row.text,
        created_at=row.created_at,
    )


class DealRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, deal: Deal) -> Deal:
        influencer_id, business_id = deal.participant_ids
        row = DealORM(
            id=deal.id,
            conversation_id=deal.chat_id if deal.chat_id else None,
            offer_type=deal.type.value,
            influencer_id=influencer_id,
            business_id=business_id,
            initiator_id=deal.initiator_id,
            offered_text=deal.offered_text,
            requested_text=deal.requested_text,
            place_name=deal.place_name,
            guests=deal.guests,
            scheduled_for=deal.scheduled_for,
            content_deadline=deal.content_deadline,
            status=deal.status.value,
            cancellation_reason=deal.cancellation_reason,
        )
        self._session.add(row)
        await self._session.flush()
        # Reload with relationships
        await self._session.refresh(row, attribute_names=["reviews"])
        return _deal_orm_to_domain(row)

    async def update(self, deal: Deal) -> Deal:
        row = await self._session.get(DealORM, deal.id)
        if row is None:
            raise ValueError(f"Deal {deal.id!r} not found for update.")
        row.status = deal.status.value
        row.guests = deal.guests
        row.place_name = deal.place_name
        row.scheduled_for = deal.scheduled_for
        row.content_deadline = deal.content_deadline
        row.cancellation_reason = deal.cancellation_reason
        row.confirmed_at = deal.confirmed_at if hasattr(deal, "confirmed_at") else row.confirmed_at
        row.visited_at = deal.visited_at if hasattr(deal, "visited_at") else row.visited_at
        row.reviewed_at = deal.reviewed_at if hasattr(deal, "reviewed_at") else row.reviewed_at
        await self._session.flush()
        await self._session.refresh(row, attribute_names=["reviews"])
        return _deal_orm_to_domain(row)

    async def get_by_id(self, deal_id: str) -> Deal | None:
        from sqlalchemy.orm import selectinload
        stmt = (
            select(DealORM)
            .where(DealORM.id == deal_id)
            .options(selectinload(DealORM.reviews))
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _deal_orm_to_domain(row) if row else None

    async def list_for_user(self, user_id: str) -> list[Deal]:
        from sqlalchemy.orm import selectinload
        stmt = (
            select(DealORM)
            .where(
                or_(
                    DealORM.influencer_id == user_id,
                    DealORM.business_id == user_id,
                )
            )
            .options(selectinload(DealORM.reviews))
            .order_by(DealORM.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [_deal_orm_to_domain(row) for row in result.scalars().all()]

    async def get_active_for_pair(self, user_a_id: str, user_b_id: str) -> Deal | None:
        """
        Return the active deal for a pair of users.
        Active = not CANCELLED and not REVIEWED.
        """
        from sqlalchemy.orm import selectinload
        stmt = (
            select(DealORM)
            .where(
                or_(
                    (DealORM.influencer_id == user_a_id) & (DealORM.business_id == user_b_id),
                    (DealORM.influencer_id == user_b_id) & (DealORM.business_id == user_a_id),
                ),
                DealORM.status.notin_(["cancelled", "reviewed"]),
            )
            .options(selectinload(DealORM.reviews))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _deal_orm_to_domain(row) if row else None

    async def add_review(self, deal_id: str, review: DealReview) -> None:
        row = DealReviewORM(
            deal_id=deal_id,
            reviewer_id=review.reviewer_id,
            reviewee_id=review.reviewee_id,
            rating=int(
                round(
                    (
                        (review.punctuality or 0)
                        + (review.offer_match or 0)
                        + (review.communication or 0)
                    )
                    / 3
                )
            ),
            punctuality=review.punctuality,
            offer_match=review.offer_match,
            communication=review.communication,
            text=review.comment,
        )
        self._session.add(row)
        await self._session.flush()


# ---------------------------------------------------------------------------
# Sync repository  — implements DealRepository Protocol
# ---------------------------------------------------------------------------

class SyncDBDealRepository:
    """
    Synchronous PostgreSQL repository for Deal + DealReview entities.

    Implements the ``DealRepository`` Protocol used by ``DealService``.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sf = session_factory

    # -- DealRepository Protocol ---------------------------------------------

    def add(self, deal: Deal) -> Deal:
        with self._sf() as session:
            influencer_id, business_id = deal.participant_ids
            row = DealORM(
                id=deal.id,
                conversation_id=deal.chat_id if deal.chat_id else None,
                offer_type=deal.type.value,
                influencer_id=influencer_id,
                business_id=business_id,
                initiator_id=deal.initiator_id,
                offered_text=deal.offered_text,
                requested_text=deal.requested_text,
                place_name=deal.place_name,
                guests=deal.guests,
                scheduled_for=deal.scheduled_for,
                content_deadline=deal.content_deadline,
                status=deal.status.value,
                cancellation_reason=deal.cancellation_reason,
            )
            session.add(row)
            session.flush()
            session.refresh(row, attribute_names=["reviews"])
            result = _deal_orm_to_domain(row)
            session.commit()
            return result

    def update(self, deal: Deal) -> Deal:
        with self._sf() as session:
            row = session.get(DealORM, deal.id)
            if row is None:
                raise ValueError(f"Deal {deal.id!r} not found for update.")
            row.status = deal.status.value
            row.guests = deal.guests
            row.place_name = deal.place_name
            row.scheduled_for = deal.scheduled_for
            row.content_deadline = deal.content_deadline
            row.cancellation_reason = deal.cancellation_reason
            row.confirmed_at = deal.confirmed_at if hasattr(deal, "confirmed_at") else row.confirmed_at
            row.visited_at = deal.visited_at if hasattr(deal, "visited_at") else row.visited_at
            row.reviewed_at = deal.reviewed_at if hasattr(deal, "reviewed_at") else row.reviewed_at
            session.flush()
            session.refresh(row, attribute_names=["reviews"])
            result = _deal_orm_to_domain(row)
            session.commit()
            return result

    def get_by_id(self, deal_id: str) -> Deal | None:
        with self._sf() as session:
            stmt = (
                select(DealORM)
                .where(DealORM.id == deal_id)
                .options(selectinload(DealORM.reviews))
            )
            row = session.execute(stmt).scalar_one_or_none()
            if row is None:
                # Try case-insensitive (iOS sends uppercase UUIDs)
                stmt = (
                    select(DealORM)
                    .where(DealORM.id == deal_id.lower())
                    .options(selectinload(DealORM.reviews))
                )
                row = session.execute(stmt).scalar_one_or_none()
            return _deal_orm_to_domain(row) if row else None

    def list_for_user(self, user_id: str) -> list[Deal]:
        with self._sf() as session:
            stmt = (
                select(DealORM)
                .where(
                    or_(
                        DealORM.influencer_id == user_id,
                        DealORM.business_id == user_id,
                    )
                )
                .options(selectinload(DealORM.reviews))
                .order_by(DealORM.created_at.desc())
            )
            return [_deal_orm_to_domain(row) for row in session.execute(stmt).scalars().all()]

    def get_active_for_pair(self, user_a_id: str, user_b_id: str) -> Deal | None:
        with self._sf() as session:
            stmt = (
                select(DealORM)
                .where(
                    or_(
                        and_(DealORM.influencer_id == user_a_id, DealORM.business_id == user_b_id),
                        and_(DealORM.influencer_id == user_b_id, DealORM.business_id == user_a_id),
                    ),
                    DealORM.status.notin_(["cancelled", "reviewed"]),
                )
                .options(selectinload(DealORM.reviews))
                .limit(1)
            )
            row = session.execute(stmt).scalar_one_or_none()
            return _deal_orm_to_domain(row) if row else None

    def get_blocking_deals_for_pair(self, user_a_id: str, user_b_id: str) -> list[Deal]:
        """Returns deals with status VISITED between the pair (blocks unmatch)."""
        with self._sf() as session:
            stmt = (
                select(DealORM)
                .where(
                    or_(
                        and_(DealORM.influencer_id == user_a_id, DealORM.business_id == user_b_id),
                        and_(DealORM.influencer_id == user_b_id, DealORM.business_id == user_a_id),
                    ),
                    DealORM.status == "visited",
                )
                .options(selectinload(DealORM.reviews))
            )
            return [_deal_orm_to_domain(row) for row in session.execute(stmt).scalars().all()]

    def list_for_pair(self, user_a_id: str, user_b_id: str) -> list[Deal]:
        """Returns all deals between the pair."""
        with self._sf() as session:
            stmt = (
                select(DealORM)
                .where(
                    or_(
                        and_(DealORM.influencer_id == user_a_id, DealORM.business_id == user_b_id),
                        and_(DealORM.influencer_id == user_b_id, DealORM.business_id == user_a_id),
                    ),
                )
                .options(selectinload(DealORM.reviews))
            )
            return [_deal_orm_to_domain(row) for row in session.execute(stmt).scalars().all()]
