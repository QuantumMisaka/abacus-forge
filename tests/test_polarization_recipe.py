"""One-stage recipe checks; no electronic-structure calculation is run."""
from pathlib import Path
import runpy

import pytest
import numpy as np
from ase import Atoms

from abacus_forge import execute
from abacus_forge.input_io import read_input
from abacus_forge.runner import LocalRunner
from abacus_forge.structure import AbacusStructure


pytestmark = pytest.mark.integration

def test_polarization_recipe_prepares_one_displacement_and_runs_one_process(tmp_path):
    recipe = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'examples/polarization_stage.py'))
    original = Atoms('Si2', positions=[[0, 0, 0], [1, 1, 1]], cell=[4, 4, 4], pbc=True)
    ws = recipe['prepare_stage'](
        tmp_path / 'one-stage', structure=original,
        parameters={'basis_type': 'pw', 'ecutwfc': 50, 'nspin': 1},
        kpoints=[2, 2, 4], gdir=3, atom_index=2, direction='x', displacement_angstrom=0.01,
    )
    params = read_input(ws.inputs_dir / 'INPUT')
    assert params['calculation'] == 'nscf'
    assert params['berry_phase'] == '1'
    assert params['symmetry'] == '-1'
    assert params['init_chg'] == 'file'
    assert params['gdir'] == '3'
    restored = AbacusStructure.from_input(ws.inputs_dir / 'STRU').atoms
    np.testing.assert_allclose(restored.positions, [[0, 0, 0], [1.01, 1, 1]], atol=1e-7)
    np.testing.assert_array_equal(original.positions, [[0, 0, 0], [1, 1, 1]])
    executable = tmp_path / 'fake-abacus'
    executable.write_text('#!/bin/sh\nprintf "invoked\\n" >> process-count\n')
    executable.chmod(0o755)
    result = execute(ws, runner=LocalRunner(executable=str(executable)))
    assert result.returncode == 0
    assert (ws.inputs_dir / 'process-count').read_text().splitlines() == ['invoked']
