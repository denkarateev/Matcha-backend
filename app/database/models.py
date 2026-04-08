"""
SQLAlchemy ORM models for MATCHA backend.

All timestamps are stored as UTC in the database. WITA (UTC+8)
conversions happen at the service/business-logic layer only.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums (use Python str-enums for clean Alembic support)
# ---------------------------------------------------------------------------

UserRoleEnum = Enum("blogger", "business", name="user_role_enum")
VerificationLevelEnum = Enum("0", "1", "2", name="verification_level_enum")
PlanTierEnum = Enum("free", "pro", "black", name="plan_tier_enum")
SwipeDirectionEnum = Enum("left", "right", "super", name="swipe_direction_enum")
MatchSourceEnum = Enum("swipe", "offer", name="match_source_enum")
OfferTypeEnum = Enum("barter", "paid", name="offer_type_enum")
OfferStatusEnum = Enum("active", "closed", "expired", name="offer_status_enum")
OfferResponseStatusEnum = Enum(
    "pending", "accepted", "declined", name="offer_response_status_enum"
)
DealStatusEnum = Enum(
    "draft",
    "confirmed",
    "visited",
    "no_show",
    "reviewed",
    "cancelled",
    name="deal_status_enum",
)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("blogger", "business", name="user_role_enum"),
        nullable=False,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    verification_level: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="0=shadow, 1=verified, 2=blue_check"
    )
    plan_tier: Mapped[str] = mapped_column(
        Enum("free", "pro", "black", name="plan_tier_enum"),
        nullable=False,
        default="free",
    )
    offer_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    profile: Mapped["Profile | None"] = relationship(
        "Profile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    swipes_made: Mapped[list["Swipe"]] = relationship(
        "Swipe", foreign_keys="Swipe.swiper_id", back_populates="swiper",
        cascade="all, delete-orphan",
    )
    swipes_received: Mapped[list["Swipe"]] = relationship(
        "Swipe", foreign_keys="Swipe.swiped_id", back_populates="swiped",
        cascade="all, delete-orphan",
    )
    messages_sent: Mapped[list["Message"]] = relationship(
        "Message", back_populates="sender"
    )

    @property
    def is_verified(self) -> bool:
        return self.verification_level >= 1

    def __repr__(self) -> str:
        return f"<User id={self.id!r} email={self.email!r} role={self.role!r}>"


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

class Profile(Base):
    __tablename__ = "profiles"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    what_we_offer: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Photos stored as comma-separated URLs; use ARRAY on Postgres.
    photo_urls: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )
    primary_photo_url: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Social / discovery
    niches: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    audience_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location_district: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    instagram_handle: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tiktok_handle: Mapped[str | None] = mapped_column(String(100), nullable=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    languages: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)

    # Collab
    collab_type: Mapped[str] = mapped_column(String(50), nullable=False, default="both")
    collab_types: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    completed_collabs_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Gamification
    badges: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    verified_visits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rating: Mapped[float | None] = mapped_column(nullable=True)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="profile")

    def __repr__(self) -> str:
        return f"<Profile user_id={self.user_id!r} display_name={self.display_name!r}>"


# ---------------------------------------------------------------------------
# Swipe
# ---------------------------------------------------------------------------

class Swipe(Base):
    __tablename__ = "swipes"
    __table_args__ = (
        UniqueConstraint("swiper_id", "swiped_id", name="uq_swipes_pair"),
        CheckConstraint("swiper_id != swiped_id", name="ck_swipes_no_self_swipe"),
        Index("ix_swipes_swiper_id", "swiper_id"),
        Index("ix_swipes_swiped_id", "swiped_id"),
        Index(
            "ix_swipes_positive_undelivered",
            "swiper_id",
            "delivered",
            postgresql_where="direction IN ('right', 'super') AND delivered = false",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    swiper_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    swiped_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[str] = mapped_column(
        Enum("left", "right", "super", name="swipe_direction_enum"),
        nullable=False,
    )
    delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    swiper: Mapped["User"] = relationship(
        "User", foreign_keys=[swiper_id], back_populates="swipes_made"
    )
    swiped: Mapped["User"] = relationship(
        "User", foreign_keys=[swiped_id], back_populates="swipes_received"
    )

    def __repr__(self) -> str:
        return (
            f"<Swipe id={self.id!r} swiper={self.swiper_id!r} "
            f"swiped={self.swiped_id!r} dir={self.direction!r}>"
        )


# ---------------------------------------------------------------------------
# Match
# ---------------------------------------------------------------------------

class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        CheckConstraint("user1_id != user2_id", name="ck_matches_no_self_match"),
        Index("ix_matches_user1_id", "user1_id"),
        Index("ix_matches_user2_id", "user2_id"),
        Index("ix_matches_active", "is_active", postgresql_where="is_active = true"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user1_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    user2_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(
        Enum("swipe", "offer", name="match_source_enum"),
        nullable=False,
        default="swipe",
    )
    first_message_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    conversation: Mapped["Conversation | None"] = relationship(
        "Conversation", back_populates="match", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Match id={self.id!r} u1={self.user1_id!r} u2={self.user2_id!r} "
            f"src={self.source!r}>"
        )


# ---------------------------------------------------------------------------
# Offer
# ---------------------------------------------------------------------------

class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (
        Index("ix_offers_business_id", "business_id"),
        Index("ix_offers_active", "is_active", postgresql_where="is_active = true"),
        Index("ix_offers_type", "type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(
        Enum("barter", "paid", name="offer_type_enum"),
        nullable=False,
    )
    blogger_receives: Mapped[str] = mapped_column(Text, nullable=False, default="")
    business_receives: Mapped[str] = mapped_column(Text, nullable=False, default="")
    photo_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    slots_total: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    slots_remaining: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    preferred_blogger_niche: Mapped[str | None] = mapped_column(String(100), nullable=True)
    min_audience: Mapped[str | None] = mapped_column(String(50), nullable=True)
    guests: Mapped[str | None] = mapped_column(String(100), nullable=True)
    special_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_last_minute: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(
        Enum("active", "closed", "expired", name="offer_status_enum"),
        nullable=False,
        default="active",
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    responses: Mapped[list["OfferResponse"]] = relationship(
        "OfferResponse", back_populates="offer", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Offer id={self.id!r} title={self.title!r} type={self.type!r}>"


# ---------------------------------------------------------------------------
# OfferResponse
# ---------------------------------------------------------------------------

class OfferResponse(Base):
    __tablename__ = "offer_responses"
    __table_args__ = (
        UniqueConstraint("offer_id", "blogger_id", name="uq_offer_responses_pair"),
        Index("ix_offer_responses_offer_id", "offer_id"),
        Index("ix_offer_responses_blogger_id", "blogger_id"),
        Index("ix_offer_responses_business_id", "business_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    offer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    blogger_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Enum("pending", "accepted", "declined", name="offer_response_status_enum"),
        nullable=False,
        default="pending",
        index=True,
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    offer: Mapped["Offer"] = relationship("Offer", back_populates="responses")

    def __repr__(self) -> str:
        return (
            f"<OfferResponse id={self.id!r} offer={self.offer_id!r} "
            f"blogger={self.blogger_id!r} status={self.status!r}>"
        )


# ---------------------------------------------------------------------------
# Conversation  (replaces Chat for clarity)
# ---------------------------------------------------------------------------

class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_match_id", "match_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    match_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("matches.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    # Denormalized for quick lookups (always sorted: user1 < user2 lexicographically)
    participant1_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    participant2_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    match: Mapped["Match | None"] = relationship("Match", back_populates="conversation")
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    def __repr__(self) -> str:
        return f"<Conversation id={self.id!r} match_id={self.match_id!r}>"


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------

class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_id", "conversation_id"),
        Index("ix_messages_sender_id", "sender_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    media_urls: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )
    sender: Mapped["User"] = relationship("User", back_populates="messages_sent")

    def __repr__(self) -> str:
        return f"<Message id={self.id!r} conv={self.conversation_id!r}>"


# ---------------------------------------------------------------------------
# Deal
# ---------------------------------------------------------------------------

class Deal(Base):
    __tablename__ = "deals"
    __table_args__ = (
        Index("ix_deals_influencer_id", "influencer_id"),
        Index("ix_deals_business_id", "business_id"),
        Index("ix_deals_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # The chat/conversation that spawned this deal
    conversation_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    offer_type: Mapped[str] = mapped_column(
        Enum("barter", "paid", name="offer_type_enum"),
        nullable=False,
    )
    influencer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    initiator_id: Mapped[str] = mapped_column(String(36), nullable=False)
    offered_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    requested_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    place_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    guests: Mapped[str] = mapped_column(String(50), nullable=False, default="solo")
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    content_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        Enum(
            "draft", "confirmed", "visited", "no_show", "reviewed", "cancelled",
            name="deal_status_enum",
        ),
        nullable=False,
        default="draft",
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    visited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    reviews: Mapped[list["DealReview"]] = relationship(
        "DealReview", back_populates="deal", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Deal id={self.id!r} status={self.status!r}>"


# ---------------------------------------------------------------------------
# DealReview
# ---------------------------------------------------------------------------

class DealReview(Base):
    __tablename__ = "deal_reviews"
    __table_args__ = (
        UniqueConstraint("deal_id", "reviewer_id", name="uq_deal_reviews_pair"),
        Index("ix_deal_reviews_deal_id", "deal_id"),
        Index("ix_deal_reviews_reviewer_id", "reviewer_id"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_deal_reviews_rating"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    deal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reviewee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    punctuality: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offer_match: Mapped[int | None] = mapped_column(Integer, nullable=True)
    communication: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    deal: Mapped["Deal"] = relationship("Deal", back_populates="reviews")

    def __repr__(self) -> str:
        return (
            f"<DealReview id={self.id!r} deal={self.deal_id!r} "
            f"reviewer={self.reviewer_id!r} rating={self.rating!r}>"
        )
