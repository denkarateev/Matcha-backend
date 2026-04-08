from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.modules.matches.domain.models import MatchSource, SwipeDirection
from app.modules.profile.schemas import ProfileRead


class SwipeRequest(BaseModel):
    target_id: str
    direction: SwipeDirection


class SwipeRead(BaseModel):
    id: str
    actor_id: str
    target_id: str
    direction: SwipeDirection
    delivered: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MatchRead(BaseModel):
    id: str
    user_ids: tuple[str, str]
    source: MatchSource
    first_message_by: str | None
    created_at: datetime
    expires_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SwipeOutcomeRead(BaseModel):
    swipe: SwipeRead
    match: MatchRead | None = None


class FeedProfileRead(ProfileRead):
    """
    Profile card returned by the discovery feed.
    Extends ProfileRead with extra feed-specific fields.
    """
    is_verified: bool = False

    model_config = ConfigDict(from_attributes=True)


class FeedResponse(BaseModel):
    """Paginated discovery feed response."""
    data: list[FeedProfileRead]
    meta: dict[str, Any]
