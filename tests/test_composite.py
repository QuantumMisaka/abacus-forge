from __future__ import annotations

import json
from pathlib import Path

from ase import Atoms

from abacus_forge.api import prepare
from abacus_forge.composite import post_eos, prepare_elastic, prepare_eos, prepare_phonon, prepare_vibration, run_eos
from tests.support.fake_executables import write_fake_abacus


def test_eos_prepare_run_post_local_pack(tmp_path: Path) -> None:
    workspace = tmp_path / "eos-case"
    prepare(workspace, structure=Atoms(symbols=["Al"], positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True), task="scf")

    prepared = prepare_eos(workspace, start=0.975, end=1.025, step=0.025)
    executable = write_fake_abacus(
        tmp_path / "fake-abacus",
        stdout_lines=[
            "TOTAL ENERGY = -3.0",
            "NATOM = 1",
            "VOLUME = 64.0",
            "ENERGY PER ATOM = -3.0",
            "SCF CONVERGED",
            "NORMAL END",
        ],
    )
    run_result = run_eos(workspace, executable=str(executable))
    post_result = post_eos(workspace)

    assert prepared.status == "prepared"
    assert prepared.summary["count"] == 3
    assert run_result.status == "completed"
    assert post_result.status == "completed"
    assert post_result.summary["count"] == 3
    assert (workspace / "reports" / "metrics_eos.json").exists()


def test_composite_prepare_variants_do_not_require_scheduler_files(tmp_path: Path) -> None:
    workspace = tmp_path / "composite-case"
    prepare(workspace, structure=Atoms(symbols=["Si"], positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True), task="scf")

    elastic = prepare_elastic(workspace)
    vibration = prepare_vibration(workspace, atom_indices=[1])
    phonon = prepare_phonon(workspace, phonopy="definitely-missing-phonopy")

    assert elastic.summary["count"] >= 1
    assert vibration.summary["count"] == 7
    assert phonon.diagnostics["optional_dependency_missing"] == "phonopy"
    assert not (workspace / "setting.json").exists()
