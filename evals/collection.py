"""Collect Phase 7 outputs from prompt agents, MCP, or deterministic domain logic."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from time import perf_counter
from typing import Protocol

from azure.ai.projects.models import PromptAgentDefinition
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pydantic import BaseModel
from src.corpus import generate as corpus_generate
from src.domain.contracts.agent_contracts import (
    ComparableCandidates,
    ComplianceReview,
    DealDeskAnswer,
    ResearchFindings,
)
from src.domain.entities.citation import Citation, EvidenceGap, EvidenceSource
from src.domain.entities.deal import Deal, Sensitivity
from src.domain.policies.conduct_policies import DEFAULT_POLICIES
from src.infrastructure.calculators import DebtServiceCalculator
from src.infrastructure.foundry.specialists import SpecialistSpec, build_specialist_specs

from evals.cases import ContractName, EvaluationCase
from evals.reporting import CollectedCaseOutput, TokenUsage


class CollectionTarget(StrEnum):
    """Execution surface responsible for a case response."""

    RESEARCH_AGENT = "research_agent"
    MCP = "mcp"
    DETERMINISTIC_DOMAIN = "deterministic_domain"


class ModelConfiguration(BaseModel):
    """One controlled model replacement for the eval-only Research agent."""

    name: str
    model: str


class AgentBinding(BaseModel):
    """Name and immutable version of a temporary eval-only agent."""

    name: str
    version: str


class TargetResult(BaseModel):
    """Response and telemetry returned by a collection target."""

    response: dict[str, object]
    latency_ms: float
    usage: TokenUsage = TokenUsage()


class CaseTargetCollector(Protocol):
    """Collect one case from its selected execution surface."""

    async def collect(
        self,
        case: EvaluationCase,
        target: CollectionTarget,
        configuration: ModelConfiguration,
    ) -> TargetResult:
        """Return the target response and available telemetry."""
        ...


class _AgentVersion(Protocol):
    version: str | int


class AgentOperationsProtocol(Protocol):
    """Narrow prompt-agent lifecycle used for temporary evaluation agents."""

    def create_version(
        self,
        agent_name: str,
        *,
        definition: PromptAgentDefinition,
        metadata: dict[str, str],
        description: str,
    ) -> _AgentVersion:
        """Create one immutable evaluation agent version."""
        ...

    def delete(self, agent_name: str) -> object:
        """Delete the temporary agent and all of its versions."""
        ...


@dataclass(frozen=True, slots=True)
class SpecialistEndpoints:
    """Connection values required to rebuild the production Research definition."""

    mcp_endpoint: str
    knowledge_base_endpoint: str
    mcp_connection_name: str = "muni-deal-desk-mcp"
    knowledge_base_connection_name: str = "municipal-deal-foundry-iq"


def target_for_case(case: EvaluationCase) -> CollectionTarget:
    """Route each declared contract to the surface that owns it."""
    if case.expected.contract in {
        ContractName.DEBT_SERVICE_SCHEDULE,
        ContractName.COMPARABLE_CANDIDATES,
    }:
        return CollectionTarget.MCP
    if case.expected.contract is ContractName.RESEARCH_FINDINGS and not (
        case.expected.required_source_document_ids
        and Sensitivity.PRIVATE in case.expected.allowed_citation_sensitivities
    ):
        return CollectionTarget.RESEARCH_AGENT
    return CollectionTarget.DETERMINISTIC_DOMAIN


async def collect_configuration(
    cases: Sequence[EvaluationCase],
    configuration: ModelConfiguration,
    collector: CaseTargetCollector,
) -> list[CollectedCaseOutput]:
    """Collect all cases once in stable dataset order."""
    outputs: list[CollectedCaseOutput] = []
    for case in cases:
        target = target_for_case(case)
        started = perf_counter()
        try:
            result = await collector.collect(case, target, configuration)
        except Exception as error:
            result = TargetResult(
                response={
                    "collection_error": type(error).__name__,
                    "detail": str(error)[:1000],
                },
                latency_ms=(perf_counter() - started) * 1000,
            )
        outputs.append(
            CollectedCaseOutput(
                case_id=case.case_id,
                target=target.value,
                model_sensitive=target is CollectionTarget.RESEARCH_AGENT,
                response=result.response,
                latency_ms=result.latency_ms,
                usage=result.usage,
            )
        )
    return outputs


def _all_deals() -> dict[str, Deal]:
    documents = corpus_generate._official_statement_documents()
    deals = {document.deal.deal_id: document.deal for document in documents}
    subject = corpus_generate._subject_deal()
    deals[subject.deal_id] = subject
    return deals


def _citations(case: EvaluationCase) -> list[Citation]:
    citations = [
        Citation(
            document_id=document_id,
            document_title=document_id,
            excerpt="Synthetic evidence used by the deterministic local evaluation target.",
            sensitivity=(
                Sensitivity.PRIVATE if document_id.startswith("PM-") else Sensitivity.PUBLIC
            ),
        )
        for document_id in case.expected.required_citation_document_ids
    ]
    citations.extend(
        Citation(
            document_id=f"EVAL-PUBLIC-{len(citations) + index}",
            document_title=title_term,
            excerpt="Synthetic evidence used by the deterministic local evaluation target.",
        )
        for index, title_term in enumerate(
            case.expected.required_citation_title_terms,
            start=1,
        )
    )
    while len(citations) < case.expected.minimum_citations:
        index = len(citations) + 1
        citations.append(
            Citation(
                document_id=f"EVAL-PUBLIC-{index}",
                document_title=f"Synthetic public source {index}",
                excerpt="Synthetic evidence used by the deterministic local evaluation target.",
            )
        )
    return citations


def _evidence_sources(case: EvaluationCase) -> list[EvidenceSource]:
    return [
        EvidenceSource(
            document_id=document_id,
            document_title=document_id,
            deal_id=f"DEAL-00{index}",
            source_type="internal_pricing_memo",
            sensitivity=Sensitivity.PRIVATE,
        )
        for index, document_id in enumerate(
            case.expected.required_source_document_ids,
            start=1,
        )
    ]


def deterministic_response(case: EvaluationCase) -> dict[str, object]:
    """Build a contract-valid offline response from committed domain facts."""
    deals = _all_deals()
    expected = case.expected
    if expected.contract is ContractName.DEBT_SERVICE_SCHEDULE:
        schedule = DebtServiceCalculator().compute_debt_service(deals[expected.deal_ids[0]])
        return schedule.model_dump(mode="json")
    if expected.contract is ContractName.COMPARABLE_CANDIDATES:
        response = ComparableCandidates(
            comparables=[deals[deal_id] for deal_id in expected.deal_ids],
            evidence_sources=_evidence_sources(case),
            excluded_by_permission=expected.excluded_by_permission or 0,
        )
        return response.model_dump(mode="json")
    if expected.contract is ContractName.RESEARCH_FINDINGS:
        gaps = (
            [
                EvidenceGap(
                    question="Expected evidence gap",
                    reason="; ".join(expected.required_gap_terms),
                )
            ]
            if expected.required_gap_terms
            else []
        )
        response = ResearchFindings(
            comparables=[deals[deal_id] for deal_id in expected.deal_ids],
            citations=_citations(case),
            evidence_sources=_evidence_sources(case),
            gaps=gaps,
            excluded_by_permission=expected.excluded_by_permission or 0,
        )
        return response.model_dump(mode="json")
    if expected.contract is ContractName.DEAL_DESK_ANSWER:
        response = DealDeskAnswer(
            summary="Deterministic public-side evaluation answer.",
            summary_citations=_citations(case),
            partial_due_to_permissions=bool(expected.partial_due_to_permissions),
        )
        return response.model_dump(mode="json")
    if expected.contract is ContractName.COMPLIANCE_REVIEW:
        text = case.input.draft_text or ""
        findings = [policy.evaluate(text) for policy in DEFAULT_POLICIES]
        response = ComplianceReview(
            findings=findings,
            requires_human_review=True,
            blocking=any(not finding.passed for finding in findings),
        )
        return response.model_dump(mode="json")
    raise ValueError(f"Unsupported deterministic contract: {expected.contract}")


class LocalCaseCollector:
    """Offline collector proving the dataset, contracts, evaluators, and gate."""

    async def collect(
        self,
        case: EvaluationCase,
        target: CollectionTarget,
        configuration: ModelConfiguration,
    ) -> TargetResult:
        """Return a deterministic contract response without Azure credentials."""
        del target, configuration
        started = perf_counter()
        response = deterministic_response(case)
        return TargetResult(
            response=response,
            latency_ms=(perf_counter() - started) * 1000,
        )


def _response_text(response: object) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text:
        return output_text
    raise RuntimeError("Agent response contained no output_text.")


def _response_usage(response: object) -> TokenUsage:
    usage = getattr(response, "usage", None)
    if usage is None:
        return TokenUsage()
    return TokenUsage(
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        total_tokens=getattr(usage, "total_tokens", None),
    )


async def _call_mcp(endpoint: str, tool_name: str, arguments: dict[str, object]) -> TargetResult:
    started = perf_counter()
    async with (
        streamable_http_client(endpoint) as (read, write, _session_id),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(tool_name, arguments=arguments)
    if result.isError:
        raise RuntimeError(f"MCP tool {tool_name} failed: {result.content}")
    structured = result.structuredContent
    if structured is None:
        text = next(
            (
                item.text
                for item in result.content
                if getattr(item, "type", None) == "text" and hasattr(item, "text")
            ),
            None,
        )
        if not isinstance(text, str):
            raise RuntimeError(f"MCP tool {tool_name} returned no structured content.")
        structured = json.loads(text)
    return TargetResult(
        response=dict(structured),
        latency_ms=(perf_counter() - started) * 1000,
    )


class CloudCaseCollector:
    """Collector using temporary Research agents and the deployed MCP endpoint."""

    def __init__(
        self,
        openai_client: object,
        mcp_endpoint: str,
        agent_bindings: dict[str, AgentBinding],
    ) -> None:
        self._openai = openai_client
        self._mcp_endpoint = mcp_endpoint
        self._agent_bindings = agent_bindings
        self._local = LocalCaseCollector()

    async def collect(
        self,
        case: EvaluationCase,
        target: CollectionTarget,
        configuration: ModelConfiguration,
    ) -> TargetResult:
        """Collect one real or deterministic response according to its target."""
        if target is CollectionTarget.DETERMINISTIC_DOMAIN:
            return await self._local.collect(case, target, configuration)
        if target is CollectionTarget.MCP:
            return await self._collect_mcp(case)
        candidates = await self._collect_candidates(case)
        return await asyncio.to_thread(
            self._collect_research,
            case,
            configuration,
            candidates,
        )

    async def _collect_candidates(self, case: EvaluationCase) -> ComparableCandidates:
        claims = sorted(set(case.input.caller_group_claims))
        common = {
            "caller_user_id": "phase-7-evaluation",
            "caller_group_claims": claims,
        }
        if case.input.par_amount is not None:
            result = await self._collect_mcp(case)
            return ComparableCandidates.model_validate(result.response)
        deals: list[Deal] = []
        for deal_id in case.expected.deal_ids:
            result = await _call_mcp(
                self._mcp_endpoint,
                "get_deal",
                {**common, "deal_id": deal_id},
            )
            deals.append(Deal.model_validate(result.response))
        return ComparableCandidates(comparables=deals)

    async def _collect_mcp(self, case: EvaluationCase) -> TargetResult:
        claims = list(case.input.caller_group_claims)
        if case.input.subject_deal_id == "DEAL-SUBJECT-001":
            claims.append(corpus_generate.SUBJECT_ACCESS_GROUP)
        common = {
            "caller_user_id": "phase-7-evaluation",
            "caller_group_claims": sorted(set(claims)),
        }
        if case.expected.contract is ContractName.DEBT_SERVICE_SCHEDULE:
            return await _call_mcp(
                self._mcp_endpoint,
                "compute_debt_service",
                {**common, "deal_id": case.input.subject_deal_id},
            )
        par_amount = case.input.par_amount or Decimal("85000000")
        tolerance = case.input.par_tolerance if case.input.par_tolerance is not None else par_amount
        tolerance_pct = (tolerance / par_amount) * Decimal("100")
        return await _call_mcp(
            self._mcp_endpoint,
            "find_comparable_deals",
            {
                **common,
                "state": "TX",
                "security_type": "unlimited_tax",
                "par_amount": str(par_amount),
                "months_back": case.input.months_back or 24,
                "par_tolerance_pct": str(tolerance_pct),
                "limit": (
                    20
                    if case.expected.required_source_document_ids
                    or case.expected.excluded_by_permission is not None
                    else max(len(case.expected.deal_ids), 1)
                ),
            },
        )

    def _collect_research(
        self,
        case: EvaluationCase,
        configuration: ModelConfiguration,
        candidates: ComparableCandidates,
    ) -> TargetResult:
        binding = self._agent_bindings[configuration.name]
        candidate_descriptors = [
            {
                "deal_id": deal.deal_id,
                "issuer": deal.issuer.name,
                "series": deal.series_name,
                "source_document_id": deal.source_document_id,
            }
            for deal in candidates.comparables
        ]
        prompt = (
            f"{case.input.question}\n"
            f"The deterministic candidates are {json.dumps(candidate_descriptors)}. Preserve "
            "this exact candidate set. Deal IDs are application identifiers and might not "
            "appear in the PDFs. Query Foundry IQ by each full issuer name and series, not by "
            "deal ID. Retrieve every relevant public document for these candidates, inspect "
            "the passages for conflicts, missing terms, filing dates, and stale information, "
            "and report each material limitation as an evidence gap without inference.\n"
            f"Evaluation inputs: {case.input.model_dump_json(exclude_none=True)}\n"
            "Return only the registered structured ResearchFindings response."
        )
        started = perf_counter()
        response = self._openai.responses.create(  # type: ignore[attr-defined]
            input=prompt,
            extra_body={
                "agent_reference": {
                    "name": binding.name,
                    "version": binding.version,
                    "type": "agent_reference",
                }
            },
        )
        findings = ResearchFindings.model_validate_json(_response_text(response))
        findings = findings.model_copy(
            update={
                "comparables": candidates.comparables,
                "evidence_sources": candidates.evidence_sources,
                "gaps": [
                    *candidates.gaps,
                    *findings.gaps,
                ],
                "excluded_by_permission": candidates.excluded_by_permission,
            }
        )
        return TargetResult(
            response=findings.model_dump(mode="json"),
            latency_ms=(perf_counter() - started) * 1000,
            usage=_response_usage(response),
        )


def _definition_with_model(
    definition: PromptAgentDefinition,
    model: str,
) -> PromptAgentDefinition:
    values = deepcopy(dict(definition))
    values["model"] = model
    return PromptAgentDefinition(**values)


def _research_spec(
    endpoints: SpecialistEndpoints,
    extraction_model: str,
    reasoning_model: str,
) -> SpecialistSpec:
    specs = build_specialist_specs(
        mcp_endpoint=endpoints.mcp_endpoint,
        mcp_connection_name=endpoints.mcp_connection_name,
        knowledge_base_endpoint=endpoints.knowledge_base_endpoint,
        knowledge_base_connection_name=endpoints.knowledge_base_connection_name,
        extraction_model=extraction_model,
        reasoning_model=reasoning_model,
    )
    return next(spec for spec in specs if spec.name == "municipal-deal-research")


@contextmanager
def temporary_research_agents(
    operations: AgentOperationsProtocol,
    *,
    endpoints: SpecialistEndpoints,
    configurations: Sequence[ModelConfiguration],
    suffix: str,
) -> Iterator[dict[str, AgentBinding]]:
    """Create model-only Research variants and always delete their agent records."""
    if not configurations:
        raise ValueError("At least one model configuration is required.")
    base = _research_spec(
        endpoints,
        extraction_model=configurations[0].model,
        reasoning_model=configurations[-1].model,
    )
    created_names: list[str] = []
    bindings: dict[str, AgentBinding] = {}
    try:
        for configuration in configurations:
            name = f"municipal-deal-research-eval-{configuration.name}-{suffix}"
            created = operations.create_version(
                name,
                definition=_definition_with_model(base.definition, configuration.model),
                metadata={"eval_only": "true", "configuration": configuration.name},
                description=f"Temporary Phase 7 {configuration.name} Research comparison.",
            )
            created_names.append(name)
            bindings[configuration.name] = AgentBinding(
                name=name,
                version=str(created.version),
            )
        yield bindings
    finally:
        cleanup_errors: list[Exception] = []
        for name in reversed(created_names):
            try:
                operations.delete(name)
            except Exception as error:
                cleanup_errors.append(error)
        if cleanup_errors:
            raise ExceptionGroup("Temporary evaluation agent cleanup failed.", cleanup_errors)
