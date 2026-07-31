"""Outbound port interfaces.

Application handlers depend only on these Protocols. Infrastructure supplies the
implementations, so the application layer imports no Azure SDK and unit tests run
without credentials.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from src.domain.contracts.agent_contracts import ComplianceReview
from src.domain.entities.citation import Citation
from src.domain.entities.deal import Deal, DebtServiceSchedule, SecurityType


class CallerContext(Protocol):
    """Identity and entitlements of the person the agent is acting for.

    Carried explicitly rather than read from ambient state so that the permission
    boundary is visible at every call site that depends on it.
    """

    @property
    def user_id(self) -> str:
        """Stable identifier for the calling user."""
        ...

    @property
    def group_claims(self) -> tuple[str, ...]:
        """Entra group identifiers used to filter retrieval."""
        ...


class KnowledgePort(Protocol):
    """Grounded retrieval over the document corpus."""

    async def search(
        self,
        query: str,
        caller: CallerContext,
        *,
        top: int = 10,
    ) -> tuple[list[Citation], int]:
        """Retrieve supporting passages for a query.

        Returns the passages the caller is entitled to see, and the count of matches
        withheld by the entitlement filter. The withheld count is returned rather
        than silently dropped so an answer can disclose that it is partial.
        """
        ...


class DealRepositoryPort(Protocol):
    """Structured lookup over extracted deal records.

    Separate from `KnowledgePort` because comparables selection filters and sorts on
    typed fields, which semantic retrieval over text chunks cannot do reliably.
    """

    async def find_comparables(
        self,
        *,
        caller: CallerContext,
        state: str,
        security_type: SecurityType,
        par_amount: Decimal,
        par_tolerance: Decimal,
        months_back: int,
        limit: int = 5,
    ) -> tuple[list[Deal], int]:
        """Find priced issues comparable to a proposed deal.

        Returns matches plus the count withheld by the entitlement filter.
        """
        ...

    async def get_deal(self, deal_id: str, caller: CallerContext) -> Deal | None:
        """Fetch a single deal the caller is entitled to see."""
        ...


class CalculatorPort(Protocol):
    """Deterministic financial computation.

    Kept out of the model path entirely: a figure that reaches a client document must
    come from arithmetic that can be re-run and audited.
    """

    def compute_debt_service(self, deal: Deal) -> DebtServiceSchedule:
        """Build a debt service schedule from a deal's maturity structure."""
        ...


class DocumentExtractionPort(Protocol):
    """Structured field extraction from source documents."""

    async def extract_deal(self, document_id: str) -> Deal | None:
        """Extract typed deal fields from a document."""
        ...


class AgentPort(Protocol):
    """Invocation of a registered specialist agent with a typed response."""

    async def invoke(
        self,
        agent_name: str,
        prompt: str,
        response_model: type,
        *,
        caller: CallerContext,
    ) -> object:
        """Invoke a specialist and return an instance of `response_model`."""
        ...


class CompliancePort(Protocol):
    """Guardrail review of generated text."""

    async def review(self, text: str) -> ComplianceReview:
        """Apply conduct policies and return the findings."""
        ...
