"""CLI runner for the local Phase 7 gate and opt-in Foundry comparison."""

from __future__ import annotations

import argparse
import asyncio
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from pydantic import BaseModel
from src.infrastructure.search.constants import API_VERSION, KNOWLEDGE_BASE_NAME

from evals.cases import build_cases
from evals.collection import (
    CloudCaseCollector,
    LocalCaseCollector,
    ModelConfiguration,
    SpecialistEndpoints,
    collect_configuration,
    temporary_research_agents,
)
from evals.comparison import ComparisonReport, compare_reports
from evals.foundry import (
    OpenAIClientProtocol,
    PortalEvaluationArtifacts,
    create_portal_evaluation,
    wait_for_portal_evaluation,
)
from evals.reporting import ConfigurationReport, evaluate_configuration, to_portal_rows


class CloudRunReport(BaseModel):
    """Saved manifest joining local reports to portal-visible artifacts."""

    generated_at: datetime
    environment: str
    configurations: list[ConfigurationReport]
    comparison: ComparisonReport
    portal: PortalEvaluationArtifacts


def portal_runs_passed(artifacts: PortalEvaluationArtifacts) -> bool:
    """Require completed portal runs with rows and no failed or errored samples."""
    return bool(artifacts.run_results) and all(
        result.status == "completed"
        and (result.total or 0) > 0
        and (result.failed or 0) == 0
        and (result.errored or 0) == 0
        for result in artifacts.run_results.values()
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Run the deterministic 25-case gate without Azure credentials.",
    )
    parser.add_argument(
        "--environment",
        default=os.environ.get("AZURE_ENV_NAME", "local"),
        help="Environment label and optional .azure/<name>/.env source.",
    )
    parser.add_argument("--project-endpoint", default=os.environ.get("AZURE_AI_PROJECT_ENDPOINT"))
    parser.add_argument("--mcp-endpoint", default=os.environ.get("MCP_ENDPOINT"))
    parser.add_argument("--search-endpoint", default=os.environ.get("AZURE_SEARCH_ENDPOINT"))
    parser.add_argument(
        "--mini-model",
        default=None,
    )
    parser.add_argument(
        "--reasoning-model",
        default=None,
    )
    parser.add_argument("--results-dir", type=Path, default=Path("evals/results"))
    return parser


def _load_environment_file(environment: str) -> None:
    path = Path(".azure") / environment / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _required(value: str | None, name: str) -> str:
    if not value:
        raise RuntimeError(f"Missing required cloud setting: {name}")
    return value


def _write_report(path: Path, report: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8", newline="\n")


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


async def _run_local(environment: str, results_dir: Path) -> ConfigurationReport:
    cases = build_cases()
    configuration = ModelConfiguration(name="local", model="deterministic-domain")
    outputs = await collect_configuration(cases, configuration, LocalCaseCollector())
    report = evaluate_configuration(
        cases,
        outputs,
        environment=environment,
        configuration=configuration.name,
        model=configuration.model,
    )
    _write_report(results_dir / f"{_stamp()}-local.json", report)
    return report


async def _run_cloud(args: argparse.Namespace) -> CloudRunReport:
    _load_environment_file(args.environment)
    project_endpoint = _required(
        args.project_endpoint or os.environ.get("AZURE_AI_PROJECT_ENDPOINT"),
        "AZURE_AI_PROJECT_ENDPOINT",
    )
    mcp_endpoint = _required(
        args.mcp_endpoint or os.environ.get("MCP_ENDPOINT"),
        "MCP_ENDPOINT",
    )
    search_endpoint = _required(
        args.search_endpoint or os.environ.get("AZURE_SEARCH_ENDPOINT"),
        "AZURE_SEARCH_ENDPOINT",
    )
    configurations = [
        ModelConfiguration(
            name="mini",
            model=(
                args.mini_model
                or os.environ.get("AZURE_AI_EXTRACTION_DEPLOYMENT")
                or "gpt-5.4-mini"
            ),
        ),
        ModelConfiguration(
            name="reasoning",
            model=(
                args.reasoning_model or os.environ.get("AZURE_AI_REASONING_DEPLOYMENT") or "gpt-5.5"
            ),
        ),
    ]
    suffix = _stamp().lower()
    endpoints = SpecialistEndpoints(
        mcp_endpoint=mcp_endpoint,
        knowledge_base_endpoint=(
            f"{search_endpoint}/knowledgebases/{KNOWLEDGE_BASE_NAME}/mcp?api-version={API_VERSION}"
        ),
    )
    credential = DefaultAzureCredential()
    project_client = AIProjectClient(project_endpoint, credential)
    try:
        openai_client = project_client.get_openai_client()
        cases = build_cases()
        with temporary_research_agents(
            project_client.agents,
            endpoints=endpoints,
            configurations=configurations,
            suffix=suffix,
        ) as bindings:
            collector = CloudCaseCollector(openai_client, mcp_endpoint, bindings)
            reports: list[ConfigurationReport] = []
            for configuration in configurations:
                outputs = await collect_configuration(cases, configuration, collector)
                reports.append(
                    evaluate_configuration(
                        cases,
                        outputs,
                        environment=args.environment,
                        configuration=configuration.name,
                        model=configuration.model,
                    )
                )
            comparison = compare_reports(reports[0], reports[1])
            for report in reports:
                _write_report(
                    args.results_dir / f"{suffix}-{report.configuration}.json",
                    report,
                )
            _write_report(args.results_dir / f"{suffix}-comparison.json", comparison)
            portal = create_portal_evaluation(
                cast(OpenAIClientProtocol, openai_client),
                definition_name=f"muni-deal-desk-phase-7-{args.environment}-{suffix}",
                runs={report.configuration: to_portal_rows(report, cases) for report in reports},
            )
            portal = wait_for_portal_evaluation(
                cast(OpenAIClientProtocol, openai_client),
                portal,
            )
    finally:
        project_client.close()
        credential.close()
    cloud_report = CloudRunReport(
        generated_at=datetime.now(UTC),
        environment=args.environment,
        configurations=reports,
        comparison=comparison,
        portal=portal,
    )
    _write_report(args.results_dir / f"{suffix}-cloud.json", cloud_report)
    return cloud_report


def main(argv: Sequence[str] | None = None) -> int:
    """Run the offline gate or the opt-in cloud comparison."""
    args = _parser().parse_args(argv)
    if args.local_only:
        report = asyncio.run(_run_local(args.environment, args.results_dir))
        print(
            f"Local gate: {'PASS' if report.gate.passed else 'FAIL'} "
            f"({report.gate.overall_pass_rate:.1%}, {len(report.cases)} cases)"
        )
        return 0 if report.gate.passed else 1
    report = asyncio.run(_run_cloud(args))
    for configuration in report.configurations:
        print(
            f"{configuration.configuration} gate: "
            f"{'PASS' if configuration.gate.passed else 'FAIL'} "
            f"({configuration.gate.overall_pass_rate:.1%})"
        )
    print(f"Foundry evaluation: {report.portal.eval_id}")
    portal_passed = portal_runs_passed(report.portal)
    return 0 if portal_passed and all(item.gate.passed for item in report.configurations) else 1


if __name__ == "__main__":
    raise SystemExit(main())
