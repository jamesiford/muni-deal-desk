"""Handler for entitlement-aware deal lookup."""

from __future__ import annotations

from src.application.handlers.compute_debt_service import DealNotFoundError
from src.application.messages import GetDeal
from src.application.ports import DealRepositoryPort
from src.domain.entities.deal import Deal


class GetDealHandler:
    """Fetches a deal without disclosing whether an unavailable record exists."""

    def __init__(self, deals: DealRepositoryPort) -> None:
        self._deals = deals

    async def handle(self, message: GetDeal) -> Deal:
        """Return a visible deal or the shared non-disclosing lookup error."""
        deal = await self._deals.get_deal(message.deal_id, message.caller)
        if deal is None:
            raise DealNotFoundError(message.deal_id)
        return deal
