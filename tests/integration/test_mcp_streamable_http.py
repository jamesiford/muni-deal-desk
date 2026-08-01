"""Streamable HTTP protocol integration tests."""

from __future__ import annotations

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from src.application.mediator import Mediator
from src.hosts.mcp_server.server import create_mcp_server


async def test_lists_phase_four_tools_over_streamable_http():
    server = create_mcp_server(Mediator(), allowed_hosts=("test",))
    app = server.streamable_http_app()
    transport = httpx.ASGITransport(app=app)

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://test") as client,
        streamable_http_client(
            "http://test/mcp",
            http_client=client,
        ) as (read, write, _session_id),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()

    assert {tool.name for tool in tools.tools} == {
        "compute_debt_service",
        "find_comparable_deals",
        "get_deal",
    }
