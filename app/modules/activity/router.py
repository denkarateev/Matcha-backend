"""
Activity router.

Endpoints
---------
GET /activity/summary  — Activity hub: likes, deals by status, applications
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.container import AppContainer
from app.core.dependencies import get_container, get_current_user_id
from app.modules.activity.schemas import ActivitySummaryRead, LikeRead
from app.modules.auth.domain.models import UserRole
from app.modules.deals.domain.models import DealStatus
from app.modules.deals.schemas import DealRead
from app.modules.matches.domain.models import SwipeDirection
from app.modules.offers.schemas import OfferResponseRead

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("/summary", response_model=ActivitySummaryRead)
def get_activity_summary(
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> ActivitySummaryRead:
    """
    Return the full activity summary for the current user.

    Likes:
      Profiles who swiped RIGHT or SUPER on the caller but where there is
      no mutual match yet (i.e. pending / unanswered likes).

    Deals grouped by status:
      active    → DRAFT | CONFIRMED
      finished  → VISITED | REVIEWED
      cancelled → CANCELLED
      no_show   → NO_SHOW

    Applications:
      - Blogger  → my own OfferResponses (outgoing)
      - Business → incoming OfferResponses on my offers
    """
    user = container.auth_service.get_user(current_user_id)
    store = container.match_service.match_repo.store

    # ------------------------------------------------------------------ #
    # Likes — people who swiped right/super on me with no match yet
    # ------------------------------------------------------------------ #
    matched_user_ids: set[str] = set()
    for match in store.matches.values():
        if current_user_id in match.user_ids:
            other = next(uid for uid in match.user_ids if uid != current_user_id)
            matched_user_ids.add(other)

    # Also collect who I've already swiped on (to exclude them from "likes")
    i_already_swiped: set[str] = {
        swipe.target_id
        for swipe in store.swipes.values()
        if swipe.actor_id == current_user_id
    }

    likes: list[LikeRead] = []
    seen_likers: set[str] = set()
    for swipe in store.swipes.values():
        actor_id = swipe.actor_id
        if swipe.target_id != current_user_id:
            continue
        if swipe.direction not in {SwipeDirection.RIGHT, SwipeDirection.SUPER}:
            continue
        if actor_id in matched_user_ids:
            continue
        if actor_id in i_already_swiped:
            continue
        if actor_id in seen_likers:
            continue
        seen_likers.add(actor_id)

        liker_profile = container.profile_service.profile_repo.get_by_user_id(actor_id)
        if not liker_profile:
            continue
        liker_user = container.auth_service.auth_repo.get_by_id(actor_id)
        likes.append(
            LikeRead(
                user_id=actor_id,
                display_name=liker_profile.display_name,
                primary_photo_url=liker_profile.primary_photo_url,
                district=liker_profile.district,
                audience_size=liker_profile.audience_size,
                niches=liker_profile.niches or [],
                is_verified=liker_user.is_verified if liker_user else False,
            )
        )

    # ------------------------------------------------------------------ #
    # Deals — grouped by status
    # ------------------------------------------------------------------ #
    all_deals = container.deal_service.list_deals(current_user_id)

    active_statuses = {DealStatus.DRAFT, DealStatus.CONFIRMED}
    finished_statuses = {DealStatus.VISITED, DealStatus.REVIEWED}

    active_deals = [DealRead.model_validate(d) for d in all_deals if d.status in active_statuses]
    finished_deals = [DealRead.model_validate(d) for d in all_deals if d.status in finished_statuses]
    cancelled_deals = [DealRead.model_validate(d) for d in all_deals if d.status == DealStatus.CANCELLED]
    no_show_deals = [DealRead.model_validate(d) for d in all_deals if d.status == DealStatus.NO_SHOW]

    # ------------------------------------------------------------------ #
    # Applications
    # ------------------------------------------------------------------ #
    if user.role == UserRole.BLOGGER:
        # Outgoing — responses I submitted
        applications_raw = [
            resp
            for resp in store.offer_responses.values()
            if resp.blogger_id == current_user_id
        ]
    else:
        # Incoming — responses on my offers
        applications_raw = container.offer_service.list_responses_for_business(current_user_id)

    applications = [OfferResponseRead.model_validate(r) for r in applications_raw]

    return ActivitySummaryRead(
        likes=likes,
        active_deals=active_deals,
        finished_deals=finished_deals,
        cancelled_deals=cancelled_deals,
        no_show_deals=no_show_deals,
        applications=applications,
    )
