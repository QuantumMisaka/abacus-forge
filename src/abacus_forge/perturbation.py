"""Lightweight structure perturbation primitives for Forge."""

from __future__ import annotations

from typing import Any

import numpy as np
from ase import Atoms

from abacus_forge.structure import AbacusStructure


def perturb_structure(
    structure: AbacusStructure | Atoms | Any,
    *,
    displacements: list[list[float]] | np.ndarray,
    copy: bool = True,
    preserve_source_format: bool = True,
) -> AbacusStructure:
    """Apply explicit per-atom displacements and return one perturbed structure."""

    base, atoms = _coerce_structure(structure, copy=copy)
    offsets = np.asarray(displacements, dtype=float)
    expected_shape = (len(atoms), 3)
    if offsets.shape != expected_shape:
        raise ValueError(f"displacements must have shape {expected_shape}, got {offsets.shape}")

    atoms.set_positions(atoms.get_positions() + offsets)
    source_format = base.source_format if preserve_source_format else "ase"
    return AbacusStructure(atoms, source_format=source_format)


def _coerce_structure(structure: AbacusStructure | Atoms | Any, *, copy: bool) -> tuple[AbacusStructure, Atoms]:
    if isinstance(structure, AbacusStructure):
        return structure, structure.atoms.copy() if copy else structure.atoms
    if isinstance(structure, Atoms):
        base = AbacusStructure(structure, source_format="ase")
        return base, structure.copy() if copy else structure

    base = AbacusStructure.from_input(structure)
    return base, base.atoms.copy() if copy else base.atoms
