"""Typed local reports and promotion-gate aggregation for Phase 7."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, Field

from evals.cases import EvaluationCase
from evals.evaluators import (
    EvaluationResult,
    EvaluationThresholds,
    GateResult,
    evaluate_case,
    evaluate_critical_gate,
)
from evals.foundry import PortalEvaluationRow


class TokenUsage(BaseModel):
    """Token counts captured from a model response when the provider exposes them."""

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class CollectedCaseOutput(BaseModel):
    """Raw output and telemetry from one case target."""

    case_id: str
    target: str
    model_sensitive: bool
    response: dict[str, object]
    latency_ms: float = Field(ge=0.0)
    usage: TokenUsage = Field(default_factory=TokenUsage)


class EvaluatedCaseOutput(CollectedCaseOutput):
    """Collected case output with deterministic evaluator results."""

    category: str
    expected_behavior: str
    evaluator_results: list[EvaluationResult]
    deterministic_pass: bool


class ConfigurationReport(BaseModel):
    """Complete local gate report for one controlled model configuration."""

    environment: str
    configuration: str
    model: str
    cases: list[EvaluatedCaseOutput]
    gate: GateResult


def evaluate_configuration(
    cases: Sequence[EvaluationCase],
    outputs: Sequence[CollectedCaseOutput],
    *,
    environment: str,
    configuration: str,
    model: str,
    thresholds: EvaluationThresholds | None = None,
) -> ConfigurationReport:
    """Evaluate a complete collection and apply committed promotion thresholds."""
    cases_by_id = {case.case_id: case for case in cases}
    outputs_by_id = {output.case_id: output for output in outputs}
    if len(outputs_by_id) != len(outputs):
        raise ValueError("Collected case IDs must be unique.")
    missing = sorted(set(cases_by_id) - set(outputs_by_id))
    unexpected = sorted(set(outputs_by_id) - set(cases_by_id))
    if missing or unexpected:
        raise ValueError(f"Collection mismatch: missing={missing}, unexpected={unexpected}")

    evaluated: list[EvaluatedCaseOutput] = []
    case_passes: dict[str, bool] = {}
    for case in cases:
        output = outputs_by_id[case.case_id]
        results = evaluate_case(case, output.response)
        passed = all(result.passed for result in results)
        case_passes[case.case_id] = passed
        evaluated.append(
            EvaluatedCaseOutput(
                **output.model_dump(),
                category=case.category.value,
                expected_behavior=case.expected_behavior,
                evaluator_results=results,
                deterministic_pass=passed,
            )
        )
    return ConfigurationReport(
        environment=environment,
        configuration=configuration,
        model=model,
        cases=evaluated,
        gate=evaluate_critical_gate(list(cases), case_passes, thresholds),
    )


def to_portal_rows(
    report: ConfigurationReport,
    cases: Sequence[EvaluationCase],
) -> list[PortalEvaluationRow]:
    """Map a local report to pre-collected inline evaluation rows."""
    questions = {case.case_id: case.input.question for case in cases}
    return [
        PortalEvaluationRow(
            case_id=result.case_id,
            category=result.category,
            configuration=report.configuration,
            question=questions[result.case_id],
            expected_behavior=result.expected_behavior,
            deterministic_pass=result.deterministic_pass,
            response=result.response,
        )
        for result in report.cases
    ]
