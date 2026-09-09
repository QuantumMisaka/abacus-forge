from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from abacus_forge import (
    BandPostprocessRequest,
    DosPostprocessRequest,
    ForgeErrorEnvelope,
    OperationOutcome,
    OperationStatus,
    PostprocessServiceSet,
    Workspace,
)
from abacus_forge.band_data import write_sample_band_artifacts
from abacus_forge.dos_data import write_sample_dos_artifacts, write_sample_dos_family_artifacts
from abacus_forge.machine_cli import exit_code_for
from abacus_forge.postprocess_algorithms import ExplicitPostprocessResult


def _operation_id(number: int) -> str:
    return f"123e4567-e89b-42d3-a456-426614174{number:03d}"


def _band_workspace(root: Path) -> Workspace:
    workspace = Workspace(root / "job")
    workspace.ensure_layout()
    write_sample_band_artifacts(workspace.inputs_dir, include_plot=False)
    return workspace


def _dos_workspace(root: Path) -> Workspace:
    workspace = Workspace(root / "job")
    workspace.ensure_layout()
    write_sample_dos_artifacts(workspace.inputs_dir)
    return workspace


def _band_request(operation_id: str, **updates: object) -> BandPostprocessRequest:
    values: dict[str, object] = {
        "operation_id": operation_id,
        "workspace_rel": "job",
        "source_paths_rel": ("inputs/BANDS_1.dat",),
        "output_dir_rel": "outputs/postprocess",
        "plot_emin": -2.0,
        "plot_emax": 2.0,
        "save_data": True,
        "save_plot": True,
    }
    values.update(updates)
    return BandPostprocessRequest(**values)


def _dos_request(operation_id: str, **updates: object) -> DosPostprocessRequest:
    values: dict[str, object] = {
        "operation_id": operation_id,
        "workspace_rel": "job",
        "dos_paths_rel": ("inputs/DOS1_smearing.dat",),
        "output_dir_rel": "outputs/postprocess",
        "plot_emin": -2.0,
        "plot_emax": 2.0,
        "save_data": True,
        "save_plot": False,
    }
    values.update(updates)
    return DosPostprocessRequest(**values)


def _event_files(workspace: Workspace) -> list[Path]:
    return sorted((workspace.reports_dir / "events").glob("*.json"))


def test_band_service_persists_relative_input_output_and_report_artifacts(tmp_path: Path) -> None:
    workspace = _band_workspace(tmp_path)
    request = _band_request(_operation_id(300))

    result = PostprocessServiceSet.default(workspace_root=tmp_path).band.postprocess(request)

    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.execution == "not_run"
    assert result.envelope.status.collection == "complete"
    assert result.envelope.status.scientific == "unassessed"
    assert str(tmp_path) not in json.dumps(result.to_dict(), sort_keys=True)

    by_path = {artifact.path_rel: artifact for artifact in result.envelope.artifacts}
    assert by_path["inputs/BANDS_1.dat"].role == "input"
    assert by_path["outputs/postprocess/band.dat"].role == "output"
    assert by_path["outputs/postprocess/band.png"].role == "output"
    report_rel = f"reports/postprocess/{request.operation_id}.json"
    assert by_path[report_rel].role == "output"
    for path_rel, artifact in by_path.items():
        path = workspace.root / path_rel
        assert path.is_file()
        assert artifact.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
        assert artifact.size_bytes == path.stat().st_size

    assert result.envelope.diagnostics["summary"]["num_points"] == 3
    assert any(observation.name == "numeric_rows" for observation in result.observations)
    assert len(_event_files(workspace)) == 1
    event = json.loads(_event_files(workspace)[0].read_text(encoding="utf-8"))
    assert event["payload"] == result.to_dict()
    assert json.loads((workspace.root / report_rel).read_text(encoding="utf-8"))["summary"]["num_points"] == 3


def test_dos_service_keeps_optional_pdos_absence_as_partial_collection(tmp_path: Path) -> None:
    workspace = _dos_workspace(tmp_path)
    request = _dos_request(_operation_id(301), include_tdos=True, include_pdos=True)

    result = PostprocessServiceSet.default(workspace_root=tmp_path).dos.postprocess(request)

    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.execution == "not_run"
    assert result.envelope.status.collection == "partial"
    assert result.envelope.to_dict()["diagnostics"]["missing_families"] == ["pdos"]
    assert "pdos" not in result.envelope.diagnostics["parsed_families"]
    assert {artifact.path_rel for artifact in result.envelope.artifacts} >= {
        "inputs/DOS1_smearing.dat",
        "outputs/postprocess/DOS.dat",
    }
    assert not (workspace.root / "outputs/postprocess/PDOS.dat").exists()
    assert len(_event_files(workspace)) == 1


