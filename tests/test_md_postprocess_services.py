import json
from pathlib import Path

from abacus_forge import MdPostprocessRequest, MdPostprocessServiceSet, OperationOutcome
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
