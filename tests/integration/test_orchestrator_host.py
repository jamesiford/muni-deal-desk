"""Invocations transport integration for the hosted workflow approval gate."""

from __future__ import annotations

import json
from decimal import Decimal

from agent_framework import RunContext, workflow
from src.domain.contracts.agent_contracts import (
    DealDeskAnswer,
    DealDeskRequest,
    HumanApprovalDecision,
    HumanApprovalRequest,
)
from src.domain.entities.deal import SecurityType
from src.hosts.orchestrator.progress import emit_progress, run_stage
from src.hosts.orchestrator.server import (
    ApprovalInvocationsHostServer,
    HostedWorkflowAgent,
)
from starlette.testclient import TestClient


def test_invocations_host_pauses_and_resumes_same_session(monkeypatch) -> None:
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")

    @workflow(name="approval-integration")
    async def approval_flow(request: DealDeskRequest, ctx: RunContext) -> str:
        draft = DealDeskAnswer(summary=request.question)
        raw_decision = await ctx.request_info(
            HumanApprovalRequest(draft=draft),
            response_type=HumanApprovalDecision,
            request_id="approval",
        )
        decision = HumanApprovalDecision.model_validate(raw_decision)
        return draft.model_dump_json() if decision.approved else ""

    agent = HostedWorkflowAgent(approval_flow.as_agent(name="approval-integration"))
    server = ApprovalInvocationsHostServer(agent)
    client = TestClient(server)
    session_url = "/invocations?agent_session_id=integration-session"
    request = DealDeskRequest(
        question="Compare the proposed issue.",
        subject_deal_id="DEAL-SUBJECT-001",
        caller_user_id="banker@example.test",
        caller_group_claims=["deal-team-private-side"],
        state="TX",
        security_type=SecurityType.UNLIMITED_TAX,
        par_amount=Decimal("85000000"),
    )

    paused = client.post(session_url, json={"message": request.model_dump(mode="json")})

    assert paused.status_code == 200
    paused_body = json.loads(paused.json()["response"])
    assert paused_body["status"] == "approval_required"
    assert paused_body["request"]["draft"]["requires_human_review"] is True

    resumed = client.post(session_url, json={"message": {"approved": True}})

    assert resumed.status_code == 200
    answer = DealDeskAnswer.model_validate_json(resumed.json()["response"])
    assert answer.summary == request.question
    assert answer.requires_human_review is True


def test_invocations_host_streams_real_stage_approval_and_final_events(monkeypatch) -> None:
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")

    async def echo(value: str) -> str:
        return value

    def create_agent() -> HostedWorkflowAgent:
        @workflow(name="streaming-approval-integration")
        async def approval_flow(request: DealDeskRequest, ctx: RunContext) -> str:
            await emit_progress(
                "status",
                message="Planner is decomposing the request.",
            )
            summary = await run_stage("plan-request", echo(request.question))
            await emit_progress(
                "citation",
                citation={
                    "document_id": "DOC-001",
                    "document_title": "Synthetic official statement",
                    "excerpt": "Synthetic evidence.",
                    "sensitivity": "public",
                },
            )
            await emit_progress(
                "evidence",
                evidence_source={
                    "document_id": "DOC-001",
                    "document_title": "Synthetic official statement",
                    "deal_id": "DEAL-001",
                    "source_type": "official_statement",
                    "sensitivity": "public",
                },
            )
            draft = DealDeskAnswer(summary=summary)
            raw_decision = await ctx.request_info(
                HumanApprovalRequest(draft=draft),
                response_type=HumanApprovalDecision,
                request_id="approval",
            )
            decision = HumanApprovalDecision.model_validate(raw_decision)
            return draft.model_dump_json() if decision.approved else ""

        return HostedWorkflowAgent(approval_flow.as_agent(name="streaming-integration"))

    server = ApprovalInvocationsHostServer(create_agent)
    client = TestClient(server)
    session_url = "/invocations?agent_session_id=streaming-session"
    request = DealDeskRequest(
        question="Compare the proposed issue.",
        subject_deal_id="DEAL-SUBJECT-001",
        caller_user_id="banker@example.test",
        caller_group_claims=["subject-deal-access"],
        state="TX",
        security_type=SecurityType.UNLIMITED_TAX,
        par_amount=Decimal("85000000"),
    )

    with client.stream(
        "POST",
        session_url,
        json={
            "message": {"operation": "start", "request": request.model_dump(mode="json")},
            "stream": True,
        },
    ) as paused:
        paused_body = "".join(paused.iter_text())

    assert paused.status_code == 200
    assert paused.headers["cache-control"] == "no-cache, no-transform"
    assert paused.headers["x-accel-buffering"] == "no"
    assert paused_body.startswith(": ")
    assert "event: status" in paused_body
    assert '"message":"Planner is decomposing the request."' in paused_body
    assert "event: stage" in paused_body
    assert '"stage":"plan-request","status":"started"' in paused_body
    assert '"stage":"plan-request","status":"completed"' in paused_body
    assert "event: citation" in paused_body
    assert "event: evidence" in paused_body
    assert "event: approval_required" in paused_body

    with client.stream(
        "POST",
        session_url,
        json={
            "message": {
                "operation": "approve",
                "decision": {"approved": True, "reviewer_notes": "Reviewed."},
            },
            "stream": True,
        },
    ) as resumed:
        resumed_body = "".join(resumed.iter_text())

    assert resumed.status_code == 200
    assert "event: final" in resumed_body
    assert '"outcome":"approved"' in resumed_body
