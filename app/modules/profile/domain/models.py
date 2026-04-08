from __future__ import annotations

from dataclasses import dataclass, field

from app.core.time import utc_now


@dataclass
class Profile:
    user_id: str
    display_name: str
    photo_urls: list[str]
    primary_photo_url: str
    country: str | None = None
    instagram_handle: str | None = None
    tiktok_handle: str | None = None
    audience_size: int | None = None
    category: str | None = None
    district: str | None = None
    website: str | None = None
    niches: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    bio: str | None = None
    description: str | None = None
    what_we_offer: str | None = None
    collab_type: str = "both"
    badges: list[str] = field(default_factory=list)
    verified_visits: int = 0
    rating: float | None = None
    review_count: int = 0
    created_at: object = field(default_factory=utc_now)
    updated_at: object = field(default_factory=utc_now)
