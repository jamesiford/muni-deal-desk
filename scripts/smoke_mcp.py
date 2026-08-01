"""List tools from a deployed streamable HTTP MCP endpoint."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from src.corpus.manifest import CorpusManifest
from src.domain.entities.deal import DebtServiceSchedule
from src.infrastructure.calculators import DebtServiceCalculator

EXPECTED_TOOLS = {"compute_debt_service", "find_comparable_deals", "get_deal"}


def expected_schedule(manifest_path: Path, deal_id: str) -> DebtServiceSchedule:
    """Compute the expected schedule from synthetic corpus ground truth."""
    manifest = CorpusManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    deal = next(
        (
            document.expected_deal
            for document in manifest.documents
            if document.expected_deal is not None and document.expected_deal.deal_id == deal_id
        ),
        None,
    )
    if deal is None:
        raise RuntimeError(f"Synthetic manifest has no deal {deal_id}.")
    return DebtServiceCalculator().compute_debt_service(deal)


def validate_schedule(actual: dict[str, object], expected: DebtServiceSchedule) -> None:
    """Require the deployed structured output to match deterministic arithmetic."""
    deployed = DebtServiceSchedule.model_validate(actual)
    if deployed != expected:
        raise RuntimeError(
            "Deployed debt service did not match the calculator: "
            f"expected principal={expected.total_principal}, interest={expected.total_interest}; "
            f"received principal={deployed.total_principal}, interest={deployed.total_interest}."
        )


async def verify(endpoint: str, manifest_path: Path, deal_id: str) -> None:
    """Verify the Phase 4 tool surface and deterministic deployed calculation."""
    async with (
        streamable_http_client(endpoint) as (read, write, _session_id),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        calculation = await session.call_tool(
            "compute_debt_service",
            {
                "deal_id": deal_id,
                "caller_user_id": "phase-four-smoke",
                "caller_group_claims": [],
            },
        )

    names = {tool.name for tool in tools.tools}
    missing = EXPECTED_TOOLS - names
    if missing:
        raise RuntimeError(f"MCP endpoint is missing tools: {', '.join(sorted(missing))}")
    if calculation.isError or calculation.structuredContent is None:
        raise RuntimeError("Deployed compute_debt_service call did not return structured output.")

    expected = expected_schedule(manifest_path, deal_id)
    validate_schedule(calculation.structuredContent, expected)
    print("MCP tools: " + ", ".join(sorted(names)))
    print(
        f"Debt service {deal_id}: principal={expected.total_principal}, "
        f"interest={expected.total_interest}"
    )


def main() -> None:
    """Parse the endpoint and run the protocol check."""
    parser = argparse.ArgumentParser()
    parser.add_argument("endpoint")
    parser.add_argument("--deal-id", default="DEAL-001")
    parser.add_argument("--manifest", type=Path, default=Path("src/corpus/out/manifest.json"))
    args = parser.parse_args()
    asyncio.run(verify(args.endpoint, args.manifest, args.deal_id))


if __name__ == "__main__":
    main()
