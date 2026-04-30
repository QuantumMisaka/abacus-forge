from __future__ import annotations

import json
import stat
from pathlib import Path

import numpy as np
import pytest
from ase import Atoms
from ase.io import write as ase_write

from abacus_forge import AbacusStructure, LocalRunner, Workspace, collect, export, perturb_structure, prepare, run
from abacus_forge.band_data import BandData, write_sample_band_artifacts
from abacus_forge.dos_data import DOSData, PDOSData, write_sample_dos_artifacts, write_sample_pdos_artifacts
from abacus_forge.sample_outputs import write_sample_analysis_outputs
from abacus_forge.structure_recognition import detect_structure_format


def test_prepare_creates_task_aware_workspace_with_assets(tmp_path: Path) -> None:
    structure = Atoms(
        symbols=["Si", "Si"],
        positions=[[0.0, 0.0, 0.0], [1.3575, 1.3575, 1.3575]],
        cell=[[3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 18.0]],
        pbc=[True, True, True],
    )
    structure_path = tmp_path / "Si_layer.cif"
    ase_write(structure_path, structure)

    pseudo_dir = tmp_path / "pseudo"
    orbital_dir = tmp_path / "orb"
    pseudo_dir.mkdir()
    orbital_dir.mkdir()
    (pseudo_dir / "Si_ONCV.upf").write_text("pseudo", encoding="utf-8")
    (orbital_dir / "Si_gga.orb").write_text("orbital", encoding="utf-8")

    workspace = prepare(
        tmp_path / "case",
        task="dos",
        structure=structure_path,
        pseudo_path=pseudo_dir,
        orbital_path=orbital_dir,
        asset_mode="copy",
        parameters={"ecutwfc": 80},
        metadata={"label": "layer-dos"},
    )

    assert detect_structure_format(workspace.inputs_dir / "STRU") == "stru"
    input_text = (workspace.inputs_dir / "INPUT").read_text(encoding="utf-8")
    assert "calculation nscf" in input_text
    assert "out_dos 1" in input_text
    assert "dip_cor_flag 1" in input_text
    assert (workspace.inputs_dir / "Si_ONCV.upf").exists()
    assert (workspace.inputs_dir / "Si_gga.orb").exists()

    meta = json.loads(workspace.meta_path.read_text(encoding="utf-8"))
    assert meta["metadata"]["label"] == "layer-dos"
    assert meta["structure_metadata"]["structure_class"] == "layer"
    assert meta["validation"]["valid"] is True


