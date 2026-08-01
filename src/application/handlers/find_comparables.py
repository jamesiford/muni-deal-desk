"""Handler for comparables selection.

Reachable from both the MCP server and the workflow orchestrator through the mediator,
so the selection rules exist in exactly one place.
"""

from __future__ import annotations

from decimal import Decimal

from src.application.messages import FindComparables
from src.application.ports import DealRepositoryPort
from src.domain.contracts.agent_contracts import ComparableCandidates
from src.domain.entities.citation import EvidenceGap


class FindComparablesHandler:
    """Selects typed comparable issues without performing narrative retrieval."""

    def __init__(self, deals: DealRepositoryPort) -> None:
        self._deals = deals

    async def handle(self, message: FindComparables) -> ComparableCandidates:
        """Find entitled comparables and record typed-data gaps."""
        tolerance = message.par_amount * (message.par_tolerance_pct / Decimal("100"))

        deals, deals_withheld = await self._deals.find_comparables(
            caller=message.caller,
            state=message.state,
            security_type=message.security_type,
            par_amount=message.par_amount,
            par_tolerance=tolerance,
            months_back=message.months_back,
            limit=message.limit,
        )

        gaps: list[EvidenceGap] = []
        if not deals:
            gaps.append(
                EvidenceGap(
                    question=f"Comparable {message.state} issues in the last "
                    f"{message.months_back} months",
                    reason="No priced issues matched the state, security type and size range.",
                )
            )

        # A comparable without call terms cannot support a pricing discussion, so the
        # absence is reported rather than left for the reader to notice.
        for deal in deals:
            if deal.call_provision is None:
                gaps.append(
                    EvidenceGap(
                        question=f"Call provisions for {deal.series_name}",
                        reason="The source document did not state redemption terms.",
                    )
                )

        return ComparableCandidates(
            comparables=deals,
            gaps=gaps,
            excluded_by_permission=deals_withheld,
        )
