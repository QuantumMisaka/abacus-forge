from __future__ import annotations

import json
import math
import os
import shutil
from pathlib import Path

import pytest

from tests.support.process import run_cli


_PYATB_SMOKE_LINE_KPOINTS = [
    {"coords": [0.0, 0.0, 0.0], "label": "G"},
    {"coords": [0.5, 0.5, 0.5], "label": "T"},
    {"coords": [0.748943434180, 0.251056565820, 0.5], "label": "H_2"},
    {"coords": [0.5, -0.251056565820, 0.251056565820], "label": "H_0"},
    {"coords": [0.5, 0.0, 0.0], "label": "L"},
    {"coords": [0.0, 0.0, 0.0], "label": "G"},
    {"coords": [0.375528282910, -0.375528282910, 0.0], "label": "S_0"},
    {"coords": [0.624471717090, 0.0, 0.375528282910], "label": "S_2"},
    {"coords": [0.5, 0.0, 0.5], "label": "F"},
    {"coords": [0.0, 0.0, 0.0], "label": "G"},
]

_PYATB_SMOKE_SOURCES = (
    "source/STRU",
    "source/data-HR-sparse_SPIN0.csr",
    "source/data-HR-sparse_SPIN1.csr",
    "source/data-SR-sparse_SPIN0.csr",
    "source/data-rR-sparse.csr",
)
_PYATB_GENERATED_NAMES = {
    "band_info.dat",
    "band_up.dat",
    "band_dn.dat",
    "band.pdf",
    "band.png",
}


def _json_document(process) -> dict[str, object]:
    assert process.stderr == ""
    value = json.loads(process.stdout)
    assert isinstance(value, dict)
    return value


def _assert_contained_artifacts(workspace: Path, payload: dict[str, object]) -> set[str]:
    envelope = payload["envelope"]
    assert isinstance(envelope, dict)
    artifacts = envelope["artifacts"]
    assert isinstance(artifacts, list)
    paths: set[str] = set()
    for item in artifacts:
        assert isinstance(item, dict)
        path_rel = item["path_rel"]
        assert isinstance(path_rel, str)
        path = Path(path_rel)
        assert not path.is_absolute() and ".." not in path.parts
        resolved = (workspace / path).resolve(strict=True)
        resolved.relative_to(workspace.resolve())
        assert resolved.is_file()
        paths.add(path_rel)
    return paths


def _assert_event_artifact_refs(workspace: Path, payload: dict[str, object]) -> None:
    operation_id = payload["operation_id"]
    envelope = payload["envelope"]
    assert isinstance(operation_id, str)
    assert isinstance(envelope, dict)
    operation = envelope["operation"]
    assert isinstance(operation, str)
    event_path = workspace / "reports" / "events" / f"{operation_id}-{operation}.json"
    event = json.loads(event_path.read_text(encoding="utf-8"))
    assert event["id"] == operation_id
    assert event["operation"] == operation
    assert event["payload"] == payload
    artifacts = envelope["artifacts"]
    diagnostics = envelope["diagnostics"]
    assert isinstance(artifacts, list)
    assert isinstance(diagnostics, dict)
    refs = diagnostics["artifact_refs"]
    assert isinstance(refs, list)
    artifact_ids = {item["id"] for item in artifacts if isinstance(item, dict)}
    assert {item["artifact_id"] for item in refs if isinstance(item, dict)} == artifact_ids
    assert all(
        isinstance(item, dict)
        and item.get("operation_id") == operation_id
        for item in refs
    )


def _assert_legacy_execute_command(
    workspace: Path, executable: Path
) -> None:
    """Check the selected process without widening the result envelope contract."""
    result_path = workspace / "forge-result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    command = result["command"]
    assert isinstance(command, list) and command
    assert Path(command[0]).resolve() == executable


def _assert_no_preexisting_generated_outputs(workspace: Path) -> None:
    for path in workspace.rglob("*"):
        if not path.is_file() or path.name not in _PYATB_GENERATED_NAMES:
            continue
        relative = path.relative_to(workspace).parts
        if relative[:2] == ("inputs", "Out"):
            pytest.fail(
                "typed PyATB smoke source contains pre-existing generated output: "
                + path.relative_to(workspace).as_posix()
            )