def test_run_and_collect_parse_enhanced_metrics(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "run-case")
    structure = Atoms(
        symbols=["Si", "Si"],
        positions=[[0.0, 0.0, 0.0], [1.3575, 1.3575, 1.3575]],
        cell=[[5.43, 0.0, 0.0], [0.0, 5.43, 0.0], [0.0, 0.0, 5.43]],
        pbc=[True, True, True],
    )
    prepare(workspace, task="band", structure=structure, parameters={"ecutwfc": 60}, kpoints=[2, 2, 2])

    fake_abacus = tmp_path / "fake-abacus"
    fake_abacus.write_text(
        "#!/usr/bin/env python3\n"
        "import os\n"
        "print(f\"OMP = {os.environ.get('OMP_NUM_THREADS', 'missing')}\")\n"
        "print('TOTAL ENERGY = -10.5')\n"
        "print('FERMI ENERGY = 3.2')\n"
        "print('BAND GAP = 1.1')\n"
        "print('SCF STEPS = 12')\n"
        "print('SCF CONVERGED')\n",
        encoding="utf-8",
    )
    fake_abacus.chmod(fake_abacus.stat().st_mode | stat.S_IEXEC)

    result = run(workspace, runner=LocalRunner(executable=str(fake_abacus), omp_threads=4))
    workspace.write_text("outputs/BANDS_1.dat", "0.0 -1.0 0.5\n1.0 -0.8 0.7\n")
    workspace.write_text("outputs/DOS1_smearing.dat", "-10.0 0.0\n0.0 1.0\n")
    workspace.write_text("outputs/PDOS", "Si 0.4\n")
    workspace.write_json("outputs/OUT.ABACUS/time.json", {"total": 14.2})
    workspace.write_json("reports/metrics_relax.json", {"converged": True, "final_structure_available": True, "workflow_goal": "relax-band"})
    workspace.write_json("reports/metrics_band.json", {"band_gap": 1.1})
    final_structure = AbacusStructure.from_input(structure).swap_axes(0, 2)
    workspace.write_text("outputs/OUT.ABACUS/STRU_ION_D", final_structure.to_stru())

    collected = collect(workspace)

    assert result.status == "completed"
    assert result.diagnostics["omp_threads"] == 4
    assert collected.status == "completed"
    assert collected.metrics["converged"] is True
    assert collected.metrics["total_energy"] == -10.5
    assert collected.metrics["scf_steps"] == 12
    assert collected.metrics["total_time"] == 14.2
    assert collected.metrics["workflow_goal"] == "relax-band"
    assert collected.metrics["band_summary"]["num_points"] == 2
    assert collected.metrics["band_artifacts"][0].endswith("BANDS_1.dat")
    assert collected.metrics["dos_summary"]["points"] == 2
    assert collected.metrics["dos_artifacts"][0].endswith("DOS1_smearing.dat")
    assert collected.metrics["pdos_summary"]["pdos_file"].endswith("PDOS")
    assert collected.metrics["pdos_artifacts"][0].endswith("PDOS")
    assert collected.metrics["relax_metrics"]["final_structure_available"] is True
    assert collected.inputs_snapshot["INPUT"]["calculation"] == "nscf"
    assert collected.inputs_snapshot["KPT_PARSED"] == {"mode": "mesh", "mesh": [2, 2, 2], "shifts": [0, 0, 0]}
    assert collected.structure_snapshot is not None
    assert collected.structure_snapshot["formula"] == "Si2"
    assert collected.final_structure_snapshot is not None
    assert collected.final_structure_snapshot["source"].endswith("STRU_ION_D")
    assert collected.diagnostics["report_json_files"]
    assert "scf_converged" in collected.diagnostics["matched_converged_markers"]
    assert collected.diagnostics["matched_nonconverged_markers"] == []
    assert collected.diagnostics["time_json_absent"] is False
    assert any(path.endswith("stdout.log") for path in collected.diagnostics["log_paths"])
    assert collected.diagnostics["stderr_nonempty"] is False


def test_export_writes_extended_json_file(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "export-case")
    prepare(workspace, task="scf")
    workspace.write_text("outputs/stdout.log", "TOTAL ENERGY = -8.0\nSCF CONVERGED\n",)
    workspace.write_text("outputs/stderr.log", "")

    result = collect(workspace)
    output = tmp_path / "result.json"
    text = export(result, destination=output)
    payload = json.loads(text)

    assert output.exists()
    assert payload["metrics"]["total_energy"] == -8.0
    assert "inputs_snapshot" in payload
    assert "diagnostics" in payload


def test_sample_artifact_writers_roundtrip_through_data_helpers(tmp_path: Path) -> None:
    out_dir = tmp_path / "outputs"
    dup_dir = out_dir / "OUT.ABACUS"

    band_written = write_sample_band_artifacts(out_dir, duplicate_dir=dup_dir)
    dos_written = write_sample_dos_artifacts(out_dir, duplicate_dir=dup_dir)
    pdos_written = write_sample_pdos_artifacts(out_dir, duplicate_dir=dup_dir)

    band = BandData.from_paths([out_dir / "BANDS_1.dat", out_dir / "BANDS_2.dat"])
    dos = DOSData.from_paths([out_dir / "DOS1_smearing.dat", out_dir / "DOS2_smearing.dat"])
    pdos = PDOSData(pdos_path=out_dir / "PDOS", tdos_path=out_dir / "TDOS")

    assert band.summary()["num_points"] == 6
    assert dos.summary()["points"] == 8
    assert pdos.summary()["pdos_file"].endswith("PDOS")
    assert "band.png" in band_written
    assert "OUT.ABACUS/BANDS_1.dat" in band_written
    assert "OUT.ABACUS/DOS1_smearing.dat" in dos_written
    assert "OUT.ABACUS/PDOS" in pdos_written


