"""MCP server composition root."""

from __future__ import annotations

import os

from azure.core.credentials import TokenCredential
from azure.identity import DefaultAzureCredential
from mcp.server.fastmcp import FastMCP

from src.application.handlers.compute_debt_service import ComputeDebtServiceHandler
from src.application.handlers.find_comparables import FindComparablesHandler
from src.application.handlers.get_deal import GetDealHandler
from src.application.mediator import Mediator
from src.application.messages import ComputeDebtService, FindComparables, GetDeal
from src.config import get_settings
from src.hosts.mcp_server.server import create_mcp_server
from src.hosts.mcp_server.settings import McpHostSettings
from src.infrastructure.calculators import DebtServiceCalculator
from src.infrastructure.mcp.factory import AdapterBundle, load_adapter_bundle
from src.infrastructure.observability.tracing import configure_azure_monitor


def configure_telemetry(connection_string: str, credential: TokenCredential) -> None:
    """Configure MCP tracing through the shared Azure Monitor adapter."""
    configure_azure_monitor("muni-deal-desk-mcp", connection_string, credential)


def create_mediator(adapters: AdapterBundle) -> Mediator:
    """Register all MCP use cases against shared adapter instances."""
    mediator = Mediator()
    mediator.register(
        ComputeDebtService,
        ComputeDebtServiceHandler(adapters.deals, DebtServiceCalculator()),
    )
    mediator.register(
        FindComparables,
        FindComparablesHandler(adapters.deals),
    )
    mediator.register(GetDeal, GetDealHandler(adapters.deals))
    return mediator


def create_runtime_server() -> FastMCP:
    """Construct the production server with managed identity and concrete adapters."""
    host_settings = McpHostSettings()  # type: ignore[call-arg]
    azure_settings = get_settings()
    credential = DefaultAzureCredential(
        managed_identity_client_id=os.getenv("AZURE_CLIENT_ID"),
    )
    if azure_settings.applicationinsights_connection_string:
        configure_telemetry(
            azure_settings.applicationinsights_connection_string,
            credential,
        )
    adapters = load_adapter_bundle(
        host_settings.adapter_factory,
        credential,
        azure_settings,
    )
    mediator = create_mediator(adapters)
    return create_mcp_server(
        mediator,
        host=host_settings.host,
        port=host_settings.port,
        allowed_hosts=tuple(
            host.strip() for host in host_settings.allowed_hosts.split(",") if host.strip()
        ),
    )
