from __future__ import annotations

import json
from pathlib import Path
import stat
import sys
import uuid

import pytest

from abacus_forge.api import prepare
from abacus_forge.atst_neb import AtstNebServiceSet
from abacus_forge.contracts import (
    AtstNebExecuteRequest,
    AtstNebPostprocessRequest,
    AtstNebPrepareRequest,
    ScfCollectRequest,
    ScfExecuteRequest,
)
from abacus_forge.relax_contracts import (
    RelaxCollectRequest,
    RelaxExecuteRequest,
    RelaxModifyRequest,
    RelaxPrepareRequest,
)
from abacus_forge.services import RelaxServiceSet, ScfServiceSet
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


_PATH_BEARING_FIELDS = frozenset(
    {
        "command",
        "cwd",
        "executable",
        "path",
        "source",
        "source_path",
        "structure_path",
        "workspace",
        "workspace_root",
    }
)
_PATH_BEARING_SUFFIXES = ("_candidates", "_command", "_path", "_paths")


def _normalize_operation_identity(
    value: object,
    *,
    operation_id: str,
    workspace_root: Path | None = None,
    field_name: str | None = None,
    source_operation_id: str | None = None,
    claim_artifact_ids: frozenset[str] = frozenset(),
) -> object:
    """Normalize only identity/path fields that necessarily differ by fixture."""
    if isinstance(value, dict):
        if field_name is None:
            raw_operation_id = value.get("operation_id")
            if isinstance(raw_operation_id, str):
                source_operation_id = raw_operation_id
            envelope = value.get("envelope")
            if isinstance(envelope, dict) and isinstance(envelope.get("artifacts"), list):
                claim_artifact_ids = frozenset(
                    artifact["id"]
                    for artifact in envelope["artifacts"]
                    if isinstance(artifact, dict)
                    and isinstance(artifact.get("id"), str)
                    and str(artifact.get("path_rel", "")).startswith("reports/claims/")
                )
        normalized = {
            key: (
                operation_id
                if key == "operation_id"
                else "<operation-claim-ref>"
                if key in {"id", "artifact_id"} and item in claim_artifact_ids
                else _normalize_operation_identity(
                    item,
                    operation_id=operation_id,
                    workspace_root=workspace_root,
                    field_name=key,
                    source_operation_id=source_operation_id,
                    claim_artifact_ids=claim_artifact_ids,
                )
            )
            for key, item in value.items()
        }
        # Admission claims contain a random owner token, so their digest is
        # an operation-identity fact rather than a portable result field.
        if str(normalized.get("path_rel", "")).startswith("reports/claims/"):
            if source_operation_id is not None:
                normalized["path_rel"] = str(normalized["path_rel"]).replace(
                    source_operation_id, operation_id
                )
            normalized["sha256"] = "<operation-claim>"
        return normalized
    if isinstance(value, list):
        return [
            _normalize_operation_identity(
                item,
                operation_id=operation_id,
                workspace_root=workspace_root,
                field_name=field_name,
                source_operation_id=source_operation_id,
                claim_artifact_ids=claim_artifact_ids,
            )
            for item in value
        ]
    if (
        workspace_root is not None
        and isinstance(value, str)
        and field_name is not None
        and (
            field_name in _PATH_BEARING_FIELDS
            or field_name.endswith(_PATH_BEARING_SUFFIXES)
        )
    ):
        return value.replace(str(workspace_root.resolve()), "<workspace>")
    return value


_STRU_TEXT = (
    "ATOMIC_SPECIES\nSi 28.085500 Si.upf\n\nLATTICE_CONSTANT\n1.0\n"
    "LATTICE_CONSTANT_UNIT\nAngstrom\n\nLATTICE_VECTORS\n"
    "4 0 0\n0 4 0\n0 0 4\n\nATOMIC_POSITIONS\nDirect\nSi\n0\n1\n"
    "0 0 0 m 1 1 1\n"
)


