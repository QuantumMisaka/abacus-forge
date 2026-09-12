import io
import json
from pathlib import Path

from abacus_forge import MdPostprocessRequest, MdPostprocessServiceSet, OperationOutcome
from abacus_forge.machine_cli import run_machine_cli


def test_machine_cli_routes_typed_md_postprocess(tmp_path: Path):
    root = tmp_path / "job"
    (root / "inputs").mkdir(parents=True)
    (root / "inputs/traj.xyz").write_text("2\nframe\nH 0 0 0\nO 1 0 0\n2\nframe\nH .1 0 0\nO 1.1 0 0\n", encoding="utf-8")
    request = {"schema_version": "forge.request/v1", "capability": "md", "operation": "postprocess", "operation_id": "123e4567-e89b-42d3-a456-426614174799", "workspace_rel": "job", "trajectory_path_rel": "inputs/traj.xyz", "analysis": ["msd_diffusion"], "output_dir_rel": "outputs/md-postprocess", "start": 0, "end": None, "stride": 1, "parameters": {"timestep": 1.0, "save_plot": False}}
    stdout, stderr = io.StringIO(), io.StringIO()
    exit_code = run_machine_cli(["operation", "postprocess", "--stdin"], stdin=io.StringIO(json.dumps(request)), stdout=stdout, stderr=stderr, cwd=tmp_path)
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["envelope"]["operation"] == "postprocess"
    assert payload["envelope"]["status"]["scientific"] == "unassessed"
    assert stderr.getvalue() == ""


def _parity_payload(operation_id: str) -> dict[str, object]:
    return {
        "schema_version": "forge.request/v1",
        "capability": "md",
        "operation": "postprocess",
        "operation_id": operation_id,
        "workspace_rel": "job",
        "trajectory_path_rel": "inputs/traj.xyz",
        "analysis": ["msd_diffusion"],
        "output_dir_rel": "outputs/md-postprocess",
        "start": 0,
        "end": None,
        "stride": 1,
        "parameters": {"timestep": 1.0, "save_data": True, "save_plot": False},
    }


def _write_parity_workspace(root: Path) -> None:
    (root / "job/inputs").mkdir(parents=True)
    (root / "job/inputs/traj.xyz").write_text(
        "2\nframe 0\nH 0 0 0\nO 1 0 0\n"
        "2\nframe 1\nH .1 0 0\nO 1.1 0 0\n",
        encoding="utf-8",
    )


def _normalize_identity(value: object, operation_id: str) -> object:
    if isinstance(value, str):
        return value.replace(operation_id, "<operation-id>")
    if isinstance(value, list):
        return [_normalize_identity(item, operation_id) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_identity(item, operation_id) for key, item in value.items()}
    return value


def test_machine_request_file_and_api_share_facts_and_output_bytes(tmp_path: Path):
    api_root, cli_root = tmp_path / "api", tmp_path / "cli"
    _write_parity_workspace(api_root)
    _write_parity_workspace(cli_root)
    api_id = "123e4567-e89b-42d3-a456-426614174800"
    cli_id = "123e4567-e89b-42d3-a456-426614174801"
    api_request = MdPostprocessRequest.from_dict(_parity_payload(api_id))
    direct = MdPostprocessServiceSet.default(workspace_root=api_root).postprocess.postprocess(api_request)
    assert isinstance(direct, OperationOutcome)

    request_file = cli_root / "request.json"
    request_file.write_text(json.dumps(_parity_payload(cli_id)), encoding="utf-8")
    stdout, stderr = io.StringIO(), io.StringIO()
    code = run_machine_cli(
        ["operation", "postprocess", "--request", "request.json"],
        stdin=io.StringIO(""), stdout=stdout, stderr=stderr, cwd=cli_root,
    )
    assert code == 0
    assert stderr.getvalue() == ""
    machine = OperationOutcome.from_dict(json.loads(stdout.getvalue()))
    assert _normalize_identity(machine.to_dict(), cli_id) == _normalize_identity(direct.to_dict(), api_id)
    assert (cli_root / "job/outputs/md-postprocess/msd.txt").read_bytes() == (api_root / "job/outputs/md-postprocess/msd.txt").read_bytes()
    assert (cli_root / "job/reports/postprocess" / f"{cli_id}.json").read_bytes() == (api_root / "job/reports/postprocess" / f"{api_id}.json").read_bytes()


