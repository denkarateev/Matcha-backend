from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.time import utc_now
from app.modules.auth.repository import AuthRepository
from app.modules.chats.domain.models import Chat, Message
from app.modules.chats.repository import ChatRepository
from app.modules.chats.schemas import MessageCreateRequest
from app.modules.deals.domain.models import DealStatus
from app.modules.deals.repository import DealRepository
from app.modules.matches.repository import MatchRepository


class ChatService:
    def __init__(
        self,
        chat_repo: ChatRepository,
        auth_repo: AuthRepository,
        match_repo: MatchRepository,
        deal_repo: DealRepository,
    ):
        self.chat_repo = chat_repo
        self.auth_repo = auth_repo
        self.match_repo = match_repo
        self.deal_repo = deal_repo

    def ensure_direct_chat(
        self,
        user_a_id: str,
        user_b_id: str,
        match_id: str | None = None,
    ) -> Chat:
        self._get_user(user_a_id)
        self._get_user(user_b_id)
        existing = self.chat_repo.get_by_pair(user_a_id, user_b_id)
        if existing:
            if match_id and existing.match_id is None:
                updated = replace(existing, match_id=match_id, updated_at=utc_now())
                return self.chat_repo.update_chat(updated)
            return existing

        chat = Chat(
            id=str(uuid4()),
            participant_ids=tuple(sorted((user_a_id, user_b_id))),
            match_id=match_id,
        )
        return self.chat_repo.add_chat(chat)

    def list_chats(self, user_id: str) -> list[Chat]:
        self._get_user(user_id)
        return self.chat_repo.list_for_user(user_id)

    def get_chat(self, user_id: str, chat_id: str) -> tuple[Chat, list[Message]]:
        chat = self.chat_repo.get_by_id(chat_id)
        if not chat:
            raise NotFoundError("Chat not found.")
        if user_id not in chat.participant_ids:
            raise ForbiddenError("You are not a participant of this chat.")
        return chat, self.chat_repo.list_messages(chat_id)

    def assert_can_send_message(self, user_id: str, chat_id: str) -> Chat:
        chat, messages = self.get_chat(user_id, chat_id)
        self._ensure_sender_can_write(user_id, chat, messages)
        return chat

    def send_message(
        self,
        user_id: str,
        chat_id: str,
        payload: MessageCreateRequest,
    ) -> Message:
        text = getattr(payload, "resolved_text", lambda: payload.text or "")()
        image_url = getattr(payload, "image_url", None)
        deal_card_id = getattr(payload, "deal_card_id", None)
        if not text and not image_url and not deal_card_id and not getattr(payload, "media_urls", []):
            from app.core.exceptions import ConflictError as _CE
            raise _CE("Message must contain text, image_url, or deal_card_id.")

        chat, messages = self.get_chat(user_id, chat_id)
        self._ensure_sender_can_write(user_id, chat, messages)

        message = Message(
            id=str(uuid4()),
            chat_id=chat_id,
            sender_id=user_id,
            text=text,
            media_urls=getattr(payload, "media_urls", []),
            image_url=image_url,
            deal_card_id=deal_card_id,
        )
        self.chat_repo.add_message(message)
        self.chat_repo.update_chat(replace(chat, updated_at=utc_now()))
        return message

    def send_deal_card(
        self,
        user_id: str,
        chat_id: str,
        deal_card_id: str,
        text: str = "",
    ) -> Message:
        chat, messages = self.get_chat(user_id, chat_id)
        self._ensure_sender_can_write(user_id, chat, messages)

        message = Message(
            id=str(uuid4()),
            chat_id=chat_id,
            sender_id=user_id,
            text=text,
            deal_card_id=deal_card_id,
        )
        self.chat_repo.add_message(message)
        self.chat_repo.update_chat(replace(chat, updated_at=utc_now()))
        return message

    def inject_system_message(self, chat_id: str, text: str) -> Message:
        """Insert a system message into a chat (for deal status changes, etc.)."""
        chat = self.chat_repo.get_by_id(chat_id)
        if not chat:
            raise NotFoundError("Chat not found.")

        message = Message(
            id=str(uuid4()),
            chat_id=chat_id,
            sender_id="system",
            text=text,
            is_system=True,
            message_type="deal_status",
        )
        self.chat_repo.add_message(message)
        self.chat_repo.update_chat(replace(chat, updated_at=utc_now()))
        return message

    def mute_chat(self, user_id: str, chat_id: str) -> Chat:
        """Add user_id to chat.muted_user_ids."""
        chat = self.chat_repo.get_by_id(chat_id)
        if not chat:
            raise NotFoundError("Chat not found.")
        if user_id not in chat.participant_ids:
            raise ForbiddenError("You are not a participant of this chat.")
        updated_muted = chat.muted_user_ids | {user_id}
        updated = replace(chat, muted_user_ids=updated_muted, updated_at=utc_now())
        return self.chat_repo.update_chat(updated)

    def unmute_chat(self, user_id: str, chat_id: str) -> Chat:
        """Remove user_id from chat.muted_user_ids."""
        chat = self.chat_repo.get_by_id(chat_id)
        if not chat:
            raise NotFoundError("Chat not found.")
        if user_id not in chat.participant_ids:
            raise ForbiddenError("You are not a participant of this chat.")
        updated_muted = chat.muted_user_ids - {user_id}
        updated = replace(chat, muted_user_ids=updated_muted, updated_at=utc_now())
        return self.chat_repo.update_chat(updated)

    def unmatch_chat(self, user_id: str, chat_id: str) -> None:
        """
        Unmatch: remove chat and match between participants.

        1. Verify participant
        2. Check for VISITED deals (blocks unmatch)
        3. Auto-cancel any DRAFT/CONFIRMED deals for the pair
        4. Remove chat and match
        """
        chat = self.chat_repo.get_by_id(chat_id)
        if not chat:
            raise NotFoundError("Chat not found.")
        if user_id not in chat.participant_ids:
            raise ForbiddenError("You are not a participant of this chat.")

        user_a_id, user_b_id = chat.participant_ids

        # Block if any VISITED deals exist
        blocking = self.deal_repo.get_blocking_deals_for_pair(user_a_id, user_b_id)
        if blocking:
            raise ConflictError(
                "Cannot unmatch while there are active visited deals."
            )

        # Auto-cancel DRAFT / CONFIRMED deals
        for deal in self.deal_repo.list_for_pair(user_a_id, user_b_id):
            if deal.status in {DealStatus.DRAFT, DealStatus.CONFIRMED}:
                cancelled = replace(
                    deal,
                    status=DealStatus.CANCELLED,
                    cancellation_reason="unmatch",
                    updated_at=utc_now(),
                )
                self.deal_repo.update(cancelled)

        # Remove match
        if chat.match_id:
            self.match_repo.delete_match(chat.match_id)

        # Remove chat and its messages
        self.chat_repo.delete_chat(chat_id)

    def get_quick_replies(self, user_id: str, chat_id: str) -> list[str]:
        """
        Return contextual quick-reply suggestions based on deal status,
        user role, and whether the first message has been sent.
        """
        chat, messages = self.get_chat(user_id, chat_id)
        user = self._get_user(user_id)
        is_blogger = user.role.value == "blogger"

        # Find partner
        partner_id = chat.participant_ids[0] if chat.participant_ids[1] == user_id else chat.participant_ids[1]

        # Check for active deal between the pair
        deal = self.deal_repo.get_active_for_pair(user_id, partner_id)

        if deal is not None:
            is_initiator = deal.initiator_id == user_id

            if deal.status == DealStatus.DRAFT:
                if is_initiator:
                    return [
                        "Just checking in on the deal",
                        "Any updates?",
                        "Let me know if you need changes",
                    ]
                else:
                    return [
                        "Looks great, accepting!",
                        "Can we adjust the terms?",
                        "What dates work for you?",
                    ]

            if deal.status == DealStatus.CONFIRMED:
                return [
                    "See you there!",
                    "Looking forward to it",
                    "Quick question about the visit",
                ]

            if deal.status == DealStatus.VISITED:
                return [
                    "Had a great time!",
                    "Content will be ready soon",
                    "Thanks for hosting!",
                ]

        # No active deal — first message templates
        participant_messages = [
            m for m in messages if not m.is_system and m.sender_id != "system"
        ]
        has_messages = len(participant_messages) > 0

        if not has_messages:
            if is_blogger:
                return [
                    "Hi! I'd love to collaborate",
                    "Hey! Love your venue",
                    "Interested in a collab?",
                ]
            else:
                return [
                    "Thanks for your interest!",
                    "Let's discuss a collab",
                    "What content do you create?",
                ]

        # Conversation already ongoing, no active deal — return empty
        return []

    def _get_user(self, user_id: str):
        user = self.auth_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found.")
        return user

    def _ensure_sender_can_write(
        self,
        user_id: str,
        chat: Chat,
        messages: list[Message],
    ) -> None:
        participant_messages = [
            message
            for message in messages
            if not message.is_system and message.sender_id != "system"
        ]
        if participant_messages or not chat.match_id:
            return

        match = self.match_repo.get_match_by_pair(*chat.participant_ids)
        if match and match.first_message_by and match.first_message_by != user_id:
            raise ConflictError("The other participant must write first for this match.")
