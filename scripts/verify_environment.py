"""Verify the deployed environment actually works.

Provisioning success is not the same as a working environment. This checks the paths
the demonstration depends on: model inference under Entra authentication, Search data
plane reachability, and a trace arriving in Application Insights.

Run automatically by `azd up` through the post-provision hook, and safe to run by hand
at any time.
"""

from __future__ import annotations

import os
import sys

# Written as a standalone operational script rather than application code: it verifies
# infrastructure, so it deliberately does not import the layered application packages.


def _fail(message: str) -> None:
    print(f"  FAIL  {message}")


def _ok(message: str) -> None:
    print(f"  ok    {message}")


def check_models() -> bool:
    """Confirm chat completions return from both the extraction and reasoning tiers."""
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import AzureOpenAI

    account = os.environ["AZURE_AI_ACCOUNT_ENDPOINT"]
    deployments = [
        os.environ["AZURE_AI_EXTRACTION_DEPLOYMENT"],
        os.environ["AZURE_AI_REASONING_DEPLOYMENT"],
    ]

    provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    client = AzureOpenAI(
        azure_endpoint=account,
        azure_ad_token_provider=provider,
        api_version="2024-10-21",
    )

    passed = True
    for deployment in deployments:
        try:
            response = client.chat.completions.create(
                model=deployment,
                messages=[{"role": "user", "content": "Reply with the single word: ready"}],
                max_completion_tokens=2000,
            )
            _ok(f"model {deployment} responded ({response.usage.total_tokens} tokens)")
        except Exception as exc:
            _fail(f"model {deployment}: {type(exc).__name__}: {exc}")
            passed = False
    return passed


def check_search() -> bool:
    """Confirm the Search data plane accepts Entra authentication."""
    from azure.identity import DefaultAzureCredential
    from azure.search.documents.indexes import SearchIndexClient

    try:
        client = SearchIndexClient(
            endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
            credential=DefaultAzureCredential(),
        )
        names = list(client.list_index_names())
        _ok(f"search reachable (indexes: {names or 'none yet'})")
        return True
    except Exception as exc:
        _fail(f"search: {type(exc).__name__}: {exc}")
        return False


def check_tracing() -> bool:
    """Emit a span and confirm the exporter flushes it to Application Insights.

    A successful flush proves the connection string and ingestion path work. The span
    takes a few minutes to become queryable, which is why this checks the export rather
    than reading it back.
    """
    connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection_string:
        _fail("APPLICATIONINSIGHTS_CONNECTION_STRING is not set")
        return False

    try:
        from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider()
        exporter = AzureMonitorTraceExporter(connection_string=connection_string)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

        # The exporter reads the globally registered provider to derive resource
        # attributes. Without this it still exports, but logs an alarming traceback.
        trace.set_tracer_provider(provider)

        tracer = provider.get_tracer("muni-deal-desk.verify")
        with tracer.start_as_current_span("environment-verification") as span:
            span.set_attribute("verification.source", "verify_environment.py")

        flushed = processor.force_flush(timeout_millis=30000)
        provider.shutdown()

        if flushed:
            _ok("application insights accepted a test trace")
            return True
        _fail("application insights did not confirm the trace flush within 30s")
        return False
    except Exception as exc:
        _fail(f"tracing: {type(exc).__name__}: {exc}")
        return False


def main() -> int:
    """Run every check and return a non-zero exit code if any fails."""
    print("")
    print("Verifying deployed environment")
    print("")

    required = [
        "AZURE_AI_ACCOUNT_ENDPOINT",
        "AZURE_AI_EXTRACTION_DEPLOYMENT",
        "AZURE_AI_REASONING_DEPLOYMENT",
        "AZURE_SEARCH_ENDPOINT",
    ]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        _fail(f"missing environment values: {', '.join(missing)}")
        return 1

    results = [check_models(), check_search(), check_tracing()]
    print("")

    if all(results):
        print("Environment verified.")
        return 0
    print("Environment verification FAILED. See failures above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