def test_local_runner_raises_clear_error_for_missing_executable(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "missing-exec")
    prepare(workspace, task="scf")

    with pytest.raises(FileNotFoundError, match="definitely-missing-abacus"):
        run(workspace, runner=LocalRunner(executable="definitely-missing-abacus"))


def test_sample_analysis_outputs_roundtrip_through_collect(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "sample-analysis")
    structure = Atoms(
        symbols=["Ni", "O"],
        positions=[[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]],
        cell=[[4.2, 0.0, 0.0], [0.0, 4.2, 0.0], [0.0, 0.0, 4.2]],
        pbc=[True, True, True],
    )
    prepare(workspace, task="pdos", structure=structure)
    workspace.write_text(
        "outputs/stdout.log",
        "TOTAL ENERGY = -11.1\nFERMI ENERGY = 3.2\nBAND GAP = 0.8\nSCF CONVERGED\n",
    )
    workspace.write_text("outputs/stderr.log", "")
    workspace.write_json("outputs/OUT.ABACUS/time.json", {"total": 9.8})
    write_sample_analysis_outputs(
        workspace,
        run_bands=True,
        run_dos=True,
        run_pdos=True,
        relax_requested=True,
        relax_workflow_goal="relax",
        band_workflow_goal="relax-band-dos",
        dos_workflow_goal="relax-band-dos",
        pdos_workflow_goal="relax-band-dos-pdos",
        band_gap=0.8,
        pdos_species=["Ni", "O"],
    )

    collected = collect(workspace)

    assert collected.status == "completed"
    assert collected.metrics["total_time"] == 9.8
    assert collected.metrics["band_summary"]["num_points"] == 12
    assert collected.metrics["dos_summary"]["points"] == 16
    assert collected.metrics["pdos_summary"]["pdos_file"].endswith("PDOS")
    assert collected.metrics["relax_metrics"]["final_structure_available"] is True
    assert collected.final_structure_snapshot is not None
    assert collected.final_structure_snapshot["source"].endswith("STRU_ION_D")
    assert len(collected.metrics["band_artifacts"]) >= 2
    assert len(collected.metrics["dos_artifacts"]) >= 2


def test_prepare_accepts_perturbed_structure_payload(tmp_path: Path) -> None:
    base = Atoms(
        symbols=["Si", "Si"],
        positions=[[0.0, 0.0, 0.0], [1.3, 1.3, 1.3]],
        cell=[[5.2, 0.0, 0.0], [0.0, 5.2, 0.0], [0.0, 0.0, 5.2]],
        pbc=[True, True, True],
    )
    perturbed = perturb_structure(base, displacements=[[0.1, 0.0, 0.0], [0.0, -0.1, 0.2]])

    workspace = prepare(tmp_path / "perturbed-case", task="scf", structure=perturbed)
    recovered = AbacusStructure.from_input(workspace.inputs_dir / "STRU", structure_format="stru")

    assert np.allclose(recovered.atoms.positions[0], [0.1, 0.0, 0.0], atol=1e-6)
    assert np.allclose(recovered.atoms.positions[1], [1.3, 1.2, 1.5], atol=1e-6)


