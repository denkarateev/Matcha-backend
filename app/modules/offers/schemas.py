from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from app.modules.offers.domain.models import OfferResponseStatus, OfferStatus, OfferType

if TYPE_CHECKING:
    from app.modules.profile.schemas import ProfileRead


class OfferCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=60)
    type: OfferType
    blogger_receives: str = Field(min_length=1, max_length=200)
    business_receives: str = Field(min_length=1, max_length=200)
    slots_total: int = Field(ge=0, le=10)  # 0 = unlimited slots
    photo_url: str = Field(min_length=1)
    expires_at: datetime | None = None
    preferred_blogger_niche: str | None = None
    min_audience: str | None = None
    guests: str | None = None
    special_conditions: str | None = None
    is_last_minute: bool = False


class OfferFilterParams(BaseModel):
    type: OfferType | None = None
    niche: str | None = None
    last_minute_only: bool = False


class OfferRespondRequest(BaseModel):
    message: str | None = Field(default=None, max_length=300)


class OfferRead(BaseModel):
    id: str
    business_id: str
    title: str
    type: OfferType
    blogger_receives: str
    business_receives: str
    slots_total: int
    slots_remaining: int
    photo_url: str
    expires_at: datetime | None
    preferred_blogger_niche: str | None
    min_audience: str | None
    guests: str | None
    special_conditions: str | None
    is_last_minute: bool
    status: OfferStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OfferResponseRead(BaseModel):
    id: str
    offer_id: str
    business_id: str
    blogger_id: str
    status: OfferResponseStatus
    message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OfferRespondResult(BaseModel):
    """Returned after a blogger responds to an offer."""
    response: OfferResponseRead
    remaining_responses: int


class OfferDetailRead(OfferRead):
    """
    Offer with creator's public profile attached.
    Used by GET /offers/{id}.
    """
    creator: object | None = None  # ProfileRead — typed loosely to avoid circular import
