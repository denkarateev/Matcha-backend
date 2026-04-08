"""
Activity summary schemas.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.modules.deals.schemas import DealRead
from app.modules.offers.schemas import OfferResponseRead
from app.modules.profile.schemas import ProfileRead


class LikeRead(BaseModel):
    """Minimal profile card for someone who liked the current user."""
    user_id: str
    display_name: str
    primary_photo_url: str
    district: str | None = None
    audience_size: int | None = None
    niches: list[str] = []
    is_verified: bool = False

    model_config = ConfigDict(from_attributes=True)


class ActivitySummaryRead(BaseModel):
    """
    Full activity summary returned by GET /activity/summary.

    - likes            — profiles who swiped right/super on me but I haven't matched yet
    - active_deals     — deals in DRAFT or CONFIRMED state
    - finished_deals   — deals in VISITED or REVIEWED state
    - cancelled_deals  — deals in CANCELLED state
    - no_show_deals    — deals in NO_SHOW state
    - applications     — my offer responses (as a blogger) or incoming responses (as a business)
    """
    likes: list[LikeRead]
    active_deals: list[DealRead]
    finished_deals: list[DealRead]
    cancelled_deals: list[DealRead]
    no_show_deals: list[DealRead]
    applications: list[OfferResponseRead]
