"""Offline contract tests for the Phase 3 Search resource definitions."""

from __future__ import annotations

from src.infrastructure.search.setup import (
    KNOWLEDGE_BASE_NAME,
    KNOWLEDGE_SOURCE_NAME,
    RETRIEVAL_INSTRUCTIONS,
    build_knowledge_base,
    build_knowledge_source,
)


def test_knowledge_artifacts_use_blob_pdfs_and_model_backed_retrieval() -> None:
    source = build_knowledge_source(
        storage_account_id="/subscriptions/test/resourceGroups/test/providers/"
        "Microsoft.Storage/storageAccounts/test",
        container_name="corpus",
        model_endpoint="https://example.openai.azure.com",
        embedding_deployment="text-embedding-3-large",
    )
    knowledge_base = build_knowledge_base(
        model_endpoint="https://example.openai.azure.com",
        chat_deployment="gpt-5.4-mini",
    )

    assert source.name == KNOWLEDGE_SOURCE_NAME
    assert source.kind == "azureBlob"
    assert source.azure_blob_parameters.container_name == "corpus"
    assert source.azure_blob_parameters.folder_path == "pdf/public"
    ingestion = source.azure_blob_parameters.ingestion_parameters
    assert ingestion.chat_completion_model is None
    assert ingestion.embedding_model.azure_open_ai_parameters.deployment_name == (
        "text-embedding-3-large"
    )
    assert knowledge_base.name == KNOWLEDGE_BASE_NAME
    assert [item.name for item in knowledge_base.knowledge_sources] == [KNOWLEDGE_SOURCE_NAME]
    assert knowledge_base.description
    assert knowledge_base.models[0].azure_open_ai_parameters.deployment_name == "gpt-5.4-mini"
    assert knowledge_base.retrieval_reasoning_effort.kind == "low"
    assert knowledge_base.output_mode == "extractiveData"
    assert knowledge_base.retrieval_instructions == RETRIEVAL_INSTRUCTIONS
