"""Typed runtime adapters for registered agents and Foundry model deployments."""

from __future__ import annotations

import asyncio

from agent_framework_foundry import FoundryChatClient
from azure.ai.projects import AIProjectClient
from azure.core.credentials import TokenCredential
from pydantic import BaseModel

from src.application.ports import CallerContext


class RegisteredSpecialistInvoker:
    """Invoke a durable prompt-agent version and parse its structured text output."""

    def __init__(
        self,
        project_endpoint: str,
        credential: TokenCredential,
        versions: dict[str, str],
    ) -> None:
        self._project_endpoint = project_endpoint
        self._credential = credential
        self._versions = versions

    async def invoke[TResponse: BaseModel](
        self,
        agent_name: str,
        prompt: str,
        response_model: type[TResponse],
        *,
        caller: CallerContext,
    ) -> TResponse:
        """Invoke a fixed agent version without forwarding private caller claims."""
        del caller
        return await asyncio.to_thread(
            self._invoke,
            agent_name,
            prompt,
            response_model,
        )

    def _invoke[TResponse: BaseModel](
        self,
        agent_name: str,
        prompt: str,
        response_model: type[TResponse],
    ) -> TResponse:
        client = AIProjectClient(self._project_endpoint, self._credential)
        try:
            response = client.get_openai_client().responses.create(
                input=prompt,
                extra_body={
                    "agent_reference": {
                        "name": agent_name,
                        "version": self._versions[agent_name],
                        "type": "agent_reference",
                    }
                },
            )
            return response_model.model_validate_json(response.output_text)
        finally:
            client.close()


class FoundryModelInvoker:
    """Run typed planner and synthesis calls against named model deployments."""

    def __init__(self, project_endpoint: str, credential: TokenCredential) -> None:
        self._project_endpoint = project_endpoint
        self._credential = credential

    async def invoke[TResponse: BaseModel](
        self,
        model: str,
        instructions: str,
        prompt: str,
        response_model: type[TResponse],
    ) -> TResponse:
        """Ask Foundry for a provider-enforced Pydantic response."""
        client = FoundryChatClient(
            project_endpoint=self._project_endpoint,
            model=model,
            credential=self._credential,
        )
        agent = client.as_agent(
            name=f"deal-desk-{response_model.__name__.lower()}",
            instructions=instructions,
            default_options={"response_format": response_model},
        )
        response = await agent.run(prompt)
        if isinstance(response.value, response_model):
            return response.value
        return response_model.model_validate_json(response.text)
