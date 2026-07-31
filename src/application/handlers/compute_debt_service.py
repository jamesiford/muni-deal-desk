"""Handler for deterministic debt service computation."""

from __future__ import annotations

from src.application.messages import ComputeDebtService
from src.application.ports import CalculatorPort, DealRepositoryPort
from src.domain.entities.deal import DebtServiceSchedule


class DealNotFoundError(LookupError):
    """Raised when a deal is absent, or present but not visible to the caller.

    Deliberately does not distinguish the two cases: telling a caller that a record
    exists but is barred would itself leak across the information barrier.
    """

    def __init__(self, deal_id: str) -> None:
        super().__init__(f"Deal {deal_id} was not found or is not available to this caller.")


class ComputeDebtServiceHandler:
    """Computes a debt service schedule for a deal the caller is entitled to see."""

    def __init__(self, deals: DealRepositoryPort, calculator: CalculatorPort) -> None:
        self._deals = deals
        self._calculator = calculator

    async def handle(self, message: ComputeDebtService) -> DebtServiceSchedule:
        """Fetch the deal, then compute its schedule arithmetically."""
        deal = await self._deals.get_deal(message.deal_id, message.caller)
        if deal is None:
            raise DealNotFoundError(message.deal_id)
        return self._calculator.compute_debt_service(deal)
