from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.core.time import utc_now
from app.modules.auth.domain.models import PlanTier, User, VerificationLevel
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import LoginRequest, RegisterRequest, VerifyUserRequest
from app.modules.profile.domain.models import Profile
from app.modules.profile.repository import ProfileRepository


class AuthService:
    def __init__(self, auth_repo: AuthRepository, profile_repo: ProfileRepository):
        self.auth_repo = auth_repo
        self.profile_repo = profile_repo

    def register(self, payload: RegisterRequest) -> tuple[User, str]:
        if self.auth_repo.get_by_email(payload.email):
            raise ConflictError("Email is already registered.")

        user = User(
            id=str(uuid4()),
            email=payload.email,
            password_hash=hash_password(payload.password),
            role=payload.role,
            full_name=payload.full_name,
        )
        self.auth_repo.add(user)

        profile = Profile(
            user_id=user.id,
            display_name=payload.full_name,
            photo_urls=[payload.primary_photo_url],
            primary_photo_url=payload.primary_photo_url,
            category=payload.category,
        )
        self.profile_repo.upsert(profile)
        return user, create_access_token(user_id=user.id, role=user.role.value)

    def login(self, payload: LoginRequest) -> tuple[User, str]:
        user = self.auth_repo.get_by_email(payload.email)
        if not user or not verify_password(payload.password, user.password_hash):
            raise UnauthorizedError("Invalid email or password.")
        return user, create_access_token(user_id=user.id, role=user.role.value)

    def get_user(self, user_id: str) -> User:
        user = self.auth_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found.")
        return user

    def verify_user(self, user_id: str, payload: VerifyUserRequest) -> User:
        user = self.get_user(user_id)
        if user.is_verified:
            return user

        plan_tier = user.plan_tier
        offer_credits = user.offer_credits
        if user.role.value == "business":
            plan_tier = PlanTier.PRO
            offer_credits = max(offer_credits, 3)

        updated_user = replace(
            user,
            verification_level=VerificationLevel.VERIFIED,
            plan_tier=plan_tier,
            offer_credits=offer_credits,
            updated_at=utc_now(),
        )
        self.auth_repo.update(updated_user)

        profile = self.profile_repo.get_by_user_id(user_id)
        if profile:
            updated_profile = replace(
                profile,
                instagram_handle=payload.instagram_handle,
                tiktok_handle=payload.tiktok_handle,
                audience_size=payload.audience_size,
                updated_at=utc_now(),
            )
            self.profile_repo.upsert(updated_profile)

        return updated_user

    def delete_user(self, user_id: str) -> None:
        """Delete a user and their profile. Caller is responsible for cascade-deleting related entities."""
        self.profile_repo.delete(user_id)
        self.auth_repo.delete(user_id)
