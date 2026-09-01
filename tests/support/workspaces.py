from __future__ import annotations

from pathlib import Path

from ase import Atoms

from abacus_forge.api import prepare
from abacus_forge.workspace import Workspace


def write_fake_lcao_scf_workspace(path: Path) -> Workspace:
    workspace = prepare(
        path,
        task="scf",
        structure=Atoms(symbols=["Si"], positions=[[0.0, 0.0, 0.0]], cell=[4.0, 4.0, 4.0], pbc=True),
        parameters={"basis_type": "lcao", "suffix": "ABACUS", "nspin": 1},
    )
    workspace.write_text("outputs/stdout.log", "FERMI ENERGY = 3.2\nSCF CONVERGED\n")
    workspace.write_text("inputs/OUT.ABACUS/data-HR-sparse_SPIN0.csr", "hr")
    workspace.write_text("inputs/OUT.ABACUS/data-SR-sparse_SPIN0.csr", "sr")
    workspace.write_text("inputs/OUT.ABACUS/data-rR-sparse.csr", "rr")
    return workspace
