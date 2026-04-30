from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from ase import Atoms
from ase.io import write as ase_write

from abacus_forge.structure import AbacusStructure, _read_stru
from abacus_forge.structure_recognition import detect_structure_format


def test_structure_detection_and_normalization_from_poscar(tmp_path: Path) -> None:
    atoms = Atoms(
        symbols=["Si", "Si"],
        positions=[[0.0, 0.0, 0.0], [1.3575, 1.3575, 1.3575]],
        cell=[[5.43, 0.0, 0.0], [0.0, 5.43, 0.0], [0.0, 0.0, 5.43]],
        pbc=[True, True, True],
    )
    path = tmp_path / "POSCAR"
    ase_write(path, atoms, format="vasp")

    assert detect_structure_format(path) == "poscar"
    structure = AbacusStructure.from_input(path)
    metadata = structure.metadata()

    assert metadata.formula == "Si2"
    assert metadata.structure_class == "bulk"
    assert metadata.atom_count == 2


def test_structure_ensure_pbc_from_xyz(tmp_path: Path) -> None:
    path = tmp_path / "cluster.xyz"
    path.write_text("1\ncomment\nHe 0.0 0.0 0.0\n", encoding="utf-8")

    structure = AbacusStructure.from_input(path, structure_format="xyz").ensure_3d_pbc(vacuum=12.0)
    metadata = structure.metadata()

    assert metadata.pbc == [True, True, True]
    assert metadata.structure_class in {"cluster", "cubic_cluster"}


def test_structure_from_mapping_and_to_stru_roundtrip(tmp_path: Path) -> None:
    structure = AbacusStructure.from_input(
        {
            "cell": [[3.5, 0.0, 0.0], [0.0, 3.6, 0.0], [0.0, 0.0, 3.7]],
            "sites": [
                {"symbol": "O", "position": [0.0, 0.0, 0.0]},
                {"symbol": "Si", "position": [1.75, 1.8, 1.85]},
            ],
        }
    )

    text = structure.to_stru(pp_map={"Si": "Si.upf", "O": "O.upf"})
    stru_path = tmp_path / "STRU"
    stru_path.write_text(text, encoding="utf-8")
    roundtrip = AbacusStructure.from_input(stru_path, structure_format="stru")

    assert structure.source_format == "mapping"
    assert "ATOMIC_SPECIES" in text
    assert "LATTICE_VECTORS" in text
    assert "ATOMIC_POSITIONS" in text
    assert roundtrip.metadata().formula == "OSi"
    assert np.allclose(roundtrip.atoms.cell.lengths(), [3.5, 3.6, 3.7])
    assert roundtrip.atoms.info["abacus_move_flags"] == [[1, 1, 1], [1, 1, 1]]


def test_to_stru_preserves_existing_move_flags(tmp_path: Path) -> None:
    atoms = Atoms(
        symbols=["Si", "O"],
        positions=[[0.0, 0.0, 0.0], [1.0, 1.5, 2.0]],
        cell=[[4.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 4.0]],
        pbc=[True, True, True],
    )
    atoms.info["abacus_move_flags"] = [[1, 0, 1], [0, 1, 0]]

    path = tmp_path / "STRU"
    path.write_text(AbacusStructure.from_input(atoms).to_stru(), encoding="utf-8")
    recovered = AbacusStructure.from_input(path, structure_format="stru")

    recovered_flags = dict(zip(recovered.atoms.get_chemical_symbols(), recovered.atoms.info["abacus_move_flags"]))
    assert recovered_flags == {"Si": [1, 0, 1], "O": [0, 1, 0]}


def test_to_stru_roundtrip_preserves_site_level_collinear_magmoms(tmp_path: Path) -> None:
    atoms = Atoms(
        symbols=["Fe", "Fe", "O"],
        scaled_positions=[[0.0, 0.0, 0.0], [0.5, 0.5, 0.5], [0.25, 0.25, 0.25]],
        cell=[[4.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 4.0]],
        pbc=[True, True, True],
    )
    atoms.set_initial_magnetic_moments([2.0, -2.0, 0.0])

    path = tmp_path / "STRU"
    path.write_text(AbacusStructure.from_input(atoms).to_stru(), encoding="utf-8")
    text = path.read_text(encoding="utf-8")
    recovered = AbacusStructure.from_input(path, structure_format="stru")

    assert "mag 2.00000000" in text
    assert "mag -2.00000000" in text
    assert recovered.atoms.get_chemical_symbols() == ["O", "Fe", "Fe"]
    assert recovered.atoms.get_initial_magnetic_moments().tolist() == pytest.approx([0.0, 2.0, -2.0])


