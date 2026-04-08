from __future__ import annotations

from dataclasses import replace

from app.core.exceptions import NotFoundError
from app.core.time import utc_now
from app.modules.auth.repository import AuthRepository
from app.modules.profile.domain.models import Profile
from app.modules.profile.repository import ProfileRepository
from app.modules.profile.schemas import ProfileUpdateRequest


class ProfileService:
    def __init__(self, profile_repo: ProfileRepository, auth_repo: AuthRepository):
        self.profile_repo = profile_repo
        self.auth_repo = auth_repo

    def get_profile(self, user_id: str) -> Profile:
        self.auth_repo.get_by_id(user_id) or self._raise_missing()
        profile = self.profile_repo.get_by_user_id(user_id)
        if not profile:
            raise NotFoundError("Profile not found.")
        return profile

    def update_profile(self, user_id: str, payload: ProfileUpdateRequest) -> Profile:
        profile = self.get_profile(user_id)
        data = payload.model_dump(exclude_unset=True)
        updated_profile = replace(profile, **data, updated_at=utc_now())
        return self.profile_repo.upsert(updated_profile)

    @staticmethod
    def _raise_missing() -> None:
        raise NotFoundError("User not found.")
