"""Deterministic evaluators for the synthetic Phase 7 dataset."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError
from src.domain.contracts.agent_contracts import (
    ComparableCandidates,
    ComplianceReview,
    DealDeskAnswer,
    ResearchFindings,
)
from src.domain.entities.deal import DebtServiceSchedule, Sensitivity

from evals.cases import ContractName, EvaluationCase, EvaluationCategory

ResponseValue = BaseModel | Mapping[str, object] | str

_CONTRACT_TYPES: dict[ContractName, type[BaseModel]] = {
    ContractName.COMPARABLE_CANDIDATES: ComparableCandidates,
    ContractName.RESEARCH_FINDINGS: ResearchFindings,
    ContractName.DEBT_SERVICE_SCHEDULE: DebtServiceSchedule,
    ContractName.DEAL_DESK_ANSWER: DealDeskAnswer,
    ContractName.COMPLIANCE_REVIEW: ComplianceReview,
}


class EvaluationResult(BaseModel):
    """Result from one deterministic evaluator."""

    evaluator: str
    passed: bool
    detail: str


class EvaluationThresholds(BaseModel):
    """Promotion thresholds applied to a complete local run."""

    minimum_pass_rate: float = Field(ge=0.0, le=1.0)
    category_minimum_pass_rates: dict[EvaluationCategory, float]
    critical_cases_must_pass: bool = True


class GateResult(BaseModel):
    """Aggregate deterministic promotion-gate result."""

    passed: bool
    overall_pass_rate: float
    category_pass_rates: dict[EvaluationCategory, float]
    failed_critical_case_ids: list[str]
    reasons: list[str]


def _validate(case: EvaluationCase, response: ResponseValue) -> BaseModel:
    contract_type = _CONTRACT_TYPES[case.expected.contract]
    if isinstance(response, str):
        return contract_type.model_validate_json(response)
    if isinstance(response, BaseModel):
        return contract_type.model_validate(response.model_dump())
    return contract_type.model_validate(dict(response))


def _invalid_contract(evaluator: str, error: ValidationError) -> EvaluationResult:
    return EvaluationResult(
        evaluator=evaluator,
        passed=False,
        detail=f"Response does not satisfy the declared contract: {error.errors()[0]['msg']}",
    )


def _payload(model: BaseModel) -> dict[str, object]:
    return model.model_dump(mode="python")


def _collect_lists(value: object, keys: set[str]) -> list[object]:
    collected: list[object] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in keys and isinstance(item, Sequence) and not isinstance(item, str):
                collected.extend(item)
            collected.extend(_collect_lists(item, keys))
    elif isinstance(value, Sequence) and not isinstance(value, str):
        for item in value:
            collected.extend(_collect_lists(item, keys))
    return collected


def _mapping_items(items: list[object]) -> list[Mapping[object, object]]:
    return [item for item in items if isinstance(item, Mapping)]


def evaluate_contract(case: EvaluationCase, response: ResponseValue) -> EvaluationResult:
    """Validate the response against the case's declared domain contract."""
    try:
        _validate(case, response)
    except ValidationError as error:
        return _invalid_contract("contract_validity", error)
    return EvaluationResult(
        evaluator="contract_validity",
        passed=True,
        detail=f"Response satisfies {case.expected.contract.value}.",
    )


def evaluate_expected_deal_ids(case: EvaluationCase, response: ResponseValue) -> EvaluationResult:
    """Require the exact ordered deal IDs declared by the case."""
    try:
        model = _validate(case, response)
    except ValidationError as error:
        return _invalid_contract("expected_deal_ids", error)

    if not case.expected.deal_ids:
        return EvaluationResult(
            evaluator="expected_deal_ids",
            passed=True,
            detail="Case declares no deal-ID expectation.",
        )

    actual: list[str] = []
    if isinstance(model, (ResearchFindings, ComparableCandidates)):
        actual = [deal.deal_id for deal in model.comparables]
    elif isinstance(model, DebtServiceSchedule):
        actual = [model.deal_id]
    elif hasattr(model, "assessments"):
        actual = [assessment.deal_id for assessment in model.assessments]

    passed = actual == case.expected.deal_ids
    return EvaluationResult(
        evaluator="expected_deal_ids",
        passed=passed,
        detail=f"Expected {case.expected.deal_ids}; received {actual}.",
    )


