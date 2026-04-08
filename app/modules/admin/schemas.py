from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.auth.domain.models import PlanTier, UserRole, VerificationLevel


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardStats(BaseModel):
    total_users: int = 0
    total_matches: int = 0
    total_deals: int = 0
    total_offers: int = 0
    active_today: int = 0


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------

class AdminUserRead(BaseModel):
    id: str
    email: str
    role: UserRole
    full_name: str
    is_active: bool
    verification_level: VerificationLevel
    plan_tier: PlanTier
    offer_credits: int
    created_at: datetime
    updated_at: datetime
    # Profile fields (joined)
    display_name: str | None = None
    instagram_handle: str | None = None
    tiktok_handle: str | None = None
    audience_size: int | None = None
    category: str | None = None
    rating: float | None = None
    review_count: int = 0
    primary_photo_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminUserDetail(AdminUserRead):
    bio: str | None = None
    description: str | None = None
    niches: list[str] = []
    languages: list[str] = []
    photo_urls: list[str] = []
    badges: list[str] = []
    verified_visits: int = 0
    district: str | None = None
    country: str | None = None
    deals: list[AdminDealBrief] = []
    matches_count: int = 0


class AdminDealBrief(BaseModel):
    id: str
    status: str
    type: str
    partner_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Forward ref update
AdminUserDetail.model_rebuild()


class UserListResponse(BaseModel):
    users: list[AdminUserRead]
    total: int


# ---------------------------------------------------------------------------
# Verification management
# ---------------------------------------------------------------------------

class VerificationSubmission(BaseModel):
    id: str
    user_id: str
    user_name: str
    user_email: str
    instagram_handle: str | None = None
    tiktok_handle: str | None = None
    audience_size: int | None = None
    screenshot_url: str | None = None
    submitted_at: datetime
    status: str = "pending"


class VerificationListResponse(BaseModel):
    submissions: list[VerificationSubmission]
    total: int


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class SetVerificationRequest(BaseModel):
    verification_level: int = Field(ge=0, le=2)


class SetAudienceRequest(BaseModel):
    audience_size: int = Field(ge=0)


class BanUserRequest(BaseModel):
    reason: str | None = None


class VerificationActionRequest(BaseModel):
    reason: str | None = None


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Deals CRM
# ---------------------------------------------------------------------------

class AdminDealRead(BaseModel):
    id: str
    chat_id: str
    participant_ids: tuple[str, str]
    initiator_id: str
    initiator_name: str | None = None
    partner_name: str | None = None
    type: str
    offered_text: str
    requested_text: str
    place_name: str | None = None
    guests: str
    scheduled_for: datetime | None = None
    content_deadline: datetime | None = None
    status: str
    checked_in_user_ids: list[str] = []
    reviews_count: int = 0
    content_proofs_count: int = 0
    cancellation_reason: str | None = None
    repeated_from_deal_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DealListResponse(BaseModel):
    deals: list[AdminDealRead]
    total: int
    status_counts: dict[str, int] = {}


class AdminDealStatusUpdate(BaseModel):
    status: str
    reason: str | None = None


class ReportItem(BaseModel):
    id: str
    reporter_id: str
    reporter_name: str | None = None
    reported_user_id: str
    reported_user_name: str | None = None
    reason: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportListResponse(BaseModel):
    reports: list[ReportItem]
    total: int