def test_prepare_supports_simple_element_level_magmoms(tmp_path: Path) -> None:
    structure = Atoms(
        symbols=["Fe", "Fe", "O"],
        positions=[[0.0, 0.0, 0.0], [1.4, 1.4, 1.4], [0.7, 0.7, 0.7]],
        cell=[[4.2, 0.0, 0.0], [0.0, 4.2, 0.0], [0.0, 0.0, 4.2]],
        pbc=[True, True, True],
    )

    workspace = prepare(
        tmp_path / "magmom-case",
        task="scf",
        structure=structure,
        magmom_by_element={"Fe": 3.0, "O": 0.5},
    )
    recovered = AbacusStructure.from_input(workspace.inputs_dir / "STRU", structure_format="stru")

    assert recovered.atoms.get_chemical_symbols() == ["O", "Fe", "Fe"]
    assert recovered.atoms.get_initial_magnetic_moments().tolist() == pytest.approx([0.5, 3.0, 3.0])
    assert "mag 3.00000000" not in (workspace.inputs_dir / "STRU").read_text(encoding="utf-8")


def test_collect_reports_missing_time_json_and_nonconverged_markers(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "unfinished-case").ensure_layout()
    workspace.write_text("outputs/stdout.log", "TOTAL ENERGY = -6.4\nSCF NOT CONVERGED\n")
    workspace.write_text("outputs/stderr.log", "")

    result = collect(workspace)

    assert result.status == "unfinished"
    assert result.metrics["converged"] is False
    assert result.diagnostics["time_json_absent"] is True
    assert "scf_not_converged" in result.diagnostics["matched_nonconverged_markers"]
    assert "No explicit convergence marker found in logs." in result.diagnostics["warnings"]


def test_collect_prefers_matching_running_log_over_out_log(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "running-preferred").ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\n")
    workspace.write_text("outputs/OUT.ABACUS/running_scf.log", "TOTAL ENERGY = -7.1\nSCF CONVERGED\n")
    workspace.write_text("outputs/out.log", "TOTAL ENERGY = -3.3\nSCF NOT CONVERGED\n")
    workspace.write_text("outputs/stderr.log", "")

    result = collect(workspace)

    assert result.status == "completed"
    assert result.metrics["total_energy"] == -7.1
    assert result.diagnostics["selected_log_path"].endswith("running_scf.log")
    assert result.diagnostics["selected_log_reason"] == "matched-input-calculation:running_scf.log"
    assert any(path.endswith("out.log") for path in result.diagnostics["ignored_log_paths"])


def test_collect_selects_running_log_matching_input_calculation(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "multi-running").ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\n")
    workspace.write_text("outputs/OUT.ABACUS/running_relax.log", "TOTAL ENERGY = -8.0\nSCF CONVERGED\n")
    workspace.write_text("outputs/OUT.ABACUS/running_scf.log", "TOTAL ENERGY = -9.5\nSCF CONVERGED\n")
    workspace.write_text("outputs/OUT.ABACUS/running_nscf.log", "TOTAL ENERGY = -6.2\nSCF CONVERGED\n")
    workspace.write_text("outputs/stderr.log", "")

    result = collect(workspace)

    assert result.status == "completed"
    assert result.metrics["total_energy"] == -9.5
    assert result.diagnostics["log_strategy"] == "selected-running-log"
    assert result.diagnostics["log_selection_ambiguous"] is False
    assert result.diagnostics["selected_log_path"].endswith("running_scf.log")
    assert len(result.diagnostics["running_log_candidates"]) == 3


def test_collect_marks_ambiguous_running_logs_and_falls_back(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "ambiguous-running").ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation md\n")
    workspace.write_text("outputs/OUT.ABACUS/running_relax.log", "TOTAL ENERGY = -8.0\nSCF CONVERGED\n")
    workspace.write_text("outputs/OUT.ABACUS/running_scf.log", "TOTAL ENERGY = -9.5\nSCF CONVERGED\n")
    workspace.write_text("outputs/stdout.log", "TOTAL ENERGY = -4.4\nSCF CONVERGED\n")
    workspace.write_text("outputs/stderr.log", "")

    result = collect(workspace)

    assert result.status == "completed"
    assert result.metrics["total_energy"] == -4.4
    assert result.diagnostics["log_selection_ambiguous"] is True
    assert result.diagnostics["selected_log_reason"] == "fallback:stdout.log"
    assert result.diagnostics["selected_log_path"].endswith("stdout.log")
    assert any("Multiple running logs detected" in warning for warning in result.diagnostics["warnings"])


