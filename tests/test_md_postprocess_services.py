import json
from pathlib import Path

from abacus_forge import ForgeErrorEnvelope, MdPostprocessRequest, MdPostprocessServiceSet, OperationOutcome
from abacus_forge.md_postprocess import MdPostprocessResult


def _request(number=700, **updates):
    values = {"operation_id": f"123e4567-e89b-42d3-a456-426614174{number:03d}", "workspace_rel": "job", "trajectory_path_rel": "inputs/traj.xyz", "analysis": ("msd_diffusion",), "parameters": {"timestep": 1.0, "save_plot": False}}
    values.update(updates)
    return MdPostprocessRequest(**values)


def test_md_service_persists_facts_artifacts_and_one_event(tmp_path: Path):
    root = tmp_path / "job"; (root / "inputs").mkdir(parents=True)
    (root / "inputs/traj.xyz").write_text("2\nframe\nH 0 0 0\nO 1 0 0\n2\nframe\nH .1 0 0\nO 1.1 0 0\n", encoding="utf-8")
    result = MdPostprocessServiceSet.default(workspace_root=tmp_path).postprocess.postprocess(_request())
    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.scientific == "unassessed"
    assert result.envelope.status.collection == "complete"
    assert {item.role for item in result.envelope.artifacts} == {"input", "provenance_manifest", "output"}
    assert (root / "outputs/md-postprocess/trajectory_source.json").is_file()
    assert len(list((root / "reports/events").glob("*.json"))) == 1
    assert str(tmp_path) not in json.dumps(result.to_dict())


def test_missing_trajectory_is_admitted_and_returns_precondition(tmp_path: Path):
    result = MdPostprocessServiceSet.default(workspace_root=tmp_path).postprocess.postprocess(_request(701))
    assert result.error_class == "precondition.missing"


def test_fake_incomplete_result_is_partial_and_missing_manifest_is_repaired(tmp_path: Path):
    root = tmp_path / "job"; (root / "inputs").mkdir(parents=True)
    trajectory = root / "inputs/traj.xyz"
    trajectory.write_text("1\nf\nH 0 0 0\n", encoding="utf-8")
    def fake(*args, **kwargs):
        return MdPostprocessResult(summary={}, diagnostics={}, results={"msd_diffusion": {}}, sampling={"start": 0, "end": 1, "stride": 1, "frame_count": 1}, generated_files=())
    result = MdPostprocessServiceSet(workspace_root=tmp_path, algorithm=fake).postprocess.postprocess(_request(702))
    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.collection == "missing_output"
    assert any(check.status == "warning" for check in result.envelope.checks)
    assert not (root / "outputs/md-postprocess/analysis.json").is_file()


def test_fake_duplicate_or_reserved_outputs_are_rejected(tmp_path: Path):
    root = tmp_path / "job"; (root / "inputs").mkdir(parents=True)
    (root / "inputs/traj.xyz").write_text("1\nf\nH 0 0 0\n", encoding="utf-8")
    def duplicate(*args, **kwargs):
        return MdPostprocessResult({}, {}, {"msd_diffusion": {}}, {"start": 0, "end": 1, "stride": 1, "frame_count": 1}, ("analysis.json", "analysis.json"))
    result = MdPostprocessServiceSet(workspace_root=tmp_path, algorithm=duplicate).postprocess.postprocess(_request(703))
    assert result.error_class == "request.invalid"
    def reserved(*args, **kwargs):
        return MdPostprocessResult({}, {}, {"msd_diffusion": {}}, {"start": 0, "end": 1, "stride": 1, "frame_count": 1}, ("trajectory_source.json",))
    result = MdPostprocessServiceSet(workspace_root=tmp_path, algorithm=reserved).postprocess.postprocess(_request(704))
    assert result.error_class == "request.path"


def test_fake_algorithm_io_is_persistence_failure(tmp_path: Path):
    root = tmp_path / "job"; (root / "inputs").mkdir(parents=True)
    (root / "inputs/traj.xyz").write_text("1\nf\nH 0 0 0\n", encoding="utf-8")
    def broken(*args, **kwargs): raise OSError("cannot write output")
    result = MdPostprocessServiceSet(workspace_root=tmp_path, algorithm=broken).postprocess.postprocess(_request(705))
    assert result.error_class == "persistence.failure"


def test_report_leaf_symlink_is_rejected_before_any_domain_write(tmp_path: Path):
    root = tmp_path / "job"
    (root / "inputs").mkdir(parents=True)
    (root / "inputs/traj.xyz").write_text("1\nf\nH 0 0 0\n", encoding="utf-8")
    report_dir = root / "reports/postprocess"
    report_dir.mkdir(parents=True)
    old_report = report_dir / "old.json"
    old_report.write_text("old\n", encoding="utf-8")
    request = _request(706)
    report = report_dir / f"{request.operation_id}.json"
    report.symlink_to(old_report)

    result = MdPostprocessServiceSet.default(workspace_root=tmp_path).postprocess.postprocess(request)

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.path"
    assert old_report.read_text(encoding="utf-8") == "old\n"
    assert not (root / "outputs").exists()
    assert not (root / "reports/events").exists()


