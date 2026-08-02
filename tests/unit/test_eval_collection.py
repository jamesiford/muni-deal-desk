"""Tests for Phase 7 case routing and collection mapping."""

from __future__ import annotations

import evals.collection as collection_module
from evals.cases import ContractName, build_cases
from evals.collection import (
    CloudCaseCollector,
    CollectionTarget,
    ModelConfiguration,
    SpecialistEndpoints,
    TargetResult,
    collect_configuration,
    deterministic_response,
    target_for_case,
    temporary_research_agents,
)


class _FakeCollector:
    def __init__(self) -> None:
        self.calls: list[tuple[str, CollectionTarget, str]] = []

    async def collect(self, case, target, configuration):
        self.calls.append((case.case_id, target, configuration.name))
        return TargetResult(response=deterministic_response(case), latency_ms=1.0)


class _FailingCollector:
    async def collect(self, case, target, configuration):
        del case, target, configuration
        raise RuntimeError("remote target unavailable")


class _Version:
    version = "1"


class _FakeAgentOperations:
    def __init__(self) -> None:
        self.created = []
        self.deleted: list[str] = []

    def create_version(self, agent_name, **kwargs):
        self.created.append((agent_name, kwargs["definition"]))
        return _Version()

    def delete(self, agent_name):
        self.deleted.append(agent_name)
        return None


async def test_collection_maps_all_25_cases_once_in_dataset_order() -> None:
    cases = build_cases()
    collector = _FakeCollector()

    outputs = await collect_configuration(
        cases,
        ModelConfiguration(name="mini", model="gpt-5.4-mini"),
        collector,
    )

    assert [output.case_id for output in outputs] == [case.case_id for case in cases]
    assert len(collector.calls) == 25
    assert all(configuration == "mini" for _, _, configuration in collector.calls)


async def test_collection_records_remote_failure_and_continues() -> None:
    cases = build_cases()[:2]

    outputs = await collect_configuration(
        cases,
        ModelConfiguration(name="mini", model="gpt-5.4-mini"),
        _FailingCollector(),
    )

    assert len(outputs) == 2
    assert outputs[0].response == {
        "collection_error": "RuntimeError",
        "detail": "remote target unavailable",
    }


def test_contracts_route_to_their_owning_execution_surface() -> None:
    cases = build_cases()
    targets = {case.case_id: target_for_case(case) for case in cases}

    assert targets["debt-service-deal-subject-001"] is CollectionTarget.MCP
    assert targets["entitlement-public-withholding"] is CollectionTarget.MCP
    assert targets["guardrail-fiduciary-implication"] is CollectionTarget.DETERMINISTIC_DOMAIN
    assert targets["comparable-subject-band"] is CollectionTarget.RESEARCH_AGENT
    private_case = next(
        case
        for case in cases
        if case.expected.contract is ContractName.RESEARCH_FINDINGS
        and case.expected.required_source_document_ids
    )
    assert target_for_case(private_case) is CollectionTarget.DETERMINISTIC_DOMAIN


def test_temporary_agents_change_only_model_and_are_deleted() -> None:
    operations = _FakeAgentOperations()
    configurations = [
        ModelConfiguration(name="mini", model="gpt-5.4-mini"),
        ModelConfiguration(name="reasoning", model="gpt-5.5"),
    ]

    with temporary_research_agents(
        operations,
        endpoints=SpecialistEndpoints(
            mcp_endpoint="https://mcp.example/mcp",
            knowledge_base_endpoint="https://search.example/knowledgebases/kb/mcp",
        ),
        configurations=configurations,
        suffix="test",
    ) as bindings:
        assert set(bindings) == {"mini", "reasoning"}

    mini_definition = dict(operations.created[0][1])
    reasoning_definition = dict(operations.created[1][1])
    assert mini_definition.pop("model") == "gpt-5.4-mini"
    assert reasoning_definition.pop("model") == "gpt-5.5"
    assert mini_definition == reasoning_definition
    assert operations.deleted == [
        "municipal-deal-research-eval-reasoning-test",
        "municipal-deal-research-eval-mini-test",
    ]


async def test_exact_match_preserves_zero_tolerance_at_mcp_boundary(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_call(_endpoint, _tool_name, arguments):
        captured.update(arguments)
        return TargetResult(
            response={"comparables": [], "evidence_sources": []},
            latency_ms=1.0,
        )

    monkeypatch.setattr(collection_module, "_call_mcp", fake_call)
    case = next(case for case in build_cases() if case.case_id == "comparable-exact-45m")
    collector = CloudCaseCollector(None, "https://mcp.example/mcp", {})

    await collector._collect_mcp(case)

    assert captured["par_tolerance_pct"] == "0"
