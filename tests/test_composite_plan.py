from __future__ import annotations

import json
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from ase import Atoms

from abacus_forge.api import prepare
from abacus_forge.composite import prepare_vibration
from abacus_forge.result import CollectionResult, RunResult
from abacus_forge.runner import LocalRunner
from tests.support.fake_executables import write_fake_abacus

pytestmark = [pytest.mark.composite, pytest.mark.integration]


def _prepared(tmp_path):
    root = tmp_path / "original"
    prepare(root, structure=Atoms("H", positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True), task="scf")
    prepare_vibration(root, atom_indices=[1])
    return root


def test_expanded_plan_is_portable(tmp_path):
    root = _prepared(tmp_path)
    payload = json.loads((root / "reports/vibration_plan.json").read_text())
    assert len(payload["subtasks"]) == 7
    assert all(item.get("unit_id") and item.get("workspace_rel") for item in payload["subtasks"])
    assert str(root) not in json.dumps(payload)
    from abacus_forge.composite.plan import list_subtasks

    moved = tmp_path / "relocated"
    shutil.move(root, moved)
    result = list_subtasks(moved, "vibration")
    assert len(result.subtasks) == 7
    assert all(Path(row["workspace"]).is_relative_to(moved) for row in result.subtasks)
    assert result.to_envelope().artifacts[0].path_rel == "reports/vibration_plan.json"


def test_expanded_units_use_the_generated_structure_with_custom_input_selector(tmp_path):
    from abacus_forge.input_io import read_input, write_input
    from abacus_forge.structure import AbacusStructure

    root = tmp_path / "custom-structure"
    prepare(root, structure=Atoms("H", positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True), task="scf")
    structure = AbacusStructure.from_input(root / "inputs/STRU", structure_format="stru")
    structure.atoms.positions[0, 0] = 0.5
    (root / "inputs/source.stru").write_text(structure.to_stru())
    params = read_input(root / "inputs/INPUT")
    write_input(root / "inputs/INPUT", {**params, "stru_file": "source.stru"})
    result = prepare_vibration(root, atom_indices=[1], stepsize=0.01)
    unit = next(row for row in result.subtasks if row.get("axis") == "x" and row.get("delta") == 0.01)
    inputs = Path(unit["workspace"]) / "inputs"
    actual_path = inputs / read_input(inputs / "INPUT").get("stru_file", "STRU")
    actual = AbacusStructure.from_input(actual_path, structure_format="stru")
    assert actual.atoms.positions[0, 0] == pytest.approx(0.51)


def test_selected_kpoint_input_is_normalized_and_bound_to_the_unit(tmp_path):
    from abacus_forge.composite.plan import collect_subtask
    from abacus_forge.input_io import read_input, read_kpt, write_input

    root = tmp_path / "selected-kpt"
    prepare(root, structure=Atoms("H", positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True), task="scf")
    (root / "inputs/selected.kpt").write_text("K_POINTS\n0\nGamma\n2 2 2 0 0 0\n")
    write_input(root / "inputs/INPUT", {**read_input(root / "inputs/INPUT"), "kpoint_file": "selected.kpt"})
    unit = prepare_vibration(root, atom_indices=[1]).subtasks[0]
    inputs = Path(unit["workspace"]) / "inputs"
    assert read_input(inputs / "INPUT").get("kpoint_file", "KPT") == "KPT"
    assert read_kpt(inputs / "KPT")["mesh"] == [2, 2, 2]
    (inputs / "KPT").write_text("K_POINTS\n0\nGamma\n6 6 6 0 0 0\n")
    with pytest.raises(ValueError, match="inputs changed"):
        collect_subtask(root, "vibration", unit["unit_id"], collector=_force_collector)


