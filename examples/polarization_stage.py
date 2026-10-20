"""Prepare one Berry NSCF input using existing Forge primitives.

This caller recipe neither launches ABACUS nor locates/reuses SCF charge files.
The caller must supply charge density from the matching displaced SCF before
executing this stage, and select a scientifically appropriate k mesh/assets.
"""
from __future__ import annotations

import math
from pathlib import Path

from abacus_forge import prepare
from abacus_forge.modify import modify_stru
from abacus_forge.structure import AbacusStructure


def prepare_stage(workspace, *, structure, parameters, kpoints, gdir,
                  atom_index, direction, displacement_angstrom,
                  pseudo_path=None, orbital_path=None):
    """Write exactly one displaced, explicit-gdir NSCF input directory."""
    if isinstance(gdir, bool) or not isinstance(gdir, int) or gdir not in (1, 2, 3):
        raise ValueError('gdir must be 1, 2 or 3')
    if direction not in ('x', 'y', 'z'):
        raise ValueError('direction must be x, y or z')
    if isinstance(displacement_angstrom, bool) or not math.isfinite(displacement_angstrom):
        raise ValueError('displacement must be finite, in angstrom')
    mesh = list(kpoints)
    if len(mesh) != 3 or any(isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in mesh):
        raise ValueError('supply three positive integer k-mesh sizes')
    source = AbacusStructure.from_input(structure)
    if isinstance(atom_index, bool) or not isinstance(atom_index, int) or not 1 <= atom_index <= len(source.atoms):
        raise ValueError('atom_index must be an existing 1-based atom')
    root = Path(workspace)
    if root.exists() or root.is_symlink():
        raise ValueError('choose a new workspace for this stage')
    displacements = [[0.0, 0.0, 0.0] for _ in source.atoms]
    displacements[atom_index - 1]['xyz'.index(direction)] = displacement_angstrom
    displaced = modify_stru(source, displacements=displacements)
    return prepare(
        root, structure=displaced, task='scf', parameters=dict(parameters),
        input_overrides={'calculation': 'nscf', 'berry_phase': 1, 'gdir': gdir,
                         'symmetry': -1, 'init_chg': 'file', 'out_band': 0},
        kpoints=mesh, pseudo_path=pseudo_path, orbital_path=orbital_path,
        asset_mode='copy', metadata={'recipe': 'polarization-single-stage',
            'atom_index': atom_index, 'direction': direction,
            'displacement_angstrom': displacement_angstrom, 'gdir': gdir},
    )
