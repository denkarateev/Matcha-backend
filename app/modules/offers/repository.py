from __future__ import annotations

from datetime import date
from typing import Protocol

from app.modules.offers.domain.models import Offer, OfferResponse


class OfferRepository(Protocol):
    def add_offer(self, offer: Offer) -> Offer: ...

    def update_offer(self, offer: Offer) -> Offer: ...

    def get_offer(self, offer_id: str) -> Offer | None: ...

    def list_offers(self) -> list[Offer]: ...

    def add_response(self, response: OfferResponse) -> OfferResponse: ...

    def update_response(self, response: OfferResponse) -> OfferResponse: ...

    def get_response(self, response_id: str) -> OfferResponse | None: ...

    def get_response_for_offer_and_blogger(
        self,
        offer_id: str,
        blogger_id: str,
    ) -> OfferResponse | None: ...

    def list_responses_for_business(self, business_id: str) -> list[OfferResponse]: ...

    def count_blogger_responses_on_date(self, blogger_id: str, day: date) -> int: ...


class InMemoryOfferRepository:
    def __init__(self, store):
        self.store = store

    def add_offer(self, offer: Offer) -> Offer:
        self.store.offers[offer.id] = offer
        self.store.persist()
        return offer

    def update_offer(self, offer: Offer) -> Offer:
        self.store.offers[offer.id] = offer
        self.store.persist()
        return offer

    def get_offer(self, offer_id: str) -> Offer | None:
        return self.store.offers.get(offer_id)

    def list_offers(self) -> list[Offer]:
        return sorted(
            self.store.offers.values(),
            key=lambda item: item.created_at,
            reverse=True,
        )

    def add_response(self, response: OfferResponse) -> OfferResponse:
        self.store.offer_responses[response.id] = response
        self.store.persist()
        return response

    def update_response(self, response: OfferResponse) -> OfferResponse:
        self.store.offer_responses[response.id] = response
        self.store.persist()
        return response

    def get_response(self, response_id: str) -> OfferResponse | None:
        return self.store.offer_responses.get(response_id)

    def get_response_for_offer_and_blogger(
        self,
        offer_id: str,
        blogger_id: str,
    ) -> OfferResponse | None:
        return next(
            (
                response
                for response in self.store.offer_responses.values()
                if response.offer_id == offer_id and response.blogger_id == blogger_id
            ),
            None,
        )

    def list_responses_for_business(self, business_id: str) -> list[OfferResponse]:
        responses = [
            response
            for response in self.store.offer_responses.values()
            if response.business_id == business_id
        ]
        return sorted(responses, key=lambda item: item.created_at, reverse=True)

    def count_blogger_responses_on_date(self, blogger_id: str, day: date) -> int:
        return sum(
            1
            for response in self.store.offer_responses.values()
            if response.blogger_id == blogger_id and response.created_at.date() == day
        )
