"""Foundry IQ knowledge-base adapter for cited public-document retrieval."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Protocol

from azure.search.documents.knowledgebases.models import (
    AzureBlobKnowledgeSourceParams,
    KnowledgeBaseMessage,
    KnowledgeBaseMessageTextContent,
    KnowledgeBaseRetrievalRequest,
)

from src.application.ports import CallerContext
from src.domain.entities.citation import Citation

from .constants import KNOWLEDGE_SOURCE_NAME


class KnowledgeBaseClientProtocol(Protocol):
    """Narrow synchronous knowledge-base retrieval surface."""

    def retrieve(self, request: KnowledgeBaseRetrievalRequest) -> object:
        """Execute one retrieval request."""
        ...


def _first_string(value: object, names: tuple[str, ...]) -> str | None:
    if isinstance(value, Mapping):
        for name in names:
            item = value.get(name)
            if isinstance(item, str) and item.strip():
                return item
        for item in value.values():
            found = _first_string(item, names)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _first_string(item, names)
            if found:
                return found
    return None


class AzureBlobKnowledgeBaseAdapter:
    """Retrieve public citations from the configured Blob-backed knowledge base."""

    def __init__(self, client: KnowledgeBaseClientProtocol) -> None:
        self._client = client

    async def search(
        self,
        query: str,
        caller: CallerContext,
        *,
        top: int = 10,
    ) -> tuple[list[Citation], int]:
        """Return cited public passages; private sources are outside this knowledge base."""
        del caller, top
        return await asyncio.to_thread(self._search, query)

    def _search(self, query: str) -> tuple[list[Citation], int]:
        response = self._client.retrieve(
            KnowledgeBaseRetrievalRequest(
                messages=[
                    KnowledgeBaseMessage(
                        role="user",
                        content=[KnowledgeBaseMessageTextContent(text=query)],
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
        references = getattr(response, "references", None) or []
        citations: list[Citation] = []
        for reference in references:
            source = getattr(reference, "source_data", None) or {}
            path = _first_string(source, ("metadata_storage_path", "url", "path", "source"))
            title = _first_string(
                source,
                ("metadata_storage_name", "document_title", "title", "name"),
            )
            excerpt = _first_string(source, ("chunk", "content", "text", "merged_content"))
            reference_id = str(getattr(reference, "id", "blob-reference"))
            document_name = title or (path.rsplit("/", 1)[-1] if path else reference_id)
            document_id = document_name.rsplit(".", 1)[0].upper()
            citations.append(
                Citation(
                    document_id=document_id,
                    document_title=document_name,
                    excerpt=excerpt or reference_id,
                )
            )
        return citations, 0
