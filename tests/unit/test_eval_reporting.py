"""Tests for local gate reporting and paired model comparison."""

from __future__ import annotations

from evals.cases import build_cases
from evals.comparison import compare_reports
from evals.evaluators import EvaluationThresholds
from evals.reporting import CollectedCaseOutput, TokenUsage, evaluate_configuration
from src.domain.contracts.agent_contracts import ComplianceReview
from src.domain.policies.conduct_policies import DEFAULT_POLICIES


def _compliance_output(case_id: str, *, model_sensitive: bool, latency_ms: float):
    case = next(case for case in build_cases() if case.case_id == case_id)
    text = case.input.draft_text or ""
    findings = [policy.evaluate(text) for policy in DEFAULT_POLICIES]
    response = ComplianceReview(
        findings=findings,
        requires_human_review=True,
        blocking=any(not finding.passed for finding in findings),
    )
    return CollectedCaseOutput(
        case_id=case_id,
        target="research",
        model_sensitive=model_sensitive,
        response=response.model_dump(mode="json"),
        latency_ms=latency_ms,
        usage=TokenUsage(total_tokens=100),
    )


def test_reporting_rejects_incomplete_collection() -> None:
    cases = [case for case in build_cases() if case.case_id.startswith("guardrail-")]

    try:
        evaluate_configuration(
            cases,
            [_compliance_output(cases[0].case_id, model_sensitive=False, latency_ms=1.0)],
            environment="test",
            configuration="mini",
            model="mini-model",
        )
    except ValueError as error:
        assert "missing=" in str(error)
    else:
        raise AssertionError("Incomplete collections must fail closed.")


def test_reporting_applies_gate_and_comparison_uses_model_sensitive_pairs() -> None:
    cases = [case for case in build_cases() if case.case_id.startswith("guardrail-")]
    thresholds = EvaluationThresholds(
        minimum_pass_rate=1.0,
        category_minimum_pass_rates={cases[0].category: 1.0},
    )
    mini_outputs = [
        _compliance_output(case.case_id, model_sensitive=True, latency_ms=10.0) for case in cases
    ]
    reasoning_outputs = [
        _compliance_output(case.case_id, model_sensitive=True, latency_ms=15.0) for case in cases
    ]
    mini = evaluate_configuration(
        cases,
        mini_outputs,
        environment="test",
        configuration="mini",
        model="mini-model",
        thresholds=thresholds,
    )
    reasoning = evaluate_configuration(
        cases,
        reasoning_outputs,
        environment="test",
        configuration="reasoning",
        model="reasoning-model",
        thresholds=thresholds,
    )

    comparison = compare_reports(mini, reasoning)

    assert mini.gate.passed
    assert comparison.paired_case_count == 4
    assert comparison.quality_winner == "tie"
    assert comparison.reasoning_mean_latency_ms - comparison.mini_mean_latency_ms == 5.0
