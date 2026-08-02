"""Verify Foundry evaluation storage and remove the temporary smoke artifacts."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from evals.foundry import (
    PortalEvaluationArtifacts,
    PortalEvaluationRow,
    create_portal_evaluation,
    wait_for_portal_evaluation,
)


def _row(case_id: str) -> PortalEvaluationRow:
    return PortalEvaluationRow(
        case_id=case_id,
        category="network_smoke",
        configuration="network-smoke",
        question="Confirm the pre-collected evaluation response is available.",
        expected_behavior="Return a structured ready status.",
        deterministic_pass=True,
        response={"status": "ready", "case_id": case_id},
    )


def _cleanup(client: object, artifacts: PortalEvaluationArtifacts | None) -> None:
    if artifacts is None:
        return
    client.evals.delete(artifacts.eval_id)
    for file_id in artifacts.data_file_ids.values():
        client.files.delete(file_id)


def main() -> None:
    """Create, verify, and remove a two-row Foundry evaluation."""
    endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
    if not endpoint:
        raise RuntimeError("AZURE_AI_PROJECT_ENDPOINT is required.")

    credential = DefaultAzureCredential()
    project = AIProjectClient(endpoint, credential)
    artifacts: PortalEvaluationArtifacts | None = None
    try:
        client = project.get_openai_client()
        artifacts = create_portal_evaluation(
            client,
            definition_name=f"muni-deal-desk-network-smoke-{datetime.now(UTC):%Y%m%dT%H%M%SZ}",
            runs={"network-smoke": [_row("network-smoke-1"), _row("network-smoke-2")]},
        )
        artifacts = wait_for_portal_evaluation(
            client,
            artifacts,
            timeout_seconds=600,
            poll_interval_seconds=5,
        )
        result = artifacts.run_results["network-smoke"]
        if result.status != "completed" or result.total != 2:
            raise RuntimeError(
                "Foundry evaluation storage failed: "
                f"status={result.status}, total={result.total}, "
                f"error={result.error_code}: {result.error_message}"
            )
        print("  ok    Foundry evaluation processed 2 private-storage rows")
    finally:
        if "client" in locals():
            _cleanup(client, artifacts)
        project.close()
        credential.close()


if __name__ == "__main__":
    main()
