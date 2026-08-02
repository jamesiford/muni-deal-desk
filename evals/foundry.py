"""Foundry OpenAI evaluation payloads for collected Phase 7 outputs."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from io import BytesIO
from typing import Protocol

from openai.types.eval_create_params import EvalCreateParams
from openai.types.evals.run_create_params import RunCreateParams
from pydantic import BaseModel

SCORE_MODEL = "gpt-5.5"


class PortalEvaluationRow(BaseModel):
    """One locally scored response uploaded to a portal-visible evaluation run."""

    case_id: str
    category: str
    configuration: str
    question: str
    expected_behavior: str
    deterministic_pass: bool
    response: dict[str, object]


class PortalEvaluationArtifacts(BaseModel):
    """Identifiers for the durable Foundry evaluation and its runs."""

    eval_id: str
    run_ids: dict[str, str]
    data_file_ids: dict[str, str]
    run_results: dict[str, PortalRunResult] = {}


class PortalRunResult(BaseModel):
    """Terminal status and diagnostics for one portal evaluation run."""

    run_id: str
    status: str
    error_code: str | None = None
    error_message: str | None = None
    passed: int | None = None
    failed: int | None = None
    errored: int | None = None
    total: int | None = None
    report_url: str | None = None


class _CreatedResource(Protocol):
    id: str


class _RunOperations(Protocol):
    def create(self, eval_id: str, **kwargs: object) -> _CreatedResource: ...

    def retrieve(self, run_id: str, *, eval_id: str) -> object: ...


class _EvalOperations(Protocol):
    @property
    def runs(self) -> _RunOperations: ...

    def create(self, **kwargs: object) -> _CreatedResource: ...

    def delete(self, eval_id: str) -> object: ...


class _FileOperations(Protocol):
    def create(self, **kwargs: object) -> _CreatedResource: ...

    def delete(self, file_id: str) -> object: ...


class OpenAIClientProtocol(Protocol):
    """Narrow generated OpenAI eval surface used by the runner."""

    @property
    def evals(self) -> _EvalOperations:
        """Return generated evaluation operations."""
        ...

    @property
    def files(self) -> _FileOperations:
        """Return durable project file operations."""
        ...


def build_eval_definition_payload(name: str) -> EvalCreateParams:
    """Build the generated-API payload for the durable Phase 7 evaluation."""
    item_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "case_id": {"type": "string"},
            "category": {"type": "string"},
            "configuration": {"type": "string"},
            "question": {"type": "string"},
            "expected_behavior": {"type": "string"},
            "deterministic_pass": {"type": "boolean"},
        },
        "required": [
            "case_id",
            "category",
            "configuration",
            "question",
            "expected_behavior",
            "deterministic_pass",
        ],
        "additionalProperties": False,
    }
    return {
        "name": name,
        "data_source_config": {
            "type": "custom",
            "item_schema": item_schema,
            "include_sample_schema": True,
        },
        "testing_criteria": [
            {
                "type": "python",
                "name": "deterministic_gate",
                "source": (
                    "def grade(sample, item):\n"
                    "    return 1.0 if item['deterministic_pass'] else 0.0\n"
                ),
                "pass_threshold": 1.0,
            },
            {
                "type": "score_model",
                "name": "expected_behavior_quality",
                "model": SCORE_MODEL,
                "input": [
                    {
                        "role": "system",
                        "content": (
                            "Score how well the response satisfies the expected behavior. "
                            "Use 1 for fully satisfied, 0 for not satisfied, and a value "
                            "between 0 and 1 for partial satisfaction."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Question: {{item.question}}\n"
                            "Expected behavior: {{item.expected_behavior}}\n"
                            "Response: {{sample.output_text}}"
                        ),
                    },
                ],
                "range": [0.0, 1.0],
                "sampling_params": {"reasoning_effort": "low"},
            },
        ],
        "metadata": {"phase": "7", "suite": "muni-deal-desk"},
    }


def render_run_jsonl(
    rows: Sequence[PortalEvaluationRow],
) -> bytes:
    """Render pre-collected outputs as an OpenAI Evals JSONL file."""
    records = [
        {
            "item": {
                "case_id": row.case_id,
                "category": row.category,
                "configuration": row.configuration,
                "question": row.question,
                "expected_behavior": row.expected_behavior,
                "deterministic_pass": row.deterministic_pass,
            },
            "sample": {
                "output_text": json.dumps(
                    row.response,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            },
        }
        for row in rows
    ]
    return "".join(f"{json.dumps(record, separators=(',', ':'))}\n" for record in records).encode()


def build_file_run_payload(
    name: str,
    file_id: str,
) -> RunCreateParams:
    """Build a run backed by a durable eval-purpose project file."""
    return {
        "name": name,
        "data_source": {
            "type": "jsonl",
            "source": {"type": "file_id", "id": file_id},
        },
    }


def create_portal_evaluation(
    client: OpenAIClientProtocol,
    *,
    definition_name: str,
    runs: Mapping[str, Sequence[PortalEvaluationRow]],
) -> PortalEvaluationArtifacts:
    """Upload durable datasets, then create one portal run per configuration."""
    definition = client.evals.create(**build_eval_definition_payload(definition_name))
    data_file_ids: dict[str, str] = {}
    run_ids: dict[str, str] = {}
    try:
        for configuration, rows in runs.items():
            filename = f"{definition_name}-{configuration}.jsonl"
            content = BytesIO(render_run_jsonl(rows))
            content.name = filename
            uploaded = client.files.create(file=content, purpose="evals")
            data_file_ids[configuration] = uploaded.id

        for configuration in runs:
            created = client.evals.runs.create(
                definition.id,
                **build_file_run_payload(
                    f"{definition_name}-{configuration}",
                    data_file_ids[configuration],
                ),
            )
            run_ids[configuration] = created.id
    except Exception:
        for file_id in data_file_ids.values():
            client.files.delete(file_id)
        client.evals.delete(definition.id)
        raise
    return PortalEvaluationArtifacts(
        eval_id=definition.id,
        run_ids=run_ids,
        data_file_ids=data_file_ids,
    )


def wait_for_portal_evaluation(
    client: OpenAIClientProtocol,
    artifacts: PortalEvaluationArtifacts,
    *,
    timeout_seconds: float = 900,
    poll_interval_seconds: float = 5,
) -> PortalEvaluationArtifacts:
    """Wait for every portal run and retain infrastructure diagnostics."""
    deadline = time.monotonic() + timeout_seconds
    pending = dict(artifacts.run_ids)
    results: dict[str, PortalRunResult] = {}
    while pending:
        for configuration, run_id in list(pending.items()):
            run = client.evals.runs.retrieve(run_id, eval_id=artifacts.eval_id)
            status = str(getattr(run, "status", "unknown"))
            if status not in {"completed", "failed", "canceled"}:
                continue
            error = getattr(run, "error", None)
            counts = getattr(run, "result_counts", None)
            results[configuration] = PortalRunResult(
                run_id=run_id,
                status=status,
                error_code=getattr(error, "code", None),
                error_message=getattr(error, "message", None),
                passed=getattr(counts, "passed", None),
                failed=getattr(counts, "failed", None),
                errored=getattr(counts, "errored", None),
                total=getattr(counts, "total", None),
                report_url=getattr(run, "report_url", None),
            )
            del pending[configuration]
        if not pending:
            break
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Portal evaluation runs did not finish: {sorted(pending)}")
        time.sleep(poll_interval_seconds)
    return artifacts.model_copy(update={"run_results": results})