def test_input_digest_follows_explicit_structure_and_kpoint_selectors(tmp_path):
    from abacus_forge.composite.plan import input_digest
    from abacus_forge.input_io import read_input, write_input

    root = _prepared(tmp_path)
    inputs = root / "inputs"
    (inputs / "source.stru").write_bytes((inputs / "STRU").read_bytes())
    (inputs / "selected.kpt").write_text("K_POINTS\n0\nGamma\n2 2 2 0 0 0\n")
    write_input(inputs / "INPUT", {**read_input(inputs / "INPUT"), "stru_file": "source.stru", "kpoint_file": "selected.kpt"})
    before = input_digest(root)
    (inputs / "selected.kpt").write_text("K_POINTS\n0\nGamma\n6 6 6 0 0 0\n")
    after = input_digest(root)
    assert after != before
    (inputs / "source.stru").write_text((inputs / "source.stru").read_text() + "\n# edited\n")
    assert input_digest(root) != after


def test_expansion_does_not_copy_reference_engine_outputs_as_displaced_results(tmp_path):
    from abacus_forge.composite.plan import collect_subtask

    root = tmp_path / "reference-has-outputs"
    prepare(root, structure=Atoms("H", positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True), task="scf")
    output = root / "inputs/OUT.ABACUS"
    output.mkdir()
    (output / "running_scf.log").write_text("NATOM = 1\nTOTAL ENERGY = -1.0\nSCF CONVERGED\nNORMAL END\n")
    unit = prepare_vibration(root, atom_indices=[1]).subtasks[1]
    assert not (Path(unit["workspace"]) / "inputs/OUT.ABACUS").exists()
    record = collect_subtask(root, "vibration", unit["unit_id"])
    assert record["status"] != "completed"


def test_legacy_charge_density_still_stages_requested_restart(tmp_path):
    from abacus_forge.composite.properties import prepare_charge_density
    from abacus_forge.input_io import read_input, write_input

    root = tmp_path / "charge-restart"
    prepare(root, structure=Atoms("H", positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True), task="scf")
    inputs = root / "inputs"
    write_input(inputs / "INPUT", {**read_input(inputs / "INPUT"), "init_chg": "file", "read_file_dir": "OUT.ABACUS"})
    restart = inputs / "OUT.ABACUS/ABACUS-CHARGE-DENSITY.restart"
    restart.parent.mkdir()
    restart.write_bytes(b"reference restart fixture")
    result = prepare_charge_density(root)
    assert result.status == "prepared"
    child_inputs = Path(result.subtasks[0]["workspace"]) / "inputs"
    assert read_input(child_inputs / "INPUT")["init_chg"] == "file"
    assert (child_inputs / "OUT.ABACUS" / restart.name).read_bytes() == restart.read_bytes()


def test_independent_units_overlap_and_only_execute_requested_units(tmp_path):
    from abacus_forge.composite.plan import execute_subtask, list_subtasks

    root = _prepared(tmp_path)
    units = list_subtasks(root, "vibration").subtasks
    barrier = threading.Barrier(2, timeout=5)

    class BarrierRunner:
        def run(self, workspace):
            barrier.wait()
            workspace.write_text("outputs/ran", workspace.root.name)
            return RunResult(workspace.root, ["controlled-engine"], 0, "completed", workspace.outputs_dir / "stdout.log", workspace.outputs_dir / "stderr.log", 1)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda unit: execute_subtask(root, "vibration", unit["unit_id"], runner=BarrierRunner()), units[:2]))
    assert all(result["status"] == "completed" for result in results)
    assert all((Path(row["workspace"]) / "outputs/ran").exists() for row in units[:2])
    assert all(not (Path(row["workspace"]) / "outputs/ran").exists() for row in units[2:])
    assert all(not (Path(row["workspace"]) / "reports/collected.json").exists() for row in units)
    assert all(result["outcome"]["envelope"]["status"]["collection"] == "not_collected" for result in results)


def _force_collector(workspace):
    return CollectionResult(workspace.root, "completed", {"normal_end": True, "converge": True, "force": [[1.0, 2.0, 3.0]]})


