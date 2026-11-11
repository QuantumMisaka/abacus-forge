from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from ase import Atoms

from abacus_forge.api import prepare
from abacus_forge.composite import elastic, vibration
from abacus_forge.result import CollectionResult
from abacus_forge.structure import AbacusStructure


pytestmark = [pytest.mark.composite, pytest.mark.experimental]


def _root(tmp_path: Path, name: str = "case") -> Path:
    root = tmp_path / name
    prepare(root, structure=Atoms("H", positions=[[0, 0, 0]], cell=[5, 5, 5], pbc=True), task="scf")
    return root


def _records(prepared, metric_for):
    return [
        {
            **item,
            "task": prepared.task,
            "unit_id": item.get("unit_id", str(Path(item["workspace"]).relative_to(prepared.workspace))),
            "status": "completed",
            "metrics": {"converge": True, "normal_end": True, **metric_for(item)},
        }
        for item in prepared.subtasks
    ]


def _stress(item):
    strain = np.asarray(item["strain"])
    e = np.array([strain[0, 0], strain[1, 1], strain[2, 2], 2 * strain[1, 2], 2 * strain[0, 2], 2 * strain[0, 1]])
    c = np.array([
        [200, 50, 60, 0, 0, 0], [50, 210, 70, 0, 0, 0], [60, 70, 220, 0, 0, 0],
        [0, 0, 0, 40, 0, 0], [0, 0, 0, 0, 50, 0], [0, 0, 0, 0, 0, 60],
    ])
    s = c @ e + np.array([1, 2, 3, 0, 0, 0])
    return {"stress": (-10 * np.array([[s[0], s[5], s[4]], [s[5], s[1], s[3]], [s[4], s[3], s[2]]])).tolist()}


def _harmonic_force(item):
    force = np.zeros((1, 3))
    if "axis" in item:
        force[0, {"x": 0, "y": 1, "z": 2}[item["axis"]]] = -float(item["delta"])
    return {"force": force.tolist()}


def test_elastic_explicit_results_fit_by_unit_id_without_collecting(tmp_path, monkeypatch):
    root = _root(tmp_path)
    prepared = elastic.prepare_elastic(root)
    records = _records(prepared, _stress)
    monkeypatch.setattr(elastic, "collect_subtask", lambda *_args, **_kwargs: pytest.fail("explicit results must not collect"))

    result = elastic.post_elastic(root, results=list(reversed(records)))

    assert result.status == "completed"
    fit = json.loads((root / "reports/metrics_elastic.json").read_text())["fit"]
    assert np.asarray(fit["elastic_tensor_GPa"])[0, 1] == pytest.approx(50)
    assert fit["shear_modulus_GPa"] == pytest.approx(60)
    assert len(result.subtasks) == 13


def test_elastic_partial_results_do_not_publish_a_partial_tensor(tmp_path):
    root = _root(tmp_path)
    prepared = elastic.prepare_elastic(root)
    result = elastic.post_elastic(root, results=_records(prepared, _stress)[:-1])
    assert result.status == "degraded"
    assert not (root / "reports/elastic_tensor.json").exists()
    assert result.summary["missing_units"]


@pytest.mark.parametrize("flat_forces", [False, True])
def test_vibration_explicit_results_build_real_hessian_and_frequencies(tmp_path, monkeypatch, flat_forces):
    root = _root(tmp_path)
    prepared = vibration.prepare_vibration(root, atom_indices=[1], stepsize=0.02)
    records = _records(prepared, _harmonic_force)
    if flat_forces:
        for record in records:
            record["metrics"]["force"] = np.asarray(record["metrics"]["force"]).reshape(-1).tolist()
    monkeypatch.setattr(vibration, "collect_subtask", lambda *_args, **_kwargs: pytest.fail("explicit results must not collect"))
    # Analysis consumes the prepared reference unit, not a mutable parent input.
    (root / "inputs/STRU").rename(root / "inputs/parent-STRU-moved")

    result = vibration.post_vibration(root, results=list(reversed(records)))

    assert result.status == "completed"
    assert result.summary["frequencies"] == pytest.approx([519.39745] * 3, rel=1e-5)
    assert result.summary["zpe"] > 0
    assert np.asarray(result.summary["hessian_eV_A2"]) == pytest.approx(np.eye(3))
    assert all(not Path(artifact.path_rel).is_absolute() for artifact in result.to_envelope().artifacts)


@pytest.mark.parametrize("metric", [None, [["nan", 0, 0]], [[0, 0, 0], [0, 0, 0]]])
def test_vibration_rejects_missing_nonfinite_or_wrong_atom_force(tmp_path, metric):
    root = _root(tmp_path)
    prepared = vibration.prepare_vibration(root, atom_indices=[1])
    records = _records(prepared, _harmonic_force)
    records[-1]["metrics"]["force"] = metric
    result = vibration.post_vibration(root, results=records)
    assert result.status == "degraded"
    assert not result.summary.get("frequencies")


@pytest.mark.parametrize("selection", [[0], [2], [1, 1], [], [True], [1.5]])
def test_vibration_invalid_selection_is_rejected_before_creating_units(tmp_path, selection):
    root = _root(tmp_path)
    with pytest.raises(ValueError):
        vibration.prepare_vibration(root, atom_indices=selection)
    assert not (root / "vibration").exists()


