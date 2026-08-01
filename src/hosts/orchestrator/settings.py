"""Configuration for the hosted orchestrator container."""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OrchestratorSettings(BaseSettings):
    """Values injected by the Foundry hosted-agent runtime or local azd environment."""

    model_config = SettingsConfigDict(extra="ignore")

    project_endpoint: str = Field(
        validation_alias=AliasChoices("FOUNDRY_PROJECT_ENDPOINT", "AZURE_AI_PROJECT_ENDPOINT")
    )
    router_model: str = Field(
        validation_alias=AliasChoices("MODEL_ROUTER_DEPLOYMENT", "AZURE_AI_ROUTER_DEPLOYMENT")
    )
    synthesis_model: str = Field(
        validation_alias=AliasChoices("SYNTHESIS_MODEL_DEPLOYMENT", "AZURE_AI_REASONING_DEPLOYMENT")
    )
    research_agent_version: str = Field(alias="RESEARCH_AGENT_VERSION")
    analyst_agent_version: str = Field(alias="ANALYST_AGENT_VERSION")
    compliance_agent_version: str = Field(alias="COMPLIANCE_AGENT_VERSION")
    manifest_path: Path = Path("src/corpus/out/manifest.json")
    applicationinsights_connection_string: str = Field(
        default="",
        alias="APPLICATIONINSIGHTS_CONNECTION_STRING",
    )
    port: int = Field(default=8088, alias="PORT")
