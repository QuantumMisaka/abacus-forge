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
            {"coords": [0.0, 0.0, 0.0], "label": "Gamma"},
            {"coords": [0.5, 0.5, 0.0], "label": "M"},
        ],
    }