@pytest.mark.parametrize("task", [elastic, vibration])
def test_reprepare_does_not_overwrite_existing_unit_inputs(tmp_path, task):
    root = _root(tmp_path)
    operation = task.prepare_elastic if task is elastic else task.prepare_vibration
    first = operation(root)
    input_path = Path(first.subtasks[0]["workspace"]) / "inputs/INPUT"
    input_path.write_text("sentinel\n")
    with pytest.raises((ValueError, FileExistsError), match="plan|already|new workspace"):
        operation(root)
    assert input_path.read_text() == "sentinel\n"


@pytest.mark.parametrize("task", [elastic, vibration])
def test_batch_run_uses_plan_and_ignores_unplanned_directories(tmp_path, monkeypatch, task):
    root = _root(tmp_path)
    operation = task.prepare_elastic if task is elastic else task.prepare_vibration
    run = task.run_elastic if task is elastic else task.run_vibration
    prepared = operation(root)
    (root / prepared.task / "deformed_stale").mkdir()
    observed = []
    monkeypatch.setattr(task, "run_subtasks", lambda _task, _root, units, **_kw: observed.extend(units))
    run(root)
    assert len(observed) == len(prepared.subtasks)
    assert all(Path(path).name != "deformed_stale" for path in observed)


@pytest.mark.parametrize("task", [elastic, vibration])
def test_prepare_accepts_relative_workspace_and_returns_artifact_records(tmp_path, monkeypatch, task):
    _root(tmp_path)
    monkeypatch.chdir(tmp_path)
    operation = task.prepare_elastic if task is elastic else task.prepare_vibration
    prepared = operation("case")
    artifacts = prepared.to_envelope().artifacts
    assert artifacts
    assert all(not Path(artifact.path_rel).is_absolute() for artifact in artifacts)
    assert all((tmp_path / "case" / artifact.path_rel).exists() for artifact in artifacts)


def test_vibration_does_not_analyze_reference_with_changed_inputs(tmp_path):
    root = _root(tmp_path)
    prepared = vibration.prepare_vibration(root, atom_indices=[1])
    records = _records(prepared, _harmonic_force)
    reference_input = Path(prepared.subtasks[0]["workspace"]) / "inputs/STRU"
    reference_input.write_text(reference_input.read_text() + "\n# altered reference\n")
    with pytest.raises(ValueError, match="reference inputs changed"):
        vibration.post_vibration(root, results=records)


@pytest.mark.parametrize("task", [elastic, vibration])
def test_default_post_rejects_changed_nonreference_unit_before_collection(tmp_path, monkeypatch, task):
    from abacus_forge.composite import common, plan

    root = _root(tmp_path)
    prepare_task = task.prepare_elastic if task is elastic else task.prepare_vibration
    post_task = task.post_elastic if task is elastic else task.post_vibration
    prepared = prepare_task(root)
    metric_for = _stress if task is elastic else _harmonic_force
    by_workspace = {Path(item["workspace"]): item for item in prepared.subtasks}

    def collect(workspace):
        metrics = {"converge": True, "normal_end": True, **metric_for(by_workspace[workspace.root])}
        return CollectionResult(workspace.root, "completed", metrics=metrics)

    # Cover both collector routes so bypassing the guarded unit API is detected.
    monkeypatch.setattr(common, "collect", collect)
    monkeypatch.setattr(plan, "collect", collect)
    assert post_task(root).status == "completed"
    changed_input = Path(prepared.subtasks[-1]["workspace"]) / "inputs/INPUT"
    changed_input.write_text(changed_input.read_text() + "\n# changed after preparation\n")

    with pytest.raises(ValueError, match="inputs changed"):
        post_task(root)


@pytest.mark.parametrize("cell", [
    [[2, 0, 0], [0, 4, 0], [0, 0, 6]],
    [[2, 0.3, 0.1], [0, 4, 0.2], [0.4, 0.6, 6]],
])
def test_elastic_tensor_matches_strain_of_actual_non_cubic_generated_cells(tmp_path, cell):
    root = tmp_path / "non-cubic"
    prepare(root, structure=Atoms("H", positions=[[0, 0, 0]], cell=cell, pbc=True), task="scf")
    prepared = elastic.prepare_elastic(root)
    reference = np.asarray(AbacusStructure.from_input(root / "inputs/STRU", structure_format="stru").atoms.cell)
    records = []
    for item in prepared.subtasks:
        generated = np.asarray(AbacusStructure.from_input(Path(item["workspace"]) / "inputs/STRU", structure_format="stru").atoms.cell)
        # ASE cells contain lattice vectors as rows: B = A @ F.T.
        deformation = np.linalg.solve(reference, generated).T
        strain = 0.5 * (deformation + deformation.T) - np.eye(3)
        voigt = np.array([strain[0, 0], strain[1, 1], strain[2, 2], 2 * strain[1, 2], 2 * strain[0, 2], 2 * strain[0, 1]])
        stress = -1000 * voigt  # C = 100 GPa identity, ABACUS stress in kbar.
        records.append({
            **item,
            "task": "elastic",
            "status": "completed",
            "metrics": {"converge": True, "stress": stress.tolist()},
        })
    result = elastic.post_elastic(root, results=records)
    assert result.status == "completed"
    tensor = json.loads((root / "reports/elastic_tensor.json").read_text())["elastic_tensor_GPa"]
    assert np.asarray(tensor) == pytest.approx(np.eye(6) * 100, abs=1e-8)
