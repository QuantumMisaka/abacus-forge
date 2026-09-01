from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from abacus_forge.api import UnitSpec, collect_unit, execute_unit


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
    if executable_path.parent != Path() or executable_path.exists():
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
