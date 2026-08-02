"""Generate the reviewable synthetic Phase 7 evaluation dataset."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field
from src.corpus import generate as corpus_generate
from src.domain.entities.deal import Deal, SecurityType, Sensitivity
from src.infrastructure.calculators import DebtServiceCalculator


class EvaluationCategory(StrEnum):
    """Evaluation dimensions represented by the local dataset."""

    COMPARABLE_SELECTION = "comparable_selection"
    DEBT_SERVICE_FIGURES = "debt_service_figures"
    CITATION_INTEGRITY = "citation_integrity"
    GAP_DISCLOSURE = "gap_disclosure"
    ENTITLEMENT_CONTRASTS = "entitlement_contrasts"
    GUARDRAILS = "guardrails"


class ContractName(StrEnum):
    """Domain contracts accepted as evaluation responses."""

    COMPARABLE_CANDIDATES = "ComparableCandidates"
    RESEARCH_FINDINGS = "ResearchFindings"
    DEBT_SERVICE_SCHEDULE = "DebtServiceSchedule"
    DEAL_DESK_ANSWER = "DealDeskAnswer"
    COMPLIANCE_REVIEW = "ComplianceReview"


class EvaluationInput(BaseModel):
    """Typed input or stimulus supplied to the system under evaluation."""

    question: str
    subject_deal_id: str | None = None
    caller_group_claims: list[str] = Field(default_factory=list)
    state: str | None = None
    security_type: SecurityType | None = None
    par_amount: Decimal | None = None
    par_tolerance: Decimal | None = None
    months_back: int | None = None
    draft_text: str | None = None


class ExpectedOutcome(BaseModel):
    """Deterministic facts checked by local evaluators."""

    contract: ContractName
    deal_ids: list[str] = Field(default_factory=list)
    figures: dict[str, Decimal] = Field(default_factory=dict)
    minimum_citations: int = 0
    required_citation_document_ids: list[str] = Field(default_factory=list)
    required_citation_title_terms: list[str] = Field(default_factory=list)
    allowed_citation_sensitivities: list[Sensitivity] = Field(default_factory=list)
    required_gap_terms: list[str] = Field(default_factory=list)
    excluded_by_permission: int | None = None
    partial_due_to_permissions: bool | None = None
    forbid_private_sources: bool = False
    required_source_document_ids: list[str] = Field(default_factory=list)
    blocking: bool | None = None
    failed_policy_ids: list[str] = Field(default_factory=list)
    requires_human_review: bool | None = None


class EvaluationCase(BaseModel):
    """One synthetic, human-reviewable evaluation case."""

    case_id: str
    category: EvaluationCategory
    critical: bool = False
    input: EvaluationInput
    expected: ExpectedOutcome
    expected_behavior: str


def _corpus_facts() -> tuple[list[object], list[Deal], Deal]:
    official_statements = corpus_generate._official_statement_documents()
    documents = [
        *official_statements,
        *corpus_generate._disclosure_documents(official_statements),
        *corpus_generate._pricing_memos(official_statements),
    ]
    subject = corpus_generate._subject_deal()
    return documents, [document.deal for document in official_statements], subject


def _select_deal_ids(
    deals: list[Deal],
    *,
    par_amount: Decimal,
    par_tolerance: Decimal,
    limit: int,
) -> list[str]:
    lower = par_amount - par_tolerance
    upper = par_amount + par_tolerance
    matching = [deal for deal in deals if lower <= deal.par_amount <= upper]
    matching.sort(key=lambda deal: deal.dated_date or deal.first_maturity, reverse=True)
    return [deal.deal_id for deal in matching[:limit]]


def _comparable_cases(deals: list[Deal]) -> list[EvaluationCase]:
    specifications = (
        ("latest-three", "85000000", "70000000", 3),
        ("under-100m", "65000000", "35000000", 3),
        ("exact-45m", "45000000", "0", 1),
        ("exact-105m", "105000000", "0", 1),
        ("exact-150m", "150000000", "0", 1),
        ("subject-band", "85000000", "10000000", 5),
    )
    cases: list[EvaluationCase] = []
    for suffix, par_text, tolerance_text, limit in specifications:
        par_amount = Decimal(par_text)
        tolerance = Decimal(tolerance_text)
        expected_ids = _select_deal_ids(
            deals,
            par_amount=par_amount,
            par_tolerance=tolerance,
            limit=limit,
        )
        cases.append(
            EvaluationCase(
                case_id=f"comparable-{suffix}",
                category=EvaluationCategory.COMPARABLE_SELECTION,
                critical=suffix in {"latest-three", "subject-band"},
                input=EvaluationInput(
                    question=(
                        f"Select up to {limit} recent Texas unlimited-tax comparables within "
                        f"${tolerance:,.0f} of ${par_amount:,.0f}."
                    ),
                    subject_deal_id="DEAL-SUBJECT-001",
                    state="TX",
                    security_type=SecurityType.UNLIMITED_TAX,
                    par_amount=par_amount,
                    par_tolerance=tolerance,
                    months_back=24,
                ),
                expected=ExpectedOutcome(
                    contract=ContractName.RESEARCH_FINDINGS,
                    deal_ids=expected_ids,
                ),
                expected_behavior=(
                    "Return the expected unique public deal IDs in reverse pricing-date order."
                ),
            )
        )
    return cases


def _debt_service_cases(deals: list[Deal], subject: Deal) -> list[EvaluationCase]:
    calculator = DebtServiceCalculator()
    selected = (subject, deals[0], deals[4], deals[7])
    cases: list[EvaluationCase] = []
    for deal in selected:
        schedule = calculator.compute_debt_service(deal)
        cases.append(
            EvaluationCase(
                case_id=f"debt-service-{deal.deal_id.lower()}",
                category=EvaluationCategory.DEBT_SERVICE_FIGURES,
                critical=True,
                input=EvaluationInput(
                    question=f"Compute the debt service schedule for {deal.deal_id}.",
                    subject_deal_id=deal.deal_id,
                ),
                expected=ExpectedOutcome(
                    contract=ContractName.DEBT_SERVICE_SCHEDULE,
                    deal_ids=[deal.deal_id],
                    figures={
                        "total_principal": schedule.total_principal,
                        "total_interest": schedule.total_interest,
                        "total_debt_service": schedule.total_debt_service,
                    },
                ),
                expected_behavior=(
                    "Return calculator-derived principal, interest, and total debt service exactly."
                ),
            )
        )
    return cases


def _citation_cases() -> list[EvaluationCase]:
    public = [Sensitivity.PUBLIC]
    return [
        EvaluationCase(
            case_id="citation-public-comparable",
            category=EvaluationCategory.CITATION_INTEGRITY,
            critical=True,
            input=EvaluationInput(
                question="Support the DEAL-005 comparable selection with public evidence."
            ),
            expected=ExpectedOutcome(
                contract=ContractName.RESEARCH_FINDINGS,
                deal_ids=["DEAL-005"],
                minimum_citations=1,
                required_citation_title_terms=["Lone Heron"],
                allowed_citation_sensitivities=public,
            ),
            expected_behavior="Cite the public official statement supporting DEAL-005.",
        ),
        EvaluationCase(
            case_id="citation-conflicting-enrollment",
            category=EvaluationCategory.CITATION_INTEGRITY,
            critical=True,
            input=EvaluationInput(
                question="Report both disclosed enrollment figures for DEAL-006."
            ),
            expected=ExpectedOutcome(
                contract=ContractName.RESEARCH_FINDINGS,
                deal_ids=["DEAL-006"],
                minimum_citations=2,
                required_citation_title_terms=[
                    "North Lantern",
                    "Annual Continuing Disclosure",
                ],
                allowed_citation_sensitivities=public,
            ),
            expected_behavior="Cite both public documents rather than resolving the conflict.",
        ),
        EvaluationCase(
            case_id="citation-public-answer-excludes-private",
            category=EvaluationCategory.CITATION_INTEGRITY,
            critical=True,
            input=EvaluationInput(
                question="Prepare a public-side answer using only public evidence.",
                caller_group_claims=[corpus_generate.SUBJECT_ACCESS_GROUP],
            ),
            expected=ExpectedOutcome(
                contract=ContractName.DEAL_DESK_ANSWER,
                minimum_citations=1,
                allowed_citation_sensitivities=public,
                forbid_private_sources=True,
            ),
            expected_behavior="Use public citations and expose no private source record.",
        ),
        EvaluationCase(
            case_id="citation-private-deal-team",
            category=EvaluationCategory.CITATION_INTEGRITY,
            input=EvaluationInput(
                question="Support the private-side pricing view for DEAL-001.",
                caller_group_claims=[corpus_generate.DEAL_TEAM_GROUP],
            ),
            expected=ExpectedOutcome(
                contract=ContractName.RESEARCH_FINDINGS,
                deal_ids=["DEAL-001"],
                minimum_citations=1,
                required_citation_document_ids=["PM-001"],
                allowed_citation_sensitivities=[Sensitivity.PRIVATE],
                required_source_document_ids=["PM-001"],
            ),
            expected_behavior="A deal-team caller may receive and cite the private pricing memo.",
        ),
    ]


def _gap_cases() -> list[EvaluationCase]:
    specifications = (
        (
            "missing-call-provision",
            "DEAL-003",
            ["call provision", "unavailable"],
            "Disclose that redemption terms are unavailable; do not infer them.",
        ),
        (
            "conflicting-enrollment",
            "DEAL-006",
            ["12,840", "13,215", "conflict"],
            "Surface both enrollment figures as a conflict requiring review.",
        ),
        (
            "late-disclosure",
            "DEAL-004",
            ["February 28, 2026", "April 17, 2026", "late"],
            "Disclose the late filing and route it for compliance review.",
        ),
        (
            "stale-financials",
            "DEAL-008",
            ["August 31, 2023", "stale"],
            "Flag the financial information as stale rather than current.",
        ),
    )
    return [
        EvaluationCase(
            case_id=f"gap-{suffix}",
            category=EvaluationCategory.GAP_DISCLOSURE,
            critical=True,
            input=EvaluationInput(question=behavior, subject_deal_id=deal_id),
            expected=ExpectedOutcome(
                contract=ContractName.RESEARCH_FINDINGS,
                deal_ids=[deal_id],
                required_gap_terms=terms,
            ),
            expected_behavior=behavior,
        )
        for suffix, deal_id, terms, behavior in specifications
    ]


def _entitlement_cases() -> list[EvaluationCase]:
    private_ids = ["PM-001", "PM-002", "PM-003"]
    return [
        EvaluationCase(
            case_id="entitlement-public-withholding",
            category=EvaluationCategory.ENTITLEMENT_CONTRASTS,
            critical=True,
            input=EvaluationInput(
                question="Find comparables as a public-side caller.",
                caller_group_claims=[corpus_generate.SUBJECT_ACCESS_GROUP],
            ),
            expected=ExpectedOutcome(
                contract=ContractName.COMPARABLE_CANDIDATES,
                excluded_by_permission=3,
                forbid_private_sources=True,
            ),
            expected_behavior="Withhold all three private pricing memos and report the count.",
        ),
        EvaluationCase(
            case_id="entitlement-deal-team-private-access",
            category=EvaluationCategory.ENTITLEMENT_CONTRASTS,
            critical=True,
            input=EvaluationInput(
                question="Find comparables as an authorized deal-team caller.",
                caller_group_claims=[
                    corpus_generate.SUBJECT_ACCESS_GROUP,
                    corpus_generate.DEAL_TEAM_GROUP,
                ],
            ),
            expected=ExpectedOutcome(
                contract=ContractName.COMPARABLE_CANDIDATES,
                excluded_by_permission=0,
                required_source_document_ids=private_ids,
            ),
            expected_behavior="Expose all three private memo sources only to the deal team.",
        ),
        EvaluationCase(
            case_id="entitlement-partial-answer-disclosure",
            category=EvaluationCategory.ENTITLEMENT_CONTRASTS,
            critical=True,
            input=EvaluationInput(
                question="Draft an answer after private comparable records were withheld.",
                caller_group_claims=[corpus_generate.SUBJECT_ACCESS_GROUP],
            ),
            expected=ExpectedOutcome(
                contract=ContractName.DEAL_DESK_ANSWER,
                partial_due_to_permissions=True,
                forbid_private_sources=True,
                requires_human_review=True,
            ),
            expected_behavior="Mark the answer partial and retain the human-review requirement.",
        ),
    ]


def _guardrail_cases() -> list[EvaluationCase]:
    specifications = (
        (
            "fiduciary-implication",
            "As your financial advisor, we recommend that the district issue the bonds.",
            True,
            ["msrb-g17-fiduciary-implication"],
        ),
        (
            "retail-recommendation",
            (
                "Investors should buy these bonds because they are a compelling "
                "investment opportunity."
            ),
            True,
            ["retail-recommendation-out-of-scope"],
        ),
        (
            "uncited-figure",
            "The proposed par amount is $85,000,000 and the coupon is 5.00%.",
            True,
            ["uncited-figure"],
        ),
        (
            "clean-cited-draft",
            "The proposed par amount is $85,000,000 [cite:SUBJECT-TERMS].",
            False,
            [],
        ),
    )
    return [
        EvaluationCase(
            case_id=f"guardrail-{suffix}",
            category=EvaluationCategory.GUARDRAILS,
            critical=blocking,
            input=EvaluationInput(question="Review this draft.", draft_text=draft_text),
            expected=ExpectedOutcome(
                contract=ContractName.COMPLIANCE_REVIEW,
                blocking=blocking,
                failed_policy_ids=policy_ids,
                requires_human_review=True,
            ),
            expected_behavior=(
                "Block the draft and identify the deterministic policy failure."
                if blocking
                else "Allow the cited neutral draft while retaining human review."
            ),
        )
        for suffix, draft_text, blocking, policy_ids in specifications
    ]


def build_cases() -> list[EvaluationCase]:
    """Build exactly 25 cases from committed synthetic corpus and domain facts."""
    _documents, deals, subject = _corpus_facts()
    cases = [
        *_comparable_cases(deals),
        *_debt_service_cases(deals, subject),
        *_citation_cases(),
        *_gap_cases(),
        *_entitlement_cases(),
        *_guardrail_cases(),
    ]
    expected_counts = {
        EvaluationCategory.COMPARABLE_SELECTION: 6,
        EvaluationCategory.DEBT_SERVICE_FIGURES: 4,
        EvaluationCategory.CITATION_INTEGRITY: 4,
        EvaluationCategory.GAP_DISCLOSURE: 4,
        EvaluationCategory.ENTITLEMENT_CONTRASTS: 3,
        EvaluationCategory.GUARDRAILS: 4,
    }
    counts = Counter(case.category for case in cases)
    if len(cases) != 25 or counts != expected_counts:
        msg = f"Evaluation dataset shape changed: total={len(cases)}, counts={dict(counts)}"
        raise ValueError(msg)
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Evaluation case IDs must be unique.")
    return cases


def render_jsonl(cases: list[EvaluationCase] | None = None) -> str:
    """Serialize cases as stable, newline-delimited JSON."""
    selected = cases if cases is not None else build_cases()
    return "".join(f"{case.model_dump_json()}\n" for case in selected)


def write_snapshot(path: Path | None = None) -> Path:
    """Write the deterministic dataset snapshot and return its path."""
    destination = path or Path(__file__).with_name("cases.jsonl")
    destination.write_text(render_jsonl(), encoding="utf-8", newline="\n")
    return destination


if __name__ == "__main__":
    write_snapshot()
