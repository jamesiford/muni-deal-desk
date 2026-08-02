"""Outbound port interfaces.

Application handlers depend only on these Protocols. Infrastructure supplies the
implementations, so the application layer imports no Azure SDK and unit tests run
without credentials.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol, TypeVar

from src.domain.contracts.agent_contracts import ComplianceReview
from src.domain.entities.citation import EvidenceSource
from src.domain.entities.deal import Deal, DebtServiceSchedule, SecurityType

TResponse = TypeVar("TResponse")


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


class DealRepositoryPort(Protocol):
    """Structured lookup over extracted deal records.

    Comparables selection filters and sorts on typed fields, which semantic retrieval
    over text chunks cannot do reliably.
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
    ) -> tuple[list[Deal], list[EvidenceSource], int]:
        """Find priced issues comparable to a proposed deal.

        Returns unique deals, visible source records, and the count withheld by the
        entitlement filter.
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
        response_model: type[TResponse],
        *,
        caller: CallerContext,
    ) -> TResponse:
        """Invoke a specialist and return an instance of `response_model`."""
        ...


class ModelPort(Protocol):
    """Typed invocation of a Foundry model deployment."""

    async def invoke(
        self,
        model: str,
        instructions: str,
        prompt: str,
        response_model: type[TResponse],
    ) -> TResponse:
        """Run a model and validate its structured response."""
        ...


class CompliancePort(Protocol):
    """Guardrail review of generated text."""

    async def review(self, text: str) -> ComplianceReview:
        """Apply conduct policies and return the findings."""
        ...
