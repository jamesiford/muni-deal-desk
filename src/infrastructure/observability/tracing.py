"""Shared Azure Monitor trace exporter configuration."""

from __future__ import annotations

from azure.core.credentials import TokenCredential
from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure_azure_monitor(
    service_name: str,
    connection_string: str,
    credential: TokenCredential,
) -> None:
    """Export OpenTelemetry spans to Application Insights with Entra authentication."""
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(
        BatchSpanProcessor(
            AzureMonitorTraceExporter(
                connection_string=connection_string,
                credential=credential,
            )
        )
    )
    trace.set_tracer_provider(provider)
