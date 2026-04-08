"""Initial schema — all MATCHA tables.

Revision ID: 001_initial
Revises: None
Create Date: 2026-04-09

Tables:
  users, profiles, swipes, matches, offers, offer_responses,
  conversations, messages, deals, deal_reviews
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Enums
    # ------------------------------------------------------------------
    user_role_enum = sa.Enum("blogger", "business", name="user_role_enum")
    plan_tier_enum = sa.Enum("free", "pro", "black", name="plan_tier_enum")
    swipe_direction_enum = sa.Enum("left", "right", "super", name="swipe_direction_enum")
    match_source_enum = sa.Enum("swipe", "offer", name="match_source_enum")
    offer_type_enum = sa.Enum("barter", "paid", name="offer_type_enum")
    offer_status_enum = sa.Enum("active", "closed", "expired", name="offer_status_enum")
    offer_response_status_enum = sa.Enum(
        "pending", "accepted", "declined", name="offer_response_status_enum"
    )
    deal_status_enum = sa.Enum(
        "draft", "confirmed", "visited", "no_show", "reviewed", "cancelled",
        name="deal_status_enum",
    )

    user_role_enum.create(op.get_bind(), checkfirst=True)
    plan_tier_enum.create(op.get_bind(), checkfirst=True)
    swipe_direction_enum.create(op.get_bind(), checkfirst=True)
    match_source_enum.create(op.get_bind(), checkfirst=True)
    offer_type_enum.create(op.get_bind(), checkfirst=True)
    offer_status_enum.create(op.get_bind(), checkfirst=True)
    offer_response_status_enum.create(op.get_bind(), checkfirst=True)
    deal_status_enum.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("blogger", "business", name="user_role_enum", create_type=False),
            nullable=False,
            index=True,
        ),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "verification_level",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
            comment="0=shadow, 1=verified, 2=blue_check",
        ),
        sa.Column(
            "plan_tier",
            sa.Enum("free", "pro", "black", name="plan_tier_enum", create_type=False),
            nullable=False,
            server_default="free",
        ),
        sa.Column("offer_credits", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ------------------------------------------------------------------
    # profiles
    # ------------------------------------------------------------------
    op.create_table(
        "profiles",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("bio", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("what_we_offer", sa.Text, nullable=True),
        sa.Column("photo_urls", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("primary_photo_url", sa.Text, nullable=False, server_default=""),
        sa.Column("niches", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("audience_size", sa.Integer, nullable=True),
        sa.Column("location_district", sa.String(100), nullable=True, index=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("instagram_handle", sa.String(100), nullable=True),
        sa.Column("tiktok_handle", sa.String(100), nullable=True),
        sa.Column("website", sa.Text, nullable=True),
        sa.Column("category", sa.String(100), nullable=True, index=True),
        sa.Column("languages", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("collab_type", sa.String(50), nullable=False, server_default="both"),
        sa.Column("collab_types", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column(
            "completed_collabs_count", sa.Integer, nullable=False, server_default=sa.text("0")
        ),
        sa.Column("badges", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("verified_visits", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("rating", sa.Float, nullable=True),
        sa.Column("review_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ------------------------------------------------------------------
    # swipes
    # ------------------------------------------------------------------
    op.create_table(
        "swipes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "swiper_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "swiped_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "direction",
            sa.Enum("left", "right", "super", name="swipe_direction_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("delivered", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("swiper_id", "swiped_id", name="uq_swipes_pair"),
        sa.CheckConstraint("swiper_id != swiped_id", name="ck_swipes_no_self_swipe"),
    )
    op.create_index("ix_swipes_swiper_id", "swipes", ["swiper_id"])
    op.create_index("ix_swipes_swiped_id", "swipes", ["swiped_id"])
    op.create_index(
        "ix_swipes_positive_undelivered",
        "swipes",
        ["swiper_id", "delivered"],
        postgresql_where=sa.text(
            "direction IN ('right', 'super') AND delivered = false"
        ),
    )

    # ------------------------------------------------------------------
    # matches
    # ------------------------------------------------------------------
    op.create_table(
        "matches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user1_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user2_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum("swipe", "offer", name="match_source_enum", create_type=False),
            nullable=False,
            server_default="swipe",
        ),
        sa.Column("first_message_by", sa.String(36), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("user1_id != user2_id", name="ck_matches_no_self_match"),
    )
    op.create_index("ix_matches_user1_id", "matches", ["user1_id"])
    op.create_index("ix_matches_user2_id", "matches", ["user2_id"])
    op.create_index(
        "ix_matches_active",
        "matches",
        ["is_active"],
        postgresql_where=sa.text("is_active = true"),
    )

    # ------------------------------------------------------------------
    # offers
    # ------------------------------------------------------------------
    op.create_table(
        "offers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "business_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "type",
            sa.Enum("barter", "paid", name="offer_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("blogger_receives", sa.Text, nullable=False, server_default=""),
        sa.Column("business_receives", sa.Text, nullable=False, server_default=""),
        sa.Column("photo_url", sa.Text, nullable=False, server_default=""),
        sa.Column("slots_total", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("slots_remaining", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("preferred_blogger_niche", sa.String(100), nullable=True),
        sa.Column("min_audience", sa.String(50), nullable=True),
        sa.Column("guests", sa.String(100), nullable=True),
        sa.Column("special_conditions", sa.Text, nullable=True),
        sa.Column(
            "is_last_minute", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "status",
            sa.Enum("active", "closed", "expired", name="offer_status_enum", create_type=False),
            nullable=False,
            server_default="active",
            index=True,
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_offers_business_id", "offers", ["business_id"])
    op.create_index(
        "ix_offers_active",
        "offers",
        ["is_active"],
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index("ix_offers_type", "offers", ["type"])

    # ------------------------------------------------------------------
    # offer_responses
    # ------------------------------------------------------------------
    op.create_table(
        "offer_responses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "offer_id",
            sa.String(36),
            sa.ForeignKey("offers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "business_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "blogger_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "accepted", "declined",
                name="offer_response_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
            index=True,
        ),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("offer_id", "blogger_id", name="uq_offer_responses_pair"),
    )
    op.create_index("ix_offer_responses_offer_id", "offer_responses", ["offer_id"])
    op.create_index("ix_offer_responses_blogger_id", "offer_responses", ["blogger_id"])
    op.create_index("ix_offer_responses_business_id", "offer_responses", ["business_id"])

    # ------------------------------------------------------------------
    # conversations
    # ------------------------------------------------------------------
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "match_id",
            sa.String(36),
            sa.ForeignKey("matches.id", ondelete="SET NULL"),
            nullable=True,
            unique=True,
        ),
        sa.Column(
            "participant1_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "participant2_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_conversations_match_id", "conversations", ["match_id"])

    # ------------------------------------------------------------------
    # messages
    # ------------------------------------------------------------------
    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sender_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "media_urls", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_sender_id", "messages", ["sender_id"])

    # ------------------------------------------------------------------
    # deals
    # ------------------------------------------------------------------
    op.create_table(
        "deals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "offer_type",
            sa.Enum("barter", "paid", name="offer_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "influencer_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "business_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("initiator_id", sa.String(36), nullable=False),
        sa.Column("offered_text", sa.Text, nullable=False, server_default=""),
        sa.Column("requested_text", sa.Text, nullable=False, server_default=""),
        sa.Column("place_name", sa.String(120), nullable=True),
        sa.Column("guests", sa.String(50), nullable=False, server_default="solo"),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft", "confirmed", "visited", "no_show", "reviewed", "cancelled",
                name="deal_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("cancellation_reason", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_deals_influencer_id", "deals", ["influencer_id"])
    op.create_index("ix_deals_business_id", "deals", ["business_id"])
    op.create_index("ix_deals_status", "deals", ["status"])

    # ------------------------------------------------------------------
    # deal_reviews
    # ------------------------------------------------------------------
    op.create_table(
        "deal_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "deal_id",
            sa.String(36),
            sa.ForeignKey("deals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reviewer_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reviewee_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("punctuality", sa.Integer, nullable=True),
        sa.Column("offer_match", sa.Integer, nullable=True),
        sa.Column("communication", sa.Integer, nullable=True),
        sa.Column("text", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("deal_id", "reviewer_id", name="uq_deal_reviews_pair"),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_deal_reviews_rating"),
    )
    op.create_index("ix_deal_reviews_deal_id", "deal_reviews", ["deal_id"])
    op.create_index("ix_deal_reviews_reviewer_id", "deal_reviews", ["reviewer_id"])


def downgrade() -> None:
    op.drop_table("deal_reviews")
    op.drop_table("deals")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("offer_responses")
    op.drop_table("offers")
    op.drop_table("matches")
    op.drop_table("swipes")
    op.drop_table("profiles")
    op.drop_table("users")

    # Drop enums
    sa.Enum(name="deal_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="offer_response_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="offer_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="offer_type_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="match_source_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="swipe_direction_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="plan_tier_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="user_role_enum").drop(op.get_bind(), checkfirst=True)
