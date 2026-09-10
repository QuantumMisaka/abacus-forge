from __future__ import annotations

import json
from pathlib import Path

import pytest

from abacus_forge import (
    MdCollectRequest,
    MdExecuteRequest,
    MdModifyRequest,
    MdPrepareRequest,
    MdServiceSet,
    OperationOutcome,
    ScfExecuteRequest,
    ScfServiceSet,
    Workspace,
)
from tests.support.fake_executables import write_fake_abacus
from tests.support.reference_workspaces import copy_native_md_workspace


def _source(path: Path) -> Path:
    path.write_text(
        "ATOMIC_SPECIES\nSi 28.085500 Si.upf\n\nLATTICE_CONSTANT\n1.0\n"
        "LATTICE_CONSTANT_UNIT\nAngstrom\n\nLATTICE_VECTORS\n"
        "8.3004 0.0 0.0\n0.0 8.3004 0.0\n0.0 0.0 25.362243471279523\n\n"
        "ATOMIC_POSITIONS\nDirect\nSi\n0.0\n1\n0.0 0.0 0.0 m 1 1 1\n",
        encoding="utf-8",
    )
    return path


def _request(cls: type, operation: str, workspace: str = "md", **kwargs: object) -> object:
    return cls(
        operation_id=f"123e4567-e89b-42d3-a456-426614174{operation}",
        workspace_rel=workspace,
        capability="md",
        **kwargs,
    )


def test_md_service_set_prepares_md_with_default_profile_and_assets(tmp_path: Path) -> None:
    source = _source(tmp_path / "md-source.STRU")
    pseudo = tmp_path / "Si.upf"
    pseudo.write_text("pseudo", encoding="utf-8")
    workspace = Workspace(tmp_path / "md")
    workspace.ensure_layout()
    source.rename(workspace.root / "source.STRU")
    services = MdServiceSet.default(workspace_root=tmp_path)

    result = services.prepare.prepare(_request(
        MdPrepareRequest, "101", structure_path_rel="source.STRU",
        pseudo_sources={"Si": str(pseudo)},
    ))

    assert isinstance(result, OperationOutcome)
    assert "calculation md" in (workspace.inputs_dir / "INPUT").read_text()
    assert "md_type nve" in (workspace.inputs_dir / "INPUT").read_text()
    assert (workspace.inputs_dir / "Si.upf").read_text() == "pseudo"
    assert result.envelope.diagnostics["task"] == "md"
    assert result.envelope.status.scientific == "unassessed"
    event = json.loads((workspace.reports_dir / "events" / "123e4567-e89b-42d3-a456-426614174101-prepare.json").read_text())
    assert event["payload"] == result.to_dict()


def test_md_service_set_rejects_scf_and_scf_rejects_md_requests(tmp_path: Path) -> None:
    md = MdServiceSet.default(workspace_root=tmp_path)
    scf = ScfServiceSet.default(workspace_root=tmp_path)
    md_request = _request(MdExecuteRequest, "102", dry_run=True)
    scf_request = ScfExecuteRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174103",
        workspace_rel="scf",
        dry_run=True,
    )

    assert md.execute.execute(scf_request).error_class == "request.invalid"
    assert scf.execute.execute(md_request).error_class == "request.invalid"


