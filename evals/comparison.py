"""Paired comparison of model-sensitive Phase 7 case results."""

from __future__ import annotations

from statistics import fmean

from pydantic import BaseModel

from evals.reporting import ConfigurationReport, EvaluatedCaseOutput


class PairedCaseComparison(BaseModel):
    """Delta for one case collected under both model configurations."""

    case_id: str
    mini_passed: bool
    reasoning_passed: bool
    latency_delta_ms: float
    total_token_delta: int | None


class ComparisonReport(BaseModel):
    """Aggregate paired comparison without statistical-significance claims."""

    mini_configuration: str
    reasoning_configuration: str
    paired_case_count: int
    mini_pass_rate: float
    reasoning_pass_rate: float
    mini_mean_latency_ms: float
    reasoning_mean_latency_ms: float
    quality_winner: str
    pairs: list[PairedCaseComparison]


def _total_tokens(result: EvaluatedCaseOutput) -> int | None:
    return result.usage.total_tokens


def compare_reports(
    mini: ConfigurationReport,
    reasoning: ConfigurationReport,
) -> ComparisonReport:
    """Compare paired model-sensitive cases from controlled configurations."""
    mini_by_id = {case.case_id: case for case in mini.cases if case.model_sensitive}
    reasoning_by_id = {case.case_id: case for case in reasoning.cases if case.model_sensitive}
    if set(mini_by_id) != set(reasoning_by_id):
        raise ValueError("Model-sensitive case sets must match for paired comparison.")
    case_ids = sorted(mini_by_id)
    if not case_ids:
        raise ValueError("At least one model-sensitive case is required for comparison.")

    pairs: list[PairedCaseComparison] = []
    for case_id in case_ids:
        mini_case = mini_by_id[case_id]
        reasoning_case = reasoning_by_id[case_id]
        mini_tokens = _total_tokens(mini_case)
        reasoning_tokens = _total_tokens(reasoning_case)
        token_delta = (
            reasoning_tokens - mini_tokens
            if mini_tokens is not None and reasoning_tokens is not None
            else None
        )
        pairs.append(
            PairedCaseComparison(
                case_id=case_id,
                mini_passed=mini_case.deterministic_pass,
                reasoning_passed=reasoning_case.deterministic_pass,
                latency_delta_ms=reasoning_case.latency_ms - mini_case.latency_ms,
                total_token_delta=token_delta,
            )
        )

    mini_rate = sum(pair.mini_passed for pair in pairs) / len(pairs)
    reasoning_rate = sum(pair.reasoning_passed for pair in pairs) / len(pairs)
    quality_winner = "tie"
    if mini_rate > reasoning_rate:
        quality_winner = mini.configuration
    elif reasoning_rate > mini_rate:
        quality_winner = reasoning.configuration
    return ComparisonReport(
        mini_configuration=mini.configuration,
        reasoning_configuration=reasoning.configuration,
        paired_case_count=len(pairs),
        mini_pass_rate=mini_rate,
        reasoning_pass_rate=reasoning_rate,
        mini_mean_latency_ms=fmean(mini_by_id[case_id].latency_ms for case_id in case_ids),
        reasoning_mean_latency_ms=fmean(
            reasoning_by_id[case_id].latency_ms for case_id in case_ids
        ),
        quality_winner=quality_winner,
        pairs=pairs,
    )
