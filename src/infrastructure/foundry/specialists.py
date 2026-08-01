"""Durable prompt-agent definitions and idempotent registration."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Protocol

from azure.ai.projects.models import (
    MCPTool,
    PromptAgentDefinition,
    PromptAgentDefinitionTextOptions,
    TextResponseFormatJsonSchema,
)
from azure.core.exceptions import ResourceNotFoundError
from pydantic import BaseModel

from src.domain.contracts.agent_contracts import (
    AnalystAssessment,
    ComplianceReview,
    ResearchFindings,
)

DEFINITION_HASH_KEY = "definition_sha256"


@dataclass(frozen=True, slots=True)
class SpecialistSpec:
    """One versioned specialist and its standalone smoke-test contract."""

    name: str
    description: str
    response_model: type[BaseModel]
    definition: PromptAgentDefinition
    smoke_prompt: str


class AgentOperationsProtocol(Protocol):
    """Narrow Azure AI Projects agent-version surface."""

    def get(self, agent_name: str) -> object:
        """Get an agent and its latest version."""
        ...

    def create_version(
        self,
        agent_name: str,
        *,
        definition: PromptAgentDefinition,
        metadata: dict[str, str],
        description: str,
    ) -> object:
        """Create an immutable agent version."""
        ...


def _response_options(model: type[BaseModel]) -> PromptAgentDefinitionTextOptions:
    schema = deepcopy(model.model_json_schema(mode="serialization"))

    def close_objects(value: object) -> None:
        if isinstance(value, dict):
            value.pop("default", None)
            properties = value.get("properties")
            if isinstance(properties, dict):
                value["additionalProperties"] = False
                value["required"] = list(properties)
            for item in value.values():
                close_objects(item)
        elif isinstance(value, list):
            for item in value:
                close_objects(item)

    close_objects(schema)
    return PromptAgentDefinitionTextOptions(
        format=TextResponseFormatJsonSchema(
            name=model.__name__,
            description=model.__doc__,
            schema=schema,
            strict=True,
        )
    )


def _mcp_tool(
    label: str,
    endpoint: str,
    connection_name: str,
    tools: list[str],
) -> MCPTool:
    return MCPTool(
        server_label=label,
        server_url=endpoint,
        require_approval="never",
        allowed_tools=tools,
        project_connection_id=connection_name,
    )


def build_specialist_specs(
    *,
    mcp_endpoint: str,
    mcp_connection_name: str,
    knowledge_base_endpoint: str,
    knowledge_base_connection_name: str,
    extraction_model: str,
    reasoning_model: str,
) -> tuple[SpecialistSpec, ...]:
    """Build the three projector-readable specialist definitions."""
    public_tool_rule = (
        "When calling a tool, set caller_user_id to 'foundry-playground' and "
        "caller_group_claims to an empty list. Never claim private-side access."
    )
    research = SpecialistSpec(
        name="municipal-deal-research",
        description="Finds cited public municipal comparables and reports evidence gaps.",
        response_model=ResearchFindings,
        definition=PromptAgentDefinition(
            model=extraction_model,
            instructions=(
                "You are the Research specialist for a municipal new-issue desk. Always call "
                "find_comparable_deals for the deterministic candidate set and permission "
                "count. Always call knowledge_base_retrieve for supporting public-document "
                "passages and citations. Never answer from your own knowledge. Preserve "
                "verbatim citations and report missing evidence as gaps. Do not interpret "
                "pricing, calculate debt service, invent missing terms, or give legal advice. "
                f"{public_tool_rule}"
            ),
            tools=[
                _mcp_tool(
                    "municipal-deal-desk",
                    mcp_endpoint,
                    mcp_connection_name,
                    ["find_comparable_deals"],
                ),
                _mcp_tool(
                    "foundry-iq-public-documents",
                    knowledge_base_endpoint,
                    knowledge_base_connection_name,
                    ["knowledge_base_retrieve"],
                ),
            ],
            text=_response_options(ResearchFindings),
        ),
        smoke_prompt=(
            "Find up to three Texas unlimited-tax comparables near $85 million from the last "
            "18 months. Use a 100 percent par tolerance and return the structured findings."
        ),
    )
    analyst = SpecialistSpec(
        name="municipal-deal-analyst",
        description="Assesses municipal structures using deterministic tool output.",
        response_model=AnalystAssessment,
        definition=PromptAgentDefinition(
            model=reasoning_model,
            instructions=(
                "You are the Analyst specialist for a municipal new-issue desk. Use get_deal "
                "and compute_debt_service before discussing a figure. Explain structural "
                "differences and pricing observations, but do not manufacture yields, legal "
                f"conclusions, or recommendations. {public_tool_rule}"
            ),
            tools=[
                _mcp_tool(
                    "municipal-deal-desk",
                    mcp_endpoint,
                    mcp_connection_name,
                    ["get_deal", "compute_debt_service"],
                )
            ],
            text=_response_options(AnalystAssessment),
        ),
        smoke_prompt=(
            "Assess public deal DEAL-001. Use get_deal and compute_debt_service, then return a "
            "structured assessment. Empty citation and gap lists are acceptable for this "
            "smoke test."
        ),
    )
    compliance = SpecialistSpec(
        name="municipal-deal-compliance",
        description="Reviews draft language and records non-legal-advice conduct findings.",
        response_model=ComplianceReview,
        definition=PromptAgentDefinition(
            model=extraction_model,
            instructions=(
                "You are the Compliance specialist for a municipal underwriting desk. Review "
                "draft language for fiduciary implications, investor recommendations, uncited "
                "figures, and required human review. Findings are modelled controls, not legal "
                "advice. Set blocking true for language that must not be returned. Always set "
                "requires_human_review true."
            ),
            text=_response_options(ComplianceReview),
        ),
        smoke_prompt=(
            "Review this draft: 'As your financial advisor, we recommend buying the bonds at "
            "4.25%.' Return only the structured compliance review."
        ),
    )
    return research, analyst, compliance


def definition_hash(definition: PromptAgentDefinition) -> str:
    """Hash the complete desired definition for idempotent version registration."""

    def plain(value: object) -> object:
        if isinstance(value, Mapping):
            return {str(key): plain(item) for key, item in value.items()}
        if isinstance(value, list):
            return [plain(item) for item in value]
        return value

    canonical = json.dumps(plain(definition), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def ensure_specialist(
    operations: AgentOperationsProtocol, spec: SpecialistSpec
) -> tuple[str, object]:
    """Create a version only when the latest definition hash differs."""
    desired_hash = definition_hash(spec.definition)
    try:
        current = operations.get(spec.name)
        latest = current.versions.latest
    except ResourceNotFoundError:
        latest = None
    if latest is not None and latest.metadata.get(DEFINITION_HASH_KEY) == desired_hash:
        return "unchanged", latest
    created = operations.create_version(
        spec.name,
        definition=spec.definition,
        metadata={DEFINITION_HASH_KEY: desired_hash},
        description=spec.description,
    )
    return "created", created