def test_md_modify_and_collect_are_factual_and_unassessed(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "md")
    workspace.ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation md\nmd_type nve\n")
    workspace.write_text("inputs/STRU", "prepared\n")
    workspace.write_text("inputs/KPT", "prepared\n")
    output = workspace.outputs_dir / "OUT.ABACUS"
    output.mkdir(parents=True)
    (output / "running_md.log").write_text("TOTAL ENERGY = -4.2\nNORMAL END\n", encoding="utf-8")
    (workspace.outputs_dir / "MD_dump").write_text("STEP 1 TEMP 300 ETOT -4.2\n", encoding="utf-8")
    services = MdServiceSet.default(workspace_root=tmp_path)

    modified = services.modify.modify(_request(MdModifyRequest, "104", input_updates={"md_nstep": 20}))
    collected = services.collect.collect(_request(MdCollectRequest, "105"))

    assert isinstance(modified, OperationOutcome)
    assert isinstance(collected, OperationOutcome)
    assert modified.envelope.diagnostics["task"] == "md"
    assert collected.envelope.status.scientific == "unassessed"
    assert collected.envelope.metrics
    metric_names = {metric.name for metric in collected.envelope.metrics}
    assert {"md_steps", "md_dump_frames", "md_dump_steps"} <= metric_names
    assert not {"md_last_temperature", "md_last_total_energy"} & metric_names
    assert "md_dump_summary" in collected.envelope.diagnostics["legacy_metrics"]
    assert any(observation.name == "md_dump_summary" for observation in collected.observations)
    assert "trajectory" not in collected.to_dict()


def test_md_context_requires_matching_input_calculation(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "md")
    workspace.ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\n")
    services = MdServiceSet.default(workspace_root=tmp_path)

    result = services.collect.collect(_request(MdCollectRequest, "106"))

    assert result.error_class == "precondition.missing"


def test_md_collect_uses_native_log_and_allows_missing_dump(tmp_path: Path) -> None:
    workspace = copy_native_md_workspace(tmp_path / "md")
    (workspace.outputs_dir / "OUT.ABACUS" / "MD_dump").unlink()
    result = MdServiceSet.default(workspace_root=tmp_path).collect.collect(
        _request(MdCollectRequest, "108")
    )

    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.collection == "complete"
    assert any(metric.name == "md_last_total_energy" for metric in result.envelope.metrics)
    assert not any(metric.name == "md_last_kinetic_energy" and metric.value == -4.2 for metric in result.envelope.metrics)
    assert result.envelope.status.scientific == "unassessed"


def test_md_collect_stdout_or_dump_without_native_log_is_partial(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "md")
    workspace.ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation md\n")
    workspace.write_text("outputs/stdout.log", "Energy (Ry) Potential (Ry) Kinetic (Ry) Temperature (K)\n-1 -1 0 300\n")
    workspace.write_text("outputs/MD_dump", "MDSTEP: 1\n")
    result = MdServiceSet.default(workspace_root=tmp_path).collect.collect(
        _request(MdCollectRequest, "109")
    )

    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.collection == "partial"
    assert not any(metric.name.startswith("md_last_") for metric in result.envelope.metrics)


def test_md_collect_malformed_native_block_is_partial(tmp_path: Path) -> None:
    workspace = copy_native_md_workspace(tmp_path / "md")
    (workspace.outputs_dir / "OUT.ABACUS" / "running_md.log").write_text(
        "Energy (Ry) Potential (Ry) Kinetic (Ry)\n-1 -1 0\n"
        "Temperature (K) Pressure (kbar)\n300\n", encoding="utf-8"
    )
    result = MdServiceSet.default(workspace_root=tmp_path).collect.collect(
        _request(MdCollectRequest, "110")
    )
    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.collection == "partial"


def test_md_collect_without_pressure_column_is_complete(tmp_path: Path) -> None:
    workspace = copy_native_md_workspace(tmp_path / "md")
    (workspace.outputs_dir / "OUT.ABACUS" / "running_md.log").write_text(
        "Energy (Ry) Potential (Ry) Kinetic (Ry)\n-1 -1 0\n"
        "Temperature (K)\n300\n!FINAL_ETOT_IS -13.605698 eV\n",
        encoding="utf-8",
    )
    result = MdServiceSet.default(workspace_root=tmp_path).collect.collect(
        _request(MdCollectRequest, "116")
    )

    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.collection == "complete"
    assert any(metric.name == "md_last_temperature" and metric.value == 300 for metric in result.envelope.metrics)
    assert not any(metric.name == "md_last_pressure" for metric in result.envelope.metrics)


