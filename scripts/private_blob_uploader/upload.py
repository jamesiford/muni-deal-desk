"""Upload the public synthetic corpus from a private Azure container instance."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from pathlib import Path

from azure.core.exceptions import HttpResponseError
from azure.identity import ManagedIdentityCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

CORPUS_ROOT = Path("/corpus")
PREFIX = "pdf/public/"
MAX_AUTHORIZATION_ATTEMPTS = 12
AUTHORIZATION_RETRY_SECONDS = 15


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _error_code(exc: HttpResponseError) -> str | None:
    error = getattr(exc, "error", None)
    code = getattr(error, "code", None) or getattr(error, "error_code", None)
    if isinstance(code, str):
        return code
    marker = "ErrorCode:"
    if marker in str(exc):
        return str(exc).split(marker, 1)[1].splitlines()[0].strip()
    return None


def _after_role_propagation[TResult](operation: Callable[[], TResult]) -> TResult:
    """Retry only the transient 403 emitted while a new role assignment propagates."""
    for attempt in range(1, MAX_AUTHORIZATION_ATTEMPTS + 1):
        try:
            return operation()
        except HttpResponseError as exc:
            if _error_code(exc) != "AuthorizationPermissionMismatch":
                raise
            if attempt == MAX_AUTHORIZATION_ATTEMPTS:
                raise
            print(
                f"storage role not active; retrying ({attempt}/{MAX_AUTHORIZATION_ATTEMPTS})",
                flush=True,
            )
            time.sleep(AUTHORIZATION_RETRY_SECONDS)
    raise RuntimeError("Authorization retry loop ended unexpectedly.")


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
        metadata = {
            "source_sha256": hashlib.sha256(content).hexdigest(),
            "document_id": document["document_id"],
            "document_title": document["title"],
            "sensitivity": "public",
        }
        _after_role_propagation(
            lambda blob_name=blob_name, content=content, metadata=metadata: container.upload_blob(
                name=blob_name,
                data=content,
                overwrite=True,
                metadata=metadata,
                content_settings=ContentSettings(content_type="application/pdf"),
            )
        )
        print(f"uploaded {blob_name}", flush=True)

    inventory: list[dict[str, object]] = []
    for blob in container.list_blobs(name_starts_with=PREFIX, include=["metadata"]):
        if blob.name not in expected_names:
            container.delete_blob(blob.name)
            print(f"deleted stale {blob.name}", flush=True)
            continue
        metadata = blob.metadata or {}
        inventory.append(
            {
                "blob_path": blob.name,
                "document_id": metadata.get("document_id"),
                "content_length": blob.size,
                "source_sha256": metadata.get("source_sha256"),
            }
        )

    container.upload_blob(
        name="manifest.json",
        data=manifest_path.read_bytes(),
        overwrite=True,
        content_settings=ContentSettings(content_type="application/json"),
    )
    print(f"uploaded {len(expected_names)} public PDFs", flush=True)
    receipt = {
        "container": container.container_name,
        "prefix": PREFIX,
        "document_count": len(inventory),
        "documents": sorted(inventory, key=lambda item: str(item["blob_path"])),
    }
    print(f"CORPUS_INVENTORY={json.dumps(receipt, separators=(',', ':'))}", flush=True)


if __name__ == "__main__":
    main()
