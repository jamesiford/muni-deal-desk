"""Upload the public synthetic corpus from a private Azure container instance."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from azure.identity import ManagedIdentityCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

CORPUS_ROOT = Path("/corpus")
PREFIX = "pdf/public/"


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> None:
    """Upload public PDFs and remove stale public-corpus blobs."""
    manifest_path = CORPUS_ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    public_documents = [
        document for document in manifest["documents"] if document["sensitivity"] == "public"
    ]
    credential = ManagedIdentityCredential(client_id=_required("AZURE_CLIENT_ID"))
    service = BlobServiceClient(
        account_url=_required("AZURE_STORAGE_BLOB_ENDPOINT"),
        credential=credential,
    )
    container = service.get_container_client(_required("AZURE_STORAGE_CORPUS_CONTAINER"))

    expected_names: set[str] = set()
    for document in public_documents:
        source = CORPUS_ROOT / document["blob_path"]
        content = source.read_bytes()
        blob_name = f"{PREFIX}{source.name}"
        expected_names.add(blob_name)
        container.upload_blob(
            name=blob_name,
            data=content,
            overwrite=True,
            metadata={
                "source_sha256": hashlib.sha256(content).hexdigest(),
                "document_id": document["document_id"],
                "document_title": document["title"],
                "sensitivity": "public",
            },
            content_settings=ContentSettings(content_type="application/pdf"),
        )
        print(f"uploaded {blob_name}", flush=True)

    for blob in container.list_blobs(name_starts_with=PREFIX):
        if blob.name not in expected_names:
            container.delete_blob(blob.name)
            print(f"deleted stale {blob.name}", flush=True)

    container.upload_blob(
        name="manifest.json",
        data=manifest_path.read_bytes(),
        overwrite=True,
        content_settings=ContentSettings(content_type="application/json"),
    )
    print(f"uploaded {len(expected_names)} public PDFs", flush=True)


if __name__ == "__main__":
    main()
