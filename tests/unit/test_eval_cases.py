"""Tests for the deterministic Phase 7 evaluation dataset."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from pathlib import Path

from evals.cases import EvaluationCategory, build_cases, render_jsonl


def test_dataset_has_exact_requested_category_distribution() -> None:
    cases = build_cases()

    assert len(cases) == 25
    assert len({case.case_id for case in cases}) == 25
    assert Counter(case.category for case in cases) == {
        EvaluationCategory.COMPARABLE_SELECTION: 6,
        EvaluationCategory.DEBT_SERVICE_FIGURES: 4,
        EvaluationCategory.CITATION_INTEGRITY: 4,
        EvaluationCategory.GAP_DISCLOSURE: 4,
        EvaluationCategory.ENTITLEMENT_CONTRASTS: 3,
        EvaluationCategory.GUARDRAILS: 4,
    }


def test_every_case_is_reviewable_and_grounded() -> None:
    for case in build_cases():
        assert case.input.question.strip()
        assert case.expected_behavior.strip()
        assert case.expected.contract.value


def test_subject_debt_service_ground_truth_comes_from_calculator() -> None:
    case = next(case for case in build_cases() if case.case_id == "debt-service-deal-subject-001")

    assert case.expected.figures == {
        "total_principal": Decimal("85000000.00"),
        "total_interest": Decimal("22673750.00"),
        "total_debt_service": Decimal("107673750.00"),
    }


def test_committed_snapshot_matches_generator_byte_for_byte() -> None:
    snapshot = Path("evals/cases.jsonl").read_text(encoding="utf-8")

    assert snapshot == render_jsonl()
