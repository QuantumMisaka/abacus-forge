from __future__ import annotations

import json
import stat
from pathlib import Path

from abacus_forge import LocalRunner, Workspace, collect, export, prepare, run


def test_prepare_creates_minimal_workspace(tmp_path: Path) -> None:
    structure = tmp_path / "Si.stru"
    structure.write_text("ATOMIC_SPECIES\nSi 28.085 Si.upf\n", encoding="utf-8")

    workspace = prepare(
        tmp_path / "case",
        structure=structure,
        parameters={"calculation": "scf", "ecutwfc": 80},
        kpoints=[2, 2, 2],
        metadata={"label": "minimal"},
    )

    assert (workspace.inputs_dir / "STRU").exists()
    assert "ecutwfc 80" in (workspace.inputs_dir / "INPUT").read_text(encoding="utf-8")
    assert "2 2 2 0 0 0" in (workspace.inputs_dir / "KPT").read_text(encoding="utf-8")

    meta = json.loads(workspace.meta_path.read_text(encoding="utf-8"))
    assert meta["metadata"]["label"] == "minimal"
    assert meta["parameters"]["calculation"] == "scf"


def test_run_and_collect_parse_basic_metrics(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "run-case")
    prepare(workspace)

    fake_abacus = tmp_path / "fake-abacus"
    fake_abacus.write_text(
        "#!/usr/bin/env python3\n"
        "import os\n"
        "print(f\"OMP = {os.environ.get('OMP_NUM_THREADS', 'missing')}\")\n"
        "print('TOTAL ENERGY = -10.5')\n"
        "print('FERMI ENERGY = 3.2')\n"
        "print('BAND GAP = 1.1')\n"
        "print('SCF CONVERGED')\n",
        encoding="utf-8",
    )
    fake_abacus.chmod(fake_abacus.stat().st_mode | stat.S_IEXEC)

    result = run(workspace, runner=LocalRunner(executable=str(fake_abacus), omp_threads=4))
    collected = collect(workspace)

    assert result.status == "completed"
    assert result.command[-2] == "--input-dir"
    assert "OMP = 4" in result.stdout_path.read_text(encoding="utf-8")
    assert collected.status == "completed"
    assert collected.metrics["converged"] is True
    assert collected.metrics["total_energy"] == -10.5
    assert "outputs/stdout.log" in collected.artifacts


def test_export_writes_json_file(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "export-case")
    prepare(workspace)
    workspace.write_text("outputs/stdout.log", "TOTAL ENERGY = -8.0\nSCF CONVERGED\n")
    workspace.write_text("outputs/stderr.log", "")

    result = collect(workspace)
    output = tmp_path / "result.json"
    text = export(result, destination=output)

    assert output.exists()
    assert json.loads(text)["metrics"]["total_energy"] == -8.0


def test_collect_extracts_band_and_dos_summaries(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "summary-case")
    prepare(workspace)
    workspace.write_text("outputs/stdout.log", "TOTAL ENERGY = -8.0\nBAND GAP = 1.2\nSCF CONVERGED\n")
    workspace.write_text("outputs/stderr.log", "")
    workspace.write_text("outputs/BANDS_1.dat", "0.0 -1.0 0.5\n1.0 -0.8 0.7\n")
    workspace.write_text("outputs/DOS1_smearing.dat", "-10.0 0.0\n0.0 1.0\n")
    workspace.write_text("outputs/DOS2_smearing.dat", "-10.0 0.0\n0.0 0.8\n")
    workspace.write_text("outputs/PDOS", "Ni 0.4\nO 0.6\n")
    workspace.write_text("outputs/TDOS", "-1.0 0.1\n0.0 1.0\n")
    workspace.write_json("reports/metrics_band.json", {"band_gap": 1.2})
    workspace.write_json("reports/metrics_dos.json", {"energy_window": {"emin_ev": -10.0, "emax_ev": 10.0}})
    workspace.write_json("reports/metrics_pdos.json", {"projection_mode": "species"})

    result = collect(workspace)

    assert result.metrics["band_summary"]["num_kpoints"] == 2
    assert result.metrics["band_metrics"]["band_gap"] == 1.2
    assert result.metrics["dos_summary"]["points"] == 4
    assert result.metrics["dos_metrics"]["energy_window"]["emax_ev"] == 10.0
    assert result.metrics["pdos_summary"]["pdos_file"].endswith("PDOS")
    assert result.metrics["pdos_metrics"]["projection_mode"] == "species"


def test_runner_builds_mpirun_command(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "mpi-case")
    workspace.ensure_layout()
    runner = LocalRunner(executable="abacus", mpi_ranks=8)

    command = runner.build_command(workspace)

    assert command[:3] == ["mpirun", "-np", "8"]
    assert command[-2:] == ["--input-dir", str(workspace.inputs_dir)]
