from __future__ import annotations

from uuid import uuid4

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.time import local_date, utc_now
from app.modules.auth.domain.models import PlanTier, UserRole
from app.modules.auth.repository import AuthRepository
from app.modules.chats.service import ChatService
from app.modules.matches.domain.models import MatchSource
from app.modules.matches.service import MatchService
from app.modules.offers.domain.models import (
    Offer,
    OfferResponse,
    OfferResponseStatus,
    OfferStatus,
)
from app.modules.offers.repository import OfferRepository
from app.modules.offers.schemas import (
    OfferCreateRequest,
    OfferFilterParams,
    OfferRespondRequest,
)


class OfferService:
    def __init__(
        self,
        offer_repo: OfferRepository,
        auth_repo: AuthRepository,
        match_service: MatchService,
        chat_service: ChatService,
        timezone_name: str,
    ):
        self.offer_repo = offer_repo
        self.auth_repo = auth_repo
        self.match_service = match_service
        self.chat_service = chat_service
        self.timezone_name = timezone_name

    def list_offers(self, filters: OfferFilterParams | None = None) -> list[Offer]:
        offers = [
            offer for offer in self.offer_repo.list_offers() if offer.status == OfferStatus.ACTIVE
        ]
        if not filters:
            return offers
        if filters.type:
            offers = [offer for offer in offers if offer.type == filters.type]
        if filters.niche:
            offers = [
                offer
                for offer in offers
                if offer.preferred_blogger_niche in {None, filters.niche}
            ]
        if filters.last_minute_only:
            offers = [offer for offer in offers if offer.is_last_minute]
        return offers

    def list_responses_for_business(self, business_id: str) -> list[OfferResponse]:
        user = self._get_user(business_id)
        if user.role != UserRole.BUSINESS:
            raise ForbiddenError("Only businesses can view incoming offer responses.")
        return self.offer_repo.list_responses_for_business(business_id)

    def create_offer(self, actor_id: str, payload: OfferCreateRequest) -> Offer:
        user = self._get_user(actor_id)
        if user.role != UserRole.BUSINESS:
            raise ForbiddenError("Only businesses can create offers.")
        if not user.is_verified:
            raise ForbiddenError("Only verified businesses can create offers.")
        if payload.is_last_minute and user.plan_tier != PlanTier.BLACK:
            raise ForbiddenError("Last Minute offers are only available on Black tier.")
        if user.offer_credits < 1:
            raise ConflictError("No Offer Credits left.")

        offer = Offer(
            id=str(uuid4()),
            business_id=actor_id,
            title=payload.title,
            type=payload.type,
            blogger_receives=payload.blogger_receives,
            business_receives=payload.business_receives,
            slots_total=payload.slots_total,
            slots_remaining=payload.slots_total,
            photo_url=payload.photo_url,
            expires_at=payload.expires_at,
            preferred_blogger_niche=payload.preferred_blogger_niche,
            min_audience=payload.min_audience,
            guests=payload.guests,
            special_conditions=payload.special_conditions,
            is_last_minute=payload.is_last_minute,
        )
        self.offer_repo.add_offer(offer)
        user.offer_credits -= 1
        self.auth_repo.update(user)
        return offer

    def close_offer(self, actor_id: str, offer_id: str) -> Offer:
        user = self._get_user(actor_id)
        if user.role != UserRole.BUSINESS:
            raise ForbiddenError("Only businesses can close offers.")

        offer = self._get_offer(offer_id)
        if offer.business_id != actor_id:
            raise ForbiddenError("Only the offer owner can close this offer.")
        if offer.status != OfferStatus.ACTIVE:
            raise ConflictError("Offer is no longer active.")

        offer.status = OfferStatus.CLOSED
        offer.updated_at = utc_now()
        return self.offer_repo.update_offer(offer)

    def respond_to_offer(
        self,
        actor_id: str,
        offer_id: str,
        payload: OfferRespondRequest,
    ) -> tuple[OfferResponse, int]:
        """Returns (saved_response, remaining_daily_responses)."""
        user = self._get_user(actor_id)
        if user.role != UserRole.BLOGGER:
            raise ForbiddenError("Only bloggers can respond to offers.")
        if not user.is_verified:
            raise ForbiddenError("Only verified bloggers can respond to offers.")

        offer = self._get_offer(offer_id)
        is_unlimited = offer.slots_total == 0
        if offer.status != OfferStatus.ACTIVE or (not is_unlimited and offer.slots_remaining < 1):
            raise ConflictError("Offer is no longer available.")

        existing = self.offer_repo.get_response_for_offer_and_blogger(offer_id, actor_id)
        if existing and existing.status == OfferResponseStatus.PENDING:
            raise ConflictError("Offer response already submitted.")

        today = local_date(self.timezone_name)
        response_count = self.offer_repo.count_blogger_responses_on_date(actor_id, today)
        if response_count >= 3:
            raise ConflictError("Daily offer response limit reached.")

        response = OfferResponse(
            id=str(uuid4()),
            offer_id=offer_id,
            business_id=offer.business_id,
            blogger_id=actor_id,
            message=payload.message,
        )
        saved = self.offer_repo.add_response(response)
        remaining = max(0, 3 - response_count - 1)  # responses left after this one
        return saved, remaining

    def accept_response(self, actor_id: str, response_id: str) -> OfferResponse:
        response = self._get_response(response_id)
        if response.business_id != actor_id:
            raise ForbiddenError("Only the offer owner can accept a response.")
        if response.status != OfferResponseStatus.PENDING:
            raise ConflictError("Response is not pending.")

        offer = self._get_offer(response.offer_id)
        is_unlimited = offer.slots_total == 0
        if not is_unlimited and offer.slots_remaining < 1:
            raise ConflictError("No offer slots remaining.")

        if not is_unlimited:
            offer.slots_remaining -= 1
            offer.status = OfferStatus.CLOSED if offer.slots_remaining == 0 else offer.status
        offer.updated_at = utc_now()
        self.offer_repo.update_offer(offer)

        response.status = OfferResponseStatus.ACCEPTED
        response.updated_at = utc_now()
        self.offer_repo.update_response(response)

        match = self.match_service.ensure_match_for_pair(
            actor_id,
            response.blogger_id,
            source=MatchSource.OFFER,
        )
        self.chat_service.ensure_direct_chat(actor_id, response.blogger_id, match_id=match.id)
        return response

    def decline_response(self, actor_id: str, response_id: str) -> OfferResponse:
        response = self._get_response(response_id)
        if response.business_id != actor_id:
            raise ForbiddenError("Only the offer owner can decline a response.")
        if response.status != OfferResponseStatus.PENDING:
            raise ConflictError("Response is not pending.")

        response.status = OfferResponseStatus.DECLINED
        response.updated_at = utc_now()
        return self.offer_repo.update_response(response)

    def _get_user(self, user_id: str):
        user = self.auth_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found.")
        return user

    def _get_offer(self, offer_id: str) -> Offer:
        offer = self.offer_repo.get_offer(offer_id)
        if not offer:
            raise NotFoundError("Offer not found.")
        return offer

    def _get_response(self, response_id: str) -> OfferResponse:
        response = self.offer_repo.get_response(response_id)
        if not response:
            raise NotFoundError("Offer response not found.")
        return response