def _write_relax_scenario(root: Path, capability: str, operation: str) -> Workspace:
    workspace = Workspace(root / "job").ensure_layout()
    if operation == "prepare":
        workspace.write_text("source.STRU", _STRU_TEXT)
        return workspace
    workspace.write_text("inputs/INPUT", f"INPUT_PARAMETERS\ncalculation {capability}\necutwfc 80\n")
    workspace.write_text("inputs/STRU", _STRU_TEXT)
    workspace.write_text("inputs/KPT", "K_POINTS\n0\nGamma\n1 1 1 0 0 0\n")
    if operation == "collect":
        workspace.write_text(f"outputs/OUT.ABACUS/running_{capability}.log", "TOTAL ENERGY = -4.2\n")
        workspace.write_text("outputs/OUT.ABACUS/STRU_ION_D", _STRU_TEXT)
    return workspace


def _write_script(path: Path, body: str) -> Path:
    path.write_text(f"#!{sys.executable}\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def _write_fake_atst(path: Path, *, fail: bool = False) -> Path:
    body = """
import pathlib, sys
args = sys.argv[1:]
if __FAIL__:
    print('fake atst failure', file=sys.stderr)
    raise SystemExit(7)
if args[:2] == ['neb', 'make']:
    pathlib.Path(args[args.index('-o') + 1]).write_text('neb chain\\n')
elif args and args[0] == 'run':
    pass
elif args[:2] == ['neb', 'summary']:
    pathlib.Path(args[args.index('--output') + 1]).write_text('{"images": 2}\\n')
elif args[:2] == ['neb', 'post']:
    prefix = pathlib.Path(args[args.index('--output-prefix') + 1])
    prefix.parent.mkdir(parents=True, exist_ok=True)
    prefix.with_suffix('.cif').write_text('data: fake\\n')
    prefix.with_suffix('.stru').write_text('ATOMIC_SPECIES\\n')
else:
    print('unsupported fake atst argv', args, file=sys.stderr)
    raise SystemExit(2)
""".replace("__FAIL__", "True" if fail else "False")
    return _write_script(path, body)


def _atst_request(operation: str, operation_id: str, workspace_rel: str = "neb", **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "forge.request/v1",
        "capability": "atst-neb",
        "operation": operation,
        "operation_id": operation_id,
        "workspace_rel": workspace_rel,
    }
    if operation == "prepare":
        payload.update({"init_structure_path_rel": "init.stru", "final_structure_path_rel": "final.stru"})
    elif operation == "execute":
        payload["config_path_rel"] = "workflow.yaml"
    elif operation == "postprocess":
        payload["trajectory_path_rel"] = "neb.traj"
    payload.update(extra)
    return payload


def _write_neb_fixture(root: Path) -> None:
    workspace = root / "neb"
    workspace.mkdir(parents=True)
    for name, content in (("init.stru", "init"), ("final.stru", "final"), ("workflow.yaml", "config"), ("neb.traj", "traj")):
        (workspace / name).write_text(content, encoding="utf-8")


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


@pytest.mark.parametrize("stdout,collection", [("SCF CONVERGED\n", "partial"), ("TOTAL ENERGY = -4.2\n", "complete")])
def test_operation_stdin_matches_direct_collect_api(tmp_path: Path, stdout: str, collection: str) -> None:
    api_workspace = _write_prepared_scf(tmp_path / "api", stdout=stdout)
    cli_workspace = _write_prepared_scf(tmp_path / "cli", stdout=stdout)
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
    assert json.loads(process.stdout)["envelope"]["status"]["collection"] == collection
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


def test_operation_parity_normalizer_preserves_non_path_strings(tmp_path: Path) -> None:
    root = tmp_path / "root"
    payload = {
        "diagnostics": {
            "cwd": str(root / "job"),
            "message": f"caller supplied {root} literally",
        }
    }
    assert _normalize_operation_identity(
        payload,
        operation_id="<operation-id>",
        workspace_root=root,
    ) == {
        "diagnostics": {
            "cwd": "<workspace>/job",
            "message": f"caller supplied {root} literally",
        }
    }


@pytest.mark.parametrize("capability", ["relax", "cell-relax"])
@pytest.mark.parametrize("operation", ["prepare", "modify", "collect"])
def test_relax_operation_request_file_matches_direct_api(
    tmp_path: Path, capability: str, operation: str
) -> None:
    api_root = tmp_path / capability / operation / "api"
    cli_root = tmp_path / capability / operation / "cli"
    _write_relax_scenario(api_root, capability, operation)
    _write_relax_scenario(cli_root, capability, operation)
    request_types = {
        "prepare": RelaxPrepareRequest,
        "modify": RelaxModifyRequest,
        "collect": RelaxCollectRequest,
    }
    extras = {
        "prepare": {"structure_path_rel": "source.STRU", "parameters": {"ecutwfc": 80}},
        "modify": {"input_updates": {"ecutwfc": 90}},
        "collect": {},
    }
    direct_request = request_types[operation](
        operation_id=str(uuid.uuid4()),
        workspace_rel="job",
        capability=capability,
        **extras[operation],
    )
    cli_request = request_types[operation](
        operation_id=str(uuid.uuid4()),
        workspace_rel="job",
        capability=capability,
        **extras[operation],
    )
    services = RelaxServiceSet.default(workspace_root=api_root)
    direct = getattr(getattr(services, operation), operation)(direct_request)
    request_file = cli_root / f"{operation}-request.json"
    request_file.write_text(json.dumps(cli_request.to_dict()), encoding="utf-8")

    process = run_cli(
        "operation",
        operation,
        "--request",
        request_file,
        cwd=cli_root,
    )

    assert process.returncode == 0
    assert process.stderr == ""
    assert len(_parse_concatenated_json_values(process.stdout)) == 1
    assert _normalize_operation_identity(
        json.loads(process.stdout),
        operation_id="<operation-id>",
        workspace_root=cli_root,
    ) == _normalize_operation_identity(
        direct.to_dict(),
        operation_id="<operation-id>",
        workspace_root=api_root,
    )


@pytest.mark.parametrize("capability", ["relax", "cell-relax"])
def test_relax_execute_stdin_matches_direct_api(tmp_path: Path, capability: str) -> None:
    api_root = tmp_path / capability / "execute" / "api"
    cli_root = tmp_path / capability / "execute" / "cli"
    cli_root.mkdir(parents=True)
    direct_request = RelaxExecuteRequest(
        operation_id=str(uuid.uuid4()),
        workspace_rel="job",
        capability=capability,
        dry_run=True,
    )
    cli_request = RelaxExecuteRequest(
        operation_id=str(uuid.uuid4()),
        workspace_rel="job",
        capability=capability,
        dry_run=True,
    )
    direct = RelaxServiceSet.default(workspace_root=api_root).execute.execute(direct_request)

    process = run_cli(
        "operation",
        "execute",
        "--stdin",
        cwd=cli_root,
        input_text=json.dumps(cli_request.to_dict()),
    )

    assert process.returncode == 0
    assert process.stderr == ""
    assert len(_parse_concatenated_json_values(process.stdout)) == 1
    assert json.loads(process.stdout)["envelope"]["status"]["execution"] == "skipped"
    assert _normalize_operation_identity(
        json.loads(process.stdout),
        operation_id="<operation-id>",
        workspace_root=cli_root,
    ) == _normalize_operation_identity(
        direct.to_dict(),
        operation_id="<operation-id>",
        workspace_root=api_root,
    )


def test_machine_process_discovery_emits_one_json_document_and_no_diagnostics() -> None:
    for argv in (
        ("capabilities",),
        ("schema", "scf", "collect"),
        ("schema", "relax", "prepare"),
        ("schema", "cell-relax", "modify"),
    ):
        result = run_cli(*argv)
        assert result.returncode == 0
        assert result.stderr == ""
        assert len(_parse_concatenated_json_values(result.stdout)) == 1


def test_atst_neb_machine_process_supports_stdin_prepare_and_request_file_execute(tmp_path: Path) -> None:
    _write_neb_fixture(tmp_path)
    fake = _write_fake_atst(tmp_path / "atst")
    env = {"PATH": str(tmp_path) + ":" + str(Path(sys.executable).parent)}
    prepare_request = _atst_request("prepare", "123e4567-e89b-42d3-a456-426614174220")
    prepared = run_cli("operation", "prepare", "--stdin", cwd=tmp_path, env=env, input_text=json.dumps(prepare_request))
    assert prepared.returncode == 0
    assert json.loads(prepared.stdout)["envelope"]["operation"] == "prepare"
    request_file = tmp_path / "execute.json"
    request_file.write_text(json.dumps(_atst_request("execute", "123e4567-e89b-42d3-a456-426614174221")), encoding="utf-8")
    executed = run_cli("operation", "execute", "--request", request_file, cwd=tmp_path, env=env)
    assert executed.returncode == 0
    assert json.loads(executed.stdout)["envelope"]["operation"] == "execute"
    assert fake.is_file()


def test_atst_neb_machine_process_postprocess_writes_real_outputs(tmp_path: Path) -> None:
    _write_neb_fixture(tmp_path)
    _write_fake_atst(tmp_path / "atst")
    env = {"PATH": str(tmp_path) + ":" + str(Path(sys.executable).parent)}
    request = _atst_request("postprocess", "123e4567-e89b-42d3-a456-426614174222")
    result = run_cli("operation", "postprocess", "--stdin", cwd=tmp_path, env=env, input_text=json.dumps(request))
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["envelope"]["status"]["collection"] == "complete"
    assert (tmp_path / "neb/outputs/atst/neb-ts.cif").is_file()
    assert (tmp_path / "neb/reports/atst/neb-summary.json").is_file()


def test_atst_neb_machine_discovery_and_unknown_selectors_are_structured(tmp_path: Path) -> None:
    for argv in (("capabilities",), ("schema", "atst-neb", "postprocess")):
        result = run_cli(*argv, cwd=tmp_path)
        assert result.returncode == 0
        assert len(_parse_concatenated_json_values(result.stdout)) == 1
    unknown = _atst_request("prepare", "123e4567-e89b-42d3-a456-426614174223", capability="unknown")
    result = run_cli("operation", "prepare", "--stdin", cwd=tmp_path, input_text=json.dumps(unknown))
    assert result.returncode == 2
    assert json.loads(result.stdout)["error"]["class"] == "request.invalid"
    unsupported = _atst_request("export", "123e4567-e89b-42d3-a456-426614174227")
    result = run_cli("operation", "export", "--stdin", cwd=tmp_path, input_text=json.dumps(unsupported))
    assert result.returncode == 2
    assert len(_parse_concatenated_json_values(result.stdout)) == 1
    assert json.loads(result.stdout)["error"]["class"] == "request.invalid"


def test_atst_neb_missing_executable_maps_to_exit_three(tmp_path: Path) -> None:
    _write_neb_fixture(tmp_path)
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    env = {"PATH": str(empty_bin)}
    request = _atst_request("execute", "123e4567-e89b-42d3-a456-426614174224")
    result = run_cli("operation", "execute", "--stdin", cwd=tmp_path, env=env, input_text=json.dumps(request))
    assert result.returncode == 3
    assert json.loads(result.stdout)["error"]["class"] == "precondition.missing"


def test_atst_neb_fake_process_failure_maps_to_exit_four(tmp_path: Path) -> None:
    _write_neb_fixture(tmp_path)
    _write_fake_atst(tmp_path / "atst", fail=True)
    env = {"PATH": str(tmp_path) + ":" + str(Path(sys.executable).parent)}
    request = _atst_request("execute", "123e4567-e89b-42d3-a456-426614174225")
    result = run_cli("operation", "execute", "--stdin", cwd=tmp_path, env=env, input_text=json.dumps(request))
    assert result.returncode == 4
    assert json.loads(result.stdout)["envelope"]["status"]["execution"] == "failed"


def test_atst_neb_direct_service_and_machine_cli_envelopes_are_equivalent(tmp_path: Path) -> None:
    direct_root = tmp_path / "direct"
    cli_root = tmp_path / "cli"
    _write_neb_fixture(direct_root)
    _write_neb_fixture(cli_root)
    fake = _write_fake_atst(tmp_path / "atst")
    operation_id = "123e4567-e89b-42d3-a456-426614174226"
    request = AtstNebPostprocessRequest.from_dict(_atst_request("postprocess", operation_id))
    direct = AtstNebServiceSet.default(workspace_root=tmp_path / "direct", atst_executable=str(fake)).postprocess.postprocess(request)
    env = {"PATH": str(tmp_path) + ":" + str(Path(sys.executable).parent)}
    process = run_cli("operation", "postprocess", "--stdin", cwd=cli_root, env=env, input_text=json.dumps(request.to_dict()))
    assert process.returncode == 0
    assert _normalize_operation_identity(json.loads(process.stdout), operation_id=operation_id, workspace_root=cli_root) == _normalize_operation_identity(direct.to_dict(), operation_id=operation_id, workspace_root=direct_root)


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
