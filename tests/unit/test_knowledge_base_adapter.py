"""Tests for Blob-backed knowledge-base citation retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from src.infrastructure.search.knowledge_base import AzureBlobKnowledgeBaseAdapter


@dataclass
class Caller:
    user_id: str
    group_claims: tuple[str, ...]


class Client:
    def __init__(self) -> None:
        self.requests: list[object] = []

    def retrieve(self, request: object) -> object:
        self.requests.append(request)
        return SimpleNamespace(
            references=[
                SimpleNamespace(
                    id="ref-1",
                    source_data={
                        "metadata_storage_name": "os-001.pdf",
                        "chunk": "The bonds are payable from an unlimited tax pledge.",
                    },
                )
            ]
        )


async def test_blob_knowledge_adapter_returns_public_citation() -> None:
    client = Client()
    adapter = AzureBlobKnowledgeBaseAdapter(client)

    citations, withheld = await adapter.search("unlimited tax pledge", Caller("user", ()))

    assert withheld == 0
    assert citations[0].document_id == "OS-001"
    assert citations[0].document_title == "os-001.pdf"
    assert citations[0].excerpt == "The bonds are payable from an unlimited tax pledge."
    assert len(client.requests) == 1
