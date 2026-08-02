"""Register and smoke-test the three Foundry prompt specialists."""

from __future__ import annotations

import json
import os
import sys

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from pydantic import BaseModel
from src.infrastructure.foundry.specialists import build_specialist_specs, ensure_specialist
from src.infrastructure.search.constants import API_VERSION, KNOWLEDGE_BASE_NAME

KNOWLEDGE_BASE_CONNECTION_NAME = "municipal-deal-foundry-iq"


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _response_text(response: object) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text:
        return output_text
    for item in getattr(response, "output", ()):
        if getattr(item, "type", None) != "message":
            continue
        for content in getattr(item, "content", ()):
            text = getattr(content, "text", None)
            if isinstance(text, str) and text:
                return text
    raise RuntimeError("Agent response contained no text output")


def _smoke_agent(openai: object, spec: object, version: object) -> BaseModel:
    response = openai.responses.create(  # type: ignore[attr-defined]
        input=spec.smoke_prompt,
        extra_body={
            "agent_reference": {
                "name": spec.name,
                "version": version.version,
                "type": "agent_reference",
            }
        },
    )
    text = _response_text(response)
    try:
        return spec.response_model.model_validate_json(text)
    except Exception as exc:
        raise RuntimeError(
            f"{spec.name} did not return {spec.response_model.__name__}: {text}"
        ) from exc


def main() -> int:
    """Reconcile specialists and prove each one returns its contract standalone."""
    skip_smoke = "--skip-smoke" in sys.argv[1:]
    endpoint = _required("AZURE_AI_PROJECT_ENDPOINT")
    client = AIProjectClient(endpoint, DefaultAzureCredential())
    try:
        specs = build_specialist_specs(
            mcp_endpoint=_required("MCP_ENDPOINT"),
            mcp_connection_name="muni-deal-desk-mcp",
            knowledge_base_endpoint=(
                f"{_required('AZURE_SEARCH_ENDPOINT')}/knowledgebases/"
                f"{KNOWLEDGE_BASE_NAME}/mcp?api-version={API_VERSION}"
            ),
            knowledge_base_connection_name=KNOWLEDGE_BASE_CONNECTION_NAME,
            extraction_model=_required("AZURE_AI_EXTRACTION_DEPLOYMENT"),
            reasoning_model=_required("AZURE_AI_REASONING_DEPLOYMENT"),
        )
        openai = client.get_openai_client()
        versions: dict[str, str] = {}
        for spec in specs:
            status, version = ensure_specialist(client.agents, spec)
            versions[spec.name] = str(version.version)
            print(f"Agent {spec.name} version {version.version}: {status}")
            if not skip_smoke:
                result = _smoke_agent(openai, spec, version)
                print(
                    f"Agent {spec.name} contract: "
                    f"{json.dumps(result.model_dump(mode='json'), separators=(',', ':'))[:240]}"
                )
        print("AZD_AGENT_VERSIONS=" + json.dumps(versions, separators=(",", ":")))
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