def _decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def evaluate_expected_figures(case: EvaluationCase, response: ResponseValue) -> EvaluationResult:
    """Compare deterministic numeric fields without floating-point coercion."""
    try:
        model = _validate(case, response)
    except ValidationError as error:
        return _invalid_contract("expected_figures", error)

    mismatches: list[str] = []
    for field_name, expected in case.expected.figures.items():
        try:
            actual = _decimal(getattr(model, field_name))
        except AttributeError, InvalidOperation, TypeError, ValueError:
            mismatches.append(f"{field_name}=missing")
            continue
        if actual != expected:
            mismatches.append(f"{field_name}={actual} (expected {expected})")
    return EvaluationResult(
        evaluator="expected_figures",
        passed=not mismatches,
        detail="All expected figures match." if not mismatches else "; ".join(mismatches),
    )


def evaluate_citations(case: EvaluationCase, response: ResponseValue) -> EvaluationResult:
    """Check citation count, document identity, and sensitivity."""
    try:
        payload = _payload(_validate(case, response))
    except ValidationError as error:
        return _invalid_contract("citation_integrity", error)

    citations = _mapping_items(_collect_lists(payload, {"citations", "summary_citations"}))
    document_ids = {str(citation.get("document_id")) for citation in citations}
    citation_text = [
        " ".join(
            (
                str(citation.get("document_title", "")),
                str(citation.get("excerpt", "")),
            )
        ).casefold()
        for citation in citations
    ]
    required_ids = set(case.expected.required_citation_document_ids)
    required_title_terms = case.expected.required_citation_title_terms
    allowed = set(case.expected.allowed_citation_sensitivities)
    sensitivities = {
        Sensitivity(str(citation.get("sensitivity", Sensitivity.PUBLIC))) for citation in citations
    }
    failures: list[str] = []
    if len(citations) < case.expected.minimum_citations:
        failures.append(
            f"found {len(citations)} citation(s), expected at least "
            f"{case.expected.minimum_citations}"
        )
    if not required_ids <= document_ids:
        failures.append(f"missing citation document IDs {sorted(required_ids - document_ids)}")
    missing_titles = [
        term
        for term in required_title_terms
        if not any(term.casefold() in text for text in citation_text)
    ]
    if missing_titles:
        failures.append(f"missing citation title terms {missing_titles}")
    if allowed and not sensitivities <= allowed:
        disallowed = sorted(value.value for value in sensitivities - allowed)
        failures.append(f"disallowed citation sensitivities {disallowed}")
    return EvaluationResult(
        evaluator="citation_integrity",
        passed=not failures,
        detail="Citation expectations satisfied." if not failures else "; ".join(failures),
    )


def evaluate_gaps(case: EvaluationCase, response: ResponseValue) -> EvaluationResult:
    """Require planted gaps and contradictions to be disclosed explicitly."""
    try:
        payload = _payload(_validate(case, response))
    except ValidationError as error:
        return _invalid_contract("gap_disclosure", error)

    gaps = _mapping_items(_collect_lists(payload, {"gaps"}))
    citations = _mapping_items(_collect_lists(payload, {"citations", "summary_citations"}))
    gap_text = " ".join(
        f"{gap.get('question', '')} {gap.get('reason', '')}" for gap in gaps
    ).casefold()
    evidence_text = " ".join(
        f"{citation.get('document_title', '')} {citation.get('excerpt', '')}"
        for citation in citations
    ).casefold()

    def disclosed(term: str) -> bool:
        expected = term.casefold()
        if expected in gap_text:
            return True
        if expected in evidence_text and gaps:
            return True
        if expected == "stale":
            return "august 31, 2023" in evidence_text and any(
                phrase in gap_text for phrase in ("no newer", "only states", "not current")
            )
        return False

    missing = [term for term in case.expected.required_gap_terms if not disclosed(term)]
    return EvaluationResult(
        evaluator="gap_disclosure",
        passed=not missing,
        detail=(
            "All expected gap terms are disclosed." if not missing else f"Missing terms: {missing}."
        ),
    )


def evaluate_entitlements(case: EvaluationCase, response: ResponseValue) -> EvaluationResult:
    """Check withholding counts, partiality, and private-source visibility."""
    try:
        model = _validate(case, response)
    except ValidationError as error:
        return _invalid_contract("entitlement_enforcement", error)

    payload = _payload(model)
    sources = _mapping_items(_collect_lists(payload, {"evidence_sources"}))
    citations = _mapping_items(_collect_lists(payload, {"citations", "summary_citations"}))
    source_ids = {str(source.get("document_id")) for source in sources}
    private_records = [
        record
        for record in [*sources, *citations]
        if str(record.get("sensitivity", Sensitivity.PUBLIC)) == Sensitivity.PRIVATE
    ]
    failures: list[str] = []
    expected_withheld = case.expected.excluded_by_permission
    if expected_withheld is not None:
        actual_withheld = getattr(model, "excluded_by_permission", None)
        if actual_withheld != expected_withheld:
            failures.append(f"withheld={actual_withheld}, expected {expected_withheld}")
    expected_partial = case.expected.partial_due_to_permissions
    if expected_partial is not None:
        actual_partial = getattr(model, "partial_due_to_permissions", None)
        if actual_partial is not expected_partial:
            failures.append(f"partial={actual_partial}, expected {expected_partial}")
    required_sources = set(case.expected.required_source_document_ids)
    if not required_sources <= source_ids:
        failures.append(f"missing source document IDs {sorted(required_sources - source_ids)}")
    if case.expected.forbid_private_sources and private_records:
        failures.append("private citations or evidence sources were exposed")
    return EvaluationResult(
        evaluator="entitlement_enforcement",
        passed=not failures,
        detail="Entitlement expectations satisfied." if not failures else "; ".join(failures),
    )


