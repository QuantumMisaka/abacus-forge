from __future__ import annotations

import json
from pathlib import Path

import pytest

from abacus_forge import LocalRunner
from abacus_forge.api import UnitSpec, collect, prepare, prepare_unit, run
from abacus_forge.result import CollectionResult, RunResult, TaskResult
from tests.support.fake_executables import write_fake_abacus


@pytest.mark.parametrize("text,status", [("SCF CONVERGED\n", "complete"), ("TOTAL ENERGY = -4.2\nSCF NOT CONVERGED\n", "partial")])
def test_legacy_collection_keeps_historical_completeness(tmp_path: Path, text: str, status: str) -> None:
    workspace = prepare(tmp_path / "legacy", task="scf")
    workspace.write_text("outputs/stdout.log", text)
    assert collect(workspace).to_envelope().status.collection == status


def test_collection_result_to_dict_has_stable_agent_fields(tmp_path: Path) -> None:
    workspace = prepare(tmp_path / "collect-contract", task="scf")
    workspace.write_text("outputs/stdout.log", "TOTAL ENERGY = -5.0\nSCF CONVERGED\n")
    workspace.write_text("outputs/stderr.log", "")
    payload = collect(workspace).to_dict()
    assert set(payload) == {
        "workspace",
        "status",
        "metrics",
        "artifacts",
        "diagnostics",
        "inputs_snapshot",
        "structure_snapshot",
        "final_structure_snapshot",
    }
    assert payload["status"] == "completed"
    json.dumps(payload, allow_nan=False)


def test_run_result_to_dict_serializes_paths_and_exit_status(tmp_path: Path) -> None:
    workspace = prepare(tmp_path / "run-contract", task="scf")
    executable = write_fake_abacus(
        tmp_path / "fake-abacus",
        stdout_lines=["TOTAL ENERGY = -3.2", "SCF CONVERGED"],
    )
    payload = run(workspace, runner=LocalRunner(executable=str(executable))).to_dict()
    assert set(payload) == {
        "workspace",
        "command",
        "returncode",
        "status",
        "stdout_path",
        "stderr_path",
        "omp_threads",
        "diagnostics",
    }
    assert payload["workspace"] == str(workspace.root)
    assert isinstance(payload["returncode"], int)
    assert payload["stdout_path"].endswith("stdout.log")
    assert payload["stderr_path"].endswith("stderr.log")
    json.dumps(payload, allow_nan=False)


def test_unit_prepare_payload_matches_manifest_contract(tmp_path: Path) -> None:
    result = prepare_unit(UnitSpec(task="scf", unit="default", workdir=tmp_path / "unit-contract"))
    payload = result.to_dict()
    assert set(payload) == {"workspace", "task", "unit", "engine", "manifest"}
    assert payload["task"] == "scf"
    assert payload["unit"] == "default"
    assert payload["engine"] == "abacus"
    assert payload["manifest"]["prepared"] is True
    json.dumps(payload, allow_nan=False)


def test_collection_result_projects_a_v1_result_envelope(tmp_path: Path) -> None:
    workspace = prepare(tmp_path / "envelope", task="scf")
    workspace.write_text("outputs/stdout.log", "TOTAL ENERGY = -5.0\nSCF CONVERGED\n")
    workspace.write_text("outputs/stderr.log", "")
    envelope = collect(workspace).to_envelope()
    payload = envelope.to_dict()
    assert payload["schema_version"] == "forge.result/v1"
    assert payload["status"]["collection"] == "complete"
    assert payload["status"]["scientific"] == "unassessed"
    assert payload["checks"] == [{"name": "converged", "status": "passed", "message": None}]
    assert any(item["id"] == "stdout_log" and item["path_rel"] == "outputs/stdout.log" for item in payload["artifacts"])


def test_dry_run_collection_projects_skipped_axes(tmp_path: Path) -> None:
    envelope = CollectionResult(tmp_path, "dry-run", diagnostics={"dry_run": True}).to_envelope()
    assert envelope.status.to_dict() == {"execution": "skipped", "scientific": "unassessed", "collection": "not_collected"}


def test_dry_run_collection_status_is_sentinel_without_diagnostics(tmp_path: Path) -> None:
    envelope = CollectionResult(tmp_path, "dry-run").to_envelope()
    assert envelope.status.to_dict() == {"execution": "skipped", "scientific": "unassessed", "collection": "not_collected"}


def test_task_sequence_artifacts_have_unique_deterministic_ids(tmp_path: Path) -> None:
    first = tmp_path / "scf" / "outputs" / "stdout.log"
    second = tmp_path / "nscf" / "outputs" / "stdout.log"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text("a", encoding="utf-8")
    second.write_text("b", encoding="utf-8")
    envelope = TaskResult("sequence", tmp_path, "completed", artifacts={"a": str(first), "b": str(second)}).to_envelope()
    ids = [item.id for item in envelope.artifacts]
    assert len(ids) == len(set(ids)) == 2


def test_legacy_task_result_never_derives_scientific_assessment(tmp_path: Path) -> None:
    envelope = TaskResult("scf", tmp_path, "completed").to_envelope()
    assert envelope.status.scientific == "unassessed"


def test_run_and_task_external_artifacts_are_reported_in_diagnostics(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.log"
    outside.write_text("x", encoding="utf-8")
    run_result = RunResult(tmp_path, ["x"], 0, "completed", outside, outside, 1)
    assert "warnings" in run_result.to_envelope().diagnostics
    task_result = TaskResult("x", tmp_path, "completed", artifacts={"outside": str(outside)})
    assert "warnings" in task_result.to_envelope().diagnostics


def test_duplicate_stdout_aliases_are_disambiguated(tmp_path: Path) -> None:
    first = tmp_path / "stdout.log"
    second = tmp_path / "outputs" / "stdout.log"
    second.parent.mkdir()
    first.write_text("a", encoding="utf-8")
    second.write_text("b", encoding="utf-8")
    result = TaskResult("x", tmp_path, "completed", artifacts={"one": str(first), "two": str(second)})
    artifacts = result.to_envelope().artifacts
    assert [item.id for item in artifacts] == ["stdout_log", "stdout_log__2"]
