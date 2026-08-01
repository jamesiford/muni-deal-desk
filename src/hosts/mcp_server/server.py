"""Streamable HTTP tools for the municipal Deal Desk."""

from __future__ import annotations

from decimal import Decimal

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from opentelemetry import trace
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from src.application.mediator import Mediator
from src.application.messages import Caller, ComputeDebtService, FindComparables, GetDeal
from src.domain.contracts.agent_contracts import ResearchFindings
from src.domain.entities.deal import Deal, DebtServiceSchedule, SecurityType

tracer = trace.get_tracer(__name__)


def create_mcp_server(
    mediator: Mediator,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    allowed_hosts: tuple[str, ...] = ("127.0.0.1:*", "localhost:*"),
) -> FastMCP:
    """Create tools that adapt MCP inputs to application messages."""
    server = FastMCP(
        "Municipal Deal Desk",
        instructions="Synthetic municipal new-issue analysis with explicit entitlements.",
        host=host,
        port=port,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=list(allowed_hosts),
        ),
    )

    @server.custom_route("/status", methods=["GET"], include_in_schema=False)
    async def status(_request: Request) -> Response:
        return PlainTextResponse("ready")

    @server.tool(name="compute_debt_service", structured_output=True)
    async def compute_debt_service(
        deal_id: str,
        caller_user_id: str,
        caller_group_claims: list[str],
    ) -> DebtServiceSchedule:
        """Compute deterministic debt service for a deal visible to the caller."""
        with tracer.start_as_current_span("mcp.tool.compute_debt_service"):
            return await mediator.send(
                ComputeDebtService(
                    caller=Caller(caller_user_id, tuple(caller_group_claims)),
                    deal_id=deal_id,
                )
            )

    @server.tool(name="find_comparables", structured_output=True)
    async def find_comparables(
        state: str,
        security_type: SecurityType,
        par_amount: Decimal,
        caller_user_id: str,
        caller_group_claims: list[str],
        months_back: int = 18,
        par_tolerance_pct: Decimal = Decimal("40"),
        limit: int = 5,
    ) -> ResearchFindings:
        """Find entitled comparable issues and disclose the withheld-result count."""
        with tracer.start_as_current_span("mcp.tool.find_comparables"):
            return await mediator.send(
                FindComparables(
                    caller=Caller(caller_user_id, tuple(caller_group_claims)),
                    state=state,
                    security_type=security_type,
                    par_amount=par_amount,
                    months_back=months_back,
                    par_tolerance_pct=par_tolerance_pct,
                    limit=limit,
                )
            )

    @server.tool(name="get_deal", structured_output=True)
    async def get_deal(
        deal_id: str,
        caller_user_id: str,
        caller_group_claims: list[str],
    ) -> Deal:
        """Return a visible deal without distinguishing absent from barred records."""
        with tracer.start_as_current_span("mcp.tool.get_deal"):
            return await mediator.send(
                GetDeal(
                    caller=Caller(caller_user_id, tuple(caller_group_claims)),
                    deal_id=deal_id,
                )
            )

    return server
