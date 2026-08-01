"""Structured contracts exchanged between agents.

Each model below is used as `response_format` on a specialist agent, so the shape of
every agent-to-agent handoff is enforced by the model provider rather than by prompt
wording. The evaluation suite asserts against these same types, which is why they live
in the domain layer rather than beside the agents that emit them.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from src.domain.entities.citation import Citation, EvidenceGap
from src.domain.entities.deal import Deal, SecurityType


class DealDeskRequest(BaseModel):
    """Typed input to the hosted Deal Desk workflow."""

    question: str = Field(description="The banker's municipal new-issue analysis question.")
    subject_deal_id: str = Field(description="Private proposed deal visible to the deal team.")
    caller_user_id: str
    caller_group_claims: list[str] = Field(default_factory=list)
    state: str = Field(min_length=2, max_length=2)
    security_type: SecurityType
    par_amount: Decimal
    months_back: int = 18


class WorkflowPlan(BaseModel):
    """Planner decomposition used to make model routing visible in traces."""

    tasks: list[str] = Field(description="Ordered tasks required to answer the request.")
    research_focus: str = Field(description="Public evidence the Research specialist should find.")
    analysis_focus: str = Field(description="Comparisons the Analyst specialist should assess.")


class ComparableCandidates(BaseModel):
    """Typed comparable selection returned by the custom Deal Desk MCP server."""

    comparables: list[Deal] = Field(description="Candidate comparable issues, most similar first.")
    gaps: list[EvidenceGap] = Field(default_factory=list)
    excluded_by_permission: int = Field(
        default=0,
        description="Count of matching typed records withheld by caller entitlements.",
    )


class ResearchFindings(BaseModel):
    """Output of the Research specialist.

    The specialist selects candidate comparables and reports what it could not find.
    It does not interpret or price; that is the Analyst's role.
    """

    comparables: list[Deal] = Field(description="Candidate comparable issues, most similar first.")
    citations: list[Citation]
    gaps: list[EvidenceGap] = Field(default_factory=list)
    excluded_by_permission: int = Field(
        default=0,
        description=(
            "Count of candidates withheld because the caller's group claims did not "
            "permit them. Surfaced so the answer can disclose that it is partial."
        ),
    )


class ComparableAssessment(BaseModel):
    """The Analyst's view of a single comparable."""

    deal_id: str
    similarity_rationale: str
    structural_differences: list[str] = Field(default_factory=list)
    pricing_observations: list[str] = Field(default_factory=list)


class AnalystAssessment(BaseModel):
    """Output of the Analyst specialist.

    Numeric debt service figures are not produced here. They are computed by the
    calculator tool and referenced, so no figure reaching a client document originates
    from a language model.
    """

    assessments: list[ComparableAssessment]
    aggregate_observations: list[str] = Field(default_factory=list)
    citations: list[Citation]
    gaps: list[EvidenceGap] = Field(default_factory=list)


class PolicyFinding(BaseModel):
    """A single guardrail determination."""

    policy_id: str = Field(description="Identifier such as 'msrb-g17-fiduciary-implication'.")
    passed: bool
    detail: str
    offending_text: str | None = None


class ComplianceReview(BaseModel):
    """Output of the Compliance specialist.

    Models the review a supervising principal performs. It records findings; it does
    not certify compliance, and the wording of `detail` must not read as legal advice.
    """

    findings: list[PolicyFinding]
    requires_human_review: bool
    blocking: bool = Field(
        default=False,
        description="True when a finding prevents the draft from being returned at all.",
    )


class DraftSection(BaseModel):
    """A drafted section of a client-facing document."""

    heading: str
    body: str
    citations: list[Citation]


class DraftPackage(BaseModel):
    """Structured synthesis produced before independent compliance review."""

    summary: str
    summary_citations: list[Citation] = Field(default_factory=list)
    sections: list[DraftSection]
    gaps: list[EvidenceGap] = Field(default_factory=list)


class DealDeskAnswer(BaseModel):
    """Final orchestrator output.

    `requires_human_review` is always true for client-facing drafts. The human gate is
    a property of the contract rather than a runtime decision, so it cannot be lost by
    a prompt change.
    """

    summary: str
    summary_citations: list[Citation] = Field(default_factory=list)
    sections: list[DraftSection] = Field(default_factory=list)
    comparables_considered: int = 0
    total_debt_service: Decimal | None = None
    compliance: ComplianceReview | None = None
    gaps: list[EvidenceGap] = Field(default_factory=list)
    partial_due_to_permissions: bool = False
    requires_human_review: bool = True


class HumanApprovalRequest(BaseModel):
    """Draft held for a supervising principal rather than returned to the caller."""

    draft: DealDeskAnswer
    instruction: str = "Approve only after reviewing citations, figures, and compliance findings."


class HumanApprovalDecision(BaseModel):
    """Explicit supervising-principal response used to resume the workflow."""

    approved: bool
    reviewer_notes: str = ""