def test_dos_service_records_declared_pdos_and_tdos_as_input_artifacts(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "job")
    workspace.ensure_layout()
    write_sample_dos_family_artifacts(workspace.inputs_dir)
    request = _dos_request(
        _operation_id(311),
        pdos_path_rel="inputs/PDOS",
        tdos_path_rel="inputs/TDOS",
        include_tdos=True,
        include_pdos=True,
    )

    result = PostprocessServiceSet.default(workspace_root=tmp_path).dos.postprocess(request)

    assert isinstance(result, OperationOutcome)
    inputs = {
        artifact.path_rel: artifact
        for artifact in result.envelope.artifacts
        if artifact.role == "input"
    }
    assert set(inputs) == {"inputs/DOS1_smearing.dat", "inputs/PDOS", "inputs/TDOS"}
    assert result.envelope.status.collection == "complete"


def test_dos_service_reports_missing_output_when_no_optional_family_is_usable(tmp_path: Path) -> None:
    workspace = _dos_workspace(tmp_path)
    request = _dos_request(
        _operation_id(302),
        include_tdos=False,
        include_pdos=True,
        pdos_path_rel=None,
    )

    result = PostprocessServiceSet.default(workspace_root=tmp_path).dos.postprocess(request)

    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.execution == "not_run"
    assert result.envelope.status.collection == "missing_output"
    assert result.envelope.to_dict()["diagnostics"]["missing_families"] == ["pdos"]
    assert len(_event_files(workspace)) == 1


def test_parser_failure_is_an_admitted_partial_outcome_and_does_not_touch_upstream_events(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "job")
    workspace.ensure_layout()
    source = workspace.inputs_dir / "BANDS_bad.dat"
    source.write_text("# no numeric rows\nnot a table\n", encoding="utf-8")
    upstream_payload = {"kind": "execute", "status": "completed"}
    workspace.append_operation_event("execute", upstream_payload)
    request = _band_request(_operation_id(303), source_paths_rel=("inputs/BANDS_bad.dat",))

    result = PostprocessServiceSet.default(workspace_root=tmp_path).band.postprocess(request)

    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.execution == "not_run"
    assert result.envelope.status.collection == "partial"
    assert result.envelope.status.scientific == "unassessed"
    assert "numeric rows" in result.envelope.diagnostics["parse_error"]
    assert len(_event_files(workspace)) == 2
    assert all("band.dat" not in path.name for path in _event_files(workspace))
    operations = {
        json.loads(path.read_text(encoding="utf-8"))["operation"]
        for path in _event_files(workspace)
    }
    assert operations == {"execute", "postprocess"}


def test_missing_declared_source_is_precondition_after_durable_admission(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "job")
    workspace.ensure_layout()
    request = _band_request(_operation_id(304))

    result = PostprocessServiceSet.default(workspace_root=tmp_path).band.postprocess(request)

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "precondition.missing"
    assert not _event_files(workspace)
    assert (workspace.reports_dir / "claims" / f"{request.operation_id}.json").is_file()
    assert not (workspace.root / "outputs/postprocess").exists()


def test_declared_source_disappearing_after_admission_is_persisted_as_missing_output(
    tmp_path: Path,
) -> None:
    workspace = _band_workspace(tmp_path)
    request = _band_request(_operation_id(314), save_plot=False)
    source = workspace.root / "inputs/BANDS_1.dat"

    def unlinking_algorithm(
        source_paths: object, output_dir: Path, **kwargs: object
    ) -> ExplicitPostprocessResult:
        del output_dir, kwargs
        paths = tuple(source_paths)
        Path(paths[0]).unlink()
        return ExplicitPostprocessResult(
            summary={"num_points": 1},
            diagnostics={"source_count": 1},
            generated_paths=(),
        )

    result = PostprocessServiceSet(
        workspace_root=tmp_path, band_algorithm=unlinking_algorithm
    ).band.postprocess(request)

    assert isinstance(result, OperationOutcome)
    assert result.envelope.status == OperationStatus(
        execution="not_run", scientific="unassessed", collection="missing_output"
    )
    assert result.envelope.to_dict()["diagnostics"]["missing_source_paths_rel"] == [
        "inputs/BANDS_1.dat"
    ]
    assert str(tmp_path) not in json.dumps(result.to_dict(), sort_keys=True)
    assert {artifact.path_rel for artifact in result.envelope.artifacts} == {
        f"reports/postprocess/{request.operation_id}.json",
    }
    assert len(_event_files(workspace)) == 1
    assert not source.exists()


def test_repeated_operation_id_is_rejected_without_mutating_domain_files(tmp_path: Path) -> None:
    workspace = _band_workspace(tmp_path)
    request = _band_request(_operation_id(305), save_plot=False)
    services = PostprocessServiceSet.default(workspace_root=tmp_path)
    first = services.band.postprocess(request)
    assert isinstance(first, OperationOutcome)
    before_source = (workspace.inputs_dir / "BANDS_1.dat").read_bytes()
    before_output = (workspace.root / "outputs/postprocess/band.dat").read_bytes()

    second = services.band.postprocess(request)

    assert isinstance(second, ForgeErrorEnvelope)
    assert second.error_class == "operation.conflict"
    assert (workspace.inputs_dir / "BANDS_1.dat").read_bytes() == before_source
    assert (workspace.root / "outputs/postprocess/band.dat").read_bytes() == before_output
    assert len(_event_files(workspace)) == 1


