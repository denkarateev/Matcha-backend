"""
Chats router.

Endpoints
---------
GET  /chats                         — Chat home: list all chats (matches + conversations)
GET  /chats/{chat_id}               — Full chat detail with messages
GET  /chats/{chat_id}/messages      — Messages for a chat (iOS primary path)
POST /chats/{chat_id}/messages      — Send a message
GET  /chats/{chat_id}/quick-replies — Contextual quick-reply suggestions
POST /chats/{chat_id}/mute          — Mute a chat for the current user
POST /chats/{chat_id}/unmute        — Unmute a chat for the current user
POST /chats/{chat_id}/unmatch       — Unmatch: cancel deals, remove chat and match
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Annotated

from app.core.container import AppContainer
from app.core.dependencies import get_container, get_current_user_id
from app.modules.chats.schemas import (
    ChatDetailRead,
    ChatRead,
    MessageCreateRequest,
    MessageRead,
    QuickRepliesRead,
)

router = APIRouter(prefix="/chats", tags=["chats"])


# ---------------------------------------------------------------------------
# Chat list  — the "Chat Home" screen
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ChatRead])
def list_chats(
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> list[ChatRead]:
    """
    Return all chats for the current user (matched + in-progress conversations).
    Each chat exposes participant_ids and match_id so the iOS client can resolve
    profile cards for the chat list header.
    """
    chats = container.chat_service.list_chats(current_user_id)
    return [ChatRead.model_validate(chat) for chat in chats]


# ---------------------------------------------------------------------------
# Create chat (for first message from a match)
# ---------------------------------------------------------------------------

class CreateChatRequest(BaseModel):
    partner_id: str
    match_id: str | None = None


@router.post("", response_model=ChatRead, status_code=201)
def create_chat(
    payload: CreateChatRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> ChatRead:
    """Create or return existing chat between current user and partner."""
    chat = container.chat_service.ensure_direct_chat(
        current_user_id, payload.partner_id, match_id=payload.match_id
    )
    return ChatRead.model_validate(chat)


# ---------------------------------------------------------------------------
# Chat detail
# ---------------------------------------------------------------------------

@router.get("/{chat_id}", response_model=ChatDetailRead)
def get_chat(
    chat_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> ChatDetailRead:
    """Return a single chat with its full message history."""
    chat, messages = container.chat_service.get_chat(current_user_id, chat_id)
    return ChatDetailRead(
        **ChatRead.model_validate(chat).model_dump(),
        messages=[MessageRead.model_validate(message) for message in messages],
    )


# ---------------------------------------------------------------------------
# Messages sub-resource  (iOS uses these two endpoints directly)
# ---------------------------------------------------------------------------

@router.get("/{chat_id}/messages", response_model=list[MessageRead])
def list_messages(
    chat_id: str,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> list[MessageRead]:
    """
    Return messages for a chat, newest-last, paginated.

    Query params:
      limit  — max messages to return (default 50)
      offset — skip first N messages
    """
    _, messages = container.chat_service.get_chat(current_user_id, chat_id)
    # Messages are stored oldest-first; honour that ordering for the client
    paged = messages[offset: offset + limit]
    return [MessageRead.model_validate(msg) for msg in paged]


@router.post("/{chat_id}/messages", response_model=MessageRead)
def send_message(
    chat_id: str,
    payload: MessageCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> MessageRead:
    """Send a new message to the chat."""
    message = container.chat_service.send_message(current_user_id, chat_id, payload)
    return MessageRead.model_validate(message)


# ---------------------------------------------------------------------------
# Quick Replies
# ---------------------------------------------------------------------------

@router.get("/{chat_id}/quick-replies", response_model=QuickRepliesRead)
def get_quick_replies(
    chat_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> QuickRepliesRead:
    """
    Return contextual quick-reply suggestions for the chat.

    Based on deal status, user role, and conversation state.
    """
    replies = container.chat_service.get_quick_replies(current_user_id, chat_id)
    return QuickRepliesRead(replies=replies)


# ---------------------------------------------------------------------------
# Mute / Unmute / Unmatch
# ---------------------------------------------------------------------------

@router.post("/{chat_id}/mute", response_model=ChatRead)
def mute_chat(
    chat_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> ChatRead:
    """Mute a chat for the current user."""
    chat = container.chat_service.mute_chat(current_user_id, chat_id)
    return ChatRead.model_validate(chat)


@router.post("/{chat_id}/unmute", response_model=ChatRead)
def unmute_chat(
    chat_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> ChatRead:
    """Unmute a chat for the current user."""
    chat = container.chat_service.unmute_chat(current_user_id, chat_id)
    return ChatRead.model_validate(chat)


@router.post("/{chat_id}/unmatch")
def unmatch_chat(
    chat_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> dict:
    """Unmatch: cancel deals, remove chat and match."""
    container.chat_service.unmatch_chat(current_user_id, chat_id)
    return {"detail": "Unmatched successfully."}
