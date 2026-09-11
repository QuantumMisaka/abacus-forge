from __future__ import annotations

import json
import math
import os
import shutil
import uuid
from pathlib import Path

import pytest

from abacus_forge.api import UnitSpec, collect_unit, execute_unit
from abacus_forge.input_io import read_input
from abacus_forge.relax_results import _FINAL_STRUCTURE_SUFFIXES
from tests.support.process import run_cli


_REAL_SMOKE_ENGINE_TIMEOUT_SECONDS = 1800.0
_REAL_SMOKE_PROCESS_TIMEOUT_SECONDS = _REAL_SMOKE_ENGINE_TIMEOUT_SECONDS + 30.0


def _assert_contained_file(workspace_root: Path, path_rel: str) -> None:
    assert isinstance(path_rel, str)
    path = Path(path_rel)
    assert not path.is_absolute()
    assert ".." not in path.parts
    try:
        resolved = (workspace_root / path).resolve(strict=True)
        resolved.relative_to(workspace_root.resolve())
    except (OSError, RuntimeError, ValueError):
        pytest.fail(f"returned path escapes copied workspace: {path_rel}")
    assert resolved.is_file()


def _load_one_json_document(text: str) -> dict[str, object]:
    decoder = json.JSONDecoder()
    start = len(text) - len(text.lstrip())
    value, end = decoder.raw_decode(text, start)
    assert not text[end:].strip()
    assert isinstance(value, dict)
    return value


