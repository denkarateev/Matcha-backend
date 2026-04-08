from __future__ import annotations

from typing import Protocol

from app.modules.chats.domain.models import Chat, Message


class ChatRepository(Protocol):
    def add_chat(self, chat: Chat) -> Chat: ...

    def update_chat(self, chat: Chat) -> Chat: ...

    def get_by_id(self, chat_id: str) -> Chat | None: ...

    def get_by_pair(self, user_a_id: str, user_b_id: str) -> Chat | None: ...

    def list_for_user(self, user_id: str) -> list[Chat]: ...

    def add_message(self, message: Message) -> Message: ...

    def list_messages(self, chat_id: str) -> list[Message]: ...

    def delete_chat(self, chat_id: str) -> None: ...


class InMemoryChatRepository:
    def __init__(self, store):
        self.store = store

    def add_chat(self, chat: Chat) -> Chat:
        self.store.chats[chat.id] = chat
        return chat

    def update_chat(self, chat: Chat) -> Chat:
        self.store.chats[chat.id] = chat
        return chat

    def get_by_id(self, chat_id: str) -> Chat | None:
        return self.store.chats.get(chat_id)

    def get_by_pair(self, user_a_id: str, user_b_id: str) -> Chat | None:
        pair = tuple(sorted((user_a_id, user_b_id)))
        return next(
            (chat for chat in self.store.chats.values() if chat.participant_ids == pair),
            None,
        )

    def list_for_user(self, user_id: str) -> list[Chat]:
        chats = [chat for chat in self.store.chats.values() if user_id in chat.participant_ids]
        return sorted(chats, key=lambda item: item.updated_at, reverse=True)

    def add_message(self, message: Message) -> Message:
        self.store.messages[message.id] = message
        self.store.persist()
        return message

    def list_messages(self, chat_id: str) -> list[Message]:
        messages = [
            message
            for message in self.store.messages.values()
            if message.chat_id == chat_id
        ]
        return sorted(messages, key=lambda item: item.created_at)

    def delete_chat(self, chat_id: str) -> None:
        self.store.chats.pop(chat_id, None)
        # Remove all messages belonging to this chat
        msg_ids = [
            mid for mid, msg in self.store.messages.items() if msg.chat_id == chat_id
        ]
        for mid in msg_ids:
            del self.store.messages[mid]
        self.store.persist()
