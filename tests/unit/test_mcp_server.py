"""Offline MCP tool dispatch tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.application.messages import Caller
from src.domain.entities.deal import Deal, Issuer, MaturityTranche, SecurityType
from src.hosts.mcp_server.composition import create_mediator
from src.hosts.mcp_server.server import create_mcp_server
from src.infrastructure.calculators import DebtServiceCalculator
from src.infrastructure.mcp.factory import AdapterBundle


def _deal() -> Deal:
    return Deal(
        deal_id="DEAL-001",
        issuer=Issuer(issuer_id="ISS-001", name="Test ISD", state="TX"),
        series_name="Series 2026",
        security_type=SecurityType.UNLIMITED_TAX,
        par_amount=Decimal("1000000"),
        maturities=[
            MaturityTranche(
                maturity_date=date(2027, 8, 15),
                principal_amount=Decimal("1000000"),
                coupon_rate=Decimal("5.00"),
            )
        ],
    )


class RecordingAdapters:
    def __init__(self) -> None:
        self.deal = _deal()
        self.callers: list[Caller] = []

    async def get_deal(self, deal_id: str, caller: Caller) -> Deal | None:
        self.callers.append(caller)
        return self.deal if deal_id == self.deal.deal_id else None

    async def find_comparables(self, *, caller: Caller, **_filters):
        self.callers.append(caller)
        return [self.deal], [], 2


async def test_tools_dispatch_through_mediator_with_explicit_caller():
    adapters = RecordingAdapters()
    mediator = create_mediator(AdapterBundle(deals=adapters))
    server = create_mcp_server(mediator)
    caller = {"caller_user_id": "analyst", "caller_group_claims": ["public-side"]}

    _, deal_result = await server.call_tool("get_deal", {"deal_id": "DEAL-001", **caller})
    _, comparable_result = await server.call_tool(
        "find_comparable_deals",
        {
            "state": "TX",
            "security_type": "unlimited_tax",
            "par_amount": "1000000",
            **caller,
        },
    )

    assert deal_result["deal_id"] == "DEAL-001"
    assert comparable_result["excluded_by_permission"] == 2
    assert adapters.callers == [
        Caller("analyst", ("public-side",)),
        Caller("analyst", ("public-side",)),
    ]


async def test_compute_tool_matches_debt_service_calculator_values():
    adapters = RecordingAdapters()
    mediator = create_mediator(AdapterBundle(deals=adapters))
    server = create_mcp_server(mediator)

    _, result = await server.call_tool(
        "compute_debt_service",
        {
            "deal_id": "DEAL-001",
            "caller_user_id": "analyst",
            "caller_group_claims": ["public-side"],
        },
    )
    expected = DebtServiceCalculator().compute_debt_service(adapters.deal)

    assert Decimal(result["total_principal"]) == expected.total_principal
    assert Decimal(result["total_interest"]) == expected.total_interest
