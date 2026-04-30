from __future__ import annotations

import numpy as np
import pytest
from ase import Atoms

from abacus_forge import AbacusStructure, perturb_structure


def test_perturb_structure_returns_new_structure_without_mutating_input() -> None:
    atoms = Atoms(
        symbols=["Si", "O"],
        positions=[[0.0, 0.0, 0.0], [1.0, 1.5, 2.0]],
        cell=[[4.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 4.0]],
        pbc=[True, True, True],
    )

    perturbed = perturb_structure(
        atoms,
        displacements=[[0.1, 0.0, -0.1], [0.0, 0.2, 0.3]],
    )

    assert isinstance(perturbed, AbacusStructure)
    assert perturbed.source_format == "ase"
    assert np.allclose(atoms.positions[0], [0.0, 0.0, 0.0])
    assert np.allclose(perturbed.atoms.positions[0], [0.1, 0.0, -0.1])
    assert np.allclose(perturbed.atoms.positions[1], [1.0, 1.7, 2.3])


def test_perturb_structure_preserves_source_format_for_abacus_structure() -> None:
    structure = AbacusStructure(
        Atoms(
            symbols=["Al"],
            positions=[[0.2, 0.3, 0.4]],
            cell=[[3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 3.0]],
            pbc=[True, True, True],
        ),
        source_format="stru",
    )

    perturbed = perturb_structure(structure, displacements=[[0.05, 0.05, 0.05]])

    assert perturbed.source_format == "stru"
    assert np.allclose(perturbed.atoms.positions[0], [0.25, 0.35, 0.45])


def test_perturb_structure_can_mutate_in_place_when_copy_is_false() -> None:
    atoms = Atoms(
        symbols=["He"],
        positions=[[0.0, 0.0, 0.0]],
        cell=[[8.0, 0.0, 0.0], [0.0, 8.0, 0.0], [0.0, 0.0, 8.0]],
        pbc=[True, True, True],
    )

    perturbed = perturb_structure(atoms, displacements=[[0.2, -0.1, 0.3]], copy=False)

    assert np.allclose(atoms.positions[0], [0.2, -0.1, 0.3])
    assert np.allclose(perturbed.atoms.positions[0], [0.2, -0.1, 0.3])


def test_perturb_structure_validates_displacement_shape() -> None:
    atoms = Atoms(
        symbols=["Si", "Si"],
        positions=[[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]],
        cell=[[5.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 0.0, 5.0]],
        pbc=[True, True, True],
    )

    with pytest.raises(ValueError, match="shape"):
        perturb_structure(atoms, displacements=[[0.1, 0.2, 0.3]])
