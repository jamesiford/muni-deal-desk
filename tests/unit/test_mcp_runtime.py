"""Production MCP adapter and telemetry wiring tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.hosts.mcp_server import composition
from src.infrastructure.mcp import factory
from src.infrastructure.mcp.factory import AdapterBundle


def test_factory_builds_manifest_and_knowledge_base_adapters(monkeypatch) -> None:
    client = object()
    calls: list[dict[str, object]] = []

    def create_client(**kwargs):
        calls.append(kwargs)
        return client

    monkeypatch.setattr(factory, "KnowledgeBaseRetrievalClient", create_client)
    monkeypatch.setattr(factory, "ManifestDealRepository", lambda path: ("manifest", path))
    monkeypatch.setattr(factory, "AzureBlobKnowledgeBaseAdapter", lambda value: ("kb", value))
    credential = object()
    settings = SimpleNamespace(search_endpoint="https://search.example")

    bundle = factory.create_azure_search_adapters(credential, settings)

    assert bundle.deals[0] == "manifest"
    assert (
        bundle.deals[1] == Path(factory.__file__).resolve().parents[2] / "corpus/out/manifest.json"
    )
    assert bundle.knowledge == ("kb", client)
    assert calls == [
        {
            "endpoint": "https://search.example",
            "knowledge_base_name": factory.KNOWLEDGE_BASE_NAME,
            "credential": credential,
            "api_version": factory.API_VERSION,
        }
    ]


def test_runtime_uses_same_credential_for_adapters_and_telemetry(monkeypatch) -> None:
    credential = object()
    adapters = AdapterBundle(deals=object(), knowledge=object())
    telemetry_calls: list[tuple[str, object]] = []
    adapter_calls: list[tuple[str, object, object]] = []
    sentinel = object()

    monkeypatch.setenv("AZURE_CLIENT_ID", "managed-identity-client")
    monkeypatch.setattr(
        composition,
        "McpHostSettings",
        lambda: SimpleNamespace(
            adapter_factory="module:create",
            host="0.0.0.0",
            port=8000,
            allowed_hosts="mcp.example",
        ),
    )
    settings = SimpleNamespace(applicationinsights_connection_string="InstrumentationKey=test")
    monkeypatch.setattr(composition, "get_settings", lambda: settings)
    monkeypatch.setattr(
        composition,
        "DefaultAzureCredential",
        lambda **kwargs: credential,
    )
    monkeypatch.setattr(
        composition,
        "configure_telemetry",
        lambda connection_string, received_credential: telemetry_calls.append(
            (connection_string, received_credential)
        ),
    )

    def load_adapters(path, received_credential, received_settings):
        adapter_calls.append((path, received_credential, received_settings))
        return adapters

    monkeypatch.setattr(composition, "load_adapter_bundle", load_adapters)
    monkeypatch.setattr(composition, "create_mcp_server", lambda *_args, **_kwargs: sentinel)

    result = composition.create_runtime_server()

    assert result is sentinel
    assert telemetry_calls == [("InstrumentationKey=test", credential)]
    assert adapter_calls == [("module:create", credential, settings)]
