from __future__ import annotations

from typing import Protocol

from app.modules.deals.domain.models import DealStatus
from app.modules.deals.domain.models import Deal


class DealRepository(Protocol):
    def add(self, deal: Deal) -> Deal: ...

    def update(self, deal: Deal) -> Deal: ...

    def get_by_id(self, deal_id: str) -> Deal | None: ...

    def list_for_user(self, user_id: str) -> list[Deal]: ...

    def get_active_for_pair(self, user_a_id: str, user_b_id: str) -> Deal | None: ...

    def get_blocking_deals_for_pair(self, user_a_id: str, user_b_id: str) -> list[Deal]: ...

    def list_for_pair(self, user_a_id: str, user_b_id: str) -> list[Deal]: ...


class InMemoryDealRepository:
    def __init__(self, store):
        self.store = store

    def add(self, deal: Deal) -> Deal:
        self.store.deals[deal.id] = deal
        self.store.persist()
        return deal

    def update(self, deal: Deal) -> Deal:
        self.store.deals[deal.id] = deal
        self.store.persist()
        return deal

    def get_by_id(self, deal_id: str) -> Deal | None:
        # Try exact match first, then case-insensitive (iOS sends uppercase UUIDs)
        deal = self.store.deals.get(deal_id)
        if deal:
            return deal
        lower = deal_id.lower()
        return self.store.deals.get(lower)

    def list_for_user(self, user_id: str) -> list[Deal]:
        deals = [deal for deal in self.store.deals.values() if user_id in deal.participant_ids]
        return sorted(deals, key=lambda item: item.created_at, reverse=True)

    def get_active_for_pair(self, user_a_id: str, user_b_id: str) -> Deal | None:
        pair = set((user_a_id, user_b_id))
        return next(
            (
                deal
                for deal in self.store.deals.values()
                if set(deal.participant_ids) == pair
                and deal.status
                not in {DealStatus.CANCELLED, DealStatus.REVIEWED}
            ),
            None,
        )

    def get_blocking_deals_for_pair(self, user_a_id: str, user_b_id: str) -> list[Deal]:
        """Returns deals with status VISITED between the pair (blocks unmatch)."""
        pair = set((user_a_id, user_b_id))
        return [
            deal
            for deal in self.store.deals.values()
            if set(deal.participant_ids) == pair
            and deal.status == DealStatus.VISITED
        ]

    def list_for_pair(self, user_a_id: str, user_b_id: str) -> list[Deal]:
        """Returns all deals between the pair."""
        pair = set((user_a_id, user_b_id))
        return [
            deal
            for deal in self.store.deals.values()
            if set(deal.participant_ids) == pair
        ]