def test_to_stru_keeps_species_level_magmom_when_uniform(tmp_path: Path) -> None:
    atoms = Atoms(
        symbols=["Ni", "Ni"],
        scaled_positions=[[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
        cell=[[3.5, 0.0, 0.0], [0.0, 3.5, 0.0], [0.0, 0.0, 3.5]],
        pbc=[True, True, True],
    )
    atoms.set_initial_magnetic_moments([1.5, 1.5])

    path = tmp_path / "STRU"
    path.write_text(AbacusStructure.from_input(atoms).to_stru(), encoding="utf-8")
    text = path.read_text(encoding="utf-8")
    recovered = AbacusStructure.from_input(path, structure_format="stru")

    assert "mag 1.50000000" not in text
    assert "\n1.50000000\n2\n" in text
    assert recovered.atoms.get_initial_magnetic_moments().tolist() == pytest.approx([1.5, 1.5])


def test_structure_swap_axes_swaps_cell_lengths_and_scaled_positions() -> None:
    atoms = Atoms(
        symbols=["C", "C"],
        scaled_positions=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
        cell=[[3.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 5.0]],
        pbc=[True, True, True],
    )

    swapped = AbacusStructure.from_input(atoms).swap_axes(0, 2)

    assert np.allclose(swapped.atoms.cell.lengths(), [5.0, 4.0, 3.0])
    assert np.allclose(swapped.atoms.get_scaled_positions()[0], [0.3, 0.2, 0.1])
    assert np.allclose(swapped.atoms.get_scaled_positions()[1], [0.6, 0.5, 0.4])


def test_structure_make_supercell_scales_cell_and_atom_count() -> None:
    atoms = Atoms(
        symbols=["Al"],
        scaled_positions=[[0.0, 0.0, 0.0]],
        cell=[[2.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 4.0]],
        pbc=[True, True, True],
    )

    supercell = AbacusStructure.from_input(atoms).make_supercell((2, 1, 3))

    assert len(supercell.atoms) == 6
    assert np.allclose(supercell.atoms.cell.lengths(), [4.0, 3.0, 12.0])


@pytest.mark.parametrize(
    ("coordinate_mode", "position_line", "expected_position"),
    [
        ("Direct", "0.25 0.50 0.75 m 1 0 1", [0.5, 2.0, 3.0]),
        ("Cartesian", "1.0 2.0 3.0 0 1 0", [0.529177210903, 1.058354421806, 1.587531632709]),
        ("Cartesian_angstrom", "1.0 2.0 3.0 m 1 1 0", [1.0, 2.0, 3.0]),
    ],
)
def test_read_stru_supports_coordinate_modes_and_move_flags(
    tmp_path: Path,
    coordinate_mode: str,
    position_line: str,
    expected_position: list[float],
) -> None:
    stru_text = f"""ATOMIC_SPECIES
Si 28.085500 Si.upf

NUMERICAL_ORBITAL
Si.orb

LATTICE_CONSTANT
2.0
LATTICE_CONSTANT_UNIT
Angstrom

LATTICE_VECTORS
1.0 0.0 0.0
0.0 2.0 0.0
0.0 0.0 2.0

ATOMIC_POSITIONS
{coordinate_mode}
Si
1.5
1
{position_line}
"""
    stru_path = tmp_path / f"{coordinate_mode}.STRU"
    stru_path.write_text(stru_text, encoding="utf-8")

    atoms = _read_stru(stru_path)

    assert np.allclose(atoms.positions[0], expected_position)
    assert atoms.get_initial_magnetic_moments().tolist() == [1.5]
    assert atoms.info["abacus_move_flags"] == [[1, 0, 1] if coordinate_mode == "Direct" else ([0, 1, 0] if coordinate_mode == "Cartesian" else [1, 1, 0])]
    assert atoms.info["abacus_species_meta"]["Si"]["pp"] == "Si.upf"
    assert atoms.info["abacus_species_meta"]["Si"]["orb"] == "Si.orb"


def test_structure_primitive_conversion_raises_clear_error_without_pymatgen(monkeypatch) -> None:
    atoms = Atoms(
        symbols=["Na"],
        positions=[[0.0, 0.0, 0.0]],
        cell=[[3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 3.0]],
        pbc=[True, True, True],
    )
    structure = AbacusStructure.from_input(atoms)

    real_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("pymatgen"):
            raise ImportError("pymatgen is intentionally unavailable")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(RuntimeError, match="pymatgen is required"):
        structure.primitive_to_conventional()
    with pytest.raises(RuntimeError, match="pymatgen is required"):
        structure.conventional_to_primitive()
