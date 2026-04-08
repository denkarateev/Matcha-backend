"""
PostgreSQL-backed repositories for Conversation and Message entities.

Note: The domain model uses 'Chat' terminology but the DB uses 'Conversation'.
This mapper bridges both.

Two flavours:
  - ``ConversationRepository``  — async
  - ``SyncDBChatRepository`` — sync, implements ``ChatRepository``
    Protocol for the synchronous service layer.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import Conversation as ConversationORM
from app.database.models import Message as MessageORM
from app.modules.chats.domain.models import Chat, Message


def _conv_orm_to_domain(row: ConversationORM) -> Chat:
    return Chat(
        id=row.id,
        participant_ids=(row.participant1_id, row.participant2_id),
        match_id=row.match_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _msg_orm_to_domain(row: MessageORM) -> Message:
    return Message(
        id=row.id,
        chat_id=row.conversation_id,
        sender_id=row.sender_id,
        text=row.content,
        media_urls=list(row.media_urls or []),
        created_at=row.created_at,
    )


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_chat(self, chat: Chat) -> Chat:
        p1, p2 = sorted(chat.participant_ids)
        row = ConversationORM(
            id=chat.id,
            match_id=chat.match_id,
            participant1_id=p1,
            participant2_id=p2,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _conv_orm_to_domain(row)

    async def update_chat(self, chat: Chat) -> Chat:
        row = await self._session.get(ConversationORM, chat.id)
        if row is None:
            raise ValueError(f"Conversation {chat.id!r} not found.")
        if chat.match_id:
            row.match_id = chat.match_id
        await self._session.flush()
        await self._session.refresh(row)
        return _conv_orm_to_domain(row)

    async def get_by_id(self, chat_id: str) -> Chat | None:
        row = await self._session.get(ConversationORM, chat_id)
        return _conv_orm_to_domain(row) if row else None

    async def get_by_pair(self, user_a_id: str, user_b_id: str) -> Chat | None:
        p1, p2 = sorted((user_a_id, user_b_id))
        stmt = select(ConversationORM).where(
            ConversationORM.participant1_id == p1,
            ConversationORM.participant2_id == p2,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _conv_orm_to_domain(row) if row else None

    async def list_for_user(self, user_id: str) -> list[Chat]:
        stmt = (
            select(ConversationORM)
            .where(
                or_(
                    ConversationORM.participant1_id == user_id,
                    ConversationORM.participant2_id == user_id,
                )
            )
            .order_by(ConversationORM.updated_at.desc())
        )
        result = await self._session.execute(stmt)
        return [_conv_orm_to_domain(row) for row in result.scalars().all()]

    async def add_message(self, message: Message) -> Message:
        row = MessageORM(
            id=message.id,
            conversation_id=message.chat_id,
            sender_id=message.sender_id,
            content=message.text,
            media_urls=message.media_urls,
        )
        self._session.add(row)

        # Touch conversation updated_at for inbox ordering
        conv = await self._session.get(ConversationORM, message.chat_id)
        if conv:
            from datetime import datetime, timezone
            conv.updated_at = datetime.now(timezone.utc)

        await self._session.flush()
        await self._session.refresh(row)
        return _msg_orm_to_domain(row)

    async def list_messages(self, chat_id: str) -> list[Message]:
        stmt = (
            select(MessageORM)
            .where(MessageORM.conversation_id == chat_id)
            .order_by(MessageORM.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return [_msg_orm_to_domain(row) for row in result.scalars().all()]


# ---------------------------------------------------------------------------
# Sync repository  — implements ChatRepository Protocol
# ---------------------------------------------------------------------------

class SyncDBChatRepository:
    """
    Synchronous PostgreSQL repository for Conversation + Message entities.

    Implements the ``ChatRepository`` Protocol used by ``ChatService``.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sf = session_factory

    # -- ChatRepository Protocol ---------------------------------------------

    def add_chat(self, chat: Chat) -> Chat:
        with self._sf() as session:
            p1, p2 = sorted(chat.participant_ids)
            row = ConversationORM(
                id=chat.id,
                match_id=chat.match_id,
                participant1_id=p1,
                participant2_id=p2,
            )
            session.add(row)
            session.flush()
            session.refresh(row)
            result = _conv_orm_to_domain(row)
            session.commit()
            return result

    def update_chat(self, chat: Chat) -> Chat:
        with self._sf() as session:
            row = session.get(ConversationORM, chat.id)
            if row is None:
                raise ValueError(f"Conversation {chat.id!r} not found.")
            if chat.match_id:
                row.match_id = chat.match_id
            session.flush()
            session.refresh(row)
            result = _conv_orm_to_domain(row)
            session.commit()
            return result

    def get_by_id(self, chat_id: str) -> Chat | None:
        with self._sf() as session:
            row = session.get(ConversationORM, chat_id)
            return _conv_orm_to_domain(row) if row else None

    def get_by_pair(self, user_a_id: str, user_b_id: str) -> Chat | None:
        with self._sf() as session:
            p1, p2 = sorted((user_a_id, user_b_id))
            stmt = select(ConversationORM).where(
                ConversationORM.participant1_id == p1,
                ConversationORM.participant2_id == p2,
            )
            row = session.execute(stmt).scalar_one_or_none()
            return _conv_orm_to_domain(row) if row else None

    def list_for_user(self, user_id: str) -> list[Chat]:
        with self._sf() as session:
            stmt = (
                select(ConversationORM)
                .where(
                    or_(
                        ConversationORM.participant1_id == user_id,
                        ConversationORM.participant2_id == user_id,
                    )
                )
                .order_by(ConversationORM.updated_at.desc())
            )
            return [_conv_orm_to_domain(row) for row in session.execute(stmt).scalars().all()]

    def add_message(self, message: Message) -> Message:
        with self._sf() as session:
            row = MessageORM(
                id=message.id,
                conversation_id=message.chat_id,
                sender_id=message.sender_id,
                content=message.text,
                media_urls=message.media_urls,
            )
            session.add(row)

            # Touch conversation updated_at for inbox ordering
            conv = session.get(ConversationORM, message.chat_id)
            if conv:
                conv.updated_at = datetime.now(timezone.utc)

            session.flush()
            session.refresh(row)
            result = _msg_orm_to_domain(row)
            session.commit()
            return result

    def list_messages(self, chat_id: str) -> list[Message]:
        with self._sf() as session:
            stmt = (
                select(MessageORM)
                .where(MessageORM.conversation_id == chat_id)
                .order_by(MessageORM.created_at.asc())
            )
            return [_msg_orm_to_domain(row) for row in session.execute(stmt).scalars().all()]

    def delete_chat(self, chat_id: str) -> None:
        with self._sf() as session:
            # Delete all messages first
            msgs_stmt = select(MessageORM).where(MessageORM.conversation_id == chat_id)
            for msg in session.execute(msgs_stmt).scalars().all():
                session.delete(msg)
            # Delete conversation
            row = session.get(ConversationORM, chat_id)
            if row is not None:
                session.delete(row)
            session.commit()
