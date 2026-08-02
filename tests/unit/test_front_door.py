"""Tests for the local banker-facing presentation API."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi.testclient import TestClient
from src.domain.contracts.agent_contracts import DealDeskRequest, HumanApprovalDecision
from src.hosts.front_door.app import (
    DemoIdentity,
    RunRequest,
    build_deal_desk_request,
    create_front_door_app,
)


class RecordingClient:
    def __init__(self) -> None:
        self.started: list[tuple[str, DealDeskRequest]] = []
        self.approved: list[tuple[str, HumanApprovalDecision]] = []

    async def start(self, session_id: str, request: DealDeskRequest) -> AsyncIterator[str]:
        self.started.append((session_id, request))
        yield 'event: stage\ndata: {"event":"stage"}\n\n'

    async def approve(
        self,
        session_id: str,
        decision: HumanApprovalDecision,
    ) -> AsyncIterator[str]:
        self.approved.append((session_id, decision))
        yield 'event: final\ndata: {"event":"final"}\n\n'


def test_personas_share_subject_access_but_only_deal_team_has_private_access() -> None:
    public = build_deal_desk_request(
        RunRequest(
            question="Compare the proposed financing today.",
            identity=DemoIdentity.PUBLIC_SIDE,
        )
    )
    deal_team = build_deal_desk_request(
        RunRequest(
            question="Compare the proposed financing today.",
            identity=DemoIdentity.DEAL_TEAM,
        )
    )

    assert public.caller_group_claims == ["subject-deal-access"]
    assert deal_team.caller_group_claims == [
        "subject-deal-access",
        "deal-team-private-side",
    ]


def test_front_door_proxies_start_and_approval_sse() -> None:
    hosted = RecordingClient()
    app = create_front_door_app(hosted, run_id_factory=lambda: "run-001")
    client = TestClient(app)

    started = client.post(
        "/api/runs",
        json={"question": "Compare the proposed financing today.", "identity": "public_side"},
    )
    approved = client.post(
        "/api/runs/run-001/approval",
        json={"approved": True, "reviewer_notes": "Reviewed."},
    )

    assert started.status_code == 200
    assert started.headers["x-run-id"] == "run-001"
    assert started.headers["cache-control"] == "no-cache, no-transform"
    assert started.headers["x-accel-buffering"] == "no"
    assert "event: stage" in started.text
    assert hosted.started[0][1].caller_user_id == "demo-public-side"
    assert approved.status_code == 200
    assert approved.headers["x-accel-buffering"] == "no"
    assert "event: final" in approved.text
    assert hosted.approved[0][1].approved is True
