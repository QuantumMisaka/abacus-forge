import io
import json
from pathlib import Path

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
