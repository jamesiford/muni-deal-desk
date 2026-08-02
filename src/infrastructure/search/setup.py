"""Idempotent Blob knowledge-source and Foundry IQ knowledge-base setup."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping

from azure.core.exceptions import ResourceNotFoundError
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    AzureBlobKnowledgeSource,
    AzureBlobKnowledgeSourceParameters,
    AzureOpenAIVectorizerParameters,
    KnowledgeBase,
    KnowledgeBaseAzureOpenAIModel,
    KnowledgeSourceAzureOpenAIVectorizer,
    KnowledgeSourceContentExtractionMode,
    KnowledgeSourceIngestionParameters,
    KnowledgeSourceReference,
)
from azure.search.documents.knowledgebases.models import (
    KnowledgeRetrievalLowReasoningEffort,
    KnowledgeRetrievalOutputMode,
)

from .constants import KNOWLEDGE_BASE_NAME, KNOWLEDGE_SOURCE_NAME

RETRIEVAL_INSTRUCTIONS = (
    "Use official statements for original bond terms, continuing disclosures for later "
    "operating data, and material event notices for subsequent events. Prefer more recent "
    "dated disclosures for current figures. When sources conflict, surface and cite both "
    "values. Never infer an absent call provision or present stale financials as current. "
    "Private-side pricing memos are governed separately and are not part of this knowledge "
    "source."
)


def _model_parameters(
    endpoint: str,
    deployment: str,
    model_name: str,
) -> AzureOpenAIVectorizerParameters:
    return AzureOpenAIVectorizerParameters(
        resource_url=endpoint,
        deployment_name=deployment,
        model_name=model_name,
    )


def build_knowledge_source(
    *,
    storage_account_id: str,
    container_name: str,
    model_endpoint: str,
    embedding_deployment: str,
) -> AzureBlobKnowledgeSource:
    """Build the portal-visible public PDF source and generated ingestion pipeline."""
    return AzureBlobKnowledgeSource(
        name=KNOWLEDGE_SOURCE_NAME,
        description=(
            "Public synthetic municipal official statements, continuing disclosures, and "
            "material event notices stored as PDFs in Azure Blob Storage."
        ),
        azure_blob_parameters=AzureBlobKnowledgeSourceParameters(
            connection_string=f"ResourceId={storage_account_id};",
            container_name=container_name,
            folder_path="pdf/public",
            ingestion_parameters=KnowledgeSourceIngestionParameters(
                disable_image_verbalization=True,
                embedding_model=KnowledgeSourceAzureOpenAIVectorizer(
                    azure_open_ai_parameters=_model_parameters(
                        model_endpoint,
                        embedding_deployment,
                        "text-embedding-3-large",
                    )
                ),
                content_extraction_mode=KnowledgeSourceContentExtractionMode.MINIMAL,
            ),
        ),
    )


def build_knowledge_base(*, model_endpoint: str, chat_deployment: str) -> KnowledgeBase:
    """Build the model-backed knowledge base used in the Foundry IQ demonstration."""
    return KnowledgeBase(
        name=KNOWLEDGE_BASE_NAME,
        description=(
            "Grounds municipal new-issue research in wholly synthetic public official "
            "statements, continuing disclosures, and material event notices."
        ),
        knowledge_sources=[KnowledgeSourceReference(name=KNOWLEDGE_SOURCE_NAME)],
        models=[
            KnowledgeBaseAzureOpenAIModel(
                azure_open_ai_parameters=_model_parameters(
                    model_endpoint,
                    chat_deployment,
                    chat_deployment,
                )
            )
        ],
        retrieval_reasoning_effort=KnowledgeRetrievalLowReasoningEffort(),
        output_mode=KnowledgeRetrievalOutputMode.EXTRACTIVE_DATA,
        retrieval_instructions=RETRIEVAL_INSTRUCTIONS,
    )


def _clean(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            key: _clean(item)
            for key, item in value.items()
            if key
            not in {
                "e_tag",
                "@odata.etag",
                "createdResources",
                "created_resources",
                "connectionString",
                "connection_string",
            }
            and item is not None
        }
    if isinstance(value, list):
        return [_clean(item) for item in value]
    return value


def _contains(current: object, desired: object) -> bool:
    if isinstance(desired, Mapping):
        return isinstance(current, Mapping) and all(
            key in current and _contains(current[key], value) for key, value in desired.items()
        )
    if isinstance(desired, list):
        return (
            isinstance(current, list)
            and len(current) == len(desired)
            and all(_contains(left, right) for left, right in zip(current, desired, strict=True))
        )
    return current == desired


def ensure_resource(
    *,
    get: Callable[[], object],
    upsert: Callable[[object], object],
    desired: object,
) -> str:
    """Create or update a named Search resource only when its desired shape changed."""
    try:
        current = get()
    except ResourceNotFoundError:
        upsert(desired)
        return "created"
    if _contains(_clean(current.as_dict()), _clean(desired.as_dict())):  # type: ignore[attr-defined]
        return "unchanged"
    upsert(desired)
    return "updated"


def wait_for_knowledge_source(
    index_client: SearchIndexClient,
    expected_documents: int,
    get_document_count: Callable[[], int] | None = None,
    timeout_seconds: int = 900,
) -> int:
    """Wait for Blob ingestion and return the processed public-document count."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if get_document_count is not None:
            indexed = get_document_count()
            if indexed >= expected_documents:
                return indexed
        status = index_client.get_knowledge_source_status(KNOWLEDGE_SOURCE_NAME)
        completed = status.last_synchronization_state
        if completed is not None:
            failed = getattr(completed, "items_updates_failed", 0) or 0
            processed = getattr(completed, "items_updates_processed", 0) or 0
            if failed:
                errors = getattr(completed, "errors", None) or []
                detail = getattr(errors[0], "error_message", None) if errors else None
                raise RuntimeError(
                    f"Blob knowledge-source ingestion failed for {failed} document(s): {detail}"
                )
            if processed >= expected_documents:
                return processed
        time.sleep(5)
    raise TimeoutError(
        f"Blob knowledge-source ingestion did not finish within {timeout_seconds} seconds"
    )


