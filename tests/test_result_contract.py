from __future__ import annotations

import json
from pathlib import Path

from abacus_forge import LocalRunner
from abacus_forge.api import UnitSpec, collect, prepare, prepare_unit, run
from tests.support.fake_executables import write_fake_abacus


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
    assert payload["workspace"] == str(workspace.root)
    assert isinstance(payload["returncode"], int)
    assert payload["stdout_path"].endswith("stdout.log")
    assert payload["stderr_path"].endswith("stderr.log")


def test_unit_prepare_payload_matches_manifest_contract(tmp_path: Path) -> None:
    result = prepare_unit(UnitSpec(task="scf", unit="default", workdir=tmp_path / "unit-contract"))
    payload = result.to_dict()
    assert set(payload) == {"workspace", "task", "unit", "engine", "manifest"}
    assert payload["task"] == "scf"
    assert payload["unit"] == "default"
    assert payload["engine"] == "abacus"
    assert payload["manifest"]["prepared"] is True
