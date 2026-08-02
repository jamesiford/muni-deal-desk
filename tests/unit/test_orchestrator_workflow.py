"""Focused Phase 6 workflow tests."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal

from src.application.handlers.review_for_compliance import ReviewForComplianceHandler
from src.application.mediator import Mediator
from src.application.messages import ComputeDebtService, FindComparables, ReviewForCompliance
from src.domain.contracts.agent_contracts import (
    AnalystAssessment,
    ComparableCandidates,
    ComplianceReview,
    DealDeskAnswer,
    DealDeskRequest,
    DraftPackage,
    DraftSection,
    HumanApprovalDecision,
    HumanApprovalRequest,
    ResearchFindings,
    WorkflowPlan,
)
from src.domain.entities.citation import Citation, EvidenceSource
from src.domain.entities.deal import DebtServiceRow, DebtServiceSchedule, SecurityType, Sensitivity
from src.domain.policies.conduct_policies import UncitedFigurePolicy
from src.hosts.orchestrator.progress import report_progress
from src.hosts.orchestrator.workflow import (
    APPROVAL_REQUEST_ID,
    WorkflowDependencies,
    _render_citations,
    create_deal_desk_workflow,
)


class ScheduleHandler:
    async def handle(self, _message: ComputeDebtService) -> DebtServiceSchedule:
        return DebtServiceSchedule(
            deal_id="DEAL-SUBJECT-001",
            rows=[
                DebtServiceRow(
                    period_ending=date(2027, 8, 15),
                    principal=Decimal("85000000"),
                    interest=Decimal("4250000"),
                )
            ],
            total_principal=Decimal("85000000"),
            total_interest=Decimal("4250000"),
        )


class CandidatesHandler:
    async def handle(self, _message: FindComparables) -> ComparableCandidates:
        return ComparableCandidates(
            comparables=[],
            evidence_sources=[
                EvidenceSource(
                    document_id="PM-001",
                    document_title="Private pricing memo",
                    deal_id="DEAL-001",
                    source_type="internal_pricing_memo",
                    sensitivity=Sensitivity.PRIVATE,
                )
            ],
            excluded_by_permission=0,
        )


class FakeSpecialists:
    def __init__(self, *, model_blocking: bool = False) -> None:
        self.calls = 0
        self.prompts: list[tuple[type, str]] = []
        self.model_blocking = model_blocking

    async def invoke(self, agent_name, prompt, response_model, *, caller):
        del agent_name, caller
        self.calls += 1
        self.prompts.append((response_model, prompt))
        if response_model is ResearchFindings:
            return ResearchFindings(comparables=[], citations=[])
        if response_model is AnalystAssessment:
            return AnalystAssessment(assessments=[], citations=[])
        assert response_model is ComplianceReview
        return ComplianceReview(
            findings=[],
            requires_human_review=True,
            blocking=self.model_blocking,
        )


class FakeModels:
    def __init__(self, body: str) -> None:
        self.body = body
        self.calls = 0

    async def invoke(self, model, instructions, prompt, response_model):
        del model, instructions, prompt
        self.calls += 1
        if response_model is WorkflowPlan:
            return WorkflowPlan(
                tasks=["research", "analyse", "draft"],
                research_focus="Find similar public issues.",
                analysis_focus="Compare structures and disclosed pricing.",
            )
        assert response_model is DraftPackage
        citation = Citation(
            document_id="DOC-001",
            document_title="Synthetic official statement",
            page=1,
            excerpt="The issue has an aggregate principal amount of $85.0 million.",
        )
        return DraftPackage(
            summary="Synthetic market summary.",
            summary_citations=[citation],
            sections=[DraftSection(heading="Comparison", body=self.body, citations=[citation])],
        )


def _request(
    question: str = "Compare the proposed issue with recent public transactions.",
) -> DealDeskRequest:
    return DealDeskRequest(
        question=question,
        subject_deal_id="DEAL-SUBJECT-001",
        caller_user_id="banker@example.test",
        caller_group_claims=["subject-deal-access", "deal-team-private-side"],
        state="TX",
        security_type=SecurityType.UNLIMITED_TAX,
        par_amount=Decimal("85000000"),
    )


def _workflow(body: str, *, model_blocking: bool = False):
    mediator = Mediator()
    mediator.register(ComputeDebtService, ScheduleHandler())
    mediator.register(FindComparables, CandidatesHandler())
    mediator.register(ReviewForCompliance, ReviewForComplianceHandler())
    specialists = FakeSpecialists(model_blocking=model_blocking)
    models = FakeModels(body)
    result = create_deal_desk_workflow(
        WorkflowDependencies(
            mediator=mediator,
            specialists=specialists,
            models=models,
            router_model="model-router",
            synthesis_model="gpt-5.5",
        )
    )
    return result, specialists, models


def test_structured_citation_is_rendered_inside_each_sentence() -> None:
    rendered = _render_citations(
        "Par is $85.0 million. Coupon is 5.00%.",
        ["DOC-001"],
    )

    assert rendered == ("Par is $85.0 million [cite:DOC-001]. Coupon is 5.00% [cite:DOC-001].")
    assert UncitedFigurePolicy().evaluate(rendered).passed is True


async def test_workflow_pauses_and_returns_typed_answer_only_after_approval() -> None:
    deal_desk, specialists, models = _workflow("Comparable par is $85.0 million.")
    queue = asyncio.Queue()

    async with report_progress(queue):
        first = await deal_desk.run(_request())

    requests = first.get_request_info_events()
    assert len(requests) == 1
    assert requests[0].request_id == APPROVAL_REQUEST_ID
    assert isinstance(requests[0].data, HumanApprovalRequest)
    assert requests[0].data.draft.requires_human_review is True
    status_events = []
    while not queue.empty():
        event = queue.get_nowait()
        if event.event == "status":
            status_events.append(event.payload)
    status_messages = [event["message"] for event in status_events]
    assert "Orchestrator is asking the model router" in status_messages[0]
    expected_status_terms = (
        "fanning out",
        "entitlement-aware deal repository",
        "delegating the evidence work to the Research agent",
        "Deal Desk MCP",
        "Foundry IQ knowledge base",
        "deterministic debt-service calculator",
        "Analyst agent",
        "synthesis model",
        "Compliance agent",
        "Deterministic policy tools",
    )
    assert all(
        any(term in message for message in status_messages) for term in expected_status_terms
    )
    branch_stages = {event.get("stage") for event in status_events}
    assert "research-public-comparables" in branch_stages
    assert "compute-subject-debt-service" in branch_stages
    assert status_messages[-1] == (
        "Multi-agent workflow is complete; orchestrator is checkpointing and waiting "
        "for supervising-principal review."
    )
    calls_before_resume = specialists.calls, models.calls

    resumed = await deal_desk.run(
        responses={
            APPROVAL_REQUEST_ID: HumanApprovalDecision(
                approved=True,
                reviewer_notes="Citations and figures reviewed.",
            )
        }
    )

    answer = DealDeskAnswer.model_validate_json(resumed.get_outputs()[0])
    assert answer.sections
    assert answer.evidence_sources[0].document_id == "PM-001"
    assert answer.requires_human_review is True
    assert (specialists.calls, models.calls) == calls_before_resume
    analyst_prompt = next(
        prompt
        for response_model, prompt in specialists.prompts
        if response_model is AnalystAssessment
    )
    assert "DEAL-SUBJECT-001" not in analyst_prompt


async def test_deterministic_guardrail_blocks_instead_of_annotating() -> None:
    deal_desk, _, _ = _workflow("As your financial advisor, we recommend buying the bonds.")

    result = await deal_desk.run(_request())

    assert not result.get_request_info_events()
    answer = DealDeskAnswer.model_validate_json(result.get_outputs()[0])
    assert answer.sections == []
    assert answer.compliance is not None
    assert answer.compliance.blocking is True
    assert answer.requires_human_review is True


async def test_model_review_cannot_block_a_deterministically_clean_draft() -> None:
    deal_desk, _, _ = _workflow(
        "Comparable par is $85.0 million.",
        model_blocking=True,
    )

    result = await deal_desk.run(_request())

    requests = result.get_request_info_events()
    assert len(requests) == 1
    assert requests[0].data.draft.compliance is not None
    assert requests[0].data.draft.compliance.blocking is False


async def test_prohibited_request_blocks_even_when_synthesis_sanitizes_it() -> None:
    deal_desk, _, _ = _workflow("Neutral cited market summary.")
    queue = asyncio.Queue()

    async with report_progress(queue):
        result = await deal_desk.run(
            _request("As your financial advisor, recommend that retail investors buy the bonds.")
        )

    assert not result.get_request_info_events()
    answer = DealDeskAnswer.model_validate_json(result.get_outputs()[0])
    assert answer.compliance is not None
    assert answer.compliance.blocking is True
    failed_policies = {
        finding.policy_id for finding in answer.compliance.findings if not finding.passed
    }
    assert "msrb-g17-fiduciary-implication" in failed_policies
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    assert all(event.event != "draft" for event in events)