def setup_foundry_iq(
    *,
    index_client: SearchIndexClient,
    storage_account_id: str,
    container_name: str,
    model_endpoint: str,
    chat_deployment: str,
    embedding_deployment: str,
    expected_documents: int,
    prepare_generated_indexer: Callable[[str, bool], str] | None = None,
    get_index_document_count: Callable[[str], int] | None = None,
    report_progress: Callable[[str], None] | None = None,
) -> dict[str, object]:
    """Reconcile the Blob knowledge source and fully configured knowledge base."""
    progress = report_progress or (lambda _message: None)
    progress("Reconciling Blob knowledge source")
    source_status = ensure_resource(
        get=lambda: index_client.get_knowledge_source(KNOWLEDGE_SOURCE_NAME),
        upsert=index_client.create_or_update_knowledge_source,
        desired=build_knowledge_source(
            storage_account_id=storage_account_id,
            container_name=container_name,
            model_endpoint=model_endpoint,
            embedding_deployment=embedding_deployment,
        ),
    )
    progress(f"Blob knowledge source: {source_status}")
    progress("Reconciling knowledge base")
    base_status = ensure_resource(
        get=lambda: index_client.get_knowledge_base(KNOWLEDGE_BASE_NAME),
        upsert=index_client.create_or_update_knowledge_base,
        desired=build_knowledge_base(
            model_endpoint=model_endpoint,
            chat_deployment=chat_deployment,
        ),
    )
    progress(f"Knowledge base: {base_status}")
    indexer_status = "not configured"
    generated_index_name: str | None = None
    if prepare_generated_indexer is not None:
        progress("Preparing generated indexer")
        source = index_client.get_knowledge_source(KNOWLEDGE_SOURCE_NAME)
        created_resources = source.azure_blob_parameters.created_resources
        generated_index_name = created_resources["index"]
        indexer_status = prepare_generated_indexer(
            created_resources["indexer"],
            source_status != "unchanged",
        )
        progress(f"Generated indexer: {indexer_status}")
    progress("Waiting for Blob ingestion")
    count = (
        (lambda: get_index_document_count(generated_index_name))
        if get_index_document_count is not None and generated_index_name is not None
        else None
    )
    processed = wait_for_knowledge_source(
        index_client,
        expected_documents,
        get_document_count=count,
    )
    progress(f"Blob ingestion: {processed} documents")
    return {
        "knowledge_source": source_status,
        "generated_indexer": indexer_status,
        "knowledge_source_documents": processed,
        "knowledge_base": base_status,
    }