def test_gather_keeps_order_and_failed_records_and_retry_is_explicit(tmp_path):
    from abacus_forge.composite.plan import collect_subtask, gather_subtasks, list_subtasks

    root = _prepared(tmp_path)
    units = list_subtasks(root, "vibration").subtasks
    def broken(_workspace):
        raise OSError("unreadable force file")
    records = [collect_subtask(root, "vibration", unit["unit_id"], collector=broken if index == 2 else _force_collector) for index, unit in enumerate(units)]
    result = gather_subtasks(root, "vibration", reversed(records))
    assert result.status == "degraded"
    assert result.summary["failed_units"] == [units[2]["unit_id"]]
    assert [row["unit_id"] for row in result.subtasks] == [row["unit_id"] for row in units]
    assert all((root / row["record_path_rel"]).is_file() for row in records)
    old_record_path = root / records[2]["record_path_rel"]
    records[2] = collect_subtask(root, "vibration", units[2]["unit_id"], collector=_force_collector)
    assert old_record_path.is_file()
    final = gather_subtasks(root, "vibration", records)
    assert final.status == "completed"
    assert final.summary["missing_units"] == []
    partial = gather_subtasks(root, "vibration", records[:1])
    assert partial.summary["missing_units"] == [unit["unit_id"] for unit in units[1:]]
    assert partial.status == "degraded"
    assert all(not artifact.path_rel.startswith("/") for artifact in final.to_envelope().artifacts)


def test_gather_rejects_duplicate_unknown_or_mismatched_results(tmp_path):
    from abacus_forge.composite.plan import collect_subtask, gather_subtasks, list_subtasks

    root = _prepared(tmp_path)
    unit = list_subtasks(root, "vibration").subtasks[0]
    record = collect_subtask(root, "vibration", unit["unit_id"], collector=_force_collector)
    for records, expected in [([record, record], "duplicate"), ([{**record, "unit_id": "other"}], "unknown"), ([{**record, "input_digest": "changed"}], "input"), ([{**record, "phase": "execute"}], "collect")]:
        with pytest.raises(ValueError, match=expected):
            gather_subtasks(root, "vibration", records)
    with pytest.raises(ValueError, match="input"):
        path = Path(unit["workspace"]) / "inputs/INPUT"
        path.write_text(path.read_text() + "\necutwfc 120\n")
        collect_subtask(root, "vibration", unit["unit_id"], collector=_force_collector)


def test_actual_runner_and_collector_records_can_be_gathered_after_relocation(tmp_path):
    from abacus_forge.composite.plan import collect_subtask, execute_subtask, gather_subtasks, list_subtasks

    root = _prepared(tmp_path)
    executable = write_fake_abacus(tmp_path / "engine", stdout_lines=["NATOM = 1", "TOTAL ENERGY = -1.0", "SCF CONVERGED", "NORMAL END"])
    unit = list_subtasks(root, "vibration").subtasks[0]
    execution = execute_subtask(root, "vibration", unit["unit_id"], runner=LocalRunner(executable=str(executable)))
    assert execution["status"] == "completed"
    record = collect_subtask(root, "vibration", unit["unit_id"])
    assert record["metrics"]["normal_end"] is True
    relocated = tmp_path / "moved"
    shutil.move(root, relocated)
    result = gather_subtasks(relocated, "vibration", [json.loads(json.dumps(record))])
    assert result.subtasks[0]["workspace"] == str(relocated / unit["workspace_rel"])
    assert len(result.summary["missing_units"]) == 6


def test_execute_exception_is_an_individual_durable_failure(tmp_path):
    from abacus_forge.composite.plan import execute_subtask, list_subtasks

    root = _prepared(tmp_path)
    unit = list_subtasks(root, "vibration").subtasks[0]
    class BrokenRunner:
        def run(self, workspace):
            raise OSError("launcher I/O failed")
    record = execute_subtask(root, "vibration", unit["unit_id"], runner=BrokenRunner())
    assert record["status"] == "failed"
    assert record["diagnostics"]["exception_type"] == "OSError"
    assert (root / record["record_path_rel"]).is_file()
    assert record["outcome"]["envelope"]["status"]["execution"] == "failed"


def test_old_plan_remains_readable_at_original_root_without_rewriting(tmp_path):
    from abacus_forge.composite.plan import load_plan

    root = _prepared(tmp_path)
    plan_file = root / "reports/vibration_plan.json"
    current = load_plan(root, "vibration")
    old = {"task": "vibration", "stepsize": 0.01, "subtasks": [{key: value for key, value in unit.items() if key not in {"unit_id", "workspace_rel", "input_digest"}} for unit in current["subtasks"]]}
    before = json.dumps(old)
    plan_file.write_text(before)
    loaded = load_plan(root, "vibration")
    assert len(loaded["subtasks"]) == 7
    assert loaded["atom_indices"] == [1]
    assert loaded["legacy_input_binding"] == "current_inputs"
    assert plan_file.read_text() == before


