from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageCreateRequest(BaseModel):
    text: str | None = Field(default=None, max_length=1000)
    image_url: str | None = Field(default=None, max_length=500)
    deal_card_id: str | None = None
    # Legacy field
    media_urls: list[str] = Field(default_factory=list)

    def resolved_text(self) -> str:
        return self.text or ""


class MessageRead(BaseModel):
    id: str
    chat_id: str
    sender_id: str
    text: str
    media_urls: list[str]
    image_url: str | None
    deal_card_id: str | None
    is_system: bool = False
    message_type: str = "text"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatRead(BaseModel):
    id: str
    participant_ids: tuple[str, str]
    match_id: str | None
    muted_user_ids: set[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatDetailRead(ChatRead):
    messages: list[MessageRead]


class QuickRepliesRead(BaseModel):
    replies: list[str]
