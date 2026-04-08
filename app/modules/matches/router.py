"""
Matches & Discovery Feed router.

Endpoints
---------
GET  /matches/feed           — Discovery feed (filtered, ranked, opposite-role profiles)
GET  /matches                — List active matches for current user
POST /matches/swipe          — Record a swipe (left / right / super)  [iOS alias]
POST /matches/swipes         — Record a swipe (legacy path)
POST /matches/match-back     — Instantly create a mutual match
"""
from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.container import AppContainer
from app.core.dependencies import get_container, get_current_user_id
from app.modules.matches.domain.models import MatchSource, Swipe, SwipeDirection
from app.modules.matches.schemas import (
    FeedProfileRead,
    MatchRead,
    SwipeOutcomeRead,
    SwipeRead,
    SwipeRequest,
)
from app.modules.profile.schemas import ProfileRead

router = APIRouter(prefix="/matches", tags=["matches"])


# ---------------------------------------------------------------------------
# Discovery Feed
# ---------------------------------------------------------------------------

@router.get("/feed", response_model=list[FeedProfileRead])
def get_discovery_feed(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    niche: str | None = Query(default=None, description="Filter by niche, e.g. Travel"),
    district: str | None = Query(default=None, description="Filter by district, e.g. Canggu"),
    min_followers: int | None = Query(default=None, ge=0, description="Minimum audience size"),
    collab_type: str | None = Query(default=None, description="paid | barter | both"),
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> list[FeedProfileRead]:
    """
    Return a ranked discovery feed of opposite-role profiles.

    Business users see Bloggers; Blogger users see Businesses.

    Filters:
      - niche          — match profile.niches list
      - district       — exact match on profile.district
      - min_followers  — profile.audience_size >= min_followers
      - collab_type    — paid | barter | both (matches profile.collab_type)

    Ranking criteria (applied server-side):
      1. Profile completeness  (instagram_handle + bio + audience_size)
      2. Freshness             (recently updated_at)
      3. Already-swiped users are excluded

    Paginated via ?limit=&offset=
    """
    user = container.auth_service.get_user(current_user_id)

    # Collect IDs already swiped by this user
    swiped_ids: set[str] = {
        swipe.target_id
        for swipe in container.match_service.match_repo.store.swipes.values()
        if swipe.actor_id == current_user_id
    }

    # Get opposite-role profiles from in-memory store
    from app.modules.auth.domain.models import UserRole

    viewer_role = user.role
    opposite_role = UserRole.BUSINESS if viewer_role == UserRole.BLOGGER else UserRole.BLOGGER

    candidates: list[FeedProfileRead] = []
    for uid, profile in container.profile_service.profile_repo.store.profiles.items():
        if uid == current_user_id:
            continue
        if uid in swiped_ids:
            continue

        target_user = container.auth_service.auth_repo.get_by_id(uid)
        if not target_user:
            continue
        if target_user.role != opposite_role:
            continue

        # Apply filters
        if niche and niche not in (profile.niches or []):
            continue
        if district and profile.district != district:
            continue
        if min_followers is not None and (profile.audience_size is None or profile.audience_size < min_followers):
            continue
        if collab_type and collab_type != "both" and profile.collab_type not in (collab_type, "both"):
            continue

        feed_item = FeedProfileRead(
            user_id=profile.user_id,
            role=target_user.role.value,
            display_name=profile.display_name,
            photo_urls=profile.photo_urls,
            primary_photo_url=profile.primary_photo_url,
            country=profile.country,
            instagram_handle=profile.instagram_handle,
            tiktok_handle=profile.tiktok_handle,
            audience_size=profile.audience_size,
            category=profile.category,
            district=profile.district,
            website=profile.website,
            niches=profile.niches,
            languages=profile.languages,
            bio=profile.bio,
            description=profile.description,
            what_we_offer=profile.what_we_offer,
            collab_type=profile.collab_type,
            badges=profile.badges,
            verified_visits=profile.verified_visits,
            rating=profile.rating,
            review_count=profile.review_count,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
            is_verified=target_user.is_verified,
        )
        candidates.append(feed_item)

    # Rank: completeness score (instagram + bio + audience) then recency
    def rank_key(fp: FeedProfileRead):
        completeness = sum([
            1 if fp.instagram_handle else 0,
            1 if fp.bio else 0,
            1 if fp.audience_size else 0,
        ])
        return (completeness, fp.updated_at)

    candidates.sort(key=rank_key, reverse=True)
    return candidates[offset: offset + limit]


# ---------------------------------------------------------------------------
# Matches list
# ---------------------------------------------------------------------------

@router.get("", response_model=list[MatchRead])
def list_matches(
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> list[MatchRead]:
    matches = container.match_service.list_matches(current_user_id)
    return [MatchRead.model_validate(match) for match in matches]


# ---------------------------------------------------------------------------
# Swipe  (POST /swipe — iOS primary path)
# ---------------------------------------------------------------------------

def _do_swipe(
    payload: SwipeRequest,
    current_user_id: str,
    container: AppContainer,
) -> SwipeOutcomeRead:
    """Shared swipe logic used by both /swipe and /swipes."""
    swipe_obj, match = container.match_service.swipe(current_user_id, payload)
    return SwipeOutcomeRead(
        swipe=SwipeRead.model_validate(swipe_obj),
        match=MatchRead.model_validate(match) if match else None,
    )


@router.post("/swipe", response_model=SwipeOutcomeRead)
def swipe_v2(
    payload: SwipeRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> SwipeOutcomeRead:
    """
    Record a swipe (iOS primary path).

    Body: { target_id: str, direction: "left"|"right"|"super" }

    Returns: { swipe: ..., match: {...} | null }
    The `match` field is non-null only when a mutual match was just created.
    """
    return _do_swipe(payload, current_user_id, container)


@router.post("/swipes", response_model=SwipeOutcomeRead)
def swipe(
    payload: SwipeRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> SwipeOutcomeRead:
    """
    Record a swipe (legacy path kept for compatibility).
    """
    return _do_swipe(payload, current_user_id, container)


# ---------------------------------------------------------------------------
# Match-Back  (POST /match-back — instant mutual match)
# ---------------------------------------------------------------------------

class MatchBackRequest(SwipeRequest):
    """Re-uses SwipeRequest shape: { target_id }. direction is ignored."""
    direction: SwipeDirection = SwipeDirection.RIGHT


from pydantic import BaseModel


class MatchBackBody(BaseModel):
    target_id: str


class MatchBackRead(BaseModel):
    match: MatchRead


@router.post("/match-back", response_model=MatchBackRead)
def match_back(
    payload: MatchBackBody,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> MatchBackRead:
    """
    Instantly create a mutual match between the caller and target_id.

    Used in the iOS Activity screen where a user taps "Match Back" on someone
    who already liked them.  Internally records a RIGHT swipe for each side
    (idempotent) and returns the resulting Match object.
    """
    ms = container.match_service
    store = ms.match_repo.store

    # Ensure actor → target swipe exists (right)
    existing_actor = ms.match_repo.get_latest_swipe(current_user_id, payload.target_id)
    if not existing_actor or existing_actor.direction not in {SwipeDirection.RIGHT, SwipeDirection.SUPER}:
        new_swipe = Swipe(
            id=str(uuid4()),
            actor_id=current_user_id,
            target_id=payload.target_id,
            direction=SwipeDirection.RIGHT,
            delivered=True,
        )
        ms.match_repo.add_swipe(new_swipe)

    # Ensure target → actor swipe exists (right) — synthetic for match-back
    existing_target = ms.match_repo.get_latest_swipe(payload.target_id, current_user_id)
    if not existing_target or existing_target.direction not in {SwipeDirection.RIGHT, SwipeDirection.SUPER}:
        synth_swipe = Swipe(
            id=str(uuid4()),
            actor_id=payload.target_id,
            target_id=current_user_id,
            direction=SwipeDirection.RIGHT,
            delivered=True,
        )
        ms.match_repo.add_swipe(synth_swipe)

    match = ms.ensure_match_for_pair(
        current_user_id,
        payload.target_id,
        source=MatchSource.SWIPE,
    )
    return MatchBackRead(match=MatchRead.model_validate(match))
