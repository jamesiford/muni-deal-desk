"""Tests for deterministic manifest-backed deal lookup."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from src.domain.entities.deal import SecurityType
from src.infrastructure.manifest_repository import ManifestDealRepository

DEAL_TEAM = "deal-team-private-side"
SUBJECT_ACCESS = "subject-deal-access"


@dataclass
class Caller:
    user_id: str
    group_claims: tuple[str, ...]


async def test_comparables_are_unique_and_report_private_sources() -> None:
    repository = ManifestDealRepository(
        Path("src/corpus/out/manifest.json"),
        today=date(2026, 7, 31),
    )

    deals, _, withheld = await repository.find_comparables(
        caller=Caller("public-user", ()),
        state="TX",
        security_type=SecurityType.UNLIMITED_TAX,
        par_amount=Decimal("90000000"),
        par_tolerance=Decimal("60000000"),
        months_back=24,
        limit=20,
    )

    assert len({deal.deal_id for deal in deals}) == len(deals)
    assert withheld == 3


async def test_deal_team_sees_no_withheld_source_records() -> None:
    repository = ManifestDealRepository(
        Path("src/corpus/out/manifest.json"),
        today=date(2026, 7, 31),
    )

    _, _, withheld = await repository.find_comparables(
        caller=Caller("deal-team-user", (DEAL_TEAM,)),
        state="TX",
        security_type=SecurityType.UNLIMITED_TAX,
        par_amount=Decimal("90000000"),
        par_tolerance=Decimal("60000000"),
        months_back=24,
        limit=20,
    )

    assert withheld == 0


async def test_identity_switch_changes_comparable_evidence_sources() -> None:
    repository = ManifestDealRepository(
        Path("src/corpus/out/manifest.json"),
        today=date(2026, 7, 31),
    )
    filters = {
        "state": "TX",
        "security_type": SecurityType.UNLIMITED_TAX,
        "par_amount": Decimal("85000000"),
        "par_tolerance": Decimal("60000000"),
        "months_back": 24,
        "limit": 20,
    }

    _, public_evidence, public_withheld = await repository.find_comparables(
        caller=Caller("public-user", (SUBJECT_ACCESS,)),
        **filters,
    )
    _, deal_team_evidence, deal_team_withheld = await repository.find_comparables(
        caller=Caller("deal-team-user", (SUBJECT_ACCESS, DEAL_TEAM)),
        **filters,
    )

    public_ids = {source.document_id for source in public_evidence}
    deal_team_ids = {source.document_id for source in deal_team_evidence}
    assert not public_ids & {"PM-001", "PM-002", "PM-003"}
    assert {"PM-001", "PM-002", "PM-003"} <= deal_team_ids
    assert public_withheld == 3
    assert deal_team_withheld == 0


async def test_get_deal_returns_visible_public_record() -> None:
    repository = ManifestDealRepository(Path("src/corpus/out/manifest.json"))

    deal = await repository.get_deal("DEAL-001", Caller("public-user", ()))

    assert deal is not None
    assert deal.issuer.name == "Blue Mesa Fictional Independent School District"


async def test_subject_deal_requires_deal_team_claim() -> None:
    repository = ManifestDealRepository(Path("src/corpus/out/manifest.json"))

    public = await repository.get_deal("DEAL-SUBJECT-001", Caller("public-user", ()))
    private = await repository.get_deal("DEAL-SUBJECT-001", Caller("deal-team-user", (DEAL_TEAM,)))

    assert public is None
    assert private is not None
    assert private.par_amount == Decimal("85000000")


async def test_subject_deal_allows_public_demo_persona_claim() -> None:
    repository = ManifestDealRepository(Path("src/corpus/out/manifest.json"))

    subject = await repository.get_deal(
        "DEAL-SUBJECT-001",
        Caller("public-user", (SUBJECT_ACCESS,)),
    )

    assert subject is not None
