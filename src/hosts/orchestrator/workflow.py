"""Typed Agent Framework workflow for the municipal Deal Desk."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from decimal import Decimal

from agent_framework import (
    CheckpointStorage,
    FunctionalWorkflow,
    InMemoryCheckpointStorage,
    RunContext,
    step,
    workflow,
)
from opentelemetry import trace

from src.application.mediator import Mediator
from src.application.messages import (
    Caller,
    ComputeDebtService,
    FindComparables,
    ReviewForCompliance,
)
from src.application.ports import AgentPort, ModelPort
from src.domain.contracts.agent_contracts import (
    AnalystAssessment,
    ComplianceReview,
    DealDeskAnswer,
    DealDeskRequest,
    DraftPackage,
    HumanApprovalDecision,
    HumanApprovalRequest,
    ResearchFindings,
    WorkflowPlan,
)
from src.domain.entities.deal import DebtServiceSchedule
from src.hosts.orchestrator.progress import emit_progress, run_stage

RESEARCH_AGENT = "municipal-deal-research"
ANALYST_AGENT = "municipal-deal-analyst"
COMPLIANCE_AGENT = "municipal-deal-compliance"
APPROVAL_REQUEST_ID = "supervising-principal-approval"

tracer = trace.get_tracer(__name__)


@dataclass(frozen=True, slots=True)
class WorkflowDependencies:
    """Runtime dependencies supplied by the orchestrator composition root."""

    mediator: Mediator
    specialists: AgentPort
    models: ModelPort
    router_model: str
    synthesis_model: str


def _caller(request: DealDeskRequest) -> Caller:
    return Caller(request.caller_user_id, tuple(request.caller_group_claims))


def _render_citations(text: str, document_ids: list[str]) -> str:
    if not document_ids:
        return text
    markers = " ".join(f"[cite:{document_id}]" for document_id in document_ids)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    rendered: list[str] = []
    for sentence in sentences:
        if sentence.endswith((".", "!", "?")):
            rendered.append(f"{sentence[:-1]} {markers}{sentence[-1]}")
        else:
            rendered.append(f"{sentence} {markers}")
    return " ".join(rendered)


def _draft_text(draft: DraftPackage, schedule: DebtServiceSchedule) -> str:
    summary = _render_citations(
        draft.summary,
        [citation.document_id for citation in draft.summary_citations],
    )
    sections = "\n".join(
        f"{section.heading}\n"
        f"{
            _render_citations(
                section.body,
                [citation.document_id for citation in section.citations],
            )
        }"
        for section in draft.sections
    )
    total = (
        f"Computed total debt service: ${schedule.total_debt_service:,.2f} "
        f"[source:{schedule.deal_id}]."
    )
    return f"{summary}\n{sections}\n{total}"


def _merge_reviews(model: ComplianceReview, deterministic: ComplianceReview) -> ComplianceReview:
    """Keep model findings visible while deterministic controls own blocking."""
    return ComplianceReview(
        findings=[*model.findings, *deterministic.findings],
        requires_human_review=True,
        blocking=deterministic.blocking,
    )


def _withheld_answer(
    summary: str,
    research: ResearchFindings,
    schedule: DebtServiceSchedule,
    compliance: ComplianceReview,
) -> str:
    return DealDeskAnswer(
        summary=summary,
        sections=[],
        comparables_considered=len(research.comparables),
        total_debt_service=schedule.total_debt_service,
        compliance=compliance,
        evidence_sources=research.evidence_sources,
        gaps=research.gaps,
        partial_due_to_permissions=research.excluded_by_permission > 0,
        requires_human_review=True,
    )


def create_deal_desk_workflow(
    dependencies: WorkflowDependencies,
    *,
    checkpoint_storage: CheckpointStorage | None = None,
) -> FunctionalWorkflow:
    """Build a replayable workflow whose model calls are cached across HITL resume."""
    storage = checkpoint_storage or InMemoryCheckpointStorage()

    @step(name="plan-request")
    async def plan_request(request: DealDeskRequest) -> WorkflowPlan:
        with tracer.start_as_current_span("orchestrator.plan"):
            return await run_stage(
                "plan-request",
                dependencies.models.invoke(
                    dependencies.router_model,
                    (
                        "Decompose the municipal request into public research and structural "
                        "analysis tasks. Do not answer the request or invent facts."
                    ),
                    request.model_dump_json(),
                    WorkflowPlan,
                ),
            )

    @step(name="research-public-comparables")
    async def research_public(
        request: DealDeskRequest,
        plan: WorkflowPlan,
    ) -> ResearchFindings:
        return await run_stage(
            "research-public-comparables",
            _research_public(request, plan),
        )

    async def _research_public(
        request: DealDeskRequest,
        plan: WorkflowPlan,
    ) -> ResearchFindings:
        candidates = await dependencies.mediator.send(
            FindComparables(
                caller=_caller(request),
                state=request.state,
                security_type=request.security_type,
                par_amount=request.par_amount,
                months_back=request.months_back,
                par_tolerance_pct=Decimal("100"),
                limit=20,
            )
        )
        prompt = (
            f"{plan.research_focus}\nRetrieve cited public evidence for these deterministic "
            f"candidate deals: {[deal.deal_id for deal in candidates.comparables]}. "
            "Use Foundry IQ for public passages. Do not request private-side access."
        )
        with tracer.start_as_current_span("specialist.research"):
            findings = await dependencies.specialists.invoke(
                RESEARCH_AGENT,
                prompt,
                ResearchFindings,
                caller=_caller(request),
            )
        merged = findings.model_copy(
            update={
                "comparables": candidates.comparables,
                "evidence_sources": candidates.evidence_sources,
                "gaps": [*candidates.gaps, *findings.gaps],
                "excluded_by_permission": candidates.excluded_by_permission,
            }
        )
        for source in merged.evidence_sources:
            await emit_progress("evidence", evidence_source=source.model_dump(mode="json"))
        for citation in merged.citations:
            await emit_progress("citation", citation=citation.model_dump(mode="json"))
        return merged

    @step(name="compute-subject-debt-service")
    async def compute_subject(request: DealDeskRequest) -> DebtServiceSchedule:
        with tracer.start_as_current_span("tool.compute_debt_service"):
            return await run_stage(
                "compute-subject-debt-service",
                dependencies.mediator.send(
                    ComputeDebtService(
                        caller=_caller(request),
                        deal_id=request.subject_deal_id,
                    )
                ),
            )

    @step(name="assess-comparables")
    async def assess_comparables(
        request: DealDeskRequest,
        plan: WorkflowPlan,
        research: ResearchFindings,
    ) -> AnalystAssessment:
        prompt = (
            f"{plan.analysis_focus}\nAssess only the public comparable issues in this "
            f"research handoff: {research.model_dump_json()}. Do not request or infer any "
            "private proposed-deal facts."
        )
        with tracer.start_as_current_span("specialist.analyst"):
            return await run_stage(
                "assess-comparables",
                dependencies.specialists.invoke(
                    ANALYST_AGENT,
                    prompt,
                    AnalystAssessment,
                    caller=_caller(request),
                ),
            )

    @step(name="synthesize-draft")
    async def synthesize(
        request: DealDeskRequest,
        plan: WorkflowPlan,
        research: ResearchFindings,
        analysis: AnalystAssessment,
        schedule: DebtServiceSchedule,
    ) -> DraftPackage:
        prompt = (
            f"Request: {request.model_dump_json()}\nPlan: {plan.model_dump_json()}\n"
            f"Research: {research.model_dump_json()}\n"
            f"Analysis: {analysis.model_dump_json()}\n"
            f"Deterministic debt service: {schedule.model_dump_json()}"
        )
        with tracer.start_as_current_span("model.synthesize"):
            draft = await run_stage(
                "synthesize-draft",
                dependencies.models.invoke(
                    dependencies.synthesis_model,
                    (
                        "Draft a concise issuer-facing market summary. Preserve citations and "
                        "evidence gaps. Put citations supporting the summary in "
                        "summary_citations and citations supporting each section in that "
                        "section's citations. Do not give legal advice or investor "
                        "recommendations."
                    ),
                    prompt,
                    DraftPackage,
                ),
            )
            return draft

    @step(name="review-draft")
    async def review_draft(
        request: DealDeskRequest,
        draft: DraftPackage,
        schedule: DebtServiceSchedule,
    ) -> ComplianceReview:
        return await run_stage(
            "review-draft",
            _review_draft(request, draft, schedule),
        )

    async def _review_draft(
        request: DealDeskRequest,
        draft: DraftPackage,
        schedule: DebtServiceSchedule,
    ) -> ComplianceReview:
        text = _draft_text(draft, schedule)
        with tracer.start_as_current_span("specialist.compliance"):
            model_review = await dependencies.specialists.invoke(
                COMPLIANCE_AGENT,
                text,
                ComplianceReview,
                caller=_caller(request),
            )
        with tracer.start_as_current_span("guardrail.deterministic"):
            draft_review = await dependencies.mediator.send(
                ReviewForCompliance(caller=_caller(request), text=text)
            )
            request_review = await dependencies.mediator.send(
                ReviewForCompliance(caller=_caller(request), text=request.question)
            )
        request_findings = [
            finding
            for finding in request_review.findings
            if not finding.passed and finding.policy_id != "uncited-figure"
        ]
        deterministic = ComplianceReview(
            findings=[*request_findings, *draft_review.findings],
            requires_human_review=True,
            blocking=bool(request_findings) or draft_review.blocking,
        )
        review = _merge_reviews(model_review, deterministic)
        for finding in review.findings:
            await emit_progress("policy", finding=finding.model_dump(mode="json"))
        return review

    @workflow(
        name="municipal-deal-desk",
        description="Plan, research, analyse, guard and approve a municipal new-issue draft.",
        checkpoint_storage=storage,
    )
    async def deal_desk(request: DealDeskRequest, ctx: RunContext) -> DealDeskAnswer:
        plan = await plan_request(request)
        research, schedule = await asyncio.gather(
            research_public(request, plan),
            compute_subject(request),
        )
        analysis = await assess_comparables(request, plan, research)
        draft = await synthesize(request, plan, research, analysis, schedule)
        compliance = await review_draft(request, draft, schedule)
        if compliance.blocking:
            return _withheld_answer(
                "Draft blocked by compliance controls and withheld from the caller.",
                research,
                schedule,
                compliance,
            ).model_dump_json()

        await emit_progress("draft", draft=draft.model_dump(mode="json"))

        answer = DealDeskAnswer(
            summary=draft.summary,
            summary_citations=draft.summary_citations,
            sections=draft.sections,
            comparables_considered=len(research.comparables),
            total_debt_service=schedule.total_debt_service,
            compliance=compliance,
            evidence_sources=research.evidence_sources,
            gaps=[*research.gaps, *analysis.gaps, *draft.gaps],
            partial_due_to_permissions=research.excluded_by_permission > 0,
            requires_human_review=True,
        )
        with tracer.start_as_current_span("approval.request"):
            raw_decision = await ctx.request_info(
                HumanApprovalRequest(draft=answer),
                response_type=HumanApprovalDecision,
                request_id=APPROVAL_REQUEST_ID,
            )
        decision = HumanApprovalDecision.model_validate(raw_decision)
        if not decision.approved:
            return _withheld_answer(
                "Draft rejected by the supervising principal and withheld from the caller.",
                research,
                schedule,
                compliance,
            ).model_dump_json()
        return answer.model_dump_json()

    return deal_desk
