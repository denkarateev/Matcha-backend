from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.deals.domain.models import CancellationReason, DealStatus
from app.modules.offers.domain.models import OfferType


class DealCreateRequest(BaseModel):
    partner_id: str
    type: OfferType
    you_offer: str = Field(min_length=1, max_length=200)
    you_receive: str = Field(min_length=1, max_length=200)
    place_name: str | None = Field(default=None, max_length=120)
    guests: str = "solo"
    date_time: datetime | None = None
    content_deadline: datetime | None = None

    # Legacy field aliases kept for backward compatibility
    counterparty_id: str | None = None
    offered_text: str | None = None
    requested_text: str | None = None
    scheduled_for: datetime | None = None
    location_name: str | None = None

    def resolved_partner_id(self) -> str:
        return self.partner_id or self.counterparty_id or ""

    def resolved_offered_text(self) -> str:
        return self.you_offer or self.offered_text or ""

    def resolved_requested_text(self) -> str:
        return self.you_receive or self.requested_text or ""

    def resolved_place_name(self) -> str | None:
        value = self.place_name or self.location_name
        if value is None:
            return None
        value = value.strip()
        return value or None

    def resolved_scheduled_for(self) -> datetime | None:
        return self.date_time or self.scheduled_for


class DealReviewRequest(BaseModel):
    punctuality: int | None = Field(default=None, ge=1, le=5)
    offer_match: int | None = Field(default=None, ge=1, le=5)
    communication: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=300)


class DealCancelRequest(BaseModel):
    reason: CancellationReason = CancellationReason.OTHER


class DealContentProofRequest(BaseModel):
    post_url: str = Field(min_length=1, max_length=500)
    screenshot_url: str | None = Field(default=None, max_length=500)


class ContentProofRead(BaseModel):
    submitter_id: str
    post_url: str
    screenshot_url: str | None
    submitted_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DealReviewRead(BaseModel):
    reviewer_id: str
    reviewee_id: str
    punctuality: int | None
    offer_match: int | None
    communication: int | None
    comment: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def _truncate_microseconds(dt: datetime) -> str:
    """Truncate microseconds to milliseconds for iOS compatibility."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


class DealRead(BaseModel):
    id: str
    chat_id: str
    participant_ids: tuple[str, str]
    initiator_id: str
    type: OfferType
    offered_text: str
    requested_text: str
    place_name: str | None
    guests: str
    scheduled_for: datetime | None
    content_deadline: datetime | None
    status: DealStatus
    checked_in_user_ids: set[str]
    reviews: list[DealReviewRead]
    content_proofs: list[ContentProofRead]
    cancellation_reason: str | None
    repeated_from_deal_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={datetime: _truncate_microseconds},
    )
