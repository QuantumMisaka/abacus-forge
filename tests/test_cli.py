from __future__ import annotations

import json
from pathlib import Path

import pytest
from ase import Atoms
from ase.io import write as ase_write

from abacus_forge.cli import main
from abacus_forge.input_io import read_input, read_kpt
from abacus_forge.structure import AbacusStructure
from abacus_forge.workspace import Workspace
from tests.support.fake_executables import write_fake_abacus, write_fake_pyatb
from tests.support.workspaces import write_fake_lcao_scf_workspace


def test_cli_prepare_collect_and_export(tmp_path: Path, capsys) -> None:
    structure = Atoms(symbols=["Si"], positions=[[0.0, 0.0, 0.0]])
    structure_path = tmp_path / "Si.xyz"
    ase_write(structure_path, structure)
    workspace = tmp_path / "cli-case"

    assert (
        main(
            [
                "prepare",
                str(workspace),
                "--structure",
                str(structure_path),
                "--structure-format",
                "xyz",
                "--task",
                "relax",
                "--ensure-pbc",
                "--parameter",
                "ecutwfc=70",
                "--kpoint",
                "3",
                "--kpoint",
                "3",
                "--kpoint",
                "1",
            ]
        )
        == 0
    )
    capsys.readouterr()

    (workspace / "outputs").mkdir(exist_ok=True)
    (workspace / "outputs" / "stdout.log").write_text("TOTAL ENERGY = -6.4\nSCF CONVERGED\n", encoding="utf-8")
    (workspace / "outputs" / "stderr.log").write_text("", encoding="utf-8")

    assert main(["collect", str(workspace), "--json"]) == 0
    collect_out = capsys.readouterr().out
    payload = json.loads(collect_out)
    assert payload["status"] == "completed"
    assert payload["structure_snapshot"] is not None
    assert payload["inputs_snapshot"]["INPUT"]["calculation"] == "relax"

    export_path = tmp_path / "cli-result.json"
    assert main(["export", str(workspace), "--output", str(export_path)]) == 0
    capsys.readouterr()
    assert json.loads(export_path.read_text(encoding="utf-8"))["metrics"]["total_energy"] == -6.4


