"""
Deals router.

Endpoints
---------
GET  /deals                         — List user's deals
POST /deals                         — Create a deal card
POST /deals/{id}/accept             — Accept a deal (moves to Confirmed)
POST /deals/{id}/decline            — Decline a deal
POST /deals/{id}/check-in           — Record check-in (both → Visited)
POST /deals/{id}/cancel             — Cancel deal
POST /deals/{id}/review             — Submit review
POST /deals/{id}/content-proof      — Submit content proof
POST /deals/{id}/repeat             — Repeat collab (Black only)

Legacy aliases:
POST /deals/{id}/confirm            — Same as accept
POST /deals/{id}/no-show            — Mark no-show
POST /deals/{id}/rate               — Submit a review (iOS alias)
POST /deals/{id}/reviews            — Submit a review (legacy path)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.container import AppContainer
from app.core.dependencies import get_container, get_current_user_id
from app.modules.deals.schemas import (
    DealCancelRequest,
    DealContentProofRequest,
    DealCreateRequest,
    DealRead,
    DealReviewRequest,
)

router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("", response_model=list[DealRead])
def list_deals(
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> list[DealRead]:
    deals = container.deal_service.list_deals(current_user_id)
    return [DealRead.model_validate(deal) for deal in deals]


@router.get("/{deal_id}", response_model=DealRead)
def get_deal(
    deal_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> DealRead:
    deal = container.deal_service.get_deal(current_user_id, deal_id)
    return DealRead.model_validate(deal)


@router.post("", response_model=DealRead, status_code=201)
def create_deal(
    payload: DealCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> DealRead:
    """
    Create a new Deal card in Draft status.

    Body: { partner_id, type, you_offer, you_receive, guests?, date_time?, content_deadline? }
    """
    deal = container.deal_service.create_deal(current_user_id, payload)
    return DealRead.model_validate(deal)


@router.post("/{deal_id}/accept", response_model=DealRead)
def accept_deal(
    deal_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> DealRead:
    """Accept a deal — moves status from Draft → Confirmed."""
    deal = container.deal_service.accept_deal(current_user_id, deal_id)
    return DealRead.model_validate(deal)


@router.post("/{deal_id}/confirm", response_model=DealRead)
def confirm_deal(
    deal_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> DealRead:
    """Legacy alias for accept."""
    deal = container.deal_service.confirm_deal(current_user_id, deal_id)
    return DealRead.model_validate(deal)


@router.post("/{deal_id}/decline", response_model=DealRead)
def decline_deal(
    deal_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> DealRead:
    """Decline a deal — counterparty cancels a Draft deal."""
    deal = container.deal_service.decline_deal(current_user_id, deal_id)
    return DealRead.model_validate(deal)


@router.post("/{deal_id}/check-in", response_model=DealRead)
def check_in(
    deal_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> DealRead:
    """
    Record a check-in for the current user.
    When both participants check in → status moves to Visited.
    """
    deal = container.deal_service.check_in(current_user_id, deal_id)
    return DealRead.model_validate(deal)


@router.post("/{deal_id}/no-show", response_model=DealRead)
def mark_no_show(
    deal_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> DealRead:
    deal = container.deal_service.mark_no_show(current_user_id, deal_id)
    return DealRead.model_validate(deal)


def _submit_review(
    deal_id: str,
    payload: DealReviewRequest,
    current_user_id: str,
    container: AppContainer,
) -> DealRead:
    deal = container.deal_service.submit_review(current_user_id, deal_id, payload)
    return DealRead.model_validate(deal)


@router.post("/{deal_id}/review", response_model=DealRead)
def submit_review(
    deal_id: str,
    payload: DealReviewRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> DealRead:
    """
    Submit a review for a deal.

    Body: { punctuality?: 1-5, offer_match?: 1-5, communication?: 1-5, comment?: str }
    Reviews are hidden until both sides submit or 7-day deadline passes.
    """
    return _submit_review(deal_id, payload, current_user_id, container)


@router.post("/{deal_id}/rate", response_model=DealRead)
def rate_deal(
    deal_id: str,
    payload: DealReviewRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> DealRead:
    """Submit a review — iOS primary path alias."""
    return _submit_review(deal_id, payload, current_user_id, container)


@router.post("/{deal_id}/reviews", response_model=DealRead)
def legacy_submit_review(
    deal_id: str,
    payload: DealReviewRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> DealRead:
    """Submit a review — legacy path."""
    return _submit_review(deal_id, payload, current_user_id, container)


@router.post("/{deal_id}/cancel", response_model=DealRead)
def cancel_deal(
    deal_id: str,
    payload: DealCancelRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> DealRead:
    """
    Cancel a deal.

    Body: { reason: "schedule_conflict"|"changed_conditions"|"no_response"|"other" }
    """
    deal = container.deal_service.cancel_deal(current_user_id, deal_id, payload)
    return DealRead.model_validate(deal)


@router.post("/{deal_id}/content-proof", response_model=DealRead)
def submit_content_proof(
    deal_id: str,
    payload: DealContentProofRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> DealRead:
    """
    Submit content proof after a visit.

    Body: { post_url: str, screenshot_url?: str }
    """
    deal = container.deal_service.submit_content_proof(current_user_id, deal_id, payload)
    return DealRead.model_validate(deal)


@router.post("/{deal_id}/repeat", response_model=DealRead)
def repeat_deal(
    deal_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> DealRead:
    """
    Repeat a completed collab — Black plan only.
    Creates a new Draft deal with the same terms.
    """
    deal = container.deal_service.repeat_deal(current_user_id, deal_id)
    return DealRead.model_validate(deal)
