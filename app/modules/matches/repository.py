from __future__ import annotations

from typing import Protocol

from app.modules.matches.domain.models import Match, Swipe, SwipeDirection


class MatchRepository(Protocol):
    def add_swipe(self, swipe: Swipe) -> Swipe: ...

    def get_latest_swipe(self, actor_id: str, target_id: str) -> Swipe | None: ...

    def count_pending_positive_swipes(self, actor_id: str) -> int: ...

    def add_match(self, match: Match) -> Match: ...

    def get_match_by_pair(self, user_a_id: str, user_b_id: str) -> Match | None: ...

    def list_matches_for_user(self, user_id: str) -> list[Match]: ...

    def activate_pending_swipes(self, actor_id: str) -> list[Swipe]: ...

    def delete_match(self, match_id: str) -> None: ...


class InMemoryMatchRepository:
    def __init__(self, store):
        self.store = store

    def add_swipe(self, swipe: Swipe) -> Swipe:
        self.store.swipes[swipe.id] = swipe
        self.store.persist()
        return swipe

    def get_latest_swipe(self, actor_id: str, target_id: str) -> Swipe | None:
        candidates = [
            swipe
            for swipe in self.store.swipes.values()
            if swipe.actor_id == actor_id and swipe.target_id == target_id
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: item.created_at)[-1]

    def count_pending_positive_swipes(self, actor_id: str) -> int:
        return sum(
            1
            for swipe in self.store.swipes.values()
            if swipe.actor_id == actor_id
            and not swipe.delivered
            and swipe.direction in {SwipeDirection.RIGHT, SwipeDirection.SUPER}
        )

    def add_match(self, match: Match) -> Match:
        self.store.matches[match.id] = match
        self.store.persist()
        return match

    def get_match_by_pair(self, user_a_id: str, user_b_id: str) -> Match | None:
        pair = tuple(sorted((user_a_id, user_b_id)))
        return next(
            (match for match in self.store.matches.values() if match.user_ids == pair),
            None,
        )

    def list_matches_for_user(self, user_id: str) -> list[Match]:
        matches = [
            match for match in self.store.matches.values() if user_id in match.user_ids
        ]
        return sorted(matches, key=lambda item: item.created_at, reverse=True)

    def activate_pending_swipes(self, actor_id: str) -> list[Swipe]:
        activated: list[Swipe] = []
        for swipe in self.store.swipes.values():
            if swipe.actor_id == actor_id and not swipe.delivered:
                swipe.delivered = True
                activated.append(swipe)
        if activated:
            self.store.persist()
        return activated

    def delete_match(self, match_id: str) -> None:
        self.store.matches.pop(match_id, None)
        self.store.persist()
