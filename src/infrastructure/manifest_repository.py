"""Structured deal lookup over the packaged synthetic corpus manifest."""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from pathlib import Path

from src.application.ports import CallerContext
from src.corpus.manifest import CorpusManifest, DocumentEntry
from src.domain.entities.deal import Deal, SecurityType


class ManifestDealRepository:
    """Deterministic typed lookup without retaining a second Search index."""

    def __init__(self, manifest_path: Path, *, today: date | None = None) -> None:
        self._manifest = CorpusManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
        self._today = today or date.today()

    @staticmethod
    def _is_visible(entry: DocumentEntry, caller: CallerContext) -> bool:
        return not entry.allowed_group_claims or bool(
            set(entry.allowed_group_claims) & set(caller.group_claims)
        )

    @staticmethod
    def _subtract_months(value: date, months: int) -> date:
        month_index = value.year * 12 + value.month - 1 - months
        year, zero_based_month = divmod(month_index, 12)
        month = zero_based_month + 1
        day = min(value.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

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
        """Return entitled unique deals and count matching private source documents."""
        cutoff = self._subtract_months(self._today, months_back)
        lower = par_amount - par_tolerance
        upper = par_amount + par_tolerance
        matching = [
            entry
            for entry in self._manifest.documents
            if entry.expected_deal is not None
            and entry.expected_deal.issuer.state == state
            and entry.expected_deal.security_type is security_type
            and lower <= entry.expected_deal.par_amount <= upper
            and entry.expected_deal.dated_date is not None
            and entry.expected_deal.dated_date >= cutoff
        ]
        visible = [entry for entry in matching if self._is_visible(entry, caller)]
        withheld = sum(not self._is_visible(entry, caller) for entry in matching)
        deals_by_id: dict[str, Deal] = {}
        for entry in sorted(
            visible,
            key=lambda item: item.expected_deal.dated_date,  # type: ignore[union-attr,return-value]
            reverse=True,
        ):
            deal = entry.expected_deal
            if deal is not None:
                deals_by_id.setdefault(deal.deal_id, deal)
        return list(deals_by_id.values())[:limit], withheld

    async def get_deal(self, deal_id: str, caller: CallerContext) -> Deal | None:
        """Return a deal only when at least one source record is visible to the caller."""
        for entry in self._manifest.documents:
            deal = entry.expected_deal
            if deal is not None and deal.deal_id == deal_id and self._is_visible(entry, caller):
                return deal.model_copy(deep=True)
        return None
