"""Hosted orchestrator composition root."""

from __future__ import annotations

import os

from azure.identity import DefaultAzureCredential

from src.application.handlers.compute_debt_service import ComputeDebtServiceHandler
from src.application.handlers.review_for_compliance import ReviewForComplianceHandler
from src.application.mediator import Mediator
from src.application.messages import ComputeDebtService, ReviewForCompliance
from src.hosts.orchestrator.server import ApprovalInvocationsHostServer, HostedWorkflowAgent
from src.hosts.orchestrator.settings import OrchestratorSettings
from src.hosts.orchestrator.workflow import WorkflowDependencies, create_deal_desk_workflow
from src.infrastructure.calculators import DebtServiceCalculator
from src.infrastructure.foundry.runtime import FoundryModelInvoker, RegisteredSpecialistInvoker
from src.infrastructure.manifest_repository import ManifestDealRepository
from src.infrastructure.observability.tracing import configure_azure_monitor


def create_runtime_server() -> tuple[ApprovalInvocationsHostServer, int]:
    """Construct the hosted workflow and Invocations protocol server."""
    settings = OrchestratorSettings()  # type: ignore[call-arg]
    credential = DefaultAzureCredential(
        managed_identity_client_id=os.getenv("AZURE_CLIENT_ID"),
    )
    if settings.applicationinsights_connection_string:
        configure_azure_monitor(
            "muni-deal-desk-orchestrator",
            settings.applicationinsights_connection_string,
            credential,
        )

    repository = ManifestDealRepository(settings.manifest_path)
    mediator = Mediator()
    mediator.register(
        ComputeDebtService,
        ComputeDebtServiceHandler(repository, DebtServiceCalculator()),
    )
    mediator.register(ReviewForCompliance, ReviewForComplianceHandler())

    workflow = create_deal_desk_workflow(
        WorkflowDependencies(
            mediator=mediator,
            specialists=RegisteredSpecialistInvoker(
                settings.project_endpoint,
                credential,
                {
                    "municipal-deal-research": settings.research_agent_version,
                    "municipal-deal-analyst": settings.analyst_agent_version,
                    "municipal-deal-compliance": settings.compliance_agent_version,
                },
            ),
            models=FoundryModelInvoker(settings.project_endpoint, credential),
            router_model=settings.router_model,
            synthesis_model=settings.synthesis_model,
        )
    )
    functional_agent = workflow.as_agent(
        name="municipal-deal-desk",
        description=(
            "Cited municipal new-issue comparison with deterministic controls and approval."
        ),
    )
    return ApprovalInvocationsHostServer(HostedWorkflowAgent(functional_agent)), settings.port
