"""Async client for the native Foundry Hosted Agent Invocations endpoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from azure.core.credentials_async import AsyncTokenCredential

from src.domain.contracts.agent_contracts import DealDeskRequest, HumanApprovalDecision


def _session_url(endpoint: str, session_id: str) -> str:
    parts = urlsplit(endpoint)
    query = dict(parse_qsl(parts.query))
    query["agent_session_id"] = session_id
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class HostedOrchestratorClient:
    """Stream typed start and approval operations from the hosted orchestrator."""

    def __init__(
        self,
        endpoint: str,
        credential: AsyncTokenCredential,
        *,
        timeout_seconds: float = 600,
    ) -> None:
        self._endpoint = endpoint
        self._credential = credential
        self._timeout = timeout_seconds

    async def start(
        self,
        session_id: str,
        request: DealDeskRequest,
    ) -> AsyncIterator[str]:
        """Start a typed run and yield its native SSE frames."""
        async for chunk in self._stream(
            session_id,
            {"operation": "start", "request": request.model_dump(mode="json")},
        ):
            yield chunk

    async def approve(
        self,
        session_id: str,
        decision: HumanApprovalDecision,
    ) -> AsyncIterator[str]:
        """Resume a pending run with a typed approval decision."""
        async for chunk in self._stream(
            session_id,
            {"operation": "approve", "decision": decision.model_dump(mode="json")},
        ):
            yield chunk

    async def _stream(
        self,
        session_id: str,
        message: dict[str, object],
    ) -> AsyncIterator[str]:
        token = await self._credential.get_token("https://ai.azure.com/.default")
        headers = {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json",
            "x-agent-session-id": session_id,
        }
        async with (
            httpx.AsyncClient(timeout=self._timeout) as client,
            client.stream(
                "POST",
                _session_url(self._endpoint, session_id),
                headers=headers,
                json={"message": message, "stream": True},
            ) as response,
        ):
            response.raise_for_status()
            async for chunk in response.aiter_text():
                yield chunk
