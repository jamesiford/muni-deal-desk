"""Handler for comparables selection.

Reachable from both the MCP server and the workflow orchestrator through the mediator,
so the selection rules exist in exactly one place.
"""

from __future__ import annotations

from decimal import Decimal

from src.application.messages import FindComparables
from src.application.ports import DealRepositoryPort, KnowledgePort
from src.domain.contracts.agent_contracts import ResearchFindings
from src.domain.entities.citation import EvidenceGap


class FindComparablesHandler:
    """Selects comparable issues and reports what could not be found or seen."""

    def __init__(self, deals: DealRepositoryPort, knowledge: KnowledgePort) -> None:
        self._deals = deals
        self._knowledge = knowledge

    async def handle(self, message: FindComparables) -> ResearchFindings:
        """Find comparables, gather supporting citations, and record gaps."""
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

        query = (
            f"{message.state} {message.security_type.value.replace('_', ' ')} "
            f"new issue pricing and call features"
        )
        citations, citations_withheld = await self._knowledge.search(query, message.caller)

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

        return ResearchFindings(
            comparables=deals,
            citations=citations,
            gaps=gaps,
            excluded_by_permission=deals_withheld + citations_withheld,
        )
