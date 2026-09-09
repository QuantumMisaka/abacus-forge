from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from abacus_forge.api import UnitSpec, collect_unit, execute_unit
from tests.support.process import run_cli


@pytest.mark.real_smoke
def test_real_abacus_scf_execute_and_collect(tmp_path: Path) -> None:
    source_value = os.environ.get("ABACUS_FORGE_REAL_SMOKE_WORKSPACE")
    executable = os.environ.get("ABACUS_FORGE_ABACUS_EXECUTABLE")
    if not source_value or not executable:
        pytest.skip("set ABACUS_FORGE_REAL_SMOKE_WORKSPACE and ABACUS_FORGE_ABACUS_EXECUTABLE")
    source = Path(source_value)
    if not source.is_dir():
        pytest.fail(f"ABACUS_FORGE_REAL_SMOKE_WORKSPACE is not a directory: {source}")
    executable_path = Path(executable)
    if executable_path.parent != Path():
        executable_ok = executable_path.is_file() and os.access(executable_path, os.X_OK)
    else:
        executable_ok = shutil.which(executable) is not None
    if not executable_ok:
        pytest.fail(f"ABACUS_FORGE_ABACUS_EXECUTABLE is not executable: {executable}")

    workspace = tmp_path / "real-smoke"
    shutil.copytree(source, workspace, symlinks=True)
    executed = execute_unit(UnitSpec(task="scf", unit="default", workdir=workspace, executable=executable))
    collected = collect_unit(UnitSpec(task="scf", unit="default", workdir=workspace))

    assert executed.returncode == 0
    assert collected.status == "completed"
    assert isinstance(collected.metrics.get("total_energy"), (int, float))


