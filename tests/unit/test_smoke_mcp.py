"""Deterministic deployed MCP smoke-check tests."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from scripts.smoke_mcp import expected_schedule, validate_schedule


def test_manifest_schedule_matches_calculator_values() -> None:
    schedule = expected_schedule(Path("src/corpus/out/manifest.json"), "DEAL-001")

    assert schedule.total_principal == Decimal("30000000.00")
    assert schedule.total_interest == Decimal("7672500.00")


def test_deployed_schedule_mismatch_fails_honestly() -> None:
    expected = expected_schedule(Path("src/corpus/out/manifest.json"), "DEAL-001")
    actual = expected.model_dump(mode="json")
    actual["total_interest"] = "0.00"

    with pytest.raises(RuntimeError, match="did not match the calculator"):
        validate_schedule(actual, expected)
