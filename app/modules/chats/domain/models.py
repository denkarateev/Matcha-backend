from __future__ import annotations

from dataclasses import dataclass, field

from app.core.time import utc_now


@dataclass
class Chat:
    id: str
    participant_ids: tuple[str, str]
    match_id: str | None = None
    muted_user_ids: set[str] = field(default_factory=set)
    created_at: object = field(default_factory=utc_now)
    updated_at: object = field(default_factory=utc_now)


@dataclass
class Message:
    id: str
    chat_id: str
    sender_id: str
    text: str
    media_urls: list[str] = field(default_factory=list)
    image_url: str | None = None
    deal_card_id: str | None = None
    is_system: bool = False
    message_type: str = "text"  # "text" | "deal_status"
    created_at: object = field(default_factory=utc_now)
