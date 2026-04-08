"""
Offers router.

Endpoints
---------
GET  /offers                                      — List active offers (with filters)
POST /offers                                      — Create a new offer (business only)
GET  /offers/{offer_id}                           — Get offer detail with creator info
POST /offers/{offer_id}/respond                   — Blogger responds to offer (primary)
POST /offers/{offer_id}/apply                     — Blogger responds (iOS alias)
POST /offers/{offer_id}/responses                 — Blogger responds (legacy path)
POST /offers/{offer_id}/close                     — Business closes their own active offer
POST /offers/{offer_id}/cancel                    — Legacy alias for close
POST /offers/{offer_id}/accept-response/{resp_id} — Business accepts a response
POST /offers/{offer_id}/decline-response/{resp_id}— Business declines a response
GET  /offers/responses/incoming                   — Incoming responses for a business
POST /offers/responses/{id}/accept                — Accept a response (legacy path)
POST /offers/responses/{id}/decline               — Decline a response (legacy path)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.container import AppContainer
from app.core.dependencies import get_container, get_current_user_id
from app.core.exceptions import NotFoundError
from app.modules.offers.domain.models import OfferType
from app.modules.offers.schemas import (
    OfferCreateRequest,
    OfferDetailRead,
    OfferFilterParams,
    OfferRead,
    OfferRespondRequest,
    OfferRespondResult,
    OfferResponseRead,
)
from app.modules.profile.schemas import ProfileRead

router = APIRouter(prefix="/offers", tags=["offers"])


# ---------------------------------------------------------------------------
# List offers
# ---------------------------------------------------------------------------

@router.get("", response_model=list[OfferRead])
def list_offers(
    type: OfferType | None = Query(default=None),
    niche: str | None = Query(default=None),
    last_minute_only: bool = Query(default=False),
    container: AppContainer = Depends(get_container),
) -> list[OfferRead]:
    filters = OfferFilterParams(
        type=type,
        niche=niche,
        last_minute_only=last_minute_only,
    )
    offers = container.offer_service.list_offers(filters)
    return [OfferRead.model_validate(offer) for offer in offers]


# ---------------------------------------------------------------------------
# Create offer
# ---------------------------------------------------------------------------

@router.post("", response_model=OfferRead)
def create_offer(
    payload: OfferCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> OfferRead:
    offer = container.offer_service.create_offer(current_user_id, payload)
    return OfferRead.model_validate(offer)


# ---------------------------------------------------------------------------
# Incoming responses (fixed-path routes must be before /{offer_id})
# ---------------------------------------------------------------------------

@router.get("/responses/incoming", response_model=list[OfferResponseRead])
def list_incoming_responses(
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> list[OfferResponseRead]:
    responses = container.offer_service.list_responses_for_business(current_user_id)
    return [OfferResponseRead.model_validate(r) for r in responses]


@router.post("/responses/{response_id}/accept", response_model=OfferResponseRead)
def accept_response_legacy(
    response_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> OfferResponseRead:
    """Accept a response — legacy path /offers/responses/{id}/accept."""
    response = container.offer_service.accept_response(current_user_id, response_id)
    return OfferResponseRead.model_validate(response)


@router.post("/responses/{response_id}/decline", response_model=OfferResponseRead)
def decline_response_legacy(
    response_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> OfferResponseRead:
    """Decline a response — legacy path /offers/responses/{id}/decline."""
    response = container.offer_service.decline_response(current_user_id, response_id)
    return OfferResponseRead.model_validate(response)


# ---------------------------------------------------------------------------
# Offer detail  GET /offers/{offer_id}
# ---------------------------------------------------------------------------

@router.get("/{offer_id}", response_model=OfferDetailRead)
def get_offer(
    offer_id: str,
    container: AppContainer = Depends(get_container),
) -> OfferDetailRead:
    """Return offer detail including the creator's public profile."""
    offer = container.offer_service.offer_repo.get_offer(offer_id)
    if not offer:
        raise NotFoundError("Offer not found.")

    creator_profile = container.profile_service.profile_repo.get_by_user_id(offer.business_id)
    creator_read = ProfileRead.model_validate(creator_profile) if creator_profile else None

    return OfferDetailRead(
        **OfferRead.model_validate(offer).model_dump(),
        creator=creator_read,
    )


# ---------------------------------------------------------------------------
# Respond to offer  (three path aliases)
# ---------------------------------------------------------------------------

def _respond_to_offer(
    offer_id: str,
    payload: OfferRespondRequest,
    current_user_id: str,
    container: AppContainer,
) -> OfferRespondResult:
    response_obj, remaining = container.offer_service.respond_to_offer(
        current_user_id, offer_id, payload
    )
    return OfferRespondResult(
        response=OfferResponseRead.model_validate(response_obj),
        remaining_responses=remaining,
    )


@router.post("/{offer_id}/respond", response_model=OfferRespondResult)
def respond_to_offer(
    offer_id: str,
    payload: OfferRespondRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> OfferRespondResult:
    """
    Blogger responds to an offer — primary path.

    Body: { message?: string }
    Returns: { response: OfferResponseRead, remaining_responses: int }
    """
    return _respond_to_offer(offer_id, payload, current_user_id, container)


@router.post("/{offer_id}/apply", response_model=OfferRespondResult)
def apply_to_offer(
    offer_id: str,
    payload: OfferRespondRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> OfferRespondResult:
    """Blogger responds — iOS alias."""
    return _respond_to_offer(offer_id, payload, current_user_id, container)


@router.post("/{offer_id}/responses", response_model=OfferRespondResult)
def respond_to_offer_legacy(
    offer_id: str,
    payload: OfferRespondRequest,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> OfferRespondResult:
    """Blogger responds — legacy path."""
    return _respond_to_offer(offer_id, payload, current_user_id, container)


# ---------------------------------------------------------------------------
# Business closes own offer
# ---------------------------------------------------------------------------

@router.post("/{offer_id}/close", response_model=OfferRead)
def close_offer(
    offer_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> OfferRead:
    offer = container.offer_service.close_offer(current_user_id, offer_id)
    return OfferRead.model_validate(offer)


@router.post("/{offer_id}/cancel", response_model=OfferRead)
def cancel_offer_legacy(
    offer_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> OfferRead:
    """Legacy alias for closing an offer."""
    offer = container.offer_service.close_offer(current_user_id, offer_id)
    return OfferRead.model_validate(offer)


# ---------------------------------------------------------------------------
# Business accepts/declines a response — new spec paths
# ---------------------------------------------------------------------------

@router.post("/{offer_id}/accept-response/{response_id}", response_model=OfferResponseRead)
def accept_response_for_offer(
    offer_id: str,
    response_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> OfferResponseRead:
    """
    Business accepts a specific blogger response.
    Creates a match, opens a chat, and triggers a Deal Card.
    """
    response = container.offer_service.accept_response(current_user_id, response_id)
    return OfferResponseRead.model_validate(response)


@router.post("/{offer_id}/decline-response/{response_id}", response_model=OfferResponseRead)
def decline_response_for_offer(
    offer_id: str,
    response_id: str,
    current_user_id: str = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container),
) -> OfferResponseRead:
    """Business declines a specific blogger response."""
    response = container.offer_service.decline_response(current_user_id, response_id)
    return OfferResponseRead.model_validate(response)