def _assert_json_safe_finite(value: object) -> None:
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        pytest.fail(f"returned fact is not finite JSON: {exc}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        assert math.isfinite(float(value))


def _assert_no_preexisting_generated_outputs(workspace: Path, *, capability: str) -> None:
    """Keep real-smoke collection facts attributable to the new execute call."""
    preexisting: list[str] = []
    # These are the Forge-layout areas recursively inspected by collection.
    # Keep the guard aligned with that visibility so a prior running log in
    # reports/ cannot become the selected main log for a no-op executable.
    search_roots = [
        workspace,
        workspace / "inputs",
        workspace / "outputs",
        workspace / "reports",
    ]
    for root in search_roots:
        if not root.exists():
            continue
        paths = root.iterdir() if root == workspace else root.rglob("*")
        for path in paths:
            if not path.is_file():
                continue
            name = path.name
            relative = path.relative_to(workspace).as_posix()
            relative_parts = Path(relative).parts
            is_input_asset = bool(relative_parts and relative_parts[0] == "inputs")
            is_inputs_output = (
                len(relative_parts) >= 3
                and relative_parts[0] == "inputs"
                and relative_parts[1].startswith("OUT.")
            )
            is_report_asset = bool(relative_parts and relative_parts[0] == "reports")
            generated = name == "out.log" and not is_input_asset and not is_report_asset
            if capability == "md":
                generated = generated or (
                    name in {"running_md.log", "MD_dump"} and not is_input_asset
                )
            else:
                generated = generated or (name.startswith("running_") and name.endswith(".log"))
                if capability in {"relax", "cell-relax"}:
                    generated = generated or (
                        relative.endswith(_FINAL_STRUCTURE_SUFFIXES)
                        and (not is_input_asset or is_inputs_output)
                        and not is_report_asset
                    )
            if generated:
                preexisting.append(relative)
    if preexisting:
        pytest.fail(
            f"typed {capability} smoke workspace must not contain pre-existing "
            "generated outputs: " + ", ".join(sorted(set(preexisting)))
        )


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
def test_typed_scf_machine_execute_and_collect(tmp_path: Path) -> None:
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

    workspace = tmp_path / "typed-scf-smoke"
    shutil.copytree(source, workspace, symlinks=False)
    _assert_no_preexisting_generated_outputs(workspace, capability="scf")
    input_path = workspace / "inputs" / "INPUT"
    try:
        calculation = read_input(input_path).get("calculation", "").strip().lower()
    except (OSError, UnicodeError) as exc:
        pytest.fail(f"typed SCF smoke workspace has unreadable INPUT: {input_path}: {exc}")
    if calculation != "scf":
        pytest.fail(
            "typed SCF smoke workspace must declare calculation=scf in "
            f"{input_path}; got {calculation or '<missing>'!r}"
        )
    workspace_root = workspace.resolve()
    workspace_rel = workspace.name
    execute_id = str(uuid.uuid4())
    collect_id = str(uuid.uuid4())
    assert execute_id != collect_id

    execute_request = {
        "schema_version": "forge.request/v1",
        "operation": "execute",
        "operation_id": execute_id,
        "workspace_rel": workspace_rel,
        "executable": executable,
        "mpi_ranks": 1,
        "omp_threads": 1,
        "timeout_seconds": _REAL_SMOKE_ENGINE_TIMEOUT_SECONDS,
        "dry_run": False,
    }
    executed = run_cli(
        "operation",
        "execute",
        "--stdin",
        cwd=tmp_path,
        input_text=json.dumps(execute_request),
        timeout=_REAL_SMOKE_PROCESS_TIMEOUT_SECONDS,
    )
    assert executed.returncode == 0, executed.stdout + executed.stderr
    assert executed.stderr == ""
    execute_payload = _load_one_json_document(executed.stdout)
    assert execute_payload["operation_id"] == execute_id
    execute_envelope = execute_payload["envelope"]
    assert isinstance(execute_envelope, dict)
    assert execute_envelope["operation"] == "execute"
    assert execute_envelope["workspace_rel"] == workspace_rel
    execute_status = execute_envelope["status"]
    assert isinstance(execute_status, dict)
    assert execute_status["execution"] == "completed"
    assert execute_status["collection"] == "not_collected"
    assert execute_status["scientific"] == "unassessed"

    collect_request = {
        "schema_version": "forge.request/v1",
        "operation": "collect",
        "operation_id": collect_id,
        "workspace_rel": workspace_rel,
    }
    collected = run_cli(
        "operation",
        "collect",
        "--stdin",
        cwd=tmp_path,
        input_text=json.dumps(collect_request),
        timeout=_REAL_SMOKE_PROCESS_TIMEOUT_SECONDS,
    )
    assert collected.returncode == 0, collected.stdout + collected.stderr
    assert collected.stderr == ""
    collect_payload = _load_one_json_document(collected.stdout)
    assert collect_payload["operation_id"] == collect_id
    collect_envelope = collect_payload["envelope"]
    assert isinstance(collect_envelope, dict)
    assert collect_envelope["operation"] == "collect"
    assert collect_envelope["workspace_rel"] == workspace_rel
    collect_status = collect_envelope["status"]
    assert isinstance(collect_status, dict)
    assert collect_status["collection"] == "complete"
    assert collect_status["execution"] == "not_run"
    assert collect_status["scientific"] == "unassessed"
    metrics = collect_envelope["metrics"]
    assert isinstance(metrics, list)
    energy_metrics = [
        metric
        for metric in metrics
        if isinstance(metric, dict) and metric.get("name") == "total_energy"
    ]
    assert len(energy_metrics) == 1
    energy = energy_metrics[0]["value"]
    assert isinstance(energy, (int, float)) and not isinstance(energy, bool)
    assert math.isfinite(float(energy))

    for operation_id, operation, payload in (
        (execute_id, "execute", execute_payload),
        (collect_id, "collect", collect_payload),
    ):
        event_path = workspace / "reports" / "events" / f"{operation_id}-{operation}.json"
        event = json.loads(event_path.read_text(encoding="utf-8"))
        assert event["id"] == operation_id
        assert event["operation"] == operation
        assert event["payload"] == payload

        envelope = payload["envelope"]
        assert isinstance(envelope, dict)
        artifacts = envelope["artifacts"]
        assert isinstance(artifacts, list)
        artifact_ids: set[str] = set()
        for artifact in artifacts:
            assert isinstance(artifact, dict)
            artifact_id = artifact["id"]
            path_rel = artifact["path_rel"]
            assert isinstance(artifact_id, str)
            assert isinstance(path_rel, str)
            artifact_ids.add(artifact_id)
            _assert_contained_file(workspace_root, path_rel)
        diagnostics = envelope["diagnostics"]
        assert isinstance(diagnostics, dict)
        artifact_refs = diagnostics["artifact_refs"]
        assert isinstance(artifact_refs, list)
        assert all(isinstance(reference, dict) for reference in artifact_refs)
        assert {
            reference["artifact_id"]
            for reference in artifact_refs
        } == artifact_ids
        assert all(
            isinstance(reference["artifact_id"], str)
            and reference["operation_id"] == operation_id
            for reference in artifact_refs
        )

    manifest = json.loads(
        (workspace / "reports" / "forge-workspace.json").read_text(encoding="utf-8")
    )
    manifest_event_records = manifest["events"]
    assert isinstance(manifest_event_records, list)
    manifest_events = {
        event["id"]: event
        for event in manifest_event_records
        if isinstance(event, dict) and isinstance(event.get("id"), str)
    }
    assert execute_id in manifest_events
    assert collect_id in manifest_events
    for operation_id, operation in ((execute_id, "execute"), (collect_id, "collect")):
        event = manifest_events[operation_id]
        assert event["operation"] == operation
        path_rel = event["path_rel"]
        assert isinstance(path_rel, str)
        assert path_rel == f"reports/events/{operation_id}-{operation}.json"
        _assert_contained_file(workspace_root, path_rel)


@pytest.mark.real_smoke
def test_typed_md_machine_execute_and_collect(tmp_path: Path) -> None:
    source_value = os.environ.get("ABACUS_FORGE_MD_SMOKE_WORKSPACE")
    executable = os.environ.get("ABACUS_FORGE_ABACUS_EXECUTABLE")
    missing = [
        name
        for name, value in (
            ("ABACUS_FORGE_MD_SMOKE_WORKSPACE", source_value),
            ("ABACUS_FORGE_ABACUS_EXECUTABLE", executable),
        )
        if not value
    ]
    if missing:
        pytest.skip("typed MD smoke skipped: set " + " and ".join(missing))

    assert source_value is not None
    assert executable is not None
    source = Path(source_value)
    if not source.is_dir():
        pytest.fail(
            "ABACUS_FORGE_MD_SMOKE_WORKSPACE is not a directory: "
            f"{source}"
        )
    executable_path = Path(executable)
    if executable_path.parent != Path():
        executable_ok = executable_path.is_file() and os.access(executable_path, os.X_OK)
    else:
        executable_ok = shutil.which(executable) is not None
    if not executable_ok:
        pytest.fail(f"ABACUS_FORGE_ABACUS_EXECUTABLE is not executable: {executable}")

    workspace = tmp_path / "typed-md-smoke"
    # Materialize links while copying the prepared source so execution cannot
    # write through a preserved output symlink into the caller's workspace.
    shutil.copytree(source, workspace, symlinks=False)
    _assert_no_preexisting_generated_outputs(workspace, capability="md")
    input_path = workspace / "inputs" / "INPUT"
    try:
        calculation = read_input(input_path).get("calculation", "").strip().lower()
    except (OSError, UnicodeError) as exc:
        pytest.fail(f"typed MD smoke workspace has unreadable INPUT: {input_path}: {exc}")
    if calculation != "md":
        pytest.fail(
            "typed MD smoke workspace must declare calculation=md in "
            f"{input_path}; got {calculation or '<missing>'!r}"
        )

    workspace_root = workspace.resolve()
    workspace_rel = workspace.name
    execute_id = str(uuid.uuid4())
    collect_id = str(uuid.uuid4())
    assert execute_id != collect_id
    assert uuid.UUID(execute_id).version == 4
    assert uuid.UUID(collect_id).version == 4

    execute_request = {
        "schema_version": "forge.request/v1",
        "operation": "execute",
        "operation_id": execute_id,
        "workspace_rel": workspace_rel,
        "capability": "md",
        "executable": executable,
        "mpi_ranks": 1,
        "omp_threads": 1,
        "timeout_seconds": _REAL_SMOKE_ENGINE_TIMEOUT_SECONDS,
        "dry_run": False,
    }
    executed = run_cli(
        "operation",
        "execute",
        "--stdin",
        cwd=tmp_path,
        input_text=json.dumps(execute_request),
        timeout=_REAL_SMOKE_PROCESS_TIMEOUT_SECONDS,
    )
    assert executed.returncode == 0, executed.stdout + executed.stderr
    assert executed.stderr == ""
    execute_payload = _load_one_json_document(executed.stdout)
    _assert_json_safe_finite(execute_payload)
    assert execute_payload["operation_id"] == execute_id
    execute_envelope = execute_payload["envelope"]
    assert isinstance(execute_envelope, dict)
    assert execute_envelope["operation"] == "execute"
    assert execute_envelope["workspace_rel"] == workspace_rel
    execute_status = execute_envelope["status"]
    assert isinstance(execute_status, dict)
    assert execute_status["execution"] == "completed"
    assert execute_status["collection"] == "not_collected"
    assert execute_status["scientific"] == "unassessed"

    collect_request = {
        "schema_version": "forge.request/v1",
        "operation": "collect",
        "operation_id": collect_id,
        "workspace_rel": workspace_rel,
        "capability": "md",
    }
    collected = run_cli(
        "operation",
        "collect",
        "--stdin",
        cwd=tmp_path,
        input_text=json.dumps(collect_request),
        timeout=_REAL_SMOKE_PROCESS_TIMEOUT_SECONDS,
    )
    assert collected.returncode == 0, collected.stdout + collected.stderr
    assert collected.stderr == ""
    collect_payload = _load_one_json_document(collected.stdout)
    _assert_json_safe_finite(collect_payload)
    assert collect_payload["operation_id"] == collect_id
    collect_envelope = collect_payload["envelope"]
    assert isinstance(collect_envelope, dict)
    assert collect_envelope["operation"] == "collect"
    assert collect_envelope["workspace_rel"] == workspace_rel
    collect_status = collect_envelope["status"]
    assert isinstance(collect_status, dict)
    assert collect_status["collection"] == "complete"
    assert collect_status["execution"] == "not_run"
    assert collect_status["scientific"] == "unassessed"

    metrics = collect_envelope["metrics"]
    assert isinstance(metrics, list)
    metrics_by_name: dict[str, dict[str, object]] = {}
    for metric in metrics:
        assert isinstance(metric, dict)
        name = metric.get("name")
        assert isinstance(name, str)
        _assert_json_safe_finite(metric.get("value"))
        metrics_by_name[name] = metric
    required_native_md_metrics = {
        "md_last_total_energy",
        "md_last_potential_energy",
        "md_last_kinetic_energy",
        "md_last_temperature",
    }
    assert required_native_md_metrics <= metrics_by_name.keys(), (
        "typed MD collection did not expose the required native parser facts: "
        f"missing={sorted(required_native_md_metrics - metrics_by_name.keys())}"
    )
    for name in required_native_md_metrics:
        value = metrics_by_name[name]["value"]
        assert isinstance(value, (int, float)) and not isinstance(value, bool)
        assert math.isfinite(float(value))
    diagnostics = collect_envelope["diagnostics"]
    assert isinstance(diagnostics, dict)
    legacy_metrics = diagnostics.get("legacy_metrics")
    if legacy_metrics is not None:
        _assert_json_safe_finite(legacy_metrics)

    for operation_id, operation, payload in (
        (execute_id, "execute", execute_payload),
        (collect_id, "collect", collect_payload),
    ):
        event_path_rel = f"reports/events/{operation_id}-{operation}.json"
        _assert_contained_file(workspace_root, event_path_rel)
        event = json.loads((workspace / event_path_rel).read_text(encoding="utf-8"))
        assert event["id"] == operation_id
        assert event["operation"] == operation
        assert event["payload"] == payload

        envelope = payload["envelope"]
        assert isinstance(envelope, dict)
        artifacts = envelope["artifacts"]
        assert isinstance(artifacts, list)
        artifact_ids: set[str] = set()
        for artifact in artifacts:
            assert isinstance(artifact, dict)
            artifact_id = artifact["id"]
            path_rel = artifact["path_rel"]
            assert isinstance(artifact_id, str)
            assert isinstance(path_rel, str)
            artifact_ids.add(artifact_id)
            _assert_contained_file(workspace_root, path_rel)
        envelope_diagnostics = envelope["diagnostics"]
        assert isinstance(envelope_diagnostics, dict)
        artifact_refs = envelope_diagnostics["artifact_refs"]
        assert isinstance(artifact_refs, list)
        assert all(isinstance(reference, dict) for reference in artifact_refs)
        assert {
            reference["artifact_id"]
            for reference in artifact_refs
        } == artifact_ids
        assert all(
            isinstance(reference["artifact_id"], str)
            and reference["operation_id"] == operation_id
            for reference in artifact_refs
        )

    manifest = json.loads(
        (workspace / "reports" / "forge-workspace.json").read_text(encoding="utf-8")
    )
    manifest_events = manifest["events"]
    assert isinstance(manifest_events, list)
    manifest_by_id = {
        event["id"]: event
        for event in manifest_events
        if isinstance(event, dict) and isinstance(event.get("id"), str)
    }
    assert execute_id in manifest_by_id
    assert collect_id in manifest_by_id
    for operation_id, operation in ((execute_id, "execute"), (collect_id, "collect")):
        event = manifest_by_id[operation_id]
        assert event["operation"] == operation
        path_rel = event["path_rel"]
        assert isinstance(path_rel, str)
        assert path_rel == f"reports/events/{operation_id}-{operation}.json"
        _assert_contained_file(workspace_root, path_rel)


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
    _assert_no_preexisting_generated_outputs(workspace, capability=capability)
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
        timeout=_REAL_SMOKE_PROCESS_TIMEOUT_SECONDS,
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
        timeout=_REAL_SMOKE_PROCESS_TIMEOUT_SECONDS,
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
            (
                "STRU_FINAL",
                "STRU_FINAL.cif",
                "STRU_ION_D",
                "STRU_NOW",
                "STRU_NOW.cif",
                "STRU.cif",
                "STRU",
            )
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
