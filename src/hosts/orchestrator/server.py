"""Invocations transport adapter with session-scoped human approval resume."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from agent_framework import (
    AgentSession,
    BaseAgent,
    FunctionalWorkflowAgent,
)
from agent_framework_foundry_hosting import InvocationsHostServer
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from src.domain.contracts.agent_contracts import (
    DealDeskRequest,
    HumanApprovalDecision,
    HumanApprovalRequest,
)


def _message_payload(message: object) -> object:
    if isinstance(message, str):
        return json.loads(message)
    return message


class HostedWorkflowAgent(BaseAgent):
    """Supply session methods missing from the experimental functional agent adapter."""

    def __init__(self, agent: FunctionalWorkflowAgent) -> None:
        super().__init__(id=agent.id, name=agent.name, description=agent.description)
        self._agent = agent

    @property
    def pending_requests(self) -> dict[str, object]:
        """Pending human requests from the delegated workflow agent."""
        return self._agent.pending_requests

    def run(
        self,
        messages: object | None = None,
        *,
        stream: bool = False,
        session: AgentSession | None = None,
        function_invocation_kwargs: dict[str, object] | None = None,
        client_kwargs: dict[str, object] | None = None,
        **kwargs: object,
    ) -> object:
        """Delegate execution while accepting the complete hosted-agent protocol."""
        del function_invocation_kwargs, client_kwargs
        return self._agent.run(messages, stream=stream, session=session, **kwargs)


class ApprovalInvocationsHostServer(InvocationsHostServer):
    """Map an Invocations session's next message to the pending workflow request."""

    def __init__(self, agent: HostedWorkflowAgent) -> None:
        self._workflow_agent = agent
        self._pending_session_id: str | None = None
        super().__init__(agent)

    async def _handle_invoke(self, request: Request) -> Response:
        data = await request.json()
        session_id: str = request.state.session_id
        message = data.get("message")
        if message is None:
            return Response(content="Missing 'message' in request", status_code=400)

        try:
            if self._workflow_agent.pending_requests:
                if session_id != self._pending_session_id:
                    return Response(
                        content="A different session owns the pending approval.",
                        status_code=409,
                    )
                decision = HumanApprovalDecision.model_validate(_message_payload(message))
                response = await self._workflow_agent.run(
                    responses={next(iter(self._workflow_agent.pending_requests)): decision},
                    session=self._session(session_id),
                )
                self._pending_session_id = None
                body = response.text
            else:
                deal_request = DealDeskRequest.model_validate(_message_payload(message))
                response = await self._workflow_agent.run(
                    deal_request,
                    session=self._session(session_id),
                )
                body = response.text
                if self._workflow_agent.pending_requests:
                    self._pending_session_id = session_id
                    request_id, event = next(iter(self._workflow_agent.pending_requests.items()))
                    approval = HumanApprovalRequest.model_validate(event.data)
                    body = json.dumps(
                        {
                            "status": "approval_required",
                            "request_id": request_id,
                            "request": approval.model_dump(mode="json"),
                        },
                        separators=(",", ":"),
                    )
        except (json.JSONDecodeError, ValidationError) as exc:
            return Response(content=f"Invalid typed message: {exc}", status_code=400)

        if data.get("stream", False):

            async def stream_response() -> AsyncGenerator[str]:
                yield body

            return StreamingResponse(stream_response(), media_type="text/event-stream")
        return JSONResponse({"response": body, "session_id": session_id})

    def _session(self, session_id: str) -> AgentSession:
        return self._sessions.setdefault(session_id, AgentSession(session_id=session_id))
