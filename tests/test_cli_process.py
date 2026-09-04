from __future__ import annotations

import json
from pathlib import Path
import stat
import sys

from abacus_forge.api import prepare
from abacus_forge.contracts import ScfCollectRequest, ScfExecuteRequest
from abacus_forge.services import ScfServiceSet
from abacus_forge.workspace import Workspace
from tests.support.fake_executables import write_fake_abacus
from tests.support.process import run_cli
from tests.support.workspaces import write_fake_lcao_scf_workspace


def _parse_concatenated_json_values(text: str) -> list[object]:
    decoder = json.JSONDecoder()
    values: list[object] = []
    position = 0
    while text[position:].strip():
        position += len(text[position:]) - len(text[position:].lstrip())
        value, position = decoder.raw_decode(text, position)
        values.append(value)
    return values


def _write_prepared_scf(root: Path, *, stdout: str = "SCF CONVERGED\n") -> Workspace:
    workspace = prepare(root / "scf", task="scf")
    for input_name in ("INPUT", "STRU", "KPT"):
        if not (workspace.inputs_dir / input_name).exists():
            workspace.write_text(f"inputs/{input_name}", "prepared\n")
    workspace.write_text("outputs/stdout.log", stdout)
    return workspace


def _operation_request(operation: str, operation_id: str, **extra: object) -> dict[str, object]:
    return {
        "schema_version": "forge.request/v1",
        "operation": operation,
        "operation_id": operation_id,
        "workspace_rel": "scf",
        **extra,
    }


def _normalize_operation_identity(value: object, *, operation_id: str, workspace_root: Path | None = None) -> object:
    """Normalize only identity/path fields that necessarily differ by fixture."""
    if isinstance(value, dict):
        normalized = {
            key: operation_id if key == "operation_id" else _normalize_operation_identity(
                item, operation_id=operation_id, workspace_root=workspace_root
            )
            for key, item in value.items()
        }
        # Admission claims contain a random owner token, so their digest is
        # an operation-identity fact rather than a portable result field.
        if str(normalized.get("path_rel", "")).startswith("reports/claims/"):
            normalized["sha256"] = "<operation-claim>"
        return normalized
    if isinstance(value, list):
        return [
            _normalize_operation_identity(item, operation_id=operation_id, workspace_root=workspace_root)
            for item in value
        ]
    if workspace_root is not None and isinstance(value, str):
        return value.replace(str(workspace_root.resolve()), "<workspace>")
    return value


def _write_script(path: Path, body: str) -> Path:
    path.write_text(f"#!{sys.executable}\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


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


def test_operation_stdin_matches_direct_collect_api(tmp_path: Path) -> None:
    api_workspace = _write_prepared_scf(tmp_path / "api")
    cli_workspace = _write_prepared_scf(tmp_path / "cli")
    api_request = ScfCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174201",
        workspace_rel="scf",
    )
    cli_request = ScfCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174201",
        workspace_rel="scf",
    )

    direct = ScfServiceSet.default(workspace_root=api_workspace.root.parent).collect.collect(api_request)
    process = run_cli(
        "operation",
        "collect",
        "--stdin",
        cwd=cli_workspace.root.parent,
        input_text=json.dumps(cli_request.to_dict()),
    )

    assert process.returncode == 0
    assert process.stderr == ""
    assert len(_parse_concatenated_json_values(process.stdout)) == 1
    assert _normalize_operation_identity(
        json.loads(process.stdout), operation_id=cli_request.operation_id, workspace_root=cli_workspace.root.parent
    ) == _normalize_operation_identity(
        direct.to_dict(), operation_id=cli_request.operation_id, workspace_root=api_workspace.root.parent
    )


