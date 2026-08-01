"""Infrastructure adapter loading for the MCP composition root."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

from azure.core.credentials import TokenCredential
from azure.search.documents.knowledgebases import KnowledgeBaseRetrievalClient

from src.application.ports import DealRepositoryPort, KnowledgePort
from src.config import Settings
from src.infrastructure.manifest_repository import ManifestDealRepository
from src.infrastructure.search.constants import API_VERSION, KNOWLEDGE_BASE_NAME
from src.infrastructure.search.knowledge_base import AzureBlobKnowledgeBaseAdapter


@dataclass(frozen=True, slots=True)
class AdapterBundle:
    """Concrete data adapters shared by all MCP handlers."""

    deals: DealRepositoryPort
    knowledge: KnowledgePort


class AdapterFactory(Protocol):
    """Factory supplied by the retrieval implementation."""

    def __call__(self, credential: TokenCredential, settings: Settings) -> AdapterBundle:
        """Construct data adapters from managed identity and typed settings."""
        ...


def create_azure_search_adapters(
    credential: TokenCredential,
    settings: Settings,
) -> AdapterBundle:
    """Build typed manifest lookup and Blob-backed knowledge retrieval adapters."""
    manifest_path = Path(__file__).resolve().parents[2] / "corpus" / "out" / "manifest.json"
    client = KnowledgeBaseRetrievalClient(
        endpoint=settings.search_endpoint,
        knowledge_base_name=KNOWLEDGE_BASE_NAME,
        credential=credential,
        api_version=API_VERSION,
    )
    return AdapterBundle(
        deals=ManifestDealRepository(manifest_path),
        knowledge=AzureBlobKnowledgeBaseAdapter(client),
    )


def load_adapter_bundle(
    factory_path: str,
    credential: TokenCredential,
    settings: Settings,
) -> AdapterBundle:
    """Load `module:function` without coupling the host to a retrieval implementation."""
    module_name, separator, function_name = factory_path.partition(":")
    if not separator or not module_name or not function_name:
        raise RuntimeError("MCP_ADAPTER_FACTORY must use the form 'module:function'.")

    try:
        factory = getattr(import_module(module_name), function_name)
    except (ImportError, AttributeError) as exc:
        raise RuntimeError(f"MCP_ADAPTER_FACTORY '{factory_path}' could not be imported.") from exc
    if not callable(factory):
        raise RuntimeError(f"MCP_ADAPTER_FACTORY '{factory_path}' is not callable.")

    return cast(AdapterFactory, factory)(credential, settings)
