"""Tests for generated OpenAI evaluation payload construction."""

from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace

from evals.foundry import (
    PortalEvaluationArtifacts,
    PortalEvaluationRow,
    PortalRunResult,
    build_eval_definition_payload,
    create_portal_evaluation,
    wait_for_portal_evaluation,
)
from evals.runner import portal_runs_passed


@dataclass
class _Created:
    id: str


class _FakeRuns:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def create(self, eval_id: str, **kwargs: object) -> _Created:
        self.calls.append((eval_id, kwargs))
        return _Created(f"run-{len(self.calls)}")

    def retrieve(self, run_id: str, *, eval_id: str):
        del eval_id
        return SimpleNamespace(
            status="completed",
            error=None,
            result_counts=SimpleNamespace(passed=1, failed=0, errored=0, total=1),
            report_url=f"https://foundry.example/{run_id}",
        )


class _FakeEvals:
    def __init__(self) -> None:
        self.definition: dict[str, object] | None = None
        self.runs = _FakeRuns()

    def create(self, **kwargs: object) -> _Created:
        self.definition = kwargs
        return _Created("eval-1")

    def delete(self, eval_id: str) -> None:
        del eval_id


class _FakeFiles:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> _Created:
        self.calls.append(kwargs)
        return _Created(f"file-{len(self.calls)}")

    def delete(self, file_id: str) -> None:
        del file_id


class _FakeOpenAI:
    def __init__(self) -> None:
        self.evals = _FakeEvals()
        self.files = _FakeFiles()


def _row(configuration: str) -> PortalEvaluationRow:
    return PortalEvaluationRow(
        case_id="case-1",
        category="guardrails",
        configuration=configuration,
        question="Review this draft.",
        expected_behavior="Block the deterministic policy failure.",
        deterministic_pass=True,
        response={"blocking": True},
    )


def test_definition_uses_python_and_fixed_score_model_graders() -> None:
    payload = build_eval_definition_payload("phase-7")
    criteria = list(payload["testing_criteria"])

    assert criteria[0]["type"] == "python"
    assert "deterministic_pass" in criteria[0]["source"]
    assert criteria[1]["type"] == "score_model"
    assert criteria[1]["model"] == "gpt-5.5"
    assert "pass_threshold" not in criteria[1]


def test_portal_submission_uploads_files_before_creating_two_runs() -> None:
    client = _FakeOpenAI()

    artifacts = create_portal_evaluation(
        client,
        definition_name="phase-7",
        runs={"mini": [_row("mini")], "reasoning": [_row("reasoning")]},
    )

    assert artifacts.eval_id == "eval-1"
    assert artifacts.run_ids == {"mini": "run-1", "reasoning": "run-2"}
    assert artifacts.data_file_ids == {"mini": "file-1", "reasoning": "file-2"}
    assert client.evals.definition is not None
    assert client.evals.definition["data_source_config"]["type"] == "custom"
    assert [call["purpose"] for call in client.files.calls] == ["evals", "evals"]
    first_file = client.files.calls[0]["file"]
    assert first_file.name == "phase-7-mini.jsonl"
    first_record = json.loads(first_file.getvalue().decode().splitlines()[0])
    assert first_record["item"] == {
        "case_id": "case-1",
        "category": "guardrails",
        "configuration": "mini",
        "question": "Review this draft.",
        "expected_behavior": "Block the deterministic policy failure.",
        "deterministic_pass": True,
    }
    first_run = client.evals.runs.calls[0]
    assert first_run[0] == "eval-1"
    assert first_run[1]["data_source"]["source"] == {
        "type": "file_id",
        "id": "file-1",
    }


def test_portal_wait_records_terminal_run_results() -> None:
    client = _FakeOpenAI()
    artifacts = create_portal_evaluation(
        client,
        definition_name="phase-7",
        runs={"mini": [_row("mini")]},
    )

    completed = wait_for_portal_evaluation(
        client,
        artifacts,
        timeout_seconds=1,
        poll_interval_seconds=0,
    )

    assert completed.run_results["mini"].status == "completed"
    assert completed.run_results["mini"].total == 1


def test_portal_gate_rejects_failed_or_errored_samples() -> None:
    artifacts = PortalEvaluationArtifacts(
        eval_id="eval-1",
        run_ids={"mini": "run-1"},
        data_file_ids={"mini": "file-1"},
        run_results={
            "mini": PortalRunResult(
                run_id="run-1",
                status="completed",
                passed=24,
                failed=1,
                errored=0,
                total=25,
            )
        },
    )

    assert not portal_runs_passed(artifacts)
    passing = artifacts.model_copy(
        update={
            "run_results": {
                "mini": artifacts.run_results["mini"].model_copy(update={"passed": 25, "failed": 0})
            }
        }
    )
    assert portal_runs_passed(passing)
