from __future__ import annotations

import json
from pathlib import Path

import pytest

from abacus_forge import collect
from abacus_forge.workspace import Workspace


def test_collect_matches_abacustest_reference_for_force_stress_and_pressure(tmp_path: Path) -> None:
    fixture_root = Path(
        "/home/pku-jianghong/liuzhaoqing/work/sidereus/paimon/repo/abacus-test/tests/test_collectdata/abacus-scf"
    )
    reference = json.loads((fixture_root / "abacus.json").read_text(encoding="utf-8"))["output"][0]

    workspace = Workspace(tmp_path / "reference-case").ensure_layout()
    workspace.write_text("inputs/INPUT", (fixture_root / "INPUT").read_text(encoding="utf-8"))
    workspace.write_text("inputs/KPT", "K_POINTS\n0\nGamma\n5 5 2 0 0 0\n")
    workspace.write_text(
        "inputs/STRU",
        """ATOMIC_SPECIES
Si 28.085500 Si.upf

LATTICE_CONSTANT
1.0
LATTICE_CONSTANT_UNIT
Angstrom

LATTICE_VECTORS
8.3004 0.0 0.0
0.0 8.3004 0.0
0.0 0.0 25.362243471279523

ATOMIC_POSITIONS
Direct
Si
0.0
1
0.0 0.0 0.0 m 1 1 1
""",
    )
    workspace.write_text("outputs/OUT.ABACUS/running_scf.log", (fixture_root / "OUT.ABACUS" / "running_scf.log").read_text(encoding="utf-8"))
    workspace.write_text("outputs/out.log", (fixture_root / "out.log").read_text(encoding="utf-8"))
    workspace.write_text("outputs/OUT.ABACUS/INPUT", (fixture_root / "OUT.ABACUS" / "INPUT").read_text(encoding="utf-8"))
    workspace.write_text("outputs/stderr.log", "")
    workspace.write_json("outputs/OUT.ABACUS/time.json", json.loads((fixture_root / "time.json").read_text(encoding="utf-8")))

    result = collect(workspace)

    expected_force = [value for row in reference["force"] for value in row]
    expected_stress = [value for row in reference["stress"] for value in row]
    volume = 8.3004 * 8.3004 * 25.362243471279523
    kbar_to_ev_per_angstrom3 = 3.398927420868445e-6 * 27.211396132 / 0.52917721092**3
    expected_virial = [value * volume * kbar_to_ev_per_angstrom3 for value in expected_stress]

    assert result.status == "completed"
    assert result.diagnostics["selected_log_path"].endswith("running_scf.log")
    assert result.diagnostics["selected_log_reason"] == "matched-input-calculation:running_scf.log"
    assert any(path.endswith("out.log") for path in result.diagnostics["ignored_log_paths"])
    assert result.inputs_snapshot["KPT_PARSED"] == {"mode": "mesh", "mesh": [5, 5, 2], "shifts": [0, 0, 0]}
    assert len(result.metrics["force"]) == 81
    assert len(result.metrics["forces"]) == 1
    assert result.metrics["force"][0] == pytest.approx(expected_force[0])
    assert result.metrics["force"][len(result.metrics["force"]) // 2] == pytest.approx(expected_force[len(expected_force) // 2])
    assert result.metrics["force"][-1] == pytest.approx(expected_force[-1])
    assert result.metrics["stress"] == pytest.approx(expected_stress)
    assert len(result.metrics["stresses"]) == 1
    assert result.metrics["stresses"][0] == pytest.approx(expected_stress)
    assert result.metrics["pressure"] == pytest.approx(-48.548971477133335)
    assert result.metrics["pressures"] == pytest.approx([-48.548971477133335])
    assert result.metrics["virial"][0] == pytest.approx(expected_virial[0])
    assert result.metrics["virial"][len(result.metrics["virial"]) // 2] == pytest.approx(expected_virial[len(expected_virial) // 2])
    assert result.metrics["virial"][-1] == pytest.approx(expected_virial[-1])
    assert len(result.metrics["virials"]) == 1
    assert result.metrics["virials"][0] == pytest.approx(expected_virial)
    assert result.metrics["total_time"] == pytest.approx(932.927)
