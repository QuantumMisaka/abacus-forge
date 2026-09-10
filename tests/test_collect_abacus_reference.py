from __future__ import annotations

import json
from pathlib import Path

import pytest

from abacus_forge import collect
from abacus_forge.workspace import Workspace
from tests.support.reference_workspaces import FIXTURE_ROOT, copy_abacustest_scf_workspace, copy_native_md_workspace


def test_collect_matches_abacustest_reference_for_force_stress_and_pressure(tmp_path: Path) -> None:
    reference = json.loads((FIXTURE_ROOT / "abacus.json").read_text(encoding="utf-8"))["output"][0]

    workspace = copy_abacustest_scf_workspace(tmp_path / "reference-case")

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


def test_collect_prefers_last_native_final_energy_marker(tmp_path: Path) -> None:
    workspace = copy_abacustest_scf_workspace(tmp_path / "native-final-energy")
    path = workspace.outputs_dir / "OUT.ABACUS" / "running_scf.log"
    path.write_text(path.read_text(encoding="utf-8") +
                    "!FINAL_ETOT_IS -10.25 eV\n!FINAL_ETOT_IS -9.75 eV\n",
                    encoding="utf-8")

    result = collect(workspace)

    assert result.metrics["total_energy"] == pytest.approx(-9.75)


def test_collect_parses_native_md_rows_and_keeps_energy_families_separate(tmp_path: Path) -> None:
    result = collect(copy_native_md_workspace(tmp_path / "native-md"))
    factor = 13.605698

    assert result.metrics["total_energy"] == pytest.approx(-129.256631)
    assert result.metrics["md_last_total_energy"] == pytest.approx(-9.5 * factor)
    assert result.metrics["md_last_potential_energy"] == pytest.approx(-10.0 * factor)
    assert result.metrics["md_last_kinetic_energy"] == pytest.approx(0.5 * factor)
    assert result.metrics["md_last_temperature"] == pytest.approx(310.0)
    assert result.metrics["md_last_pressure"] == pytest.approx(3.0)
    assert result.metrics["md_dump_frames"] == 2
    assert result.metrics["md_dump_steps"] == 2
    assert result.diagnostics["native_md_block_complete"] is True


def test_collect_extracts_native_abacus_and_md_metrics(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "native-metrics").ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation md\n")
    workspace.write_text("inputs/KPT", "K_POINTS\n0\nGamma\n1 1 1 0 0 0\n")
    workspace.write_text(
        "outputs/stdout.log",
        "\n".join(
            [
                "ABACUS VERSION: 3.8.0",
                "TOTAL ENERGY = -6.0",
                "NATOM = 2",
                "NELEC = 8",
                "VOLUME = 20.0",
                "RELAX STEPS = 4",
                "LARGEST GRADIENT = 0.001",
                "DRHO_LAST = 1e-8",
                "SCF CONVERGED",
                "NORMAL END",
            ]
        )
        + "\n",
    )
    workspace.write_text("outputs/stderr.log", "")
    workspace.write_text("outputs/MD_dump", "STEP 1 TEMP 300 ETOT -5.9\nSTEP 2 TEMP 305 ETOT -6.0\n")

    result = collect(workspace)

    assert result.metrics["version"] == "3.8.0"
    assert result.metrics["natom"] == 2
    assert result.metrics["nelec"] == 8
    assert result.metrics["volume"] == 20.0
    assert result.metrics["energy_per_atom"] == -3.0
    assert result.metrics["relax_steps"] == 4
    assert result.metrics["largest_gradient"] == pytest.approx(0.001)
    assert result.metrics["drho_last"] == pytest.approx(1e-8)
    assert result.metrics["normal_end"] is True
    assert result.metrics["converge"] is True
    assert result.metrics["md_steps"] == 2
    assert result.metrics["md_last_temperature"] == 305