def test_input_symlink_inside_workspace_is_rejected_as_non_exact_path(tmp_path: Path):
    root = tmp_path / "job"
    (root / "inputs").mkdir(parents=True)
    actual = root / "inputs/actual.xyz"
    actual.write_text("1\nf\nH 0 0 0\n", encoding="utf-8")
    (root / "inputs/traj.xyz").symlink_to(actual)

    result = MdPostprocessServiceSet.default(workspace_root=tmp_path).postprocess.postprocess(_request(707))

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.path"
    assert not (root / "reports/events").exists()


def test_stale_declared_outputs_are_not_counted_as_this_operation(tmp_path: Path):
    root = tmp_path / "job"
    (root / "inputs").mkdir(parents=True)
    (root / "inputs/traj.xyz").write_text("1\nf\nH 0 0 0\n", encoding="utf-8")
    output = root / "outputs/md-postprocess"
    output.mkdir(parents=True)
    (output / "msd.txt").write_text("stale\n", encoding="utf-8")
    (output / "analysis.json").write_text("{\"stale\": true}\n", encoding="utf-8")

    def no_write(*args, **kwargs):
        return MdPostprocessResult(
            summary={}, diagnostics={}, results={"msd_diffusion": {}},
            sampling={"start": 0, "end": 1, "stride": 1, "frame_count": 1},
            generated_files=(),
        )

    result = MdPostprocessServiceSet(workspace_root=tmp_path, algorithm=no_write).postprocess.postprocess(_request(708))

    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.collection == "missing_output"
    assert "outputs/md-postprocess/msd.txt" not in {artifact.path_rel for artifact in result.envelope.artifacts}


def test_algorithm_cannot_publish_arbitrary_output_names(tmp_path: Path):
    root = tmp_path / "job"
    (root / "inputs").mkdir(parents=True)
    (root / "inputs/traj.xyz").write_text("1\nf\nH 0 0 0\n", encoding="utf-8")

    def arbitrary(*args, **kwargs):
        output = Path(kwargs["output_dir"])
        output.mkdir(parents=True, exist_ok=True)
        (output / "notes.txt").write_text("not a canonical result\n", encoding="utf-8")
        return MdPostprocessResult(
            summary={}, diagnostics={}, results={"msd_diffusion": {}},
            sampling={"start": 0, "end": 1, "stride": 1, "frame_count": 1},
            generated_files=("notes.txt",),
        )

    result = MdPostprocessServiceSet(workspace_root=tmp_path, algorithm=arbitrary).postprocess.postprocess(_request(709))

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.invalid"


def test_nonfinite_algorithm_facts_are_rejected_without_event(tmp_path: Path):
    root = tmp_path / "job"
    (root / "inputs").mkdir(parents=True)
    (root / "inputs/traj.xyz").write_text("1\nf\nH 0 0 0\n", encoding="utf-8")

    def nonfinite(*args, **kwargs):
        return MdPostprocessResult(
            summary={"bad": float("nan")}, diagnostics={}, results={},
            sampling={"start": 0, "end": 1, "stride": 1, "frame_count": 1},
            generated_files=(),
        )

    result = MdPostprocessServiceSet(workspace_root=tmp_path, algorithm=nonfinite).postprocess.postprocess(_request(710))

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.invalid"
    assert not (root / "reports/events").exists()


def test_malformed_trajectory_is_precondition_after_admission(tmp_path: Path):
    root = tmp_path / "job"
    (root / "inputs").mkdir(parents=True)
    (root / "inputs/traj.xyz").write_text("not an XYZ trajectory\n", encoding="utf-8")

    result = MdPostprocessServiceSet.default(workspace_root=tmp_path).postprocess.postprocess(_request(711))

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "precondition.missing"
    assert (root / "reports/claims" / "123e4567-e89b-42d3-a456-426614174711.json").is_file()
    assert not (root / "reports/events").exists()


def test_rdf_service_tracks_each_declared_pair_as_output(tmp_path: Path):
    root = tmp_path / "job"
    (root / "inputs").mkdir(parents=True)
    (root / "inputs/traj.xyz").write_text(
        '3\nLattice="4 0 0 0 4 0 0 0 4" Properties=species:S:1:pos:R:3 pbc="T T T"\n'
        "H 0 0 0\nO 1 0 0\nC 1.2 0 0\n",
        encoding="utf-8",
    )
    request = _request(712, analysis=("rdf",), parameters={"elements": ["H-O", "H-C"], "rmax": 1.5, "nbins": 3, "save_plot": False})

    result = MdPostprocessServiceSet.default(workspace_root=tmp_path).postprocess.postprocess(request)

    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.collection == "complete"
    paths = {artifact.path_rel for artifact in result.envelope.artifacts}
    assert "outputs/md-postprocess/rdf_H_O.txt" in paths
    assert "outputs/md-postprocess/rdf_H_C.txt" in paths
    assert "outputs/md-postprocess/analysis.json" in paths
