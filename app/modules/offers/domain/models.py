from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.core.time import utc_now


class OfferType(str, Enum):
    BARTER = "barter"
    PAID = "paid"
    BOTH = "both"


class OfferStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    EXPIRED = "expired"


class OfferResponseStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


@dataclass
class Offer:
    id: str
    business_id: str
    title: str
    type: OfferType
    blogger_receives: str
    business_receives: str
    slots_total: int
    slots_remaining: int
    photo_url: str
    expires_at: object | None = None
    preferred_blogger_niche: str | None = None
    min_audience: str | None = None
    guests: str | None = None
    special_conditions: str | None = None
    is_last_minute: bool = False
    status: OfferStatus = OfferStatus.ACTIVE
    created_at: object = field(default_factory=utc_now)
    updated_at: object = field(default_factory=utc_now)


@dataclass
class OfferResponse:
    id: str
    offer_id: str
    business_id: str
    blogger_id: str
    status: OfferResponseStatus = OfferResponseStatus.PENDING
    message: str | None = None
    created_at: object = field(default_factory=utc_now)
    updated_at: object = field(default_factory=utc_now)