def evaluate_guardrails(case: EvaluationCase, response: ResponseValue) -> EvaluationResult:
    """Check deterministic blocking, failed policies, and human review."""
    try:
        model = _validate(case, response)
    except ValidationError as error:
        return _invalid_contract("guardrail_blocking", error)

    review = model.compliance if isinstance(model, DealDeskAnswer) else model
    failures: list[str] = []
    expected_review = case.expected.requires_human_review
    actual_review = getattr(model, "requires_human_review", None)
    if expected_review is not None and actual_review is not expected_review:
        failures.append(f"requires_human_review={actual_review}, expected {expected_review}")
    compliance_expected = case.expected.blocking is not None or bool(
        case.expected.failed_policy_ids
    )
    if review is None and compliance_expected:
        failures.append("compliance review is missing")
    elif isinstance(review, ComplianceReview):
        if case.expected.blocking is not None and review.blocking is not case.expected.blocking:
            failures.append(f"blocking={review.blocking}, expected {case.expected.blocking}")
        actual_failed = {finding.policy_id for finding in review.findings if not finding.passed}
        expected_failed = set(case.expected.failed_policy_ids)
        if actual_failed != expected_failed:
            failures.append(
                f"failed policies={sorted(actual_failed)}, expected {sorted(expected_failed)}"
            )
    return EvaluationResult(
        evaluator="guardrail_blocking",
        passed=not failures,
        detail="Guardrail expectations satisfied." if not failures else "; ".join(failures),
    )


def evaluate_case(case: EvaluationCase, response: ResponseValue) -> list[EvaluationResult]:
    """Run every deterministic evaluator for one response."""
    return [
        evaluate_contract(case, response),
        evaluate_expected_deal_ids(case, response),
        evaluate_expected_figures(case, response),
        evaluate_citations(case, response),
        evaluate_gaps(case, response),
        evaluate_entitlements(case, response),
        evaluate_guardrails(case, response),
    ]


def load_thresholds(path: Path | None = None) -> EvaluationThresholds:
    """Load the committed local promotion thresholds."""
    source = path or Path(__file__).with_name("thresholds.json")
    return EvaluationThresholds.model_validate_json(source.read_text(encoding="utf-8"))


def evaluate_critical_gate(
    cases: list[EvaluationCase],
    case_passes: Mapping[str, bool],
    thresholds: EvaluationThresholds | None = None,
) -> GateResult:
    """Apply overall, category, and critical-case promotion thresholds."""
    selected_thresholds = thresholds or load_thresholds()
    category_results: dict[EvaluationCategory, list[bool]] = defaultdict(list)
    results: list[bool] = []
    failed_critical: list[str] = []
    for case in cases:
        passed = case_passes.get(case.case_id, False)
        results.append(passed)
        category_results[case.category].append(passed)
        if case.critical and not passed:
            failed_critical.append(case.case_id)

    overall_rate = sum(results) / len(results) if results else 0.0
    category_rates = {
        category: sum(values) / len(values) for category, values in category_results.items()
    }
    reasons: list[str] = []
    if overall_rate < selected_thresholds.minimum_pass_rate:
        reasons.append(
            f"overall pass rate {overall_rate:.3f} is below "
            f"{selected_thresholds.minimum_pass_rate:.3f}"
        )
    for category, minimum in selected_thresholds.category_minimum_pass_rates.items():
        actual = category_rates.get(category, 0.0)
        if actual < minimum:
            reasons.append(f"{category.value} pass rate {actual:.3f} is below {minimum:.3f}")
    if selected_thresholds.critical_cases_must_pass and failed_critical:
        reasons.append(f"critical cases failed: {failed_critical}")
    return GateResult(
        passed=not reasons,
        overall_pass_rate=overall_rate,
        category_pass_rates=category_rates,
        failed_critical_case_ids=failed_critical,
        reasons=reasons,
    )
