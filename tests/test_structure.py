from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from ase import Atoms
from ase.io import write as ase_write

from abacus_forge.structure import BOHR_TO_ANG, AbacusStructure, _read_stru
from abacus_forge.structure_recognition import detect_structure_format, detect_vacuum_info


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


def test_to_stru_writes_orbital_map_for_lcao_inputs() -> None:
    structure = AbacusStructure.from_input(Atoms(symbols=["Ni", "O"], positions=[[0, 0, 0], [1, 1, 1]], cell=[4, 4, 4], pbc=True))

    text = structure.to_stru(pp_map={"Ni": "Ni.upf", "O": "O.upf"}, orb_map={"Ni": "Ni.orb", "O": "O.orb"})

    assert "NUMERICAL_ORBITAL" in text
    assert "Ni.orb" in text
    assert "O.orb" in text


def test_stru_roundtrip_preserves_species_metadata_and_masses_after_sorting(tmp_path: Path) -> None:
    source = tmp_path / "source.STRU"
    source.write_text(
        "ATOMIC_SPECIES\n"
        "Fe 55.123456 Fe.source.upf\n"
        "O 16.654321 O.source.upf\n\n"
        "NUMERICAL_ORBITAL\n"
        "Fe.source.orb\n"
        "O.source.orb\n\n"
        "LATTICE_CONSTANT\n"
        "1.889726124626\n\n"
        "LATTICE_VECTORS\n"
        "4 0 0\n0 4 0\n0 0 4\n\n"
        "ATOMIC_POSITIONS\n"
        "Direct\n"
        "Fe\n0\n1\n0.1 0.2 0.3 m 1 0 1\n"
        "O\n0\n1\n0.4 0.5 0.6 m 0 1 0\n",
        encoding="utf-8",
    )

    structure = AbacusStructure.from_input(source, structure_format="stru")
    text = structure.to_stru(
        pp_map={"Fe": "Fe.override.upf", "O": ""},
        orb_map={"Fe": "", "O": "O.override.orb"},
    )
    destination = tmp_path / "roundtrip.STRU"
    destination.write_text(text, encoding="utf-8")
    recovered = AbacusStructure.from_input(destination, structure_format="stru")

    assert recovered.atoms.get_chemical_symbols() == ["O", "Fe"]
    assert recovered.atoms.get_masses().tolist() == pytest.approx([16.654321, 55.123456])
    assert recovered.atoms.info["abacus_species_meta"] == {
        "O": {"mass": 16.654321, "pp": "O.source.upf", "orb": "O.override.orb"},
        "Fe": {"mass": 55.123456, "pp": "Fe.override.upf", "orb": "Fe.source.orb"},
    }


def test_to_stru_serializes_geometry_with_native_bohr_lattice_units() -> None:
    atoms = Atoms(
        symbols=["Si"],
        scaled_positions=[[0.25, 0.5, 0.75]],
        cell=[[3.2, 0.1, 0.0], [0.0, 4.1, 0.2], [0.3, 0.0, 5.6]],
        pbc=True,
    )
    text = AbacusStructure.from_input(atoms).to_stru()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lattice_constant = float(lines[lines.index("LATTICE_CONSTANT") + 1].split()[0])
    vector_start = lines.index("LATTICE_VECTORS") + 1
    native_cell = np.asarray(
        [[float(value) for value in lines[vector_start + offset].split()[:3]] for offset in range(3)]
    )

    assert "LATTICE_CONSTANT_UNIT" not in lines
    assert lattice_constant * BOHR_TO_ANG == pytest.approx(1.0)
    assert native_cell * lattice_constant * BOHR_TO_ANG == pytest.approx(atoms.cell.array)


def test_read_stru_accepts_species_labels_with_inline_comments(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "examples" / "NiO_inputs" / "STRU"

    atoms = _read_stru(source)

    assert atoms.get_chemical_symbols() == ["Ni", "Ni", "O", "O"]


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
        ("Cartesian", "1.0 2.0 3.0 0 1 0", [2.0, 4.0, 6.0]),
        ("Cartesian_angstrom", "1.0 2.0 3.0 m 1 1 0", [1.0, 2.0, 3.0]),
        ("Cartesian_au", "1.0 2.0 3.0 m 1 1 0", [BOHR_TO_ANG, 2 * BOHR_TO_ANG, 3 * BOHR_TO_ANG]),
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


@pytest.mark.parametrize("coordinate_mode", ["Cartesian_angstrom_center_xy", "Cartesian_unknown", "Directly"])
def test_read_stru_rejects_unrecognized_coordinate_modes(tmp_path: Path, coordinate_mode: str) -> None:
    stru_path = tmp_path / "unsupported.STRU"
    stru_path.write_text(
        "ATOMIC_SPECIES\nSi 28.0855 Si.upf\n\n"
        "LATTICE_CONSTANT\n2.0\nLATTICE_CONSTANT_UNIT\nAngstrom\n\n"
        "LATTICE_VECTORS\n1 0 0\n0 1 0\n0 0 1\n\n"
        f"ATOMIC_POSITIONS\n{coordinate_mode}\nSi\n0\n1\n0 0 0\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported coordinate mode"):
        _read_stru(stru_path)


def test_detect_vacuum_uses_circular_fractional_gaps_and_face_heights() -> None:
    atoms = Atoms(
        symbols=["Si"] * 4,
        scaled_positions=[
            [0.10, 0.10, 0.98],
            [0.35, 0.35, 0.02],
            [0.60, 0.60, 0.98],
            [0.85, 0.85, 0.02],
        ],
        cell=[[10.0, 0.0, 0.0], [2.0, 10.0, 0.0], [0.0, 0.0, 20.0]],
        pbc=True,
    )

    direct_map, direct_axes, direct_heights = detect_vacuum_info(atoms)

    assert direct_axes == [False, False, True]
    assert direct_map[2] == pytest.approx(19.2)
    assert direct_heights == pytest.approx([9.8058067569, 10.0, 20.0])

    translated = atoms.copy()
    translated.set_scaled_positions(atoms.get_scaled_positions(wrap=False) + [1.4, -2.2, 3.7])
    rotation = np.asarray([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    rotated = atoms.copy()
    rotated.set_cell(atoms.cell.array @ rotation, scale_atoms=False)
    rotated.set_positions(atoms.positions @ rotation)

    translated_map, translated_axes, translated_heights = detect_vacuum_info(translated)
    assert translated_map == pytest.approx(direct_map)
    assert translated_axes == direct_axes
    assert translated_heights == pytest.approx(direct_heights)
    rotated_map, rotated_axes, rotated_heights = detect_vacuum_info(rotated)
    assert rotated_map == direct_map
    assert rotated_axes == direct_axes
    assert rotated_heights == pytest.approx(direct_heights)


def test_detect_vacuum_handles_empty_degenerate_and_nonperiodic_cells() -> None:
    empty = Atoms(symbols=[], cell=np.zeros((3, 3)), pbc=True)
    degenerate = Atoms(
        symbols=["H"],
        positions=[[0.0, 0.0, 0.0]],
        cell=[[3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 0.0]],
        pbc=True,
    )
    nonperiodic = Atoms(
        symbols=["H"],
        positions=[[0.0, 0.0, 0.0]],
        cell=[3.0, 3.0, 3.0],
        pbc=[True, True, False],
    )

    for atoms in (empty, degenerate, nonperiodic):
        vacuum_map, vacuum_axes, heights = detect_vacuum_info(atoms)
        assert vacuum_map == {}
        assert vacuum_axes == [False, False, False]
        assert np.all(np.isfinite(heights))


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
