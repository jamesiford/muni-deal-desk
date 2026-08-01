"""Get-deal handler entitlement tests."""

from __future__ import annotations

from decimal import Decimal

import pytest
from src.application.handlers.compute_debt_service import DealNotFoundError
from src.application.handlers.get_deal import GetDealHandler
from src.application.messages import Caller, GetDeal
from src.domain.entities.deal import Deal, Issuer, SecurityType


class RecordingDealRepository:
    def __init__(self, deal: Deal | None) -> None:
        self.deal = deal
        self.calls: list[tuple[str, Caller]] = []

    async def get_deal(self, deal_id: str, caller: Caller) -> Deal | None:
        self.calls.append((deal_id, caller))
        return self.deal


def _deal() -> Deal:
    return Deal(
        deal_id="DEAL-001",
        issuer=Issuer(issuer_id="ISS-001", name="Test ISD", state="TX"),
        series_name="Series 2026",
        security_type=SecurityType.UNLIMITED_TAX,
        par_amount=Decimal("1000000"),
    )


class TestGetDealHandler:
    async def test_returns_visible_deal_and_passes_explicit_caller(self):
        caller = Caller(user_id="analyst", group_claims=("public-side",))
        repository = RecordingDealRepository(_deal())

        result = await GetDealHandler(repository).handle(GetDeal(caller, "DEAL-001"))

        assert result.deal_id == "DEAL-001"
        assert repository.calls == [("DEAL-001", caller)]

    async def test_absent_or_barred_deal_has_the_same_error(self):
        repository = RecordingDealRepository(None)

        with pytest.raises(DealNotFoundError, match="not found or is not available"):
            await GetDealHandler(repository).handle(
                GetDeal(Caller(user_id="analyst"), "DEAL-PRIVATE")
            )
