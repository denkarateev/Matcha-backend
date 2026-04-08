from __future__ import annotations

from uuid import uuid4

from app.core.exceptions import ConflictError, NotFoundError
from app.core.time import utc_now
from app.modules.auth.domain.models import UserRole
from app.modules.auth.repository import AuthRepository
from app.modules.chats.service import ChatService
from app.modules.matches.domain.models import Match, MatchSource, Swipe, SwipeDirection
from app.modules.matches.repository import MatchRepository
from app.modules.matches.schemas import SwipeRequest


class MatchService:
    def __init__(
        self,
        match_repo: MatchRepository,
        auth_repo: AuthRepository,
        chat_service: ChatService,
    ):
        self.match_repo = match_repo
        self.auth_repo = auth_repo
        self.chat_service = chat_service

    def swipe(self, actor_id: str, payload: SwipeRequest) -> tuple[Swipe, Match | None]:
        if actor_id == payload.target_id:
            raise ConflictError("Users cannot swipe on themselves.")

        actor = self._get_user(actor_id)
        target = self._get_user(payload.target_id)
        if actor.role == target.role:
            raise ConflictError(
                "Matches are only available between a blogger and a business."
            )

        is_positive = payload.direction in {SwipeDirection.RIGHT, SwipeDirection.SUPER}
        delivered = actor.is_verified
        if is_positive and not delivered:
            queued_likes = self.match_repo.count_pending_positive_swipes(actor_id)
            if queued_likes >= 20:
                raise ConflictError(
                    "Shadow accounts can queue up to 20 likes before verification."
                )

        swipe = Swipe(
            id=str(uuid4()),
            actor_id=actor_id,
            target_id=payload.target_id,
            direction=payload.direction,
            delivered=delivered,
        )
        self.match_repo.add_swipe(swipe)

        match = None
        if is_positive and delivered:
            reciprocal = self.match_repo.get_latest_swipe(payload.target_id, actor_id)
            if (
                reciprocal
                and reciprocal.delivered
                and reciprocal.direction in {SwipeDirection.RIGHT, SwipeDirection.SUPER}
            ):
                match = self.ensure_match_for_pair(
                    actor_id,
                    payload.target_id,
                    source=MatchSource.SWIPE,
                )

        return swipe, match

    def ensure_match_for_pair(
        self,
        user_a_id: str,
        user_b_id: str,
        source: MatchSource,
    ) -> Match:
        existing = self.match_repo.get_match_by_pair(user_a_id, user_b_id)
        if existing:
            return existing

        first_message_by = None
        user_a = self._get_user(user_a_id)
        user_b = self._get_user(user_b_id)
        if source == MatchSource.SWIPE:
            if {
                user_a.role,
                user_b.role,
            } == {UserRole.BLOGGER, UserRole.BUSINESS}:
                first_message_by = (
                    user_a.id if user_a.role == UserRole.BLOGGER else user_b.id
                )

        match = Match(
            id=str(uuid4()),
            user_ids=tuple(sorted((user_a_id, user_b_id))),
            source=source,
            first_message_by=first_message_by,
        )
        self.match_repo.add_match(match)
        self.chat_service.ensure_direct_chat(user_a_id, user_b_id, match_id=match.id)
        return match

    def activate_pending_likes(self, actor_id: str) -> list[Match]:
        matches: list[Match] = []
        activated_swipes = self.match_repo.activate_pending_swipes(actor_id)
        for swipe in activated_swipes:
            if swipe.direction not in {SwipeDirection.RIGHT, SwipeDirection.SUPER}:
                continue
            reciprocal = self.match_repo.get_latest_swipe(swipe.target_id, swipe.actor_id)
            if (
                reciprocal
                and reciprocal.delivered
                and reciprocal.direction in {SwipeDirection.RIGHT, SwipeDirection.SUPER}
            ):
                match = self.ensure_match_for_pair(
                    swipe.actor_id,
                    swipe.target_id,
                    source=MatchSource.SWIPE,
                )
                matches.append(match)
        return matches

    def list_matches(self, user_id: str) -> list[Match]:
        self._get_user(user_id)
        now = utc_now()
        matches = self.match_repo.list_matches_for_user(user_id)
        # Filter out expired matches that never had a first message
        return [
            m for m in matches
            if m.expires_at is None
            or m.first_message_by is not None
            or m.expires_at > now
        ]

    def expire_stale_matches(self) -> list[str]:
        """Remove matches past their 48h window with no first message. Returns deleted IDs."""
        now = utc_now()
        deleted_ids: list[str] = []
        # Iterate all users' matches via the store
        seen: set[str] = set()
        for match in list(self.match_repo.store.matches.values()):
            if match.id in seen:
                continue
            seen.add(match.id)
            if (
                match.expires_at is not None
                and match.first_message_by is None
                and match.expires_at <= now
            ):
                self.match_repo.delete_match(match.id)
                deleted_ids.append(match.id)
        return deleted_ids

    def _get_user(self, user_id: str):
        user = self.auth_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found.")
        return user