@pytest.mark.real_smoke
def test_typed_relax_machine_execute_and_collect(tmp_path: Path) -> None:
    source_value = os.environ.get("ABACUS_FORGE_RELAX_SMOKE_WORKSPACE")
    executable = os.environ.get("ABACUS_FORGE_ABACUS_EXECUTABLE")
    capability = os.environ.get("ABACUS_FORGE_RELAX_SMOKE_CAPABILITY", "relax")
    missing = [
        name
        for name, value in (
            ("ABACUS_FORGE_RELAX_SMOKE_WORKSPACE", source_value),
            ("ABACUS_FORGE_ABACUS_EXECUTABLE", executable),
        )
        if not value
    ]
    if missing:
        pytest.skip(
            "typed Relax smoke skipped: set "
            + ", ".join(missing)
            + " (ABACUS_FORGE_RELAX_SMOKE_CAPABILITY defaults to relax)"
        )

    assert source_value is not None
    assert executable is not None
    if capability not in {"relax", "cell-relax"}:
        pytest.fail(
            "ABACUS_FORGE_RELAX_SMOKE_CAPABILITY must be one of: relax, cell-relax; "
            f"got {capability!r}"
        )

    source = Path(source_value)
    if not source.is_dir():
        pytest.fail(
            "ABACUS_FORGE_RELAX_SMOKE_WORKSPACE is not a directory: "
            f"{source}"
        )
    executable_path = Path(executable)
    if executable_path.parent != Path():
        executable_ok = executable_path.is_file() and os.access(executable_path, os.X_OK)
    else:
        executable_ok = shutil.which(executable) is not None
    if not executable_ok:
        pytest.fail(f"ABACUS_FORGE_ABACUS_EXECUTABLE is not executable: {executable}")

    workspace = tmp_path / "typed-relax-smoke"
    # Materialize links while copying the prepared source so execution cannot
    # write through a preserved output symlink into the caller's workspace.
    shutil.copytree(source, workspace, symlinks=False)
    workspace_root = workspace.resolve()
    workspace_rel = workspace.name
    execute_id = "123e4567-e89b-42d3-a456-426614174102"
    collect_id = "123e4567-e89b-42d3-a456-426614174103"
    execute_request = {
        "schema_version": "forge.request/v1",
        "operation": "execute",
        "operation_id": execute_id,
        "workspace_rel": workspace_rel,
        "capability": capability,
        "executable": executable,
        "mpi_ranks": 1,
        "omp_threads": 1,
        "timeout_seconds": None,
        "dry_run": False,
    }
    executed = run_cli(
        "operation",
        "execute",
        "--stdin",
        cwd=tmp_path,
        input_text=json.dumps(execute_request),
    )
    assert executed.returncode == 0, executed.stdout + executed.stderr
    assert executed.stderr == ""
    execute_payload = json.loads(executed.stdout)
    assert execute_payload["operation_id"] == execute_id
    assert execute_payload["envelope"]["operation"] == "execute"
    assert execute_payload["envelope"]["workspace_rel"] == workspace_rel
    assert execute_payload["envelope"]["status"]["execution"] == "completed"
    assert execute_payload["envelope"]["status"]["scientific"] == "unassessed"
    execute_event_path = workspace / "reports" / "events" / f"{execute_id}-execute.json"
    execute_event = json.loads(execute_event_path.read_text(encoding="utf-8"))
    assert execute_event["id"] == execute_id
    assert execute_event["operation"] == "execute"
    assert execute_event["payload"] == execute_payload

    collect_request = {
        "schema_version": "forge.request/v1",
        "operation": "collect",
        "operation_id": collect_id,
        "workspace_rel": workspace_rel,
        "capability": capability,
    }
    collected = run_cli(
        "operation",
        "collect",
        "--stdin",
        cwd=tmp_path,
        input_text=json.dumps(collect_request),
    )
    assert collected.returncode == 0, collected.stdout + collected.stderr
    assert collected.stderr == ""
    collect_payload = json.loads(collected.stdout)
    assert collect_payload["operation_id"] == collect_id
    collect_envelope = collect_payload["envelope"]
    assert collect_envelope["operation"] == "collect"
    assert collect_envelope["workspace_rel"] == workspace_rel
    assert collect_envelope["status"]["collection"] == "complete"
    assert collect_envelope["status"]["scientific"] == "unassessed"
    energy_metrics = [
        metric for metric in collect_envelope["metrics"] if metric["name"] == "total_energy"
    ]
    assert len(energy_metrics) == 1
    energy = energy_metrics[0]["value"]
    assert isinstance(energy, (int, float)) and not isinstance(energy, bool)

    final_structure_artifacts = [
        artifact
        for artifact in collect_envelope["artifacts"]
        if artifact["path_rel"].endswith(
            ("STRU_ION_D", "STRU_NOW.cif", "STRU.cif", "STRU")
        )
        and "OUT.ABACUS" in Path(artifact["path_rel"]).parts
    ]
    assert final_structure_artifacts
    for artifact in final_structure_artifacts:
        path_rel = artifact["path_rel"]
        assert not Path(path_rel).is_absolute()
        try:
            resolved_path = (workspace / path_rel).resolve(strict=True)
            resolved_path.relative_to(workspace_root)
        except (OSError, RuntimeError, ValueError):
            pytest.fail(
                f"final structure artifact escapes copied workspace: {path_rel}"
            )
        assert resolved_path.is_file()

    collect_event_path = workspace / "reports" / "events" / f"{collect_id}-collect.json"
    collect_event = json.loads(collect_event_path.read_text(encoding="utf-8"))
    assert collect_event["id"] == collect_id
    assert collect_event["operation"] == "collect"
    assert collect_event["payload"] == collect_payload

    manifest = json.loads(
        (workspace / "reports" / "forge-workspace.json").read_text(encoding="utf-8")
    )
    manifest_events = {event["id"]: event for event in manifest["events"]}
    assert manifest_events[execute_id]["operation"] == "execute"
    assert manifest_events[collect_id]["operation"] == "collect"
    for event in (manifest_events[execute_id], manifest_events[collect_id]):
        event_path = Path(event["path_rel"])
        assert not event_path.is_absolute()
        assert ".." not in event_path.parts
        assert (workspace / event_path).is_file()
