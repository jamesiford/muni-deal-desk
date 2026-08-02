"""Invocations transport adapter with session-scoped human approval resume."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator, Callable, Mapping

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
    DealDeskAnswer,
    DealDeskRequest,
    HumanApprovalDecision,
    HumanApprovalRequest,
)
from src.hosts.orchestrator.progress import ProgressEvent, report_progress

SCHEMA_VERSION = "1.0"


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

    def __init__(
        self,
        agent: HostedWorkflowAgent | Callable[[], HostedWorkflowAgent],
    ) -> None:
        if isinstance(agent, HostedWorkflowAgent):
            seed = agent
            self._agent_factory = lambda: agent
        else:
            seed = agent()
            self._agent_factory = agent
        self._workflow_agents: dict[str, HostedWorkflowAgent] = {}
        super().__init__(seed)

    def _workflow_agent(self, session_id: str) -> HostedWorkflowAgent:
        return self._workflow_agents.setdefault(session_id, self._agent_factory())

    @staticmethod
    def _decode_message(message: object) -> tuple[str, object]:
        payload = _message_payload(message)
        if isinstance(payload, Mapping) and "operation" in payload:
            operation = str(payload["operation"])
            if operation == "start":
                return operation, payload.get("request")
            if operation == "approve":
                return operation, payload.get("decision")
            raise ValueError(f"Unsupported operation: {operation}")
        return "auto", payload

    @staticmethod
    def _event_payload(run_id: str, sequence: int, data: Mapping[str, object]) -> str:
        event_name = str(data["event"])
        payload = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "sequence": sequence,
            **data,
        }
        return (
            f"id: {run_id}:{sequence}\n"
            f"event: {event_name}\n"
            f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"
        )

    @staticmethod
    def _result_events(
        agent: HostedWorkflowAgent,
        response_text: str,
    ) -> list[dict[str, object]]:
        if agent.pending_requests:
            request_id, event = next(iter(agent.pending_requests.items()))
            approval = HumanApprovalRequest.model_validate(event.data)
            answer = approval.draft
            events = ApprovalInvocationsHostServer._answer_detail_events(answer)
            events.append(
                {
                    "event": "approval_required",
                    "request_id": request_id,
                    "request": approval.model_dump(mode="json"),
                }
            )
            return events

        answer = DealDeskAnswer.model_validate_json(response_text)
        events = ApprovalInvocationsHostServer._answer_detail_events(answer)
        if answer.compliance is not None and answer.compliance.blocking:
            outcome = "blocked"
        elif "rejected" in answer.summary.lower():
            outcome = "rejected"
        else:
            outcome = "approved"
        events.append(
            {
                "event": "final",
                "outcome": outcome,
                "answer": answer.model_dump(mode="json"),
            }
        )
        return events

    @staticmethod
    def _answer_detail_events(answer: DealDeskAnswer) -> list[dict[str, object]]:
        events: list[dict[str, object]] = []
        citations = [
            *answer.summary_citations,
            *(citation for section in answer.sections for citation in section.citations),
        ]
        seen: set[tuple[str, str]] = set()
        for citation in citations:
            key = (citation.document_id, citation.excerpt)
            if key not in seen:
                seen.add(key)
                events.append({"event": "citation", "citation": citation.model_dump(mode="json")})
        if answer.compliance is not None:
            events.extend(
                {"event": "policy", "finding": finding.model_dump(mode="json")}
                for finding in answer.compliance.findings
            )
        return events

    async def _run(
        self,
        agent: HostedWorkflowAgent,
        operation: str,
        payload: object,
        session: AgentSession,
    ) -> object:
        if operation == "approve" or (operation == "auto" and agent.pending_requests):
            decision = HumanApprovalDecision.model_validate(payload)
            return await agent.run(
                responses={next(iter(agent.pending_requests)): decision},
                session=session,
            )
        deal_request = DealDeskRequest.model_validate(payload)
        return await agent.run(deal_request, session=session)

    async def _handle_invoke(self, request: Request) -> Response:
        data = await request.json()
        session_id: str = request.state.session_id
        message = data.get("message")
        if message is None:
            return Response(content="Missing 'message' in request", status_code=400)

        try:
            operation, payload = self._decode_message(message)
            agent = self._workflow_agent(session_id)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            return Response(content=f"Invalid typed message: {exc}", status_code=400)

        if data.get("stream", False):

            async def stream_response() -> AsyncGenerator[str]:
                sequence = 0
                queue: asyncio.Queue[ProgressEvent] = asyncio.Queue()
                loop = asyncio.get_running_loop()
                next_keepalive = loop.time() + 5

                # A padded SSE comment forces managed proxies to flush headers and
                # small stage events instead of buffering until the draft arrives.
                yield f": {' ' * 2048}\n\n"

                async def execute() -> object:
                    async with report_progress(queue):
                        return await self._run(
                            agent,
                            operation,
                            payload,
                            self._session(session_id),
                        )

                task = asyncio.create_task(execute())
                try:
                    while not task.done():
                        try:
                            progress = await asyncio.wait_for(queue.get(), timeout=0.25)
                        except TimeoutError:
                            if loop.time() >= next_keepalive:
                                yield ": keepalive\n\n"
                                next_keepalive = loop.time() + 5
                            continue
                        sequence += 1
                        yield self._event_payload(
                            session_id,
                            sequence,
                            {"event": progress.event, **progress.payload},
                        )
                    while not queue.empty():
                        progress = queue.get_nowait()
                        sequence += 1
                        yield self._event_payload(
                            session_id,
                            sequence,
                            {"event": progress.event, **progress.payload},
                        )
                    response = await task
                    for event in self._result_events(agent, response.text):
                        sequence += 1
                        yield self._event_payload(session_id, sequence, event)
                except Exception:
                    sequence += 1
                    yield self._event_payload(
                        session_id,
                        sequence,
                        {
                            "event": "error",
                            "code": "workflow_failed",
                            "message": "The workflow could not complete this request.",
                            "retryable": False,
                        },
                    )

            return StreamingResponse(
                stream_response(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache, no-transform",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        try:
            response = await self._run(
                agent,
                operation,
                payload,
                self._session(session_id),
            )
            if agent.pending_requests:
                request_id, event = next(iter(agent.pending_requests.items()))
                approval = HumanApprovalRequest.model_validate(event.data)
                body = json.dumps(
                    {
                        "status": "approval_required",
                        "request_id": request_id,
                        "request": approval.model_dump(mode="json"),
                    },
                    separators=(",", ":"),
                )
            else:
                body = response.text
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            return Response(content=f"Invalid typed message: {exc}", status_code=400)
        return JSONResponse({"response": body, "session_id": session_id})

    def _session(self, session_id: str) -> AgentSession:
        return self._sessions.setdefault(session_id, AgentSession(session_id=session_id))
