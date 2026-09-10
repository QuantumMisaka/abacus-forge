from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from abacus_forge import (
    MdCollectRequest,
    MdExecuteRequest,
    MdModifyRequest,
    MdPostprocessRequest,
    MdPrepareRequest,
    MdServiceSet,
    OperationOutcome,
    Workspace,
)
from abacus_forge.discovery import capabilities_document, request_schema_document
from abacus_forge.machine_cli import decode_operation_request, run_machine_cli
from tests.support.fake_executables import write_fake_abacus
from tests.support.reference_workspaces import copy_native_md_workspace
from tests.support.process import run_cli


OPERATION_ID = "123e4567-e89b-42d3-a456-426614174000"


def _payload(operation: str, **extra: object) -> dict[str, object]:
    return {
        "schema_version": "forge.request/v1",
        "operation": operation,
        "operation_id": OPERATION_ID,
        "workspace_rel": ".",
        "capability": "md",
        **extra,
    }


def test_md_is_discoverable_and_has_five_operation_schemas() -> None:
    descriptors = capabilities_document()["capabilities"]
    md = next(item for item in descriptors if item["name"] == "md")
    assert md["maturity"] == "experimental"
    assert md["engine"] == "abacus"
    assert md["operations"] == ["prepare", "modify", "execute", "collect", "postprocess"]
    assert md["artifact_roles"] == ["input", "provenance_manifest", "output"]
    for operation in md["operations"]:
        schema = request_schema_document("md", operation)["request_schema"]
        assert schema["title"] == f"Md{operation.title()}Request"
        assert schema["properties"]["capability"]["const"] == "md"


@pytest.mark.parametrize("operation,request_type", [
    ("prepare", MdPrepareRequest),
    ("execute", MdExecuteRequest),
])
def test_md_request_is_decoded_by_capability(operation: str, request_type: type) -> None:
    extra = {"structure_path_rel": "source.STRU"} if operation == "prepare" else {"dry_run": True}
    request = decode_operation_request(operation, _payload(operation, **extra))
    assert isinstance(request, request_type)
    assert request.capability == "md"


def test_md_postprocess_decodes_but_export_remains_rejected(tmp_path: Path) -> None:
    request = decode_operation_request(
        "postprocess",
        _payload("postprocess", trajectory_path_rel="outputs/md.traj", analysis=["rdf"]),
    )
    assert isinstance(request, MdPostprocessRequest)
    assert request.to_dict()["output_dir_rel"] == "outputs/md-postprocess"

    stdout, stderr = io.StringIO(), io.StringIO()
    code = run_machine_cli(
        ["operation", "export", "--stdin"],
        stdin=io.StringIO(json.dumps(_payload("export"))), stdout=stdout, stderr=stderr, cwd=tmp_path,
    )
    assert code == 2
    assert json.loads(stdout.getvalue())["error"]["class"] == "request.invalid"
    assert stderr.getvalue() == ""


def test_md_dry_run_and_prepare_use_machine_envelope(tmp_path: Path) -> None:
    source = tmp_path / "source.STRU"
    source.write_text(
        "ATOMIC_SPECIES\nSi 28.0855 Si.upf\n\nLATTICE_CONSTANT\n1.0\n"
        "LATTICE_CONSTANT_UNIT\nAngstrom\n\nLATTICE_VECTORS\n"
        "1 0 0\n0 1 0\n0 0 1\n\nATOMIC_POSITIONS\nDirect\nSi\n0\n1\n0 0 0 m 1 1 1\n",
        encoding="utf-8",
    )
    for operation, extra, operation_id in (
        ("prepare", {"structure_path_rel": "source.STRU"}, OPERATION_ID),
        ("execute", {"dry_run": True}, "123e4567-e89b-42d3-a456-426614174001"),
    ):
        stdout, stderr = io.StringIO(), io.StringIO()
        code = run_machine_cli(
            ["operation", operation, "--stdin"],
            stdin=io.StringIO(json.dumps({**_payload(operation, **extra), "operation_id": operation_id})),
            stdout=stdout, stderr=stderr, cwd=tmp_path,
        )
        assert code == 0
        result = json.loads(stdout.getvalue())
        assert result["operation_id"] == operation_id
        assert result["envelope"]["operation"] == operation
        assert result["envelope"]["status"]["scientific"] == "unassessed"
        assert stderr.getvalue() == ""


def _md_workspace(root: Path, operation: str) -> None:
    workspace = Workspace(root / "job")
    workspace.ensure_layout()
    if operation == "prepare":
        (workspace.root / "source.STRU").write_text(
            "ATOMIC_SPECIES\nSi 28.0855 Si.upf\n\nLATTICE_CONSTANT\n1.0\n"
            "LATTICE_CONSTANT_UNIT\nAngstrom\n\nLATTICE_VECTORS\n"
            "1 0 0\n0 1 0\n0 0 1\n\nATOMIC_POSITIONS\nDirect\nSi\n"
            "0\n1\n0 0 0 m 1 1 1\n", encoding="utf-8"
        )
    else:
        workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation md\nmd_type nve\n")
        workspace.write_text("inputs/STRU", "prepared\n")
        workspace.write_text("inputs/KPT", "prepared\n")
        if operation == "collect":
            output = workspace.outputs_dir / "OUT.ABACUS"
            output.mkdir(parents=True, exist_ok=True)
            (output / "running_md.log").write_text(
                "TOTAL ENERGY = -4.2\nNORMAL END\n", encoding="utf-8"
            )
            (workspace.outputs_dir / "MD_dump").write_text(
                "STEP 1 TEMP 300 ETOT -4.2\n", encoding="utf-8"
            )


