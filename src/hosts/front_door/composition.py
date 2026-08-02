"""Local front-door composition root."""

from __future__ import annotations

from azure.identity.aio import DefaultAzureCredential
from fastapi import FastAPI

from src.hosts.front_door.app import create_front_door_app
from src.hosts.front_door.settings import FrontDoorSettings
from src.infrastructure.foundry.hosted_client import HostedOrchestratorClient


def create_runtime_app() -> tuple[FastAPI, FrontDoorSettings]:
    """Construct the local API using developer identity against Foundry."""
    settings = FrontDoorSettings()  # type: ignore[call-arg]
    credential = DefaultAzureCredential()
    client = HostedOrchestratorClient(settings.orchestrator_endpoint, credential)
    app = create_front_door_app(
        client,
        allowed_origin=settings.allowed_origin,
        frontend_dist=settings.frontend_dist,
    )
    return app, settings
