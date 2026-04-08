from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class ProfileUpdateRequest(BaseModel):
    """
    Profile update payload.

    Accepts both the original field names and the iOS-friendly aliases:
      name              → display_name
      photo_url         → primary_photo_url (single-photo shortcut)
      collaboration_type → collab_type
    """
    # Core fields
    display_name: str | None = Field(default=None, min_length=1, max_length=50)
    photo_urls: list[str] | None = None
    primary_photo_url: str | None = None
    country: str | None = None
    instagram_handle: str | None = None
    tiktok_handle: str | None = None
    audience_size: int | None = Field(default=None, ge=1)
    category: str | None = None
    district: str | None = None
    website: HttpUrl | None = None
    niches: list[str] | None = None
    languages: list[str] | None = None
    bio: str | None = Field(default=None, max_length=150)
    description: str | None = Field(default=None, max_length=200)
    what_we_offer: str | None = Field(default=None, max_length=200)
    collab_type: str | None = None

    # iOS-friendly aliases (resolved via validator below)
    name: str | None = Field(default=None, min_length=1, max_length=50, exclude=True)
    photo_url: str | None = Field(default=None, exclude=True)
    collaboration_type: str | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def _resolve_aliases(self) -> "ProfileUpdateRequest":
        if self.name is not None and self.display_name is None:
            self.display_name = self.name
        if self.photo_url is not None and self.primary_photo_url is None:
            self.primary_photo_url = self.photo_url
        if self.collaboration_type is not None and self.collab_type is None:
            self.collab_type = self.collaboration_type
        return self


class ProfileRead(BaseModel):
    user_id: str
    role: str
    display_name: str
    photo_urls: list[str]
    primary_photo_url: str
    country: str | None
    instagram_handle: str | None
    tiktok_handle: str | None
    audience_size: int | None
    category: str | None
    district: str | None
    website: str | None
    niches: list[str]
    languages: list[str]
    bio: str | None
    description: str | None
    what_we_offer: str | None
    collab_type: str
    badges: list[str]
    verified_visits: int
    rating: float | None
    review_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