def test_collect_discovers_output_log_with_custom_name_under_outputs(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "custom-output-log").ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\n")
    workspace.write_text("outputs/OUT.ABACUS/running_scf.log", "TOTAL ENERGY = -7.2\nSCF CONVERGED\n")
    workspace.write_text(
        "outputs/abacus.log",
        "Atomic-orbital Based Ab-initio\n"
        "total 12.5\n"
        " ITER SOLVER ETOT/eV EDIFF/eV DRHO TIME/s\n"
        " 1 DA -10.0 0.2 1e-4 0.5\n",
    )
    workspace.write_text("outputs/stderr.log", "")

    result = collect(workspace)

    assert result.status == "completed"
    assert result.metrics["total_energy"] == -7.2
    assert result.metrics["total_time"] == 12.5
    assert result.metrics["denergy"] == pytest.approx([0.2])
    assert result.metrics["scf_time_each_step"] == pytest.approx([0.5])
    assert result.diagnostics["output_log_path"].endswith("abacus.log")
    assert result.diagnostics["output_log_reason"] == "banner-discovery"


def test_collect_discovers_output_log_from_workspace_root(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "root-output-log").ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\n")
    workspace.write_text("outputs/OUT.ABACUS/running_scf.log", "TOTAL ENERGY = -8.3\nSCF CONVERGED\n")
    workspace.write_text("job.log", "Atomic-orbital Based Ab-initio\ntotal 8.0\n")
    workspace.write_text("outputs/stderr.log", "")

    result = collect(workspace)

    assert result.status == "completed"
    assert result.metrics["total_time"] == 8.0
    assert result.diagnostics["output_log_path"].endswith("job.log")


def test_collect_output_log_discovery_is_deterministic_when_multiple_candidates_exist(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "multiple-output-candidates").ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\n")
    workspace.write_text("outputs/OUT.ABACUS/running_scf.log", "TOTAL ENERGY = -8.3\nSCF CONVERGED\n")
    workspace.write_text("job.log", "Atomic-orbital Based Ab-initio\ntotal 8.0\n")
    workspace.write_text("outputs/abacus.log", "Atomic-orbital Based Ab-initio\ntotal 9.0\n")
    workspace.write_text("outputs/stderr.log", "")

    result = collect(workspace)

    assert result.metrics["total_time"] == 8.0
    assert result.diagnostics["output_log_path"].endswith("job.log")
    assert result.diagnostics["output_log_selection_ambiguous"] is True
    assert len(result.diagnostics["output_log_candidates"]) == 2


def test_collect_output_log_override_takes_priority_and_reports_missing_override(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "output-override").ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\n")
    workspace.write_text("outputs/OUT.ABACUS/running_scf.log", "TOTAL ENERGY = -8.3\nSCF CONVERGED\n")
    workspace.write_text("outputs/stdout.log", "Atomic-orbital Based Ab-initio\ntotal 5.0\n")
    workspace.write_text("outputs/custom-screen.log", "Atomic-orbital Based Ab-initio\ntotal 11.0\n")
    workspace.write_text("outputs/stderr.log", "")

    overridden = collect(workspace, output_log="outputs/custom-screen.log")
    assert overridden.metrics["total_time"] == 11.0
    assert overridden.diagnostics["output_log_reason"] == "override"
    assert overridden.diagnostics["output_log_override_requested"] == "outputs/custom-screen.log"

    fallback = collect(workspace, output_log="outputs/missing-screen.log")
    assert fallback.metrics["total_time"] == 5.0
    assert fallback.diagnostics["output_log_override_missing"] is True
    assert fallback.diagnostics["output_log_path"].endswith("stdout.log")
