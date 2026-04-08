from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.core.time import utc_now


class UserRole(str, Enum):
    BLOGGER = "blogger"
    BUSINESS = "business"


class VerificationLevel(int, Enum):
    SHADOW = 0
    VERIFIED = 1
    BLUE_CHECK = 2


class PlanTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    BLACK = "black"


@dataclass
class User:
    id: str
    email: str
    password_hash: str
    role: UserRole
    full_name: str
    is_active: bool = True
    verification_level: VerificationLevel = VerificationLevel.SHADOW
    plan_tier: PlanTier = PlanTier.FREE
    offer_credits: int = 0
    created_at: object = field(default_factory=utc_now)
    updated_at: object = field(default_factory=utc_now)

    @property
    def is_verified(self) -> bool:
        return self.verification_level >= VerificationLevel.VERIFIED
