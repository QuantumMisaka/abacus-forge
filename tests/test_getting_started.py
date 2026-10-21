"""Check the public, engine-free path through an installed Forge environment."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]


def _installed_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    return env


def _bash_block(path: Path, index: int = 0) -> str:
    blocks = re.findall(r"```bash\n(.*?)\n```", path.read_text(encoding="utf-8"), re.S)
    return blocks[index]


def test_getting_started_script_reports_actual_statuses(tmp_path: Path) -> None:
    workspace = tmp_path / "from-script"
    process = subprocess.run(
        [sys.executable, "-I", str(ROOT / "examples" / "getting_started.py"),
         "--workspace", str(workspace), "--exercise-errors"],
        cwd=tmp_path, env=_installed_env(), text=True, capture_output=True, timeout=30,
    )
    assert process.returncode == 0, process.stderr
    result = json.loads(process.stdout)
    assert result["structure_file"] == "Si.cif"
    assert result["prepared_files"] == [
        "scf/inputs/INPUT", "scf/inputs/STRU", "scf/inputs/KPT"
    ]
    assert all((workspace / name).is_file() for name in result["prepared_files"])
    assert result["dry_run_status"] == {
        "execution": "skipped", "collection": "not_collected", "scientific": "unassessed"
    }
    assert result["engine_started"] is False
    assert result["missing_executable"]["error"]["class"] == "precondition.missing"
    assert result["missing_inputs"]["error"]["class"] == "precondition.missing"
    assert result["collect_without_engine_status"]["collection"] in (
        "missing_output", "partial"
    )


def test_documented_quickstart_and_agent_snippets(tmp_path: Path) -> None:
    env = _installed_env()
    readme_dir = tmp_path / "readme"
    readme_dir.mkdir()
    process = subprocess.run(
        ["bash", "-eu", "-c", _bash_block(ROOT / "README.md", 1)],
        cwd=readme_dir, env=env, text=True, capture_output=True, timeout=30,
    )
    assert process.returncode == 0, process.stderr
    assert "'execution': 'skipped'" in process.stdout
    assert (readme_dir / "forge-first-run" / "scf" / "inputs" / "STRU").is_file()

    quickstart = _bash_block(ROOT / "docs" / "quickstart.md")
    process = subprocess.run(
        ["bash", "-eu", "-c", quickstart], cwd=tmp_path, env=env,
        text=True, capture_output=True, timeout=30,
    )
    assert process.returncode == 0, process.stderr
    assert "'execution': 'skipped'" in process.stdout
    assert (tmp_path / "forge-first-run" / "scf" / "inputs" / "STRU").is_file()

    guide = ROOT / "docs" / "agents.md"
    for index in (0, 1):
        process = subprocess.run(
            ["bash", "-eu", "-c", _bash_block(guide, index)],
            cwd=tmp_path, env=env, text=True, capture_output=True, timeout=30,
        )
        assert process.returncode == 0, process.stderr
    result = json.loads(process.stdout)
    assert result["dry_run"] == {
        "execution": "skipped", "collection": "not_collected", "scientific": "unassessed"
    }
    assert result["missing_executable"] == "precondition.missing"
    assert result["collect_without_engine"] in ("missing_output", "partial")
