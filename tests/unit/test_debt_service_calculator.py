"""Debt service calculator tests.

The calculator exists so that no figure reaching a client document originates from a
language model. These tests are what make that claim defensible.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.domain.entities.deal import Deal, Issuer, MaturityTranche, SecurityType
from src.infrastructure.calculators import DebtServiceCalculator


def _deal(maturities: list[MaturityTranche]) -> Deal:
    return Deal(
        deal_id="TEST-001",
        issuer=Issuer(issuer_id="ISS-1", name="Test ISD", state="TX"),
        series_name="Unlimited Tax School Building Bonds, Series 2026",
        security_type=SecurityType.UNLIMITED_TAX,
        par_amount=sum((m.principal_amount for m in maturities), Decimal("0")),
        maturities=maturities,
    )


class TestDebtServiceCalculator:
    def test_empty_maturities_returns_zero_schedule(self):
        schedule = DebtServiceCalculator().compute_debt_service(_deal([]))
        assert schedule.rows == []
        assert schedule.total_debt_service == Decimal("0.00")

    def test_single_maturity_interest_is_principal_times_coupon(self):
        tranche = MaturityTranche(
            maturity_date=date(2027, 8, 15),
            principal_amount=Decimal("1000000"),
            coupon_rate=Decimal("5.00"),
        )
        schedule = DebtServiceCalculator().compute_debt_service(_deal([tranche]))

        assert len(schedule.rows) == 1
        assert schedule.total_principal == Decimal("1000000.00")
        assert schedule.total_interest == Decimal("50000.00")

    def test_interest_accrues_until_each_tranche_matures(self):
        # A 2-year tranche pays interest in both years; a 1-year tranche pays in one.
        maturities = [
            MaturityTranche(
                maturity_date=date(2027, 8, 15),
                principal_amount=Decimal("1000000"),
                coupon_rate=Decimal("5.00"),
            ),
            MaturityTranche(
                maturity_date=date(2028, 8, 15),
                principal_amount=Decimal("1000000"),
                coupon_rate=Decimal("5.00"),
            ),
        ]
        schedule = DebtServiceCalculator().compute_debt_service(_deal(maturities))

        assert len(schedule.rows) == 2
        # Year one: both tranches outstanding. Year two: only the 2028 tranche.
        assert schedule.rows[0].interest == Decimal("100000.00")
        assert schedule.rows[1].interest == Decimal("50000.00")
        assert schedule.total_interest == Decimal("150000.00")

    def test_principal_lands_in_its_maturity_year(self):
        maturities = [
            MaturityTranche(
                maturity_date=date(2027, 8, 15),
                principal_amount=Decimal("400000"),
                coupon_rate=Decimal("4.00"),
            ),
            MaturityTranche(
                maturity_date=date(2028, 8, 15),
                principal_amount=Decimal("600000"),
                coupon_rate=Decimal("4.00"),
            ),
        ]
        schedule = DebtServiceCalculator().compute_debt_service(_deal(maturities))

        assert schedule.rows[0].principal == Decimal("400000.00")
        assert schedule.rows[1].principal == Decimal("600000.00")

    def test_row_total_sums_principal_and_interest(self):
        tranche = MaturityTranche(
            maturity_date=date(2027, 8, 15),
            principal_amount=Decimal("1000000"),
            coupon_rate=Decimal("5.00"),
        )
        schedule = DebtServiceCalculator().compute_debt_service(_deal([tranche]))
        assert schedule.rows[0].total == Decimal("1050000.00")

    def test_gap_years_without_maturities_are_still_rows(self):
        # Interest is payable in a year with no maturing principal, so the schedule
        # must not skip it.
        maturities = [
            MaturityTranche(
                maturity_date=date(2027, 8, 15),
                principal_amount=Decimal("500000"),
                coupon_rate=Decimal("4.00"),
            ),
            MaturityTranche(
                maturity_date=date(2030, 8, 15),
                principal_amount=Decimal("500000"),
                coupon_rate=Decimal("4.00"),
            ),
        ]
        schedule = DebtServiceCalculator().compute_debt_service(_deal(maturities))

        assert len(schedule.rows) == 4
        assert schedule.rows[1].principal == Decimal("0.00")
        assert schedule.rows[1].interest > Decimal("0.00")
