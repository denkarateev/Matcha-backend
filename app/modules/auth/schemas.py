from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.auth.domain.models import PlanTier, UserRole, VerificationLevel


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: UserRole
    full_name: str = Field(min_length=1, max_length=50)
    primary_photo_url: str = Field(min_length=1)
    category: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class VerifyUserRequest(BaseModel):
    instagram_handle: str = Field(min_length=1)
    tiktok_handle: str | None = None
    audience_size: int = Field(ge=1)


class UserRead(BaseModel):
    id: str
    email: EmailStr
    role: UserRole
    full_name: str
    is_active: bool
    verification_level: VerificationLevel
    plan_tier: PlanTier
    offer_credits: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuthTokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class PhotoUploadRead(BaseModel):
    url: str
