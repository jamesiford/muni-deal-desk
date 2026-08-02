"""FastAPI presentation bridge for the native Foundry Hosted Agent."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.domain.contracts.agent_contracts import DealDeskRequest, HumanApprovalDecision
from src.domain.entities.deal import SecurityType

SUBJECT_ACCESS = "subject-deal-access"
DEAL_TEAM_ACCESS = "deal-team-private-side"


class DemoIdentity(StrEnum):
    """Presentation personas, not authentication identities."""

    PUBLIC_SIDE = "public_side"
    DEAL_TEAM = "deal_team"


class RunRequest(BaseModel):
    """Browser-safe run request."""

    question: str = Field(min_length=10, max_length=4000)
    identity: DemoIdentity


class ApprovalRequest(BaseModel):
    """Supervising-principal decision from the front door."""

    approved: bool
    reviewer_notes: str = Field(default="", max_length=1000)


class OrchestratorStreamPort:
    """Structural type for the bridge's hosted-agent dependency."""

    def start(self, session_id: str, request: DealDeskRequest) -> AsyncIterator[str]:
        """Start one streamed workflow run."""
        ...

    def approve(
        self,
        session_id: str,
        decision: HumanApprovalDecision,
    ) -> AsyncIterator[str]:
        """Resume one streamed workflow run."""
        ...


def build_deal_desk_request(request: RunRequest) -> DealDeskRequest:
    """Map a fixed demo persona to explicit application claims."""
    if request.identity is DemoIdentity.DEAL_TEAM:
        user_id = "demo-deal-team"
        claims = [SUBJECT_ACCESS, DEAL_TEAM_ACCESS]
    else:
        user_id = "demo-public-side"
        claims = [SUBJECT_ACCESS]
    return DealDeskRequest(
        question=request.question,
        subject_deal_id="DEAL-SUBJECT-001",
        caller_user_id=user_id,
        caller_group_claims=claims,
        state="TX",
        security_type=SecurityType.UNLIMITED_TAX,
        par_amount="85000000",
        months_back=18,
    )


async def _safe_stream(stream: AsyncIterator[str], run_id: str) -> AsyncIterator[str]:
    try:
        async for chunk in stream:
            yield chunk
    except Exception:
        payload = {
            "schema_version": "1.0",
            "run_id": run_id,
            "sequence": 1,
            "event": "error",
            "code": "hosted_agent_unavailable",
            "message": "The hosted workflow is unavailable. Try again after checking its status.",
            "retryable": True,
        }
        yield f"event: error\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


def create_front_door_app(
    client: OrchestratorStreamPort,
    *,
    allowed_origin: str = "http://localhost:5173",
    frontend_dist: Path | None = None,
    run_id_factory: Callable[[], str] | None = None,
) -> FastAPI:
    """Create the local presentation API with no duplicated business rules."""
    app = FastAPI(title="Municipal Deal Desk", docs_url=None, redoc_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[allowed_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    runs: set[str] = set()
    new_run_id = run_id_factory or (lambda: str(uuid4()))

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ready"}

    @app.post("/api/runs")
    async def start_run(request: RunRequest) -> StreamingResponse:
        run_id = new_run_id()
        runs.add(run_id)
        deal_request = build_deal_desk_request(request)
        return StreamingResponse(
            _safe_stream(client.start(run_id, deal_request), run_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "X-Run-Id": run_id,
            },
        )

    @app.post("/api/runs/{run_id}/approval")
    async def approve_run(run_id: str, request: ApprovalRequest) -> StreamingResponse:
        if run_id not in runs:
            raise HTTPException(status_code=404, detail="Run not found.")
        decision = HumanApprovalDecision(
            approved=request.approved,
            reviewer_notes=request.reviewer_notes,
        )
        return StreamingResponse(
            _safe_stream(client.approve(run_id, decision), run_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "X-Run-Id": run_id,
            },
        )

    static_root = frontend_dist
    if static_root is not None and static_root.exists():
        assets = static_root / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}")
        async def frontend(path: str) -> FileResponse:
            candidate = static_root / path
            return FileResponse(candidate if candidate.is_file() else static_root / "index.html")

    return app
