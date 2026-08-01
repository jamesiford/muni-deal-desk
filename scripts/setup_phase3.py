"""Create and validate Phase 3 data-plane artifacts using Microsoft Entra auth."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Callable
from pathlib import Path
from urllib.request import Request, urlopen

from azure.ai.contentunderstanding import ContentUnderstandingClient
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.knowledgebases import KnowledgeBaseRetrievalClient
from azure.search.documents.knowledgebases.models import (
    AzureBlobKnowledgeSourceParams,
    KnowledgeBaseMessage,
    KnowledgeBaseMessageTextContent,
    KnowledgeBaseRetrievalRequest,
)
from src.corpus.manifest import CorpusManifest
from src.infrastructure.content_understanding import (
    ANALYZER_ID,
    ContentUnderstandingDealExtractor,
    build_deal_analyzer,
    ensure_deal_analyzer,
    ensure_model_defaults,
)
from src.infrastructure.search.constants import API_VERSION
from src.infrastructure.search.setup import (
    KNOWLEDGE_BASE_NAME,
    KNOWLEDGE_SOURCE_NAME,
    setup_foundry_iq,
)


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _model_endpoint(account_name: str) -> str:
    return f"https://{account_name}.openai.azure.com"


def _load_manifest(path: Path) -> CorpusManifest:
    return CorpusManifest.model_validate_json(path.read_text(encoding="utf-8"))


def _private_indexer_preparer(
    endpoint: str,
    credential: DefaultAzureCredential,
) -> Callable[[str, bool], str]:
    """Preserve the generated indexer while forcing shared-private-link execution."""
    token = credential.get_token("https://search.azure.com/.default").token

    def send(method: str, url: str, body: dict[str, object] | None = None) -> object:
        data = json.dumps(body).encode() if body is not None else None
        request = Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        with urlopen(request, timeout=60) as response:
            content = response.read()
        return json.loads(content) if content else None

    def prepare(indexer_name: str, source_changed: bool) -> str:
        uri = f"{endpoint.rstrip('/')}/indexers/{indexer_name}?api-version=2025-09-01"
        indexer = send("GET", uri)
        if not isinstance(indexer, dict):
            raise RuntimeError("Generated Blob indexer definition was not an object")
        configuration = indexer.setdefault("parameters", {}).setdefault("configuration", {})
        changed = configuration.get("executionEnvironment") != "private"
        if changed:
            configuration["executionEnvironment"] = "private"
            indexer.pop("@odata.context", None)
            send("PUT", uri, indexer)
        if changed or source_changed:
            send(
                "POST",
                f"{endpoint.rstrip('/')}/indexers/{indexer_name}/reset?api-version=2025-09-01",
            )
            send(
                "POST",
                f"{endpoint.rstrip('/')}/indexers/{indexer_name}/run?api-version=2025-09-01",
            )
        return "updated" if changed else "unchanged"

    return prepare


async def _validate_content_understanding(
    client: ContentUnderstandingClient,
    manifest: CorpusManifest,
    corpus_root: Path,
) -> int:
    entries = {entry.document_id: entry for entry in manifest.documents}
    extractor = ContentUnderstandingDealExtractor(
        client,
        lambda document_id: (corpus_root / entries[document_id].blob_path).read_bytes(),
        lambda document_id: {
            "deal_id": entries[document_id].expected_deal.deal_id,
            "issuer": {
                "issuer_id": entries[document_id].expected_deal.issuer.issuer_id,
            },
            "sensitivity": entries[document_id].sensitivity,
        },
    )
    mismatches: list[str] = []
    for entry in manifest.documents:
        try:
            extracted = await extractor.extract_deal(entry.document_id)
        except Exception as exc:
            raise RuntimeError(
                f"Content Understanding could not map {entry.document_id}: {exc}"
            ) from exc
        if extracted != entry.expected_deal:
            expected = (
                entry.expected_deal.model_dump(mode="json")
                if entry.expected_deal is not None
                else None
            )
            actual = extracted.model_dump(mode="json") if extracted is not None else None
            differing_fields = sorted(
                name
                for name in set(expected or {}) | set(actual or {})
                if (expected or {}).get(name) != (actual or {}).get(name)
            )
            mismatches.append(f"{entry.document_id} ({', '.join(differing_fields)})")

    if mismatches:
        raise RuntimeError(
            "Content Understanding extraction did not match the manifest for: "
            + ", ".join(mismatches)
        )
    return len(manifest.documents)


def _validate_knowledge_base(
    endpoint: str,
    credential: DefaultAzureCredential,
    index_client: SearchIndexClient,
) -> int:
    knowledge_source = index_client.get_knowledge_source(KNOWLEDGE_SOURCE_NAME)
    if knowledge_source.kind != "azureBlob":
        raise RuntimeError(
            f"Knowledge source kind is {knowledge_source.kind!r}, expected 'azureBlob'"
        )
    knowledge_base = index_client.get_knowledge_base(KNOWLEDGE_BASE_NAME)
    if not knowledge_base.models:
        raise RuntimeError("Knowledge base has no chat completions model")
    if knowledge_base.retrieval_reasoning_effort.kind != "low":
        raise RuntimeError("Knowledge base retrieval reasoning effort is not low")
    if knowledge_base.output_mode != "extractiveData":
        raise RuntimeError("Knowledge base output mode is not extractive data")
    if not knowledge_base.retrieval_instructions:
        raise RuntimeError("Knowledge base retrieval instructions are empty")

    client = KnowledgeBaseRetrievalClient(
        endpoint=endpoint,
        knowledge_base_name=KNOWLEDGE_BASE_NAME,
        credential=credential,
        api_version=API_VERSION,
    )
    response = client.retrieve(
        KnowledgeBaseRetrievalRequest(
            messages=[
                KnowledgeBaseMessage(
                    role="user",
                    content=[
                        KnowledgeBaseMessageTextContent(
                            text=(
                                "Which fictional school district issues have an unlimited "
                                "tax pledge?"
                            )
                        )
                    ],
                )
            ],
            include_activity=True,
            knowledge_source_params=[
                AzureBlobKnowledgeSourceParams(
                    knowledge_source_name=KNOWLEDGE_SOURCE_NAME,
                    include_references=True,
                    include_reference_source_data=True,
                )
            ],
        )
    )
    references = response.references or []
    if not references:
        raise RuntimeError("Knowledge base returned no cited references")
    return len(references)


def main() -> int:
    """Reconcile analyzer, Search pipeline and Foundry IQ knowledge base."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("src/corpus/out/manifest.json"),
    )
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=Path("src/corpus/out"),
    )
    parser.add_argument(
        "--validate-content-understanding",
        action="store_true",
        help="Analyze every local PDF and compare cloud output to the manifest.",
    )
    args = parser.parse_args()

    account_endpoint = _required("AZURE_AI_ACCOUNT_ENDPOINT")
    account_name = _required("AZURE_AI_ACCOUNT_NAME")
    embedding_deployment = _required("AZURE_AI_EMBEDDING_DEPLOYMENT")
    extraction_deployment = _required("AZURE_AI_EXTRACTION_DEPLOYMENT")
    search_endpoint = _required("AZURE_SEARCH_ENDPOINT")
    credential = DefaultAzureCredential()
    manifest = _load_manifest(args.manifest)

    analyzer_client = ContentUnderstandingClient(
        endpoint=account_endpoint,
        credential=credential,
    )
    defaults_status = ensure_model_defaults(
        analyzer_client,
        {
            extraction_deployment: extraction_deployment,
            "text-embedding-3-large": embedding_deployment,
        },
    )
    print(f"Content Understanding model defaults: {defaults_status}")
    analyzer_status = ensure_deal_analyzer(
        analyzer_client,
        build_deal_analyzer(
            completion_model=extraction_deployment,
            embedding_model=embedding_deployment,
        ),
    )
    print(f"Content Understanding analyzer {ANALYZER_ID}: {analyzer_status}")

    if args.validate_content_understanding:
        extracted_count = asyncio.run(
            _validate_content_understanding(
                analyzer_client,
                manifest,
                args.corpus_root,
            )
        )
        print(f"Content Understanding validation: {extracted_count} documents matched")

    index_client = SearchIndexClient(
        endpoint=search_endpoint,
        credential=credential,
        api_version=API_VERSION,
    )
    model_endpoint = _model_endpoint(account_name)
    storage_account_id = (
        f"/subscriptions/{_required('AZURE_SUBSCRIPTION_ID')}"
        f"/resourceGroups/{_required('AZURE_RESOURCE_GROUP')}"
        f"/providers/Microsoft.Storage/storageAccounts/"
        f"{_required('AZURE_STORAGE_ACCOUNT_NAME')}"
    )
    resources = setup_foundry_iq(
        index_client=index_client,
        storage_account_id=storage_account_id,
        container_name=_required("AZURE_STORAGE_CORPUS_CONTAINER"),
        model_endpoint=model_endpoint,
        chat_deployment=extraction_deployment,
        embedding_deployment=embedding_deployment,
        expected_documents=sum(
            not document.allowed_group_claims for document in manifest.documents
        ),
        prepare_generated_indexer=_private_indexer_preparer(search_endpoint, credential),
    )
    for name, status in resources.items():
        print(f"Search {name}: {status}")

    reference_count = _validate_knowledge_base(search_endpoint, credential, index_client)
    print(f"Knowledge base validation: {reference_count} cited references")
    if not args.validate_content_understanding:
        print("Content Understanding extraction validation: skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
