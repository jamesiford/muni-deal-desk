"""Configuration for the local FastAPI front door."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FrontDoorSettings(BaseSettings):
    """Local bridge settings populated from the selected azd environment."""

    model_config = SettingsConfigDict(extra="ignore")

    orchestrator_endpoint: str = Field(alias="AGENT_ORCHESTRATOR_INVOCATIONS_ENDPOINT")
    allowed_origin: str = Field(default="http://localhost:5173", alias="FRONT_DOOR_ORIGIN")
    frontend_dist: Path = Path("frontend/dist")
    host: str = "127.0.0.1"
    port: int = 8080