def test_plan_rejects_units_outside_root_and_duplicate_workspaces(tmp_path):
    from abacus_forge.composite.plan import load_plan

    root = _prepared(tmp_path)
    path = root / "reports/vibration_plan.json"
    plan = json.loads(path.read_text())
    plan["subtasks"][1]["workspace_rel"] = plan["subtasks"][0]["workspace_rel"]
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="duplicate"):
        load_plan(root, "vibration")
    plan["subtasks"][1]["workspace_rel"] = "../outside"
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError):
        load_plan(root, "vibration")


@pytest.mark.cli
def test_cli_unit_handoff_and_partial_gather(tmp_path):
    from tests.support.process import run_cli

    root = _prepared(tmp_path)
    listed = run_cli("vibration", "units", root, "--json")
    assert listed.returncode == 0, listed.stderr
    units = json.loads(listed.stdout)["subtasks"]
    executable = write_fake_abacus(tmp_path / "engine", stdout_lines=["NATOM = 1", "SCF CONVERGED", "NORMAL END"])
    executed = run_cli("vibration", "execute-unit", root, "--unit-id", units[0]["unit_id"], "--executable", executable, "--json")
    assert executed.returncode == 0, executed.stderr
    assert json.loads(executed.stdout)["phase"] == "execute"
    collected = run_cli("vibration", "collect-unit", root, "--unit-id", units[0]["unit_id"], "--json")
    assert collected.returncode == 0, collected.stderr
    record_file = tmp_path / "force.json"
    record_file.write_text(collected.stdout)
    gathered = run_cli("vibration", "gather", root, "--results", record_file, "--json")
    assert gathered.returncode == 1
    payload = json.loads(gathered.stdout)
    assert payload["status"] == "degraded"
    assert len(payload["summary"]["missing_units"]) == 6
    gathered_file = tmp_path / "gathered.json"
    gathered_file.write_text(gathered.stdout)
    posted = run_cli("vibration", "post", root, "--results", gathered_file, "--json")
    assert posted.returncode == 1, posted.stderr
    assert json.loads(posted.stdout)["status"] == "degraded"
    assert all(not (Path(unit["workspace"]) / "outputs/stdout.log").exists() for unit in units[1:])


@pytest.mark.cli
@pytest.mark.parametrize("task,options", [("elastic", []), ("vibration", ["--atom-indices", "1"]), ("phonon", ["--supercell", "1", "1", "1"])])
def test_cli_expansion_and_explicit_post_are_consumable_json(tmp_path, task, options):
    from tests.support.process import run_cli
    import numpy as np

    if task == "phonon":
        pytest.importorskip("phonopy")
    root = tmp_path / task
    prepare(root, structure=Atoms("H", positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True), task="scf")
    prepared = run_cli(task, "prepare", root, *options, "--json")
    assert prepared.returncode == 0, prepared.stderr
    units = json.loads(prepared.stdout)["subtasks"]
    records = []
    for unit in units:
        metrics = {"normal_end": True, "converge": True}
        if task == "elastic":
            strain = np.asarray(unit["strain"])
            metrics["stress"] = (-1000 * np.array([strain[0, 0], strain[1, 1], strain[2, 2], 2 * strain[1, 2], 2 * strain[0, 2], 2 * strain[0, 1]])).tolist()
        else:
            from abacus_forge.structure import AbacusStructure
            atoms = AbacusStructure.from_input(Path(unit["workspace"]) / "inputs/STRU", structure_format="stru").atoms
            metrics["force"] = (-atoms.positions).reshape(-1).tolist()
        records.append({**unit, "status": "completed", "metrics": metrics})
    path = tmp_path / "records.json"
    path.write_text(json.dumps(list(reversed(records))))
    result = run_cli(task, "post", root, "--results", path, "--json")
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "completed"
    assert all(not (Path(unit["workspace"]) / "outputs/stdout.log").exists() for unit in units)
