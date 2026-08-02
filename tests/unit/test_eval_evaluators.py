"""Focused tests for deterministic Phase 7 evaluators and gating."""

from __future__ import annotations

from evals.cases import EvaluationCase, build_cases
from evals.evaluators import (
    evaluate_case,
    evaluate_citations,
    evaluate_contract,
    evaluate_critical_gate,
    evaluate_entitlements,
    evaluate_expected_deal_ids,
    evaluate_expected_figures,
    evaluate_gaps,
    evaluate_guardrails,
    load_thresholds,
)
from src.corpus import generate as corpus_generate
from src.domain.contracts.agent_contracts import (
    ComparableCandidates,
    ComplianceReview,
    DealDeskAnswer,
    ResearchFindings,
)
from src.domain.entities.citation import Citation, EvidenceGap, EvidenceSource
from src.domain.entities.deal import Deal, Sensitivity
from src.domain.policies.conduct_policies import DEFAULT_POLICIES
from src.infrastructure.calculators import DebtServiceCalculator


def _case(case_id: str) -> EvaluationCase:
    return next(case for case in build_cases() if case.case_id == case_id)


def _deal(deal_id: str) -> Deal:
    return next(
        document.deal
        for document in corpus_generate._official_statement_documents()
        if document.deal.deal_id == deal_id
    )


def _review(text: str) -> ComplianceReview:
    findings = [policy.evaluate(text) for policy in DEFAULT_POLICIES]
    return ComplianceReview(
        findings=findings,
        requires_human_review=True,
        blocking=any(not finding.passed for finding in findings),
    )


def test_contract_and_ordered_deal_id_evaluators() -> None:
    case = _case("comparable-subject-band")
    response = ResearchFindings(
        comparables=[_deal(deal_id) for deal_id in case.expected.deal_ids],
        citations=[],
    )

    assert evaluate_contract(case, response).passed
    assert evaluate_expected_deal_ids(case, response).passed
    assert not evaluate_contract(case, {"comparables": "not-a-list"}).passed


def test_figure_evaluator_reads_computed_total_property() -> None:
    case = _case("debt-service-deal-subject-001")
    schedule = DebtServiceCalculator().compute_debt_service(corpus_generate._subject_deal())

    assert evaluate_expected_figures(case, schedule).passed
    assert not evaluate_expected_figures(
        case,
        schedule.model_copy(update={"total_interest": schedule.total_interest + 1}),
    ).passed


def test_citation_evaluator_checks_documents_and_sensitivity() -> None:
    case = _case("citation-conflicting-enrollment")
    citations = [
        Citation(
            document_id=f"fiq-ref-{index}",
            document_title=title_term,
            excerpt="Synthetic enrollment disclosure.",
        )
        for index, title_term in enumerate(case.expected.required_citation_title_terms)
    ]
    response = ResearchFindings(
        comparables=[_deal("DEAL-006")],
        citations=citations,
    )

    assert evaluate_citations(case, response).passed
    assert not evaluate_citations(
        case,
        response.model_copy(update={"citations": citations[:1]}),
    ).passed


def test_gap_evaluator_requires_every_ground_truth_term() -> None:
    case = _case("gap-conflicting-enrollment")
    response = ResearchFindings(
        comparables=[_deal("DEAL-006")],
        citations=[],
        gaps=[
            EvidenceGap(
                question="Which enrollment figure is current?",
                reason="12,840 conflicts with 13,215; review is required.",
            )
        ],
    )

    assert evaluate_gaps(case, response).passed
    assert not evaluate_gaps(
        case,
        response.model_copy(
            update={"gaps": [EvidenceGap(question="Enrollment?", reason="Unavailable.")]}
        ),
    ).passed


def test_entitlement_evaluator_distinguishes_public_and_deal_team_sources() -> None:
    public_case = _case("entitlement-public-withholding")
    public_response = ComparableCandidates(
        comparables=[_deal("DEAL-001")],
        excluded_by_permission=3,
    )
    assert evaluate_entitlements(public_case, public_response).passed
    assert all(result.passed for result in evaluate_case(public_case, public_response))

    private_case = _case("entitlement-deal-team-private-access")
    private_response = ComparableCandidates(
        comparables=[],
        evidence_sources=[
            EvidenceSource(
                document_id=document_id,
                document_title=document_id,
                deal_id=f"DEAL-00{index}",
                source_type="internal_pricing_memo",
                sensitivity=Sensitivity.PRIVATE,
            )
            for index, document_id in enumerate(("PM-001", "PM-002", "PM-003"), start=1)
        ],
        excluded_by_permission=0,
    )
    assert evaluate_entitlements(private_case, private_response).passed
    assert not evaluate_entitlements(public_case, private_response).passed


def test_partial_answer_entitlement_and_human_review_are_checked() -> None:
    case = _case("entitlement-partial-answer-disclosure")
    response = DealDeskAnswer(summary="Public-only answer.", partial_due_to_permissions=True)

    assert evaluate_entitlements(case, response).passed
    assert evaluate_guardrails(case, response).passed


def test_guardrail_evaluator_checks_blocking_and_failed_policy_ids() -> None:
    blocked_case = _case("guardrail-fiduciary-implication")
    blocked = _review(blocked_case.input.draft_text or "")
    assert evaluate_guardrails(blocked_case, blocked).passed

    clean_case = _case("guardrail-clean-cited-draft")
    clean = _review(clean_case.input.draft_text or "")
    assert evaluate_guardrails(clean_case, clean).passed
    assert not evaluate_guardrails(blocked_case, clean).passed


def test_gate_allows_one_noncritical_miss_but_rejects_critical_miss() -> None:
    cases = build_cases()
    passes = {case.case_id: True for case in cases}
    passes["comparable-exact-45m"] = False

    allowed = evaluate_critical_gate(cases, passes, load_thresholds())
    assert allowed.passed
    assert allowed.overall_pass_rate == 0.96

    passes["debt-service-deal-subject-001"] = False
    blocked = evaluate_critical_gate(cases, passes, load_thresholds())
    assert not blocked.passed
    assert "debt-service-deal-subject-001" in blocked.failed_critical_case_ids
