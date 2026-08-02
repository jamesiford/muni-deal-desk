"""Prompt specialist definition and idempotency tests."""

from __future__ import annotations

from types import SimpleNamespace

from azure.core.exceptions import ResourceNotFoundError
from src.domain.contracts.agent_contracts import (
    AnalystAssessment,
    ComplianceReview,
    ResearchFindings,
)
from src.infrastructure.foundry.specialists import (
    DEFINITION_HASH_KEY,
    build_specialist_specs,
    definition_hash,
    ensure_specialist,
)


class Operations:
    def __init__(self, latest: object | None = None) -> None:
        self.latest = latest
        self.created: list[dict[str, object]] = []

    def get(self, _agent_name: str) -> object:
        if self.latest is None:
            raise ResourceNotFoundError("missing")
        return SimpleNamespace(versions=SimpleNamespace(latest=self.latest))

    def create_version(self, agent_name: str, **kwargs: object) -> object:
        self.created.append({"agent_name": agent_name, **kwargs})
        return SimpleNamespace(version="1", metadata=kwargs["metadata"])


def _specs():
    return build_specialist_specs(
        mcp_endpoint="https://example.test/mcp",
        mcp_connection_name="mcp-connection",
        knowledge_base_endpoint=(
            "https://search.example/knowledgebases/municipal-deal-knowledge-base/"
            "mcp?api-version=2026-05-01-preview"
        ),
        knowledge_base_connection_name="foundry-iq-connection",
        extraction_model="gpt-5.4-mini",
        reasoning_model="gpt-5.5",
    )


def test_specialists_use_models_tools_and_structured_contracts() -> None:
    research, analyst, compliance = _specs()

    assert research.response_model is ResearchFindings
    assert research.definition.model == "gpt-5.4-mini"
    assert research.definition.tools[0].server_label == "municipal-deal-desk"
    assert research.definition.tools[0].allowed_tools == ["find_comparable_deals"]
    assert research.definition.tools[1].server_label == "foundry-iq-public-documents"
    assert research.definition.tools[1].allowed_tools == ["knowledge_base_retrieve"]
    assert research.definition.tools[1].project_connection_id == "foundry-iq-connection"
    research_schema = research.definition.text.format.schema
    assert research_schema["additionalProperties"] is False
    assert research_schema["required"] == list(research_schema["properties"])
    assert research_schema["$defs"]["Deal"]["additionalProperties"] is False
    schema_text = str(research_schema)
    assert "pattern" not in schema_text
    par_amount_schema = research_schema["$defs"]["Deal"]["properties"]["par_amount"]
    assert par_amount_schema == {"title": "Par Amount", "type": "number"}

    assert analyst.response_model is AnalystAssessment
    assert analyst.definition.model == "gpt-5.5"
    assert analyst.definition.tools[0].allowed_tools == ["get_deal", "compute_debt_service"]

    assert compliance.response_model is ComplianceReview
    assert compliance.definition.model == "gpt-5.4-mini"
    assert compliance.definition.tools is None


def test_registration_creates_when_agent_is_missing() -> None:
    operations = Operations()
    spec = _specs()[0]

    status, version = ensure_specialist(operations, spec)

    assert status == "created"
    assert version.version == "1"
    assert operations.created[0]["metadata"] == {
        DEFINITION_HASH_KEY: definition_hash(spec.definition)
    }


def test_registration_skips_matching_latest_version() -> None:
    spec = _specs()[0]
    latest = SimpleNamespace(
        version="7",
        metadata={DEFINITION_HASH_KEY: definition_hash(spec.definition)},
    )
    operations = Operations(latest)

    status, version = ensure_specialist(operations, spec)

    assert status == "unchanged"
    assert version is latest
    assert operations.created == []
