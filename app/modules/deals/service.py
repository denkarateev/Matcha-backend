from __future__ import annotations

from statistics import mean
from uuid import uuid4

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.time import utc_now
from app.modules.auth.domain.models import PlanTier, UserRole
from app.modules.auth.repository import AuthRepository
from app.modules.chats.service import ChatService
from app.modules.deals.domain.models import (
    CancellationReason,
    ContentProof,
    Deal,
    DealReview,
    DealStatus,
)
from app.modules.deals.repository import DealRepository
from app.modules.deals.schemas import (
    DealCancelRequest,
    DealContentProofRequest,
    DealCreateRequest,
    DealReviewRequest,
)
from app.modules.profile.repository import ProfileRepository


class DealService:
    def __init__(
        self,
        deal_repo: DealRepository,
        auth_repo: AuthRepository,
        chat_service: ChatService,
        profile_repo: ProfileRepository,
    ):
        self.deal_repo = deal_repo
        self.auth_repo = auth_repo
        self.chat_service = chat_service
        self.profile_repo = profile_repo

    def list_deals(self, user_id: str) -> list[Deal]:
        self._get_user(user_id)
        return self.deal_repo.list_for_user(user_id)

    def get_deal(self, user_id: str, deal_id: str) -> Deal:
        deal = self._get_deal(deal_id)
        self._ensure_participant(user_id, deal)
        return deal

    def create_deal(self, actor_id: str, payload: DealCreateRequest) -> Deal:
        actor = self._get_user(actor_id)
        partner_id = payload.resolved_partner_id()
        if not partner_id:
            raise ConflictError("partner_id is required.")
        if actor_id == partner_id:
            raise ConflictError("Cannot create a deal with yourself.")
        partner = self._get_user(partner_id)
        participant_ids = self._resolve_participant_ids(actor, partner)

        # Allow multiple deals per pair — only block if one is already active (not cancelled/reviewed)
        existing = self.deal_repo.get_active_for_pair(actor_id, partner_id)
        if existing:
            raise ConflictError("There is already an active deal for this pair.")

        chat = self.chat_service.ensure_direct_chat(actor_id, partner_id)
        self.chat_service.assert_can_send_message(actor_id, chat.id)
        deal = Deal(
            id=str(uuid4()),
            chat_id=chat.id,
            participant_ids=participant_ids,
            initiator_id=actor_id,
            type=payload.type,
            offered_text=payload.resolved_offered_text(),
            requested_text=payload.resolved_requested_text(),
            place_name=payload.resolved_place_name(),
            guests=payload.guests,
            scheduled_for=payload.resolved_scheduled_for(),
            content_deadline=payload.content_deadline,
        )
        saved = self.deal_repo.add(deal)
        self.chat_service.send_deal_card(
            actor_id,
            saved.chat_id,
            saved.id,
            text="Great! Here's our deal offer \U0001f447",
        )
        return saved

    def accept_deal(self, actor_id: str, deal_id: str) -> Deal:
        deal = self._get_deal(deal_id)
        self._ensure_participant(actor_id, deal)
        if deal.status != DealStatus.DRAFT:
            raise ConflictError("Only draft deals can be accepted.")
        if actor_id == deal.initiator_id:
            raise ConflictError("Initiator cannot self-accept the deal.")

        deal.status = DealStatus.CONFIRMED
        deal.updated_at = utc_now()
        updated = self.deal_repo.update(deal)
        date_str = ""
        if updated.scheduled_for:
            date_str = f" See you on {updated.scheduled_for:%b %d}"
        self.chat_service.inject_system_message(
            updated.chat_id,
            f"\u2705 Deal confirmed!{date_str}",
        )
        return updated

    def confirm_deal(self, actor_id: str, deal_id: str) -> Deal:
        """Alias for accept_deal — legacy path."""
        return self.accept_deal(actor_id, deal_id)

    def decline_deal(self, actor_id: str, deal_id: str) -> Deal:
        deal = self._get_deal(deal_id)
        self._ensure_participant(actor_id, deal)
        if deal.status != DealStatus.DRAFT:
            raise ConflictError("Only draft deals can be declined.")
        if actor_id == deal.initiator_id:
            raise ConflictError("Initiator cannot decline their own deal.")

        deal.status = DealStatus.CANCELLED
        deal.cancellation_reason = "declined"
        deal.updated_at = utc_now()
        updated = self.deal_repo.update(deal)
        self.chat_service.inject_system_message(
            updated.chat_id,
            "\u274c Deal declined",
        )
        return updated

    def check_in(self, actor_id: str, deal_id: str) -> Deal:
        deal = self._get_deal(deal_id)
        self._ensure_participant(actor_id, deal)
        if deal.status != DealStatus.CONFIRMED:
            raise ConflictError("Check-in is only available for confirmed deals.")

        deal.checked_in_user_ids.add(actor_id)
        both_checked_in = set(deal.checked_in_user_ids) == set(deal.participant_ids)
        if both_checked_in:
            deal.status = DealStatus.VISITED
            for user_id in deal.participant_ids:
                self.profile_repo.increment_verified_visits(user_id)
        deal.updated_at = utc_now()
        updated = self.deal_repo.update(deal)
        if both_checked_in:
            self.chat_service.inject_system_message(
                updated.chat_id,
                "\U0001f4cd Both checked in! Collaboration in progress",
            )
        return updated

    def mark_no_show(self, actor_id: str, deal_id: str) -> Deal:
        deal = self._get_deal(deal_id)
        self._ensure_participant(actor_id, deal)
        if deal.status != DealStatus.CONFIRMED:
            raise ConflictError("No-show can only be marked from confirmed deals.")
        if actor_id not in deal.checked_in_user_ids or len(deal.checked_in_user_ids) != 1:
            raise ConflictError("No-show can be marked only by the checked-in party.")

        deal.status = DealStatus.NO_SHOW
        deal.updated_at = utc_now()
        updated = self.deal_repo.update(deal)
        self.chat_service.inject_system_message(
            updated.chat_id,
            "\u26a0\ufe0f No-show reported",
        )
        return updated

    def submit_review(
        self,
        actor_id: str,
        deal_id: str,
        payload: DealReviewRequest,
    ) -> Deal:
        deal = self._get_deal(deal_id)
        self._ensure_participant(actor_id, deal)
        if deal.status not in {DealStatus.VISITED, DealStatus.NO_SHOW}:
            raise ConflictError("Reviews are available only after the visit or no-show.")
        if any(review.reviewer_id == actor_id for review in deal.reviews):
            raise ConflictError("Review already submitted.")

        reviewee_id = next(uid for uid in deal.participant_ids if uid != actor_id)
        if deal.status == DealStatus.NO_SHOW:
            if actor_id not in deal.checked_in_user_ids:
                raise ForbiddenError("Only the affected party can review a no-show.")
            if payload.offer_match or payload.communication:
                raise ConflictError("No-show reviews only support punctuality.")

        review = DealReview(
            reviewer_id=actor_id,
            reviewee_id=reviewee_id,
            punctuality=payload.punctuality,
            offer_match=payload.offer_match,
            communication=payload.communication,
            comment=payload.comment,
        )
        deal.reviews.append(review)
        deal.updated_at = utc_now()

        scores = [s for s in [review.punctuality, review.offer_match, review.communication] if s]
        if scores:
            self.profile_repo.apply_review_score(reviewee_id, mean(scores))

        became_reviewed = False
        if deal.status == DealStatus.NO_SHOW or len(deal.reviews) >= 2:
            deal.status = DealStatus.REVIEWED
            became_reviewed = True

        updated = self.deal_repo.update(deal)
        if became_reviewed:
            self.chat_service.inject_system_message(
                updated.chat_id,
                "\u2b50 Deal completed! Reviews submitted",
            )
        return updated

    def cancel_deal(
        self,
        actor_id: str,
        deal_id: str,
        payload: DealCancelRequest,
    ) -> Deal:
        if payload.reason == CancellationReason.DECLINED:
            return self.decline_deal(actor_id, deal_id)

        deal = self._get_deal(deal_id)
        self._ensure_participant(actor_id, deal)
        if deal.status not in {DealStatus.DRAFT, DealStatus.CONFIRMED}:
            raise ConflictError("Only draft or confirmed deals can be cancelled.")

        deal.status = DealStatus.CANCELLED
        deal.cancellation_reason = payload.reason.value
        deal.updated_at = utc_now()
        updated = self.deal_repo.update(deal)
        self.chat_service.inject_system_message(
            updated.chat_id,
            "\u274c Deal cancelled",
        )
        return updated

    def submit_content_proof(
        self,
        actor_id: str,
        deal_id: str,
        payload: DealContentProofRequest,
    ) -> Deal:
        deal = self._get_deal(deal_id)
        self._ensure_participant(actor_id, deal)
        if deal.status not in {DealStatus.VISITED, DealStatus.REVIEWED}:
            raise ConflictError("Content proof can only be submitted after a visit.")

        already = any(p.submitter_id == actor_id for p in deal.content_proofs)
        if already:
            raise ConflictError("Content proof already submitted.")

        proof = ContentProof(
            submitter_id=actor_id,
            post_url=payload.post_url,
            screenshot_url=payload.screenshot_url,
        )
        deal.content_proofs.append(proof)
        deal.updated_at = utc_now()
        return self.deal_repo.update(deal)

    def repeat_deal(self, actor_id: str, deal_id: str) -> Deal:
        """Black-tier-only: create a new deal card based on an existing reviewed deal."""
        user = self._get_user(actor_id)
        if user.plan_tier != PlanTier.BLACK:
            raise ForbiddenError("Repeat collab is only available on the Black plan.")

        original = self._get_deal(deal_id)
        self._ensure_participant(actor_id, original)
        if original.status not in {DealStatus.REVIEWED, DealStatus.VISITED}:
            raise ConflictError("Only completed deals can be repeated.")

        partner_id = next(uid for uid in original.participant_ids if uid != actor_id)
        active = self.deal_repo.get_active_for_pair(actor_id, partner_id)
        if active:
            raise ConflictError("There is already an active deal with this partner.")

        chat = self.chat_service.ensure_direct_chat(actor_id, partner_id)
        new_deal = Deal(
            id=str(uuid4()),
            chat_id=chat.id,
            participant_ids=original.participant_ids,
            initiator_id=actor_id,
            type=original.type,
            offered_text=original.offered_text,
            requested_text=original.requested_text,
            place_name=original.place_name,
            guests=original.guests,
            repeated_from_deal_id=deal_id,
        )
        saved = self.deal_repo.add(new_deal)
        self.chat_service.send_deal_card(
            actor_id,
            saved.chat_id,
            saved.id,
            text="Let's repeat this collab \U0001f447",
        )
        return saved

    def _get_deal(self, deal_id: str) -> Deal:
        deal = self.deal_repo.get_by_id(deal_id)
        if not deal:
            raise NotFoundError("Deal not found.")
        return deal

    def _get_user(self, user_id: str):
        user = self.auth_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found.")
        return user

    @staticmethod
    def _ensure_participant(user_id: str, deal: Deal) -> None:
        if user_id not in deal.participant_ids:
            raise ForbiddenError("You are not a participant of this deal.")

    @staticmethod
    def _resolve_participant_ids(actor, partner) -> tuple[str, str]:
        if actor.role == partner.role:
            raise ConflictError(
                "Deals are only available between a blogger and a business."
            )

        if actor.role == UserRole.BLOGGER:
            return actor.id, partner.id
        return partner.id, actor.id