def test_source_symlink_escape_is_rejected_before_admission(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "job")
    workspace.ensure_layout()
    outside = tmp_path / "outside.dat"
    outside.write_text("0 -1 1\n", encoding="utf-8")
    (workspace.inputs_dir / "escaped.dat").symlink_to(outside)
    request = _band_request(_operation_id(306), source_paths_rel=("inputs/escaped.dat",))

    result = PostprocessServiceSet.default(workspace_root=tmp_path).band.postprocess(request)

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.path"
    assert not workspace.reports_dir.joinpath("events").exists()
    assert not workspace.reports_dir.joinpath("claims").exists()


def test_output_source_collision_and_reserved_audit_directory_are_rejected(tmp_path: Path) -> None:
    workspace = _band_workspace(tmp_path)
    (workspace.inputs_dir / "band.dat").write_text("0 -1 1\n", encoding="utf-8")
    services = PostprocessServiceSet.default(workspace_root=tmp_path)

    collision = services.band.postprocess(
        _band_request(_operation_id(307), source_paths_rel=("inputs/band.dat",), output_dir_rel="inputs")
    )
    reserved = services.band.postprocess(
        _band_request(_operation_id(308), output_dir_rel="reports/events")
    )

    assert isinstance(collision, ForgeErrorEnvelope)
    assert collision.error_class == "request.invalid"
    assert isinstance(reserved, ForgeErrorEnvelope)
    assert reserved.error_class == "request.path"
    assert not (workspace.reports_dir / "events" / f"{_operation_id(308)}-postprocess.json").exists()


def test_algorithm_oserror_maps_to_persistence_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _band_workspace(tmp_path)
    request = _band_request(_operation_id(312), save_plot=False)

    def fail_algorithm(*args: object, **kwargs: object) -> object:
        raise PermissionError("destination is not writable")

    monkeypatch.setattr("abacus_forge.postprocess_services.process_band_files", fail_algorithm)
    result = PostprocessServiceSet.default(workspace_root=tmp_path).band.postprocess(request)

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "persistence.failure"
    assert exit_code_for(result) == 5
    assert not _event_files(workspace)


def test_missing_declared_generated_target_is_audited_as_missing_output(tmp_path: Path) -> None:
    workspace = _band_workspace(tmp_path)
    request = _band_request(_operation_id(313), save_plot=False)

    def no_write_algorithm(
        source_paths: object, output_dir: Path, **kwargs: object
    ) -> ExplicitPostprocessResult:
        del source_paths, kwargs
        return ExplicitPostprocessResult(
            summary={"num_points": 1},
            diagnostics={"source_count": 1},
            generated_paths=(output_dir / "band.dat",),
        )

    result = PostprocessServiceSet(
        workspace_root=tmp_path, band_algorithm=no_write_algorithm
    ).band.postprocess(request)

    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.collection == "missing_output"
    assert {artifact.path_rel for artifact in result.envelope.artifacts} == {
        "inputs/BANDS_1.dat",
        f"reports/postprocess/{request.operation_id}.json",
    }
    assert len(_event_files(workspace)) == 1


def test_algorithm_generated_path_is_rejected_when_no_outputs_are_requested(tmp_path: Path) -> None:
    workspace = _band_workspace(tmp_path)
    request = _band_request(_operation_id(315), save_data=False, save_plot=False)

    def undeclared_output_algorithm(
        source_paths: object, output_dir: Path, **kwargs: object
    ) -> ExplicitPostprocessResult:
        del source_paths, kwargs
        return ExplicitPostprocessResult(
            summary={"num_points": 1},
            diagnostics={"source_count": 1},
            generated_paths=(output_dir / "band.dat",),
        )

    result = PostprocessServiceSet(
        workspace_root=tmp_path, band_algorithm=undeclared_output_algorithm
    ).band.postprocess(request)

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.invalid"
    assert not _event_files(workspace)


def test_service_set_rejects_mismatched_typed_requests(tmp_path: Path) -> None:
    _band_workspace(tmp_path)
    _dos_workspace(tmp_path)
    services = PostprocessServiceSet.default(workspace_root=tmp_path)

    band_result = services.band.postprocess(_dos_request(_operation_id(309)))
    dos_result = services.dos.postprocess(_band_request(_operation_id(310)))

    assert isinstance(band_result, ForgeErrorEnvelope)
    assert band_result.error_class == "request.invalid"
    assert isinstance(dos_result, ForgeErrorEnvelope)
    assert dos_result.error_class == "request.invalid"
