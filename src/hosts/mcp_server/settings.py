"""MCP host settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class McpHostSettings(BaseSettings):
    """Runtime configuration specific to the MCP host."""

    model_config = SettingsConfigDict(extra="ignore")

    adapter_factory: str = Field(alias="MCP_ADAPTER_FACTORY")
    allowed_hosts: str = Field(default="127.0.0.1:*,localhost:*", alias="MCP_ALLOWED_HOSTS")
    host: str = Field(default="0.0.0.0", alias="MCP_HOST")
    port: int = Field(default=8000, alias="PORT")