def test_cli_new_tasks_help_and_dry_run(tmp_path: Path, capsys) -> None:
    structure = Atoms(symbols=["Si"], positions=[[0.0, 0.0, 0.0]], cell=[4, 4, 4], pbc=True)
    structure_path = tmp_path / "Si.xyz"
    ase_write(structure_path, structure)

    with pytest.raises(SystemExit) as help_exit:
        main(["cell-relax", "--help"])
    assert help_exit.value.code == 0
    capsys.readouterr()

    assert (
        main(
            [
                "md",
                str(tmp_path / "md-dry-run"),
                "--structure",
                str(structure_path),
                "--structure-format",
                "xyz",
                "--dry-run",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "dry-run"
    assert payload["inputs_snapshot"]["INPUT"]["calculation"] == "md"


def test_cli_composite_eos_prepare(tmp_path: Path, capsys) -> None:
    structure = Atoms(symbols=["Al"], positions=[[0.0, 0.0, 0.0]], cell=[4, 4, 4], pbc=True)
    structure_path = tmp_path / "Al.xyz"
    ase_write(structure_path, structure)
    workspace = tmp_path / "eos-cli"

    assert main(["prepare", str(workspace), "--structure", str(structure_path), "--structure-format", "xyz"]) == 0
    capsys.readouterr()
    assert main(["eos", "prepare", str(workspace), "--start", "0.975", "--end", "1.025", "--step", "0.025", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "prepared"
    assert payload["summary"]["count"] == 3


def test_cli_and_workflow_collection_payloads_are_mappable(tmp_path: Path, capsys) -> None:
    workspace = Workspace(tmp_path / "shared-case")
    workspace.ensure_layout()
    workspace.write_text("outputs/stdout.log", "TOTAL ENERGY = -5.0\nFERMI ENERGY = 1.1\nSCF CONVERGED\n")
    workspace.write_text("outputs/stderr.log", "")

    assert main(["collect", str(workspace.root), "--json"]) == 0
    cli_payload = json.loads(capsys.readouterr().out)

    from abacus_forge.api import collect

    workflow_payload = collect(workspace).to_dict()
    assert cli_payload["status"] == workflow_payload["status"]
    assert cli_payload["metrics"] == workflow_payload["metrics"]
    assert set(cli_payload["artifacts"]) == set(workflow_payload["artifacts"])


def test_cli_collect_supports_explicit_output_log_override(tmp_path: Path, capsys) -> None:
    workspace = Workspace(tmp_path / "cli-output-override")
    workspace.ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\n")
    workspace.write_text("outputs/OUT.ABACUS/running_scf.log", "TOTAL ENERGY = -5.0\nSCF CONVERGED\n")
    workspace.write_text("outputs/stdout.log", "Atomic-orbital Based Ab-initio\ntotal 3.0\n")
    workspace.write_text("outputs/custom.log", "Atomic-orbital Based Ab-initio\ntotal 7.0\n")
    workspace.write_text("outputs/stderr.log", "")

    assert main(["collect", str(workspace.root), "--output-log", "outputs/custom.log", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["metrics"]["total_time"] == 7.0
    assert payload["diagnostics"]["output_log_reason"] == "override"


def test_cli_prepare_pyatb_band_from_scf_workspace(tmp_path: Path, capsys) -> None:
    scf = write_fake_lcao_scf_workspace(tmp_path / "scf")
    workspace = tmp_path / "pyatb-prepare"

    assert (
        main(
            [
                "prepare",
                str(workspace),
                "--pyatb",
                "--scf-workspace",
                str(scf.root),
                "--segments",
                "12",
                "--point",
                "0,0,0:G",
                "--point",
                "0.5,0,0:X",
                "--efermi",
                "4.4",
                "--copy-outputs",
            ]
        )
        == 0
    )
    capsys.readouterr()

    pyatb_input = (workspace / "inputs" / "Input").read_text(encoding="utf-8")
    assert "fermi_energy  4.4" in pyatb_input
    assert "kpoint_label  G, X" in pyatb_input
    assert "0.0 0.0 0.0 12" in pyatb_input
    assert (workspace / "inputs" / "KPT_band").exists()
    assert (workspace / "inputs" / "OUT.ABACUS" / "data-HR-sparse_SPIN0.csr").read_text(encoding="utf-8") == "hr"
    metadata = json.loads((workspace / "meta.json").read_text(encoding="utf-8"))
    assert metadata["kind"] == "abacus-forge.pyatb-band"


def test_cli_run_pyatb_uses_pyatb_runner(tmp_path: Path, capsys) -> None:
    workspace = Workspace(tmp_path / "pyatb-run").ensure_layout()
    workspace.write_text("inputs/Input", "INPUT_PARAMETERS\n{}\n")
    executable = write_fake_pyatb(tmp_path / "fake-pyatb")

    assert main(["run", str(workspace.root), "--pyatb", "--executable", str(executable), "--omp", "2", "--timeout", "5"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "completed"
    assert payload["returncode"] == 0
    assert payload["omp_threads"] == 2
    assert payload["command"] == [str(executable)]
    assert (workspace.inputs_dir / "Out" / "Band_Structure" / "band_info.dat").exists()
    assert (workspace.outputs_dir / "stdout.log").read_text(encoding="utf-8").strip() == "pyatb done"


def test_cli_collect_and_export_pyatb_json(tmp_path: Path, capsys) -> None:
    workspace = Workspace(tmp_path / "pyatb-collect").ensure_layout()
    workspace.write_text("inputs/Input", "INPUT_PARAMETERS\n{}\n")
    workspace.write_text("inputs/Out/Band_Structure/band_info.dat", "Band gap is 1.23\n")
    workspace.write_text("inputs/Out/Band_Structure/band.png", "fake")
    workspace.write_text("outputs/stderr.log", "")

    assert main(["collect", str(workspace.root), "--pyatb", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "completed"
    assert payload["metrics"]["band_gap"] == 1.23
    assert payload["metrics"]["band_picture"].endswith("band.png")

    export_path = tmp_path / "pyatb-result.json"
    assert main(["export", str(workspace.root), "--pyatb", "--output", str(export_path)]) == 0
    capsys.readouterr()
    exported = json.loads(export_path.read_text(encoding="utf-8"))
    assert exported["metrics"]["band_gap"] == 1.23


def test_cli_pyatb_rejects_invalid_primitive_arguments(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="requires --scf-workspace"):
        main(["prepare", str(tmp_path / "pyatb"), "--pyatb", "--point", "0,0,0:G"])

    with pytest.raises(SystemExit, match="requires at least one --point"):
        main(["prepare", str(tmp_path / "pyatb"), "--pyatb", "--scf-workspace", str(tmp_path / "scf")])

    with pytest.raises(SystemExit, match="does not accept --mpi"):
        main(["run", str(tmp_path / "pyatb"), "--pyatb", "--mpi", "2"])

    with pytest.raises(SystemExit, match="does not accept --output-log"):
        main(["collect", str(tmp_path / "pyatb"), "--pyatb", "--output-log", "outputs/stdout.log"])


def test_cli_prepare_supports_element_level_magmoms(tmp_path: Path, capsys) -> None:
    structure = Atoms(
        symbols=["Fe", "Fe", "O"],
        positions=[[0.0, 0.0, 0.0], [1.4, 1.4, 1.4], [0.7, 0.7, 0.7]],
        cell=[[4.2, 0.0, 0.0], [0.0, 4.2, 0.0], [0.0, 0.0, 4.2]],
        pbc=[True, True, True],
    )
    structure_path = tmp_path / "FeO.cif"
    ase_write(structure_path, structure)
    workspace = tmp_path / "cli-magmom-case"

    assert (
        main(
            [
                "prepare",
                str(workspace),
                "--structure",
                str(structure_path),
                "--task",
                "scf",
                "--magmom",
                "Fe=3.0",
                "--magmom",
                "O=0.5",
            ]
        )
        == 0
    )
    capsys.readouterr()

    recovered = AbacusStructure.from_input(workspace / "inputs" / "STRU", structure_format="stru")
    assert recovered.atoms.get_chemical_symbols() == ["O", "Fe", "Fe"]
    assert recovered.atoms.get_initial_magnetic_moments().tolist() == [0.5, 3.0, 3.0]


def test_cli_modify_stru_supports_afm_and_site_magmoms(tmp_path: Path, capsys) -> None:
    structure = Atoms(
        symbols=["Fe", "Fe", "O"],
        positions=[[0.0, 0.0, 0.0], [1.4, 1.4, 1.4], [0.7, 0.7, 0.7]],
        cell=[[4.2, 0.0, 0.0], [0.0, 4.2, 0.0], [0.0, 0.0, 4.2]],
        pbc=[True, True, True],
    )
    source = tmp_path / "source.cif"
    output = tmp_path / "STRU.modified"
    ase_write(source, structure)

    assert (
        main(
            [
                "modify-stru",
                str(source),
                "--output",
                str(output),
                "--magmom",
                "Fe=3.0",
                "--magmom",
                "O=0.5",
                "--afm",
            ]
        )
        == 0
    )
    capsys.readouterr()

    recovered = AbacusStructure.from_input(output, structure_format="stru")
    assert recovered.atoms.get_chemical_symbols() == ["O", "Fe", "Fe"]
    assert recovered.atoms.get_initial_magnetic_moments().tolist() == [0.5, 3.0, -3.0]

    output_site = tmp_path / "STRU.site.modified"
    assert (
        main(
            [
                "modify-stru",
                str(source),
                "--output",
                str(output_site),
                "--site-magmoms",
                "1.0,1.5,-0.2",
            ]
        )
        == 0
    )
    capsys.readouterr()

    recovered_site = AbacusStructure.from_input(output_site, structure_format="stru")
    assert recovered_site.atoms.get_chemical_symbols() == ["O", "Fe", "Fe"]
    assert recovered_site.atoms.get_initial_magnetic_moments().tolist() == [-0.2, 1.0, 1.5]


def test_cli_modify_input_updates_and_removes_keys(tmp_path: Path, capsys) -> None:
    source = tmp_path / "INPUT"
    output = tmp_path / "INPUT.modified"
    source.write_text("INPUT_PARAMETERS\ncalculation scf\necutwfc 80\nsmearing_sigma 0.02\n", encoding="utf-8")

    assert (
        main(
            [
                "modify-input",
                str(source),
                "--output",
                str(output),
                "--set",
                "calculation=relax",
                "--set",
                "force_thr=1e-4",
                "--remove",
                "smearing_sigma",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert read_input(output) == {
        "calculation": "relax",
        "ecutwfc": "80",
        "force_thr": "1e-4",
    }


def test_cli_modify_input_rejects_invalid_assignment(tmp_path: Path) -> None:
    source = tmp_path / "INPUT"
    source.write_text("INPUT_PARAMETERS\ncalculation scf\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="invalid parameter"):
        main(
            [
                "modify-input",
                str(source),
                "--output",
                str(tmp_path / "INPUT.modified"),
                "--set",
                "bad-assignment",
            ]
        )


def test_cli_modify_kpt_supports_mesh_and_line_modes(tmp_path: Path, capsys) -> None:
    mesh_source = tmp_path / "KPT"
    mesh_source.write_text("K_POINTS\n0\nGamma\n2 2 2 0 0 0\n", encoding="utf-8")
    mesh_output = tmp_path / "KPT.mesh.modified"

    assert (
        main(
            [
                "modify-kpt",
                str(mesh_source),
                "--output",
                str(mesh_output),
                "--mode",
                "mesh",
                "--mesh",
                "6",
                "6",
                "1",
                "--shifts",
                "1",
                "1",
                "1",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert read_kpt(mesh_output) == {"mode": "mesh", "mesh": [6, 6, 1], "shifts": [1, 1, 1]}

    line_source = tmp_path / "KPT.line"
    line_source.write_text("K_POINTS\n10\nLine\n0.0 0.0 0.0 #Gamma\n0.5 0.0 0.0 #X\n", encoding="utf-8")
    line_output = tmp_path / "KPT.line.modified"

    assert (
        main(
            [
                "modify-kpt",
                str(line_source),
                "--output",
                str(line_output),
                "--mode",
                "line",
                "--segments",
                "20",
                "--point",
                "0,0,0:Gamma",
                "--point",
                "0.5,0.5,0:M",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert read_kpt(line_output) == {
        "mode": "line",
        "segments": 20,
        "points": [
            {"coords": [0.0, 0.0, 0.0], "npoints": 20, "label": "Gamma"},
            {"coords": [0.5, 0.5, 0.0], "npoints": 1, "label": "M"},
        ],
    }


def test_cli_modify_unit_edits_workspace_inputs(tmp_path: Path, capsys) -> None:
    structure = Atoms(symbols=["Fe", "Fe"], positions=[[0, 0, 0], [1, 1, 1]], cell=[4, 4, 4], pbc=True)
    structure_path = tmp_path / "Fe2.cif"
    ase_write(structure_path, structure)
    workspace = tmp_path / "modify-unit"

    assert (
        main(
            [
                "prepare",
                str(workspace),
                "--structure",
                str(structure_path),
                "--task",
                "cell-relax",
                "--parameter",
                "smearing_sigma=0.02",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "modify",
                str(workspace),
                "--task",
                "cell-relax",
                "--set",
                "force_thr=1e-4",
                "--remove",
                "smearing_sigma",
                "--kpt-mode",
                "mesh",
                "--mesh",
                "5",
                "5",
                "1",
                "--shifts",
                "1",
                "1",
                "0",
                "--magmom",
                "Fe=3.0",
                "--afm",
                "--json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "completed"
    assert payload["modified_files"] == ["INPUT", "KPT", "STRU"]
    assert read_input(workspace / "inputs" / "INPUT")["force_thr"] == "1e-4"
    assert "smearing_sigma" not in read_input(workspace / "inputs" / "INPUT")
    assert read_kpt(workspace / "inputs" / "KPT")["mesh"] == [5, 5, 1]
    assert json.loads((workspace / "forge-result.json").read_text(encoding="utf-8"))["step"] == "modify"


def test_cli_scf_task_runs_end_to_end(tmp_path: Path, capsys) -> None:
    executable = write_fake_abacus(
        tmp_path / "fake-scf",
        stdout_lines=[
            "TOTAL ENERGY = -6.8",
            "FERMI ENERGY = 1.5",
            "SCF CONVERGED",
        ],
    )
    structure = Atoms(symbols=["Si"], positions=[[0.0, 0.0, 0.0]])
    structure_path = tmp_path / "Si.xyz"
    ase_write(structure_path, structure)

    assert (
        main(
            [
                "scf",
                str(tmp_path / "scf-task"),
                "--structure",
                str(structure_path),
                "--structure-format",
                "xyz",
                "--ensure-pbc",
                "--executable",
                str(executable),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "completed"
    assert payload["metrics"]["total_energy"] == -6.8
    assert payload["diagnostics"]["task"] == "scf"


def test_cli_band_task_requires_explicit_points(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="explicit line-mode KPT points"):
        main(["band", str(tmp_path / "band-task")])


def test_cli_dos_task_enables_pdos_outputs_and_export(tmp_path: Path, capsys) -> None:
    executable = write_fake_abacus(
        tmp_path / "fake-dos",
        stdout_lines=[
            "TOTAL ENERGY = -7.2",
            "SCF CONVERGED",
        ],
        extra_writes={
            "outputs/DOS1_smearing.dat": "-5.0 0.1\n0.0 1.3\n",
            "outputs/PDOS": "# species projected DOS\nFe 0.7\nO 0.3\n",
            "outputs/TDOS": "# total DOS\n-1.0 0.2\n0.0 1.0\n",
        },
    )
    structure = Atoms(
        symbols=["Fe", "O"],
        positions=[[0.0, 0.0, 0.0], [1.5, 1.5, 1.5]],
        cell=[[4.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 4.0]],
        pbc=[True, True, True],
    )
    structure_path = tmp_path / "FeO.cif"
    ase_write(structure_path, structure)
    export_path = tmp_path / "dos-task.json"

    assert (
        main(
            [
                "dos",
                str(tmp_path / "dos-task"),
                "--structure",
                str(structure_path),
                "--executable",
                str(executable),
                "--output",
                str(export_path),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "completed"
    assert payload["inputs_snapshot"]["INPUT"]["out_dos"] == "1"
    assert "out_pdos" not in payload["inputs_snapshot"]["INPUT"]
    assert payload["metrics"]["dos_family_summary"]["projected_dos"]["pdos_file"].endswith("PDOS")
    assert json.loads(export_path.read_text(encoding="utf-8"))["metrics"]["dos_summary"]["points"] == 2


def test_cli_collect_accepts_flat_layout(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "flat"
    out = workspace / "OUT.ABACUS"
    out.mkdir(parents=True)
    (workspace / "INPUT").write_text("INPUT_PARAMETERS\ncalculation scf\n", encoding="utf-8")
    (out / "running_scf.log").write_text("TOTAL ENERGY = -5.0\nSCF CONVERGED\n", encoding="utf-8")
    (workspace / "abacus.log").write_text("Atomic-orbital Based Ab-initio\ntotal 2.0\n", encoding="utf-8")

    assert main(["collect", str(workspace), "--layout", "flat", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "completed"
    assert payload["metrics"]["total_energy"] == -5.0
    assert payload["diagnostics"]["layout"] == "flat"


def test_cli_collect_unit_runs_band_postprocess_controls(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "band-unit"
    (workspace / "inputs").mkdir(parents=True)
    (workspace / "outputs" / "OUT.ABACUS").mkdir(parents=True)
    (workspace / "outputs" / "stdout.log").write_text("BAND GAP = 0.9\nSCF CONVERGED\n", encoding="utf-8")
    (workspace / "outputs" / "stderr.log").write_text("", encoding="utf-8")
    (workspace / "outputs" / "OUT.ABACUS" / "BANDS_1.dat").write_text("1 0.0 -1.0 0.5\n2 0.5 -0.8 0.7\n", encoding="utf-8")

    assert main(["collect", str(workspace), "--task", "band", "--unit", "nscf", "--plot-emin", "-2", "--plot-emax", "2", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["diagnostics"]["unit_postprocess"]["status"] == "completed"
    assert payload["metrics"]["band_metrics"]["band_picture"].endswith("band.png")
    assert (workspace / "outputs" / "band.png").exists()


def test_cli_collect_unit_can_skip_postprocess(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "band-unit-skip"
    (workspace / "outputs" / "OUT.ABACUS").mkdir(parents=True)
    (workspace / "outputs" / "stdout.log").write_text("SCF CONVERGED\n", encoding="utf-8")
    (workspace / "outputs" / "stderr.log").write_text("", encoding="utf-8")
    (workspace / "outputs" / "OUT.ABACUS" / "BANDS_1.dat").write_text("1 0.0 -1.0 0.5\n", encoding="utf-8")

    assert main(["collect", str(workspace), "--task", "band", "--unit", "nscf", "--no-postprocess", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["diagnostics"]["unit_postprocess"]["reason"] == "postprocess-disabled"
    assert not (workspace / "outputs" / "band.png").exists()


def test_cli_exposes_execute_alias_and_hides_relax_band_dos(tmp_path: Path, capsys) -> None:
    structure = Atoms(symbols=["Ni", "O"], positions=[[0, 0, 0], [1, 1, 1]], cell=[4, 4, 4], pbc=True)
    structure_path = tmp_path / "NiO.cif"
    ase_write(structure_path, structure)
    workspace = tmp_path / "cell-relax"
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["TOTAL ENERGY = -4.4", "SCF CONVERGED"])

    assert (
        main(
            [
                "prepare",
                str(workspace),
                "--structure",
                str(structure_path),
                "--task",
                "cell-relax",
                "--parameter",
                "basis_type=lcao",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(["execute", str(workspace), "--executable", str(executable)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "completed"

    with pytest.raises(SystemExit):
        main(["relax-band-dos", "--help"])
