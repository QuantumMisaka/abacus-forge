from __future__ import annotations

from pathlib import Path

from ase import Atoms
from ase.io import write as ase_write

from abacus_forge.structure import AbacusStructure
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