def test_md_collect_declared_non_numeric_pressure_is_partial(tmp_path: Path) -> None:
    workspace = copy_native_md_workspace(tmp_path / "md")
    (workspace.outputs_dir / "OUT.ABACUS" / "running_md.log").write_text(
        "Energy (Ry) Potential (Ry) Kinetic (Ry)\n-1 -1 0\n"
        "Temperature (K) Pressure (kbar)\n300 not-a-number\n",
        encoding="utf-8",
    )
    result = MdServiceSet.default(workspace_root=tmp_path).collect.collect(
        _request(MdCollectRequest, "117")
    )

    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.collection == "partial"


def test_md_collect_without_any_domain_output_is_missing(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "md")
    workspace.ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation md\n")
    result = MdServiceSet.default(workspace_root=tmp_path).collect.collect(
        _request(MdCollectRequest, "111")
    )
    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.collection == "missing_output"


def test_md_collect_multiple_running_logs_is_partial(tmp_path: Path) -> None:
    workspace = copy_native_md_workspace(tmp_path / "md")
    duplicate = workspace.outputs_dir / "OUT.SECOND"
    duplicate.mkdir()
    (duplicate / "running_md.log").write_text(
        (workspace.outputs_dir / "OUT.ABACUS" / "running_md.log").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    result = MdServiceSet.default(workspace_root=tmp_path).collect.collect(
        _request(MdCollectRequest, "112")
    )
    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.collection == "partial"


@pytest.mark.parametrize("relative", ["inputs/running_md.log", "reports/running_md.log"])
def test_md_collect_rejects_non_domain_running_md_alias(tmp_path: Path, relative: str) -> None:
    workspace = Workspace(tmp_path / "md")
    workspace.ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation md\n")
    workspace.write_text(relative, "Energy Potential Kinetic Temperature\n-1 -1 0 300\n")
    result = MdServiceSet.default(workspace_root=tmp_path).collect.collect(_request(MdCollectRequest, "113"))
    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.collection == "missing_output"


def test_md_collect_ignores_unrelated_output_artifacts(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "md")
    workspace.ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation md\n")
    workspace.write_text("outputs/unrelated.dat", "not a domain log\n")
    workspace.write_text("outputs/stderr.log", "\n")
    workspace.write_json("outputs/time.json", {"total": 1})
    result = MdServiceSet.default(workspace_root=tmp_path).collect.collect(_request(MdCollectRequest, "114"))
    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.collection == "missing_output"


def test_md_collect_rejects_escaped_running_md_alias(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "md")
    workspace.ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation md\n")
    outside = tmp_path / "outside-running-md.log"
    outside.write_text(
        "Energy Potential Kinetic Temperature\n-1 -1 0 300\n", encoding="utf-8"
    )
    (workspace.outputs_dir / "running_md.log").symlink_to(outside)
    result = MdServiceSet.default(workspace_root=tmp_path).collect.collect(_request(MdCollectRequest, "115"))
    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.collection == "missing_output"


def test_md_execute_runs_local_runner_and_reports_process_facts(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "md")
    workspace.ensure_layout()
    for input_name in ("INPUT", "STRU", "KPT"):
        (workspace.inputs_dir / input_name).write_text(
            "calculation md\n" if input_name == "INPUT" else "prepared\n", encoding="utf-8"
        )
    executable = write_fake_abacus(
        tmp_path / "fake-abacus", stdout_lines=["TOTAL ENERGY = -4.2", "NORMAL END"]
    )
    request = _request(MdExecuteRequest, "107", executable=str(executable))

    result = MdServiceSet.default(workspace_root=tmp_path).execute.execute(request)

    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.execution == "completed"
    assert result.envelope.status.scientific == "unassessed"
    assert {artifact.path_rel for artifact in result.envelope.artifacts} >= {
        "outputs/stdout.log", "outputs/stderr.log"
    }
    assert any(metric.name == "returncode" and metric.value == 0 for metric in result.envelope.metrics)
    assert any(metric.name == "omp_threads" for metric in result.envelope.metrics)
