from __future__ import annotations

import json
import stat
from pathlib import Path

from ase import Atoms

from abacus_forge.api import prepare
from abacus_forge.composite import post_eos, prepare_elastic, prepare_eos, prepare_phonon, prepare_vibration, run_eos


def test_eos_prepare_run_post_local_pack(tmp_path: Path) -> None:
    workspace = tmp_path / "eos-case"
    prepare(workspace, structure=Atoms(symbols=["Al"], positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True), task="scf")

    prepared = prepare_eos(workspace, start=0.975, end=1.025, step=0.025)
    executable = _write_fake_abacus(tmp_path / "fake-abacus")
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


def _write_fake_abacus(path: Path) -> Path:
    body = "\n".join(
        [
            "#!/usr/bin/env python3",
            "from pathlib import Path",
            "import sys",
            "args = sys.argv[1:]",
            "input_dir = Path(args[args.index('--input-dir') + 1])",
            "workspace = input_dir.parent",
            "text = (input_dir / 'STRU').read_text()",
            "volume = 64.0",
            "print('TOTAL ENERGY = -3.0')",
            "print('NATOM = 1')",
            "print(f'VOLUME = {volume}')",
            "print('ENERGY PER ATOM = -3.0')",
            "print('SCF CONVERGED')",
            "print('NORMAL END')",
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path
