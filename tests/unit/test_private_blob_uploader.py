"""Tests for private corpus upload role-propagation handling."""

from __future__ import annotations

from azure.core.exceptions import HttpResponseError
from scripts.private_blob_uploader import upload


def test_retries_role_propagation_error(monkeypatch) -> None:
    attempts = 0
    monkeypatch.setattr(upload.time, "sleep", lambda _seconds: None)

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise HttpResponseError(message="not active\nErrorCode:AuthorizationPermissionMismatch")
        return "uploaded"

    assert upload._after_role_propagation(operation) == "uploaded"
    assert attempts == 3


def test_does_not_retry_unrelated_storage_error(monkeypatch) -> None:
    monkeypatch.setattr(upload.time, "sleep", lambda _seconds: None)

    def operation() -> None:
        raise HttpResponseError(message="bad request\nErrorCode:InvalidBlobName")

    try:
        upload._after_role_propagation(operation)
    except HttpResponseError as exc:
        assert upload._error_code(exc) == "InvalidBlobName"
    else:
        raise AssertionError("Unrelated storage error was swallowed.")
