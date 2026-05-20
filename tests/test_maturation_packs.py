from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from ase import Atoms
from ase.io import write as ase_write

from abacus_forge.api import prepare
from abacus_forge.cli import main
from abacus_forge.composite import (
    post_bec,
    post_convergence,
    post_spin_density,
    post_vacancy,
    post_workfunc,
    prepare_bec,
    prepare_convergence,
    prepare_spin_density,
    prepare_vacancy,
    prepare_workfunc,
)
from abacus_forge.cube import CubeData, subtract_cubes
from abacus_forge.input_io import read_input
from abacus_forge.modify import modify_stru
from abacus_forge.structure import AbacusStructure


def test_modify_stru_supports_vacancy_indices_and_cli_supercell(tmp_path: Path, capsys) -> None:
    atoms = Atoms(
        symbols=["Fe", "O", "O"],
        positions=[[0.0, 0.0, 0.0], [1.2, 1.2, 1.2], [2.0, 2.0, 2.0]],
        cell=[4.0, 4.0, 4.0],
        pbc=True,
    )
    modified = modify_stru(atoms, vacancy_indices=[2])
    assert modified.atoms.get_chemical_symbols() == ["Fe", "O"]
    assert np.allclose(modified.atoms.get_positions()[1], [2.0, 2.0, 2.0])

    source = tmp_path / "FeOO.xyz"
    output = tmp_path / "STRU.super"
    ase_write(source, atoms)
    assert (
        main(
            [
                "modify-stru",
                str(source),
                "--output",
                str(output),
                "--structure-format",
                "xyz",
                "--supercell",
                "2",
                "1",
                "1",
                "--vacancy-index",
                "2",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["natoms"] == 5
    recovered = AbacusStructure.from_input(output, structure_format="stru")
    assert recovered.atoms.get_chemical_symbols().count("Fe") == 2
    assert recovered.atoms.get_chemical_symbols().count("O") == 3


def test_convergence_prepare_and_postprocess_collects_points(tmp_path: Path) -> None:
    workspace = _prepared_workspace(tmp_path / "conv-root")

    result = prepare_convergence(workspace.root, key="ecutwfc", values=["60", "80"])
    assert result.status == "prepared"
    assert result.summary == {"key": "ecutwfc", "count": 2}
    assert read_input(workspace.root / "convergence" / "ecutwfc_60" / "inputs" / "INPUT")["ecutwfc"] == "60"

    _write_completed_stdout(workspace.root / "convergence" / "ecutwfc_60", energy=-6.0)
    _write_completed_stdout(workspace.root / "convergence" / "ecutwfc_80", energy=-6.2)
    posted = post_convergence(workspace.root, key="ecutwfc")

    assert posted.status == "completed"
    assert posted.summary["key"] == "ecutwfc"
    assert posted.summary["points"] == [
        {"workspace": str(workspace.root / "convergence" / "ecutwfc_60"), "value": "60", "total_energy": -6.0, "energy_per_atom": None},
        {"workspace": str(workspace.root / "convergence" / "ecutwfc_80"), "value": "80", "total_energy": -6.2, "energy_per_atom": None},
    ]
    assert "reports/metrics_convergence.json" in posted.artifacts


def test_cube_subtraction_and_spin_density_postprocess(tmp_path: Path) -> None:
    up = _write_cube(tmp_path / "up.cube", [3.0, 4.0])
    down = _write_cube(tmp_path / "down.cube", [1.0, 1.5])
    diff = subtract_cubes(up, down)

    assert diff.data.reshape(-1).tolist() == [2.0, 2.5]

    workspace = _prepared_workspace(tmp_path / "spin-root")
    prepared = prepare_spin_density(workspace.root)
    assert prepared.status == "prepared"
    spin_dir = workspace.root / "spin-density" / "scf"
    _write_cube(spin_dir / "outputs" / "SPIN1_CHG.cube", [3.0, 4.0])
    _write_cube(spin_dir / "outputs" / "SPIN2_CHG.cube", [1.0, 1.5])
    posted = post_spin_density(workspace.root)

    assert posted.status == "completed"
    assert posted.summary["spin_density_file"].endswith("spin_density.cube")
    assert CubeData.from_file(workspace.root / "reports" / "spin_density.cube").data.reshape(-1).tolist() == [2.0, 2.5]


def test_workfunc_prepare_and_postprocess(tmp_path: Path) -> None:
    workspace = _prepared_workspace(tmp_path / "workfunc-root")
    prepared = prepare_workfunc(workspace.root, vacuum_axis="c", dipole_correction=True)
    assert prepared.status == "prepared"
    subdir = workspace.root / "workfunc" / "scf"
    params = read_input(subdir / "inputs" / "INPUT")
    assert params["out_pot"] == "2"
    assert params["dip_cor_flag"] == "1"

    _write_completed_stdout(subdir, energy=-1.0, fermi=4.0)
    _write_cube(subdir / "outputs" / "ElecStaticPot.cube", [8.0, 10.0])
    posted = post_workfunc(workspace.root, vacuum_axis="c")

    assert posted.status == "completed"
    assert posted.summary["vacuum_level_ev"] == 10.0
    assert posted.summary["work_function_ev"] == 6.0


def test_vacancy_prepare_and_postprocess(tmp_path: Path) -> None:
    workspace = _prepared_workspace(tmp_path / "vacancy-root")
    prepared = prepare_vacancy(workspace.root, vacancy_indices=[2], supercell=[1, 1, 1])
    assert prepared.status == "prepared"
    assert (workspace.root / "vacancy" / "pristine" / "inputs" / "STRU").exists()
    defect = AbacusStructure.from_input(workspace.root / "vacancy" / "defect_002" / "inputs" / "STRU", structure_format="stru")
    assert len(defect.atoms) == 1

    _write_completed_stdout(workspace.root / "vacancy" / "pristine", energy=-10.0)
    _write_completed_stdout(workspace.root / "vacancy" / "defect_002", energy=-6.0)
    (workspace.root / "vacancy" / "ref_energy.txt").write_text("Fe -2.5\n", encoding="utf-8")
    posted = post_vacancy(workspace.root)

    assert posted.status == "completed"
    assert posted.summary["formation_energies"] == [
        {"defect": "defect_002", "removed_symbol": "Fe", "formation_energy_ev": 1.5}
    ]


def test_bec_prepare_and_postprocess(tmp_path: Path) -> None:
    workspace = _prepared_workspace(tmp_path / "bec-root")
    prepared = prepare_bec(workspace.root, atom_indices=[1], displacement=0.02, directions=["x"])
    assert prepared.status == "prepared"
    assert (workspace.root / "bec" / "org" / "inputs" / "INPUT").exists()
    assert (workspace.root / "bec" / "disp_atom001_x_plus" / "inputs" / "STRU").exists()
    assert (workspace.root / "bec" / "disp_atom001_x_minus" / "inputs" / "STRU").exists()

    _write_polarization(workspace.root / "bec" / "disp_atom001_x_plus", [1.2, 0.0, 0.0])
    _write_polarization(workspace.root / "bec" / "disp_atom001_x_minus", [0.8, 0.0, 0.0])
    posted = post_bec(workspace.root)

    assert posted.status == "completed"
    assert posted.summary["bec_tensors"]["atom001"][0] == pytest.approx([10.0, 0.0, 0.0])


def test_new_property_packs_are_exposed_by_cli(tmp_path: Path, capsys) -> None:
    workspace = _prepared_workspace(tmp_path / "cli-root")

    assert main(["convergence", "prepare", str(workspace.root), "--key", "ecutwfc", "--value", "60", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "prepared"

    assert main(["spin-density", "prepare", str(workspace.root), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["task"] == "spin-density"

    assert main(["workfunc", "prepare", str(workspace.root), "--vacuum-axis", "c", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["task"] == "workfunc"


def _prepared_workspace(path: Path):
    return prepare(
        path,
        task="scf",
        structure=Atoms(
            symbols=["Fe", "O"],
            positions=[[0.0, 0.0, 0.0], [1.5, 1.5, 1.5]],
            cell=[4.0, 4.0, 4.0],
            pbc=True,
        ),
        parameters={"ecutwfc": 60, "suffix": "ABACUS"},
        kpoints=[1, 1, 1],
    )


def _write_completed_stdout(workspace: Path, *, energy: float, fermi: float | None = None) -> None:
    outputs = workspace / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    lines = [f"TOTAL ENERGY = {energy}", "SCF CONVERGED"]
    if fermi is not None:
        lines.insert(1, f"FERMI ENERGY = {fermi}")
    (outputs / "stdout.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (outputs / "stderr.log").write_text("", encoding="utf-8")


def _write_cube(path: Path, values: list[float]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(
        [
            "Forge cube fixture",
            "OUTER LOOP: X, MIDDLE LOOP: Y, INNER LOOP: Z",
            "1 0.0 0.0 0.0",
            f"1 1.0 0.0 0.0",
            f"1 0.0 1.0 0.0",
            f"{len(values)} 0.0 0.0 1.0",
            "1 0.0 0.0 0.0 0.0",
            " ".join(str(value) for value in values),
        ]
    )
    path.write_text(text + "\n", encoding="utf-8")
    return path


def _write_polarization(workspace: Path, values: list[float]) -> None:
    reports = workspace / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "polarization.json").write_text(json.dumps({"polarization": values}), encoding="utf-8")
