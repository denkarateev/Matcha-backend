from __future__ import annotations

from typing import Protocol

from app.modules.profile.domain.models import Profile


class ProfileRepository(Protocol):
    def get_by_user_id(self, user_id: str) -> Profile | None: ...

    def upsert(self, profile: Profile) -> Profile: ...

    def increment_verified_visits(self, user_id: str) -> Profile: ...

    def apply_review_score(self, user_id: str, score: float) -> Profile: ...

    def delete(self, user_id: str) -> None: ...


class InMemoryProfileRepository:
    def __init__(self, store):
        self.store = store

    def get_by_user_id(self, user_id: str) -> Profile | None:
        return self.store.profiles.get(user_id)

    def upsert(self, profile: Profile) -> Profile:
        self.store.profiles[profile.user_id] = profile
        self.store.persist()
        return profile

    def increment_verified_visits(self, user_id: str) -> Profile:
        profile = self.store.profiles[user_id]
        profile.verified_visits += 1
        self.store.persist()
        return profile

    def apply_review_score(self, user_id: str, score: float) -> Profile:
        profile = self.store.profiles[user_id]
        total = (profile.rating or 0.0) * profile.review_count
        profile.review_count += 1
        profile.rating = round((total + score) / profile.review_count, 2)
        self.store.persist()
        return profile

    def delete(self, user_id: str) -> None:
        self.store.profiles.pop(user_id, None)
        self.store.persist()