@pytest.mark.real_smoke
def test_typed_pyatb_band_machine_process_smoke(tmp_path: Path) -> None:
    source_value = os.environ.get("ABACUS_FORGE_PYATB_SMOKE_WORKSPACE")
    configured = os.environ.get("ABACUS_FORGE_PYATB_EXECUTABLE")
    fermi_value = os.environ.get("ABACUS_FORGE_PYATB_SMOKE_FERMI_ENERGY")
    missing = [
        name
        for name, value in (
            ("ABACUS_FORGE_PYATB_SMOKE_WORKSPACE", source_value),
            ("ABACUS_FORGE_PYATB_EXECUTABLE", configured),
            ("ABACUS_FORGE_PYATB_SMOKE_FERMI_ENERGY", fermi_value),
        )
        if not value
    ]
    if missing:
        pytest.skip("set " + " and ".join(missing))

    assert source_value is not None
    assert configured is not None
    assert fermi_value is not None
    source = Path(source_value)
    if not source.is_dir():
        pytest.fail(f"ABACUS_FORGE_PYATB_SMOKE_WORKSPACE is not a directory: {source}")
    executable = Path(configured)
    if executable.parent != Path():
        if not executable.is_file() or not os.access(executable, os.X_OK):
            pytest.fail(f"ABACUS_FORGE_PYATB_EXECUTABLE is not executable: {configured}")
        executable = executable.resolve()
    else:
        found = shutil.which(configured)
        if found is None:
            pytest.fail(f"ABACUS_FORGE_PYATB_EXECUTABLE is not executable: {configured}")
        executable = Path(found).resolve()
    try:
        fermi_energy = float(fermi_value)
    except ValueError as error:
        pytest.fail(f"ABACUS_FORGE_PYATB_SMOKE_FERMI_ENERGY must be finite: {fermi_value!r}")
        raise AssertionError from error
    if not math.isfinite(fermi_energy):
        pytest.fail("ABACUS_FORGE_PYATB_SMOKE_FERMI_ENERGY must be finite")

    for relative in _PYATB_SMOKE_SOURCES:
        path = source / relative
        if not path.is_file():
            pytest.fail(f"PyATB smoke source is missing required file: {path}")

    workspace = tmp_path / "pyatb-smoke"
    shutil.copytree(source, workspace, symlinks=False)
    _assert_no_preexisting_generated_outputs(workspace)
    workspace_rel = workspace.name
    base = {
        "schema_version": "forge.request/v1",
        "capability": "pyatb-band",
        "workspace_rel": workspace_rel,
    }
    prepare_id = "123e4567-e89b-42d3-a456-426614174240"
    execute_id = "123e4567-e89b-42d3-a456-426614174241"
    collect_id = "123e4567-e89b-42d3-a456-426614174242"

    prepared_process = run_cli(
        "operation",
        "prepare",
        "--stdin",
        cwd=tmp_path,
        input_text=json.dumps(
            {
                **base,
                "operation": "prepare",
                "operation_id": prepare_id,
                "structure_path_rel": "source/STRU",
                "hr_paths_rel": [
                    "source/data-HR-sparse_SPIN0.csr",
                    "source/data-HR-sparse_SPIN1.csr",
                ],
                "sr_path_rel": "source/data-SR-sparse_SPIN0.csr",
                "rr_path_rel": "source/data-rR-sparse.csr",
                "fermi_energy": fermi_energy,
                "line_kpoints": _PYATB_SMOKE_LINE_KPOINTS,
                "nspin": 2,
                "line_segments": 5,
                "max_kpoint_num": 4000,
                "handoff_mode": "copy",
            }
        ),
    )
    assert prepared_process.returncode == 0, prepared_process.stdout + prepared_process.stderr
    prepared = _json_document(prepared_process)
    assert prepared["envelope"]["status"]["execution"] == "not_run"
    assert prepared["envelope"]["status"]["scientific"] == "unassessed"
    _assert_contained_artifacts(workspace, prepared)
    _assert_event_artifact_refs(workspace, prepared)

    executed_process = run_cli(
        "operation",
        "execute",
        "--stdin",
        cwd=tmp_path,
        input_text=json.dumps(
            {
                **base,
                "operation": "execute",
                "operation_id": execute_id,
                "executable": str(executable),
                "mpi_ranks": 1,
                "omp_threads": 1,
                "timeout_seconds": 180,
                "dry_run": False,
            }
        ),
        timeout=240,
    )
    assert executed_process.returncode == 0, executed_process.stdout + executed_process.stderr
    executed = _json_document(executed_process)
    assert executed["envelope"]["status"]["execution"] == "completed"
    assert executed["envelope"]["status"]["scientific"] == "unassessed"
    diagnostics = executed["envelope"]["diagnostics"]
    assert isinstance(diagnostics, dict)
    _assert_legacy_execute_command(workspace, executable)
    _assert_contained_artifacts(workspace, executed)
    _assert_event_artifact_refs(workspace, executed)

    collected_process = run_cli(
        "operation",
        "collect",
        "--stdin",
        cwd=tmp_path,
        input_text=json.dumps(
            {
                **base,
                "operation": "collect",
                "operation_id": collect_id,
                "band_info_path_rel": "inputs/Out/Band_Structure/band_info.dat",
                "band_data_paths_rel": [
                    "inputs/Out/Band_Structure/band_up.dat",
                    "inputs/Out/Band_Structure/band_dn.dat",
                ],
                "band_picture_paths_rel": ["inputs/Out/Band_Structure/band.pdf"],
            }
        ),
        timeout=60,
    )
    assert collected_process.returncode == 0, collected_process.stdout + collected_process.stderr
    collected = _json_document(collected_process)
    envelope = collected["envelope"]
    assert isinstance(envelope, dict)
    assert envelope["status"]["collection"] == "complete"
    assert envelope["status"]["scientific"] == "unassessed"
    metrics = envelope["metrics"]
    assert isinstance(metrics, list)
    band_gaps = [
        item["value"]
        for item in metrics
        if isinstance(item, dict) and item.get("name") == "band_gap"
    ]
    assert len(band_gaps) == 1
    assert isinstance(band_gaps[0], (int, float)) and math.isfinite(float(band_gaps[0]))
    paths = _assert_contained_artifacts(workspace, collected)
    assert {
        "inputs/Out/Band_Structure/band_info.dat",
        "inputs/Out/Band_Structure/band_up.dat",
        "inputs/Out/Band_Structure/band_dn.dat",
        "inputs/Out/Band_Structure/band.pdf",
    } <= paths
    _assert_event_artifact_refs(workspace, collected)
