"""Tests for typed-only comparable selection."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.application.handlers.find_comparables import FindComparablesHandler
from src.application.messages import Caller, FindComparables
from src.domain.contracts.agent_contracts import ComparableCandidates
from src.domain.entities.deal import Deal, Issuer, SecurityType


class Deals:
    async def find_comparables(self, **_kwargs):
        return (
            [
                Deal(
                    deal_id="DEAL-001",
                    issuer=Issuer(issuer_id="ISS-001", name="Test ISD", state="TX"),
                    series_name="Series 2026",
                    security_type=SecurityType.UNLIMITED_TAX,
                    par_amount=Decimal("85000000"),
                    dated_date=date(2026, 1, 1),
                )
            ],
            [],
            2,
        )


async def test_handler_returns_typed_candidates_without_knowledge_dependency() -> None:
    result = await FindComparablesHandler(Deals()).handle(
        FindComparables(
            caller=Caller("researcher"),
            state="TX",
            security_type=SecurityType.UNLIMITED_TAX,
            par_amount=Decimal("85000000"),
        )
    )

    assert isinstance(result, ComparableCandidates)
    assert [deal.deal_id for deal in result.comparables] == ["DEAL-001"]
    assert result.excluded_by_permission == 2
