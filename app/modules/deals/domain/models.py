from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.core.time import utc_now
from app.modules.offers.domain.models import OfferType


class DealStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    VISITED = "visited"
    NO_SHOW = "no_show"
    REVIEWED = "reviewed"
    CANCELLED = "cancelled"


class CancellationReason(str, Enum):
    DECLINED = "declined"
    SCHEDULE_CONFLICT = "schedule_conflict"
    CHANGED_CONDITIONS = "changed_conditions"
    NO_RESPONSE = "no_response"
    OTHER = "other"


@dataclass
class DealReview:
    reviewer_id: str
    reviewee_id: str
    punctuality: int | None = None
    offer_match: int | None = None
    communication: int | None = None
    comment: str | None = None
    created_at: object = field(default_factory=utc_now)


@dataclass
class ContentProof:
    submitter_id: str
    post_url: str
    screenshot_url: str | None = None
    submitted_at: object = field(default_factory=utc_now)


@dataclass
class Deal:
    id: str
    chat_id: str
    participant_ids: tuple[str, str]
    initiator_id: str
    type: OfferType
    offered_text: str
    requested_text: str
    place_name: str | None = None
    guests: str = "solo"
    scheduled_for: object | None = None
    content_deadline: object | None = None
    status: DealStatus = DealStatus.DRAFT
    checked_in_user_ids: set[str] = field(default_factory=set)
    reviews: list[DealReview] = field(default_factory=list)
    content_proofs: list[ContentProof] = field(default_factory=list)
    cancellation_reason: str | None = None
    repeated_from_deal_id: str | None = None
    created_at: object = field(default_factory=utc_now)
    updated_at: object = field(default_factory=utc_now)
