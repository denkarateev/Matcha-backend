from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum

from app.core.time import utc_now

MATCH_EXPIRY_HOURS = 48


class SwipeDirection(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    SUPER = "super"


class MatchSource(str, Enum):
    SWIPE = "swipe"
    OFFER = "offer"


@dataclass
class Swipe:
    id: str
    actor_id: str
    target_id: str
    direction: SwipeDirection
    delivered: bool
    created_at: object = field(default_factory=utc_now)


def _default_expires_at():
    return utc_now() + timedelta(hours=MATCH_EXPIRY_HOURS)


@dataclass
class Match:
    id: str
    user_ids: tuple[str, str]
    source: MatchSource
    first_message_by: str | None = None
    created_at: object = field(default_factory=utc_now)
    expires_at: object = field(default_factory=_default_expires_at)
