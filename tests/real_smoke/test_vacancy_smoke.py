from __future__ import annotations

import math
import os
import shutil
from pathlib import Path

import pytest

from abacus_forge.composite.properties import post_vacancy, prepare_vacancy, run_vacancy


_REAL_SMOKE_ENGINE_TIMEOUT_SECONDS = 1800.0


@pytest.mark.real_smoke
def test_vacancy_pack_machine_execute_and_collect(tmp_path: Path) -> None:
    """Run one pristine + one defect SCF through the real ABACUS process.

    The source workspace must already be a prepared Forge workspace (with
    ``inputs/INPUT``, ``inputs/STRU``, ``inputs/KPT`` and all pseudopotential
    or orbital assets).  A ``vacancy/ref_energy.txt`` file in the source is
    optional; when present its element energies let ``post_vacancy`` compute
    formation energies.  Missing environment values skip with a precise
    reason; an invalid supplied value fails rather than producing a pass.
    """
    source_value = os.environ.get("ABACUS_FORGE_VACANCY_SMOKE_WORKSPACE")
    executable = os.environ.get("ABACUS_FORGE_ABACUS_EXECUTABLE")
    if not source_value or not executable:
        pytest.skip("set ABACUS_FORGE_VACANCY_SMOKE_WORKSPACE and ABACUS_FORGE_ABACUS_EXECUTABLE")
    source = Path(source_value)
    if not source.is_dir():
        pytest.fail(f"ABACUS_FORGE_VACANCY_SMOKE_WORKSPACE is not a directory: {source}")
    executable_path = Path(executable)
    if executable_path.parent != Path():
        executable_ok = executable_path.is_file() and os.access(executable_path, os.X_OK)
    else:
        executable_ok = shutil.which(executable) is not None
    if not executable_ok:
        pytest.fail(f"ABACUS_FORGE_ABACUS_EXECUTABLE is not executable: {executable}")

    index_raw = os.environ.get("ABACUS_FORGE_VACANCY_SMOKE_INDEX", "1")
    try:
        vacancy_index = int(index_raw)
    except ValueError:
        pytest.fail(f"ABACUS_FORGE_VACANCY_SMOKE_INDEX is not an integer: {index_raw!r}")
    if vacancy_index < 1:
        pytest.fail(f"ABACUS_FORGE_VACANCY_SMOKE_INDEX must be >= 1: {vacancy_index}")

    workspace = tmp_path / "vacancy-smoke"
    shutil.copytree(source, workspace, symlinks=False)

    prepared = prepare_vacancy(workspace, vacancy_indices=[vacancy_index])
    assert prepared.status == "prepared", prepared.diagnostics
    assert prepared.summary.get("count") == 1

    ran = run_vacancy(
        workspace,
        executable=executable,
        mpi=1,
        omp=1,
        timeout_seconds=_REAL_SMOKE_ENGINE_TIMEOUT_SECONDS,
    )
    assert ran.status == "completed", ran.summary
    assert ran.summary.get("failed") == 0
    assert ran.summary.get("total") == 2

    posted = post_vacancy(workspace)
    assert posted.status in {"completed", "degraded"}, posted.diagnostics
    formation = posted.summary.get("formation_energies")
    assert isinstance(formation, list) and len(formation) == 1
    entry = formation[0]
    assert entry["defect"] == f"defect_{vacancy_index:03d}"
    pristine_energy = posted.summary.get("reference_energies") or {}
    assert isinstance(pristine_energy, dict)

    subtasks = {item.get("role", ""): item for item in prepared.subtasks}
    assert "pristine" in subtasks
    assert any(key.startswith("defect") for key in subtasks)

    for subtask in posted.subtasks:
        metrics = subtask.get("metrics", {})
        total_energy = metrics.get("total_energy")
        if total_energy is not None:
            assert isinstance(total_energy, (int, float))
            assert math.isfinite(float(total_energy))

    # The formation energy is a parser-arithmetic fact, not a scientific
    # acceptance decision.  When reference energies are absent the formation
    # value is None and the pack reports degraded; both are acceptable here.
    for item in formation:
        value = item.get("formation_energy_ev")
        if value is not None:
            assert math.isfinite(float(value))
