"""Deterministic debt service calculation.

Implements `CalculatorPort` with plain arithmetic and no model involvement. This is the
boundary the demo makes explicit: narrative comes from a model, numbers do not.

Placed in infrastructure because it implements a port, though it has no external
dependency and is therefore directly unit-testable.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from src.domain.entities.deal import Deal, DebtServiceRow, DebtServiceSchedule

_CENTS = Decimal("0.01")
_SEMIANNUAL_PERIODS_PER_YEAR = 2


def _round(value: Decimal) -> Decimal:
    """Round to cents using half-up, the convention for debt service schedules."""
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


class DebtServiceCalculator:
    """Computes debt service from a deal's maturity structure.

    Assumes semiannual interest on a 30/360 basis, which is the standard convention for
    fixed-rate municipal bonds. Interest accrues on principal outstanding, so each
    tranche contributes interest until the period in which it matures.
    """

    def compute_debt_service(self, deal: Deal) -> DebtServiceSchedule:
        """Build an annual debt service schedule for the deal."""
        if not deal.maturities:
            return DebtServiceSchedule(
                deal_id=deal.deal_id,
                rows=[],
                total_principal=Decimal("0.00"),
                total_interest=Decimal("0.00"),
            )

        principal_by_year: dict[int, Decimal] = defaultdict(Decimal)
        interest_by_year: dict[int, Decimal] = defaultdict(Decimal)

        first_year = min(m.maturity_date.year for m in deal.maturities)
        final_year = max(m.maturity_date.year for m in deal.maturities)

        for tranche in deal.maturities:
            principal_by_year[tranche.maturity_date.year] += tranche.principal_amount

            # A tranche pays interest from the first year through its maturity year.
            semiannual_rate = (tranche.coupon_rate / Decimal("100")) / Decimal(
                _SEMIANNUAL_PERIODS_PER_YEAR
            )
            annual_interest = (
                tranche.principal_amount * semiannual_rate * Decimal(_SEMIANNUAL_PERIODS_PER_YEAR)
            )
            for year in range(first_year, tranche.maturity_date.year + 1):
                interest_by_year[year] += annual_interest

        rows = [
            DebtServiceRow(
                period_ending=date(year, 8, 15),
                principal=_round(principal_by_year[year]),
                interest=_round(interest_by_year[year]),
            )
            for year in range(first_year, final_year + 1)
        ]

        return DebtServiceSchedule(
            deal_id=deal.deal_id,
            rows=rows,
            total_principal=_round(sum(principal_by_year.values(), Decimal("0"))),
            total_interest=_round(sum(interest_by_year.values(), Decimal("0"))),
        )