def test_machine_missing_trajectory_is_exit_three_and_never_prompts(tmp_path: Path):
    payload = _parity_payload("123e4567-e89b-42d3-a456-426614174802")
    stdout, stderr = io.StringIO(), io.StringIO()
    code = run_machine_cli(
        ["operation", "postprocess", "--stdin"],
        stdin=io.StringIO(json.dumps(payload)), stdout=stdout, stderr=stderr, cwd=tmp_path,
    )
    assert code == 3
    assert json.loads(stdout.getvalue())["error"]["class"] == "precondition.missing"
    assert stderr.getvalue() == ""
    assert "prompt" not in stdout.getvalue().lower()


def test_machine_invalid_mode_is_exit_two_without_domain_files(tmp_path: Path):
    payload = _parity_payload("123e4567-e89b-42d3-a456-426614174803")
    payload["analysis"] = ["msd"]
    stdout, stderr = io.StringIO(), io.StringIO()
    code = run_machine_cli(
        ["operation", "postprocess", "--stdin"],
        stdin=io.StringIO(json.dumps(payload)), stdout=stdout, stderr=stderr, cwd=tmp_path,
    )
    assert code == 2
    assert json.loads(stdout.getvalue())["error"]["class"] == "request.schema"
    assert stderr.getvalue() == ""
    assert not (tmp_path / "job").exists()


def test_machine_invalid_md_parameters_are_schema_errors_before_admission(tmp_path: Path):
    payload = _parity_payload("123e4567-e89b-42d3-a456-426614174805")
    payload["parameters"] = {"save_plot": "false"}
    stdout, stderr = io.StringIO(), io.StringIO()

    code = run_machine_cli(
        ["operation", "postprocess", "--stdin"],
        stdin=io.StringIO(json.dumps(payload)), stdout=stdout, stderr=stderr, cwd=tmp_path,
    )

    assert code == 2
    assert json.loads(stdout.getvalue())["error"]["class"] == "request.schema"
    assert stderr.getvalue() == ""
    assert not (tmp_path / "job").exists()


def test_machine_missing_md_timestep_is_schema_error_before_admission(tmp_path: Path):
    payload = _parity_payload("123e4567-e89b-42d3-a456-426614174806")
    payload["parameters"] = {"save_plot": False}
    stdout, stderr = io.StringIO(), io.StringIO()

    code = run_machine_cli(
        ["operation", "postprocess", "--stdin"],
        stdin=io.StringIO(json.dumps(payload)), stdout=stdout, stderr=stderr, cwd=tmp_path,
    )

    assert code == 2
    assert json.loads(stdout.getvalue())["error"]["class"] == "request.schema"
    assert stderr.getvalue() == ""
    assert not (tmp_path / "job").exists()


def test_machine_output_directory_file_is_exit_five(tmp_path: Path):
    _write_parity_workspace(tmp_path)
    output = tmp_path / "job/outputs/md-postprocess"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("not a directory\n", encoding="utf-8")
    stdout, stderr = io.StringIO(), io.StringIO()
    code = run_machine_cli(
        ["operation", "postprocess", "--stdin"],
        stdin=io.StringIO(json.dumps(_parity_payload("123e4567-e89b-42d3-a456-426614174804"))),
        stdout=stdout, stderr=stderr, cwd=tmp_path,
    )
    assert code == 5
    assert json.loads(stdout.getvalue())["error"]["class"] == "persistence.failure"
    assert stderr.getvalue() == ""
