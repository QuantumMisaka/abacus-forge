from __future__ import annotations

import json
from pathlib import Path

from abacus_forge.api import prepare
from tests.support.fake_executables import write_fake_abacus
from tests.support.process import run_cli
from tests.support.workspaces import write_fake_lcao_scf_workspace


def test_prepare_json_is_machine_readable(tmp_path: Path) -> None:
    workspace = tmp_path / "prepare-json"
    result = run_cli("prepare", workspace, "--json")
    assert result.returncode == 0
    assert result.stderr == ""
    assert json.loads(result.stdout) == {"status": "prepared", "workspace": str(workspace)}


def test_prepare_without_json_keeps_legacy_path_output(tmp_path: Path) -> None:
    workspace = tmp_path / "prepare-legacy"
    result = run_cli("prepare", workspace)
    assert result.returncode == 0
    assert result.stdout.strip() == str(workspace)


def test_prepare_pyatb_json_is_machine_readable(tmp_path: Path) -> None:
    scf_workspace = write_fake_lcao_scf_workspace(tmp_path / "scf")
    workspace = tmp_path / "prepare-pyatb-json"
    result = run_cli(
        "prepare",
        workspace,
        "--pyatb",
        "--scf-workspace",
        scf_workspace.root,
        "--point",
        "0,0,0:G",
        "--json",
    )
    assert result.returncode == 0
    assert result.stderr == ""
    assert json.loads(result.stdout) == {"status": "prepared", "workspace": str(workspace)}


def test_execute_process_emits_json_and_zero_exit(tmp_path: Path) -> None:
    workspace = prepare(tmp_path / "execute", task="scf")
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["TOTAL ENERGY = -3.2", "SCF CONVERGED"])
    result = run_cli("execute", workspace.root, "--executable", executable)
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert result.stderr == ""
    assert payload["status"] == "completed"
    assert payload["returncode"] == 0


def test_execute_missing_executable_returns_structured_failure_and_127(tmp_path: Path) -> None:
    workspace = prepare(tmp_path / "missing", task="scf")
    result = run_cli("execute", workspace.root, "--executable", tmp_path / "missing-abacus")
    payload = json.loads(result.stdout)
    assert result.returncode == 127
    assert payload["returncode"] == 127
    assert payload["diagnostics"]["failure_class"] == "missing_executable"


def test_help_is_a_noninteractive_process_contract() -> None:
    help_result = run_cli("--help")
    assert help_result.returncode == 0
    assert help_result.stderr == ""
    assert "usage:" in help_result.stdout


def test_parser_error_has_nonzero_exit_and_empty_stdout() -> None:
    error_result = run_cli("not-a-forge-command")
    assert error_result.returncode == 2
    assert error_result.stdout == ""
    assert "invalid choice" in error_result.stderr
