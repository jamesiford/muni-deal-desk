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
