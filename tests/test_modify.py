from __future__ import annotations

import numpy as np
import pytest
from ase import Atoms

from abacus_forge import AbacusStructure, modify_input, modify_stru


def test_modify_input_updates_removes_and_writes_destination(tmp_path) -> None:
    source = tmp_path / "INPUT"
    source.write_text("INPUT_PARAMETERS\ncalculation scf\necutwfc 80\nsmearing_sigma 0.02\n", encoding="utf-8")
    destination = tmp_path / "INPUT.modified"

    params = modify_input(
        source,
        updates={"calculation": "relax", "force_thr": "1e-4"},
        remove_keys=["smearing_sigma"],
        destination=destination,
    )

    assert params["calculation"] == "relax"
    assert params["force_thr"] == "1e-4"
    assert "smearing_sigma" not in params
    written = destination.read_text(encoding="utf-8")
    assert "calculation relax" in written
    assert "force_thr 1e-4" in written
    assert "smearing_sigma" not in written


def test_modify_input_accepts_mapping_source() -> None:
    params = modify_input(
        {"basis_type": "lcao", "smearing_method": "gaussian"},
        updates={"smearing_sigma": 0.01},
    )

    assert params == {
        "basis_type": "lcao",
        "smearing_method": "gaussian",
        "smearing_sigma": "0.01",
    }


def test_modify_stru_applies_composed_edits_and_writes_destination(tmp_path) -> None:
    atoms = Atoms(
        symbols=["Si", "O"],
        positions=[[0.0, 0.0, 0.0], [1.0, 1.5, 2.0]],
        cell=[[3.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 5.0]],
        pbc=[True, True, True],
    )
    destination = tmp_path / "STRU.modified"

    modified = modify_stru(
        atoms,
        displacements=[[0.1, 0.0, 0.0], [0.0, 0.2, -0.1]],
        swap_axes=(0, 2),
        magmoms=[1.5, 0.5],
        move_flags=[[1, 0, 1], [0, 1, 0]],
        destination=destination,
    )

    assert isinstance(modified, AbacusStructure)
    assert np.allclose(modified.atoms.cell.lengths(), [5.0, 4.0, 3.0])
    assert np.allclose(modified.atoms.get_initial_magnetic_moments(), [1.5, 0.5])
    assert modified.atoms.info["abacus_move_flags"] == [[1, 0, 1], [0, 1, 0]]
    recovered = AbacusStructure.from_input(destination, structure_format="stru")
    recovered_magmoms = dict(zip(recovered.atoms.get_chemical_symbols(), recovered.atoms.get_initial_magnetic_moments()))
    recovered_flags = dict(zip(recovered.atoms.get_chemical_symbols(), recovered.atoms.info["abacus_move_flags"]))
    assert recovered_magmoms == {"Si": 1.5, "O": 0.5}
    assert recovered_flags == {"Si": [1, 0, 1], "O": [0, 1, 0]}


def test_modify_stru_supports_supercell_and_validate_shapes() -> None:
    structure = AbacusStructure(
        Atoms(
            symbols=["Al"],
            positions=[[0.0, 0.0, 0.0]],
            cell=[[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 2.0]],
            pbc=[True, True, True],
        ),
        source_format="stru",
    )

    supercell = modify_stru(structure, supercell=(2, 1, 2))
    assert len(supercell.atoms) == 4
    assert supercell.source_format == "stru"

    with pytest.raises(ValueError, match="magmoms must have shape"):
        modify_stru(structure, magmoms=[1.0, 2.0])
    with pytest.raises(ValueError, match="move_flags must have shape"):
        modify_stru(structure, move_flags=[[1, 1, 1], [0, 0, 0]])


def test_modify_stru_supports_element_defaults_and_afm(tmp_path) -> None:
    atoms = Atoms(
        symbols=["Fe", "Fe", "O"],
        positions=[[0.0, 0.0, 0.0], [1.4, 1.4, 1.4], [0.7, 0.7, 0.7]],
        cell=[[4.2, 0.0, 0.0], [0.0, 4.2, 0.0], [0.0, 0.0, 4.2]],
        pbc=[True, True, True],
    )
    destination = tmp_path / "STRU.afm"

    modified = modify_stru(
        atoms,
        magmom_by_element={"Fe": 3.0, "O": 0.5},
        afm=True,
        destination=destination,
    )
    recovered = AbacusStructure.from_input(destination, structure_format="stru")

    assert modified.atoms.get_initial_magnetic_moments().tolist() == pytest.approx([3.0, -3.0, 0.5])
    assert recovered.atoms.get_chemical_symbols() == ["O", "Fe", "Fe"]
    assert recovered.atoms.get_initial_magnetic_moments().tolist() == pytest.approx([0.5, 3.0, -3.0])


def test_modify_stru_explicit_magmoms_override_element_defaults_and_afm() -> None:
    atoms = Atoms(
        symbols=["Fe", "Fe", "O"],
        positions=[[0.0, 0.0, 0.0], [1.4, 1.4, 1.4], [0.7, 0.7, 0.7]],
        cell=[[4.2, 0.0, 0.0], [0.0, 4.2, 0.0], [0.0, 0.0, 4.2]],
        pbc=[True, True, True],
    )

    modified = modify_stru(
        atoms,
        magmom_by_element={"Fe": 3.0},
        afm=True,
        magmoms=[1.0, 1.5, -0.2],
    )

    assert modified.atoms.get_initial_magnetic_moments().tolist() == pytest.approx([1.0, 1.5, -0.2])
