"""Mediator messages.

Each message is a use case request. Handlers in `application/handlers` implement them.
Messages are frozen so a handler cannot mutate its input, which keeps behaviour
predictable when the same message is replayed during evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from src.domain.entities.deal import SecurityType


@dataclass(frozen=True, slots=True)
class Caller:
    """Concrete `CallerContext`. Passed explicitly on every message."""

    user_id: str
    group_claims: tuple[str, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class FindComparables:
    """Select priced issues comparable to a proposed new issue."""

    caller: Caller
    state: str
    security_type: SecurityType
    par_amount: Decimal
    months_back: int = 18
    par_tolerance_pct: Decimal = Decimal("40")
    limit: int = 5


@dataclass(frozen=True, slots=True)
class ComputeDebtService:
    """Compute a debt service schedule for a known deal."""

    caller: Caller
    deal_id: str


@dataclass(frozen=True, slots=True)
class GetDeal:
    """Fetch a deal the caller is entitled to see."""

    caller: Caller
    deal_id: str


@dataclass(frozen=True, slots=True)
class ReviewForCompliance:
    """Apply conduct policies to drafted text."""

    caller: Caller
    text: str


@dataclass(frozen=True, slots=True)
class DraftMarketSummary:
    """Produce a cited market summary for a proposed issue.

    The orchestrating use case: retrieves, analyses, drafts and reviews. Always
    returns a draft requiring human review.
    """

    caller: Caller
    request: str
    state: str
    security_type: SecurityType
    par_amount: Decimal
    months_back: int = 18