def test_operation_request_file_matches_direct_execute_api_with_typed_config(tmp_path: Path) -> None:
    api_workspace = _write_prepared_scf(tmp_path / "api", stdout="existing\n")
    cli_workspace = _write_prepared_scf(tmp_path / "cli", stdout="existing\n")
    executable = write_fake_abacus(
        tmp_path / "fake-abacus",
        stdout_lines=["TOTAL ENERGY = -3.2", "SCF CONVERGED"],
    )
    request = ScfExecuteRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174203",
        workspace_rel="scf",
        executable=str(executable),
        mpi_ranks=1,
        omp_threads=2,
        timeout_seconds=5.0,
    )
    direct = ScfServiceSet.default(workspace_root=api_workspace.root.parent).execute.execute(request)
    request_file = tmp_path / "execute-request.json"
    request_file.write_text(json.dumps(request.to_dict()), encoding="utf-8")

    process = run_cli("operation", "execute", "--request", request_file, cwd=cli_workspace.root.parent)

    assert process.returncode == 0
    assert process.stderr == ""
    assert len(_parse_concatenated_json_values(process.stdout)) == 1
    assert _normalize_operation_identity(
        json.loads(process.stdout), operation_id=request.operation_id, workspace_root=cli_workspace.root.parent
    ) == _normalize_operation_identity(
        direct.to_dict(), operation_id=request.operation_id, workspace_root=api_workspace.root.parent
    )


def test_machine_process_discovery_emits_one_json_document_and_no_diagnostics() -> None:
    for argv in (("capabilities",), ("schema", "scf", "collect")):
        result = run_cli(*argv)
        assert result.returncode == 0
        assert result.stderr == ""
        assert len(_parse_concatenated_json_values(result.stdout)) == 1


def test_operation_stdin_with_default_devnull_is_noninteractive() -> None:
    result = run_cli("operation", "collect", "--stdin")
    assert result.returncode == 2
    assert result.stderr == ""
    assert len(_parse_concatenated_json_values(result.stdout)) == 1
    assert json.loads(result.stdout)["error"]["class"] == "request.invalid"


def _run_execute_scenario(scenario: str, root: Path) -> object:
    workspace = _write_prepared_scf(root)
    if scenario == "schema":
        request = _operation_request("execute", "123e4567-e89b-42d3-a456-426614174205", schema_version="wrong")
    elif scenario == "precondition":
        request = _operation_request("execute", "123e4567-e89b-42d3-a456-426614174206")
        for input_name in ("INPUT", "STRU", "KPT"):
            (workspace.inputs_dir / input_name).unlink()
    elif scenario in {"nonzero", "timeout", "signal"}:
        if scenario == "nonzero":
            body = "raise SystemExit(7)"
        elif scenario == "timeout":
            body = "import time; time.sleep(0.3)"
        else:
            body = "import os; os.kill(os.getpid(), 15)"
        executable = _write_script(root / f"runner-{scenario}.py", body)
        request = _operation_request(
            "execute",
            {
                "nonzero": "123e4567-e89b-42d3-a456-426614174207",
                "timeout": "123e4567-e89b-42d3-a456-426614174208",
                "signal": "123e4567-e89b-42d3-a456-426614174209",
            }[scenario],
            executable=str(executable),
            timeout_seconds=0.05 if scenario == "timeout" else None,
        )
    elif scenario == "internal":
        reports = workspace.root / "reports"
        reports.rmdir()
        reports.write_text("not a directory", encoding="utf-8")
        request = _operation_request("collect", "123e4567-e89b-42d3-a456-426614174210")
        return run_cli(
            "operation", "collect", "--stdin", cwd=root, input_text=json.dumps(request)
        )
    else:
        raise AssertionError(f"unknown scenario: {scenario}")
    return run_cli(
        "operation", "execute", "--stdin", cwd=root, input_text=json.dumps(request)
    )


def test_operation_process_uses_frozen_exit_classes(tmp_path: Path) -> None:
    expected = {"schema": 2, "precondition": 3, "nonzero": 4, "timeout": 4, "signal": 4, "internal": 5}
    for scenario, exit_code in expected.items():
        result = _run_execute_scenario(scenario, tmp_path / scenario)
        assert result.returncode == exit_code
        assert result.stderr == ""
        assert len(_parse_concatenated_json_values(result.stdout)) == 1
        payload = json.loads(result.stdout)
        if scenario in {"nonzero", "timeout", "signal"}:
            assert payload["envelope"]["status"]["execution"] == "failed"
        if scenario == "internal":
            assert payload["error"]["class"] == "persistence.failure"
