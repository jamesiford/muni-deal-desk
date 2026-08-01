"""MCP server composition root."""

from __future__ import annotations

import os

from azure.core.credentials import TokenCredential
from azure.identity import DefaultAzureCredential
from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
from mcp.server.fastmcp import FastMCP
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

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


def configure_telemetry(connection_string: str, credential: TokenCredential) -> None:
    """Export MCP spans to Application Insights with Microsoft Entra authentication."""
    provider = TracerProvider(resource=Resource.create({"service.name": "muni-deal-desk-mcp"}))
    provider.add_span_processor(
        BatchSpanProcessor(
            AzureMonitorTraceExporter(
                connection_string=connection_string,
                credential=credential,
            )
        )
    )
    trace.set_tracer_provider(provider)


def create_mediator(adapters: AdapterBundle) -> Mediator:
    """Register all MCP use cases against shared adapter instances."""
    mediator = Mediator()
    mediator.register(
        ComputeDebtService,
        ComputeDebtServiceHandler(adapters.deals, DebtServiceCalculator()),
    )
    mediator.register(
        FindComparables,
        FindComparablesHandler(adapters.deals, adapters.knowledge),
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
