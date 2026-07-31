"""Domain entities for municipal new-issue analysis.

These types model the public finance concepts the Deal Desk reasons about. They carry
no Azure SDK imports and no I/O so the domain stays testable without credentials and
independently reviewable by a subject-matter expert.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class SecurityType(StrEnum):
    """Security pledge backing a municipal issue.

    Unlimited tax bonds carry an unlimited ad valorem tax pledge, which is why Texas
    school district issues are commonly compared against one another rather than
    against limited-tax or revenue credits.
    """

    UNLIMITED_TAX = "unlimited_tax"
    LIMITED_TAX = "limited_tax"
    REVENUE = "revenue"
    CERTIFICATE_OF_OBLIGATION = "certificate_of_obligation"


class Sensitivity(StrEnum):
    """Information-barrier classification for a source document.

    Broker-dealers separate public-side staff from private-side deal teams. Retrieval
    filters on this value, so it is a domain concept rather than an infrastructure
    detail.
    """

    PUBLIC = "public"
    PRIVATE = "private"


class Issuer(BaseModel):
    """A municipal issuer. Synthetic in this solution."""

    issuer_id: str
    name: str
    state: str = Field(min_length=2, max_length=2)
    county: str | None = None
    enrollment: int | None = Field(default=None, description="Student count for school districts.")
    taxable_assessed_valuation: Decimal | None = None


class CallProvision(BaseModel):
    """Optional redemption terms.

    Call features materially affect pricing, so a comparable is not usable for
    analysis unless its call provision is known.
    """

    first_call_date: date | None = None
    call_price: Decimal | None = Field(default=None, description="Percent of par, e.g. 100.")
    is_non_callable: bool = False


class MaturityTranche(BaseModel):
    """A single maturity within a serial or term bond structure."""

    maturity_date: date
    principal_amount: Decimal
    coupon_rate: Decimal = Field(description="Annual rate as a percent, e.g. 5.00.")
    yield_rate: Decimal | None = None


class RatingSet(BaseModel):
    """Ratings assigned to an issue. Any agency may be absent."""

    moodys: str | None = None
    sp: str | None = None
    fitch: str | None = None
    is_enhanced: bool = Field(
        default=False,
        description="True when supported by a guaranty programme such as the Texas PSF.",
    )


class Deal(BaseModel):
    """A municipal new issue, either priced (a comparable) or proposed (the subject)."""

    deal_id: str
    issuer: Issuer
    series_name: str
    security_type: SecurityType
    par_amount: Decimal
    dated_date: date | None = None
    first_maturity: date | None = None
    final_maturity: date | None = None
    ratings: RatingSet = Field(default_factory=RatingSet)
    call_provision: CallProvision | None = None
    maturities: list[MaturityTranche] = Field(default_factory=list)
    sensitivity: Sensitivity = Sensitivity.PUBLIC
    source_document_id: str | None = None


class DebtServiceRow(BaseModel):
    """One period of a debt service schedule."""

    period_ending: date
    principal: Decimal
    interest: Decimal

    @property
    def total(self) -> Decimal:
        """Total debt service for the period."""
        return self.principal + self.interest


class DebtServiceSchedule(BaseModel):
    """A computed debt service schedule.

    Produced by the calculator port rather than by a language model, because a model
    must never be the source of a number that reaches a client document.
    """

    deal_id: str
    rows: list[DebtServiceRow]
    total_principal: Decimal
    total_interest: Decimal

    @property
    def total_debt_service(self) -> Decimal:
        """Aggregate principal and interest across all periods."""
        return self.total_principal + self.total_interest
