"""Environment configuration.

Values are produced by `azd provision` and written to `.azure/<env>/.env`. Loading them
through a typed settings object means a missing value fails at startup with the name of
the variable, rather than surfacing later as an authentication error against an empty
endpoint.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _azd_env_file() -> Path | None:
    """Locate the azd environment file for the current default environment.

    Reads `.azure/config.json` for the default environment name so scripts pick up the
    same values `azd` uses, without requiring the caller to export anything.
    """
    import json

    repo_root = Path(__file__).resolve().parents[1]
    config = repo_root / ".azure" / "config.json"
    if not config.exists():
        return None

    try:
        default_env = json.loads(config.read_text(encoding="utf-8")).get("defaultEnvironment")
    except OSError, json.JSONDecodeError:
        return None

    if not default_env:
        return None

    env_file = repo_root / ".azure" / default_env / ".env"
    return env_file if env_file.exists() else None


class Settings(BaseSettings):
    """Configuration required to reach the deployed environment."""

    model_config = SettingsConfigDict(
        env_file=_azd_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_endpoint: str = Field(alias="AZURE_AI_PROJECT_ENDPOINT")
    account_endpoint: str = Field(alias="AZURE_AI_ACCOUNT_ENDPOINT")

    extraction_deployment: str = Field(alias="AZURE_AI_EXTRACTION_DEPLOYMENT")
    reasoning_deployment: str = Field(alias="AZURE_AI_REASONING_DEPLOYMENT")
    router_deployment: str = Field(alias="AZURE_AI_ROUTER_DEPLOYMENT")
    embedding_deployment: str = Field(alias="AZURE_AI_EMBEDDING_DEPLOYMENT")

    search_endpoint: str = Field(alias="AZURE_SEARCH_ENDPOINT")
    search_connection_name: str = Field(alias="AZURE_SEARCH_CONNECTION_NAME")

    storage_account_name: str = Field(alias="AZURE_STORAGE_ACCOUNT_NAME")
    storage_blob_endpoint: str = Field(alias="AZURE_STORAGE_BLOB_ENDPOINT")
    corpus_container: str = Field(alias="AZURE_STORAGE_CORPUS_CONTAINER", default="corpus")

    applicationinsights_connection_string: str = Field(
        alias="APPLICATIONINSIGHTS_CONNECTION_STRING",
        default="",
    )

    # Index and knowledge base names are fixed rather than derived, so the portal
    # walkthrough always finds the same artifacts.
    search_index_name: str = "muni-corpus"
    knowledge_base_name: str = "muni-deal-desk-kb"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings, raising a named error when configuration is missing."""
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as exc:
        raise RuntimeError(
            "Environment configuration is incomplete. Run `azd provision` first, or "
            "`azd env select demo` if you have more than one environment.\n"
            f"Underlying error: {exc}"
        ) from exc