def _fact_projection(result: OperationOutcome, root: Path) -> dict[str, object]:
    envelope = result.envelope.to_dict()
    observations = result.to_dict()["observations"]
    for observation in observations:
        value = observation.get("value")
        if isinstance(value, dict) and isinstance(value.get("path"), str):
            try:
                value["path"] = Path(value["path"]).relative_to(root).as_posix()
            except ValueError:
                pass
    return {
        "status": envelope["status"],
        "artifacts": envelope["artifacts"],
        "metrics": envelope["metrics"],
        "checks": envelope["checks"],
        "warnings": envelope["warnings"],
        "observations": observations,
    }


@pytest.mark.parametrize(
    "operation,request_type,extra",
    [
        ("prepare", MdPrepareRequest, {"structure_path_rel": "source.STRU"}),
        ("modify", MdModifyRequest, {"input_updates": {"md_nstep": 20}}),
        ("execute", MdExecuteRequest, {"dry_run": True}),
        ("collect", MdCollectRequest, {}),
    ],
)
def test_md_machine_cli_matches_direct_service_facts(
    tmp_path: Path, operation: str, request_type: type, extra: dict[str, object]
) -> None:
    api_root, cli_root = tmp_path / "api", tmp_path / "cli"
    _md_workspace(api_root, operation)
    _md_workspace(cli_root, operation)
    api_id = "123e4567-e89b-42d3-a456-426614174010"
    cli_id = "123e4567-e89b-42d3-a456-426614174011"
    api_request = request_type(
        operation_id=api_id, workspace_rel="job", capability="md", **extra
    )
    service = getattr(MdServiceSet.default(workspace_root=api_root), operation)
    api_result = getattr(service, operation)(api_request)
    assert isinstance(api_result, OperationOutcome)

    payload = {**_payload(operation, **extra), "operation_id": cli_id, "workspace_rel": "job"}
    stdout, stderr = io.StringIO(), io.StringIO()
    code = run_machine_cli(
        ["operation", operation, "--stdin"],
        stdin=io.StringIO(json.dumps(payload)), stdout=stdout, stderr=stderr, cwd=cli_root,
    )
    assert code == 0
    cli_result = OperationOutcome.from_dict(json.loads(stdout.getvalue()))
    assert stderr.getvalue() == ""
    assert _fact_projection(cli_result, cli_root) == _fact_projection(api_result, api_root)


@pytest.mark.parametrize(
    "operation,request_type",
    [
        ("prepare", MdPrepareRequest),
        ("modify", MdModifyRequest),
        ("execute", MdExecuteRequest),
        ("collect", MdCollectRequest),
    ],
)
def test_md_subprocess_cli_matches_direct_service_facts(
    tmp_path: Path, operation: str, request_type: type
) -> None:
    """The installed machine process preserves the same MD facts as the API."""
    api_root, cli_root = tmp_path / "api", tmp_path / "cli"
    _md_workspace(api_root, operation)
    _md_workspace(cli_root, operation)
    extra: dict[str, object] = {}
    if operation == "prepare":
        extra["structure_path_rel"] = "source.STRU"
    elif operation == "modify":
        extra["input_updates"] = {"md_nstep": 20}
    elif operation == "execute":
        extra["executable"] = str(
            write_fake_abacus(
                tmp_path / "fake-abacus",
                stdout_lines=["TOTAL ENERGY = -4.2", "NORMAL END"],
            )
        )

    api_id = "123e4567-e89b-42d3-a456-426614174020"
    cli_id = "123e4567-e89b-42d3-a456-426614174021"
    api_request = request_type(
        operation_id=api_id, workspace_rel="job", capability="md", **extra
    )
    api_service = getattr(MdServiceSet.default(workspace_root=api_root), operation)
    api_result = getattr(api_service, operation)(api_request)
    assert isinstance(api_result, OperationOutcome)

    payload = {
        **_payload(operation, **extra),
        "operation_id": cli_id,
        "workspace_rel": "job",
    }
    process = run_cli(
        "operation", operation, "--stdin", cwd=cli_root, input_text=json.dumps(payload)
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert process.stderr == ""
    cli_result = OperationOutcome.from_dict(json.loads(process.stdout))
    assert _fact_projection(cli_result, cli_root) == _fact_projection(api_result, api_root)


def test_native_md_machine_cli_preserves_native_energy_facts(tmp_path: Path) -> None:
    api_root, cli_root = tmp_path / "api", tmp_path / "cli"
    copy_native_md_workspace(api_root / "job")
    copy_native_md_workspace(cli_root / "job")
    api_request = MdCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174030",
        workspace_rel="job", capability="md",
    )
    api_result = MdServiceSet.default(workspace_root=api_root).collect.collect(api_request)
    assert isinstance(api_result, OperationOutcome)
    payload = _payload("collect", operation_id="123e4567-e89b-42d3-a456-426614174031", workspace_rel="job")
    process = run_cli("operation", "collect", "--stdin", cwd=cli_root, input_text=json.dumps(payload))
    assert process.returncode == 0, process.stdout + process.stderr
    cli_result = OperationOutcome.from_dict(json.loads(process.stdout))
    assert cli_result.envelope.to_dict()["status"] == api_result.envelope.to_dict()["status"]
    assert cli_result.envelope.to_dict()["metrics"] == api_result.envelope.to_dict()["metrics"]
    cli_facts = {item["name"]: item["value"] for item in cli_result.to_dict()["observations"]}
    api_facts = {item.name: item.value for item in api_result.observations}
    for name in ("total_energy", "md_last_total_energy", "md_last_potential_energy", "md_last_kinetic_energy", "md_last_temperature", "md_last_pressure"):
        assert cli_facts[name] == api_facts[name]
    assert cli_result.envelope.status.collection == "complete"
