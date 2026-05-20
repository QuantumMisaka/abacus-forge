"""Local property packs for cube, work-function, vacancy, and BEC workflows."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from abacus_forge.api import collect
from abacus_forge.composite.common import artifacts_under, ensure_root, require_prepared_inputs, run_subtasks, write_subtask, write_task_result
from abacus_forge.cube import CubeData, add_cubes, planar_average, subtract_cubes
from abacus_forge.input_io import read_input
from abacus_forge.modify import modify_stru
from abacus_forge.result import TaskResult
from abacus_forge.structure import AbacusStructure
from abacus_forge.workspace import Workspace


def prepare_charge_density(workspace: str | Path) -> TaskResult:
    return _prepare_single_property(workspace, task="charge-density", relative="charge-density/scf", updates={"out_chg": 1})


def prepare_spin_density(workspace: str | Path) -> TaskResult:
    return _prepare_single_property(workspace, task="spin-density", relative="spin-density/scf", updates={"out_chg": 1, "nspin": 2})


def prepare_elf(workspace: str | Path) -> TaskResult:
    return _prepare_single_property(workspace, task="elf", relative="elf/scf", updates={"out_elf": 1})


def prepare_bader(workspace: str | Path) -> TaskResult:
    return _prepare_single_property(workspace, task="bader", relative="bader/scf", updates={"out_chg": 1})


def prepare_charge_diff(workspace: str | Path) -> TaskResult:
    root = ensure_root(workspace)
    input_params, structure, kpt_payload = require_prepared_inputs(root)
    subtasks = []
    for name in ("full", "subsystem1", "subsystem2"):
        sub = write_subtask(
            root,
            f"charge-diff/{name}",
            input_params={**input_params, "out_chg": 1},
            structure=structure,
            kpt_payload=kpt_payload,
            metadata={"task": "charge-diff", "role": name},
        )
        subtasks.append({"workspace": str(sub.root), "role": name})
    path = write_task_result(root, "reports/charge_diff_plan.json", {"task": "charge-diff", "subtasks": subtasks})
    return TaskResult(
        task="charge-diff",
        workspace=root.root,
        status="prepared",
        subtasks=subtasks,
        summary={"count": len(subtasks)},
        artifacts={str(path.relative_to(root.root)): str(path)},
    )


def run_charge_density(workspace: str | Path, **kwargs: Any) -> TaskResult:
    return _run_pack(workspace, "charge-density", "charge-density", **kwargs)


def run_spin_density(workspace: str | Path, **kwargs: Any) -> TaskResult:
    return _run_pack(workspace, "spin-density", "spin-density", **kwargs)


def run_elf(workspace: str | Path, **kwargs: Any) -> TaskResult:
    return _run_pack(workspace, "elf", "elf", **kwargs)


def run_bader(workspace: str | Path, **kwargs: Any) -> TaskResult:
    return _run_pack(workspace, "bader", "bader", **kwargs)


def run_charge_diff(workspace: str | Path, **kwargs: Any) -> TaskResult:
    return _run_pack(workspace, "charge-diff", "charge-diff", **kwargs)


def post_charge_density(workspace: str | Path) -> TaskResult:
    root = ensure_root(workspace)
    cube = _find_first(root.root / "charge-density", ["*CHG*.cube", "*.cube"])
    summary = {"charge_density_file": str(cube) if cube else None}
    path = write_task_result(root, "reports/metrics_charge_density.json", summary)
    return TaskResult("charge-density", root.root, "completed" if cube else "degraded", summary=summary, artifacts={**artifacts_under(root, "charge-density"), str(path.relative_to(root.root)): str(path)})


def post_spin_density(workspace: str | Path) -> TaskResult:
    root = ensure_root(workspace)
    base = root.root / "spin-density"
    up = _find_first(base, ["SPIN1_CHG.cube", "*SPIN1*.cube", "*UP*.cube"])
    down = _find_first(base, ["SPIN2_CHG.cube", "*SPIN2*.cube", "*DOWN*.cube"])
    diagnostics = {"spin_up": str(up) if up else None, "spin_down": str(down) if down else None}
    if up is None or down is None:
        summary = {"spin_density_file": None}
        path = write_task_result(root, "reports/metrics_spin_density.json", summary)
        return TaskResult("spin-density", root.root, "degraded", summary=summary, artifacts={str(path.relative_to(root.root)): str(path)}, diagnostics=diagnostics)
    output = root.root / "reports" / "spin_density.cube"
    subtract_cubes(up, down).write(output)
    summary = {"spin_density_file": str(output)}
    path = write_task_result(root, "reports/metrics_spin_density.json", summary)
    return TaskResult("spin-density", root.root, "completed", summary=summary, artifacts={**artifacts_under(root, "spin-density"), str(output.relative_to(root.root)): str(output), str(path.relative_to(root.root)): str(path)}, diagnostics=diagnostics)


def post_charge_diff(workspace: str | Path) -> TaskResult:
    root = ensure_root(workspace)
    base = root.root / "charge-diff"
    full = _find_first(base / "full", ["*CHG*.cube", "*.cube"])
    sub1 = _find_first(base / "subsystem1", ["*CHG*.cube", "*.cube"])
    sub2 = _find_first(base / "subsystem2", ["*CHG*.cube", "*.cube"])
    diagnostics = {"full": str(full) if full else None, "subsystem1": str(sub1) if sub1 else None, "subsystem2": str(sub2) if sub2 else None}
    if full is None or sub1 is None or sub2 is None:
        summary = {"charge_density_difference_file": None}
        path = write_task_result(root, "reports/metrics_charge_diff.json", summary)
        return TaskResult("charge-diff", root.root, "degraded", summary=summary, artifacts={str(path.relative_to(root.root)): str(path)}, diagnostics=diagnostics)
    summed = add_cubes([sub1, sub2])
    output = root.root / "reports" / "charge_density_diff.cube"
    subtract_cubes(full, summed).write(output)
    summary = {"charge_density_difference_file": str(output)}
    path = write_task_result(root, "reports/metrics_charge_diff.json", summary)
    return TaskResult("charge-diff", root.root, "completed", summary=summary, artifacts={**artifacts_under(root, "charge-diff"), str(output.relative_to(root.root)): str(output), str(path.relative_to(root.root)): str(path)}, diagnostics=diagnostics)


def post_elf(workspace: str | Path) -> TaskResult:
    root = ensure_root(workspace)
    cube = _find_first(root.root / "elf", ["*ELF*.cube", "*.cube"])
    summary = {"elf_file": str(cube) if cube else None}
    path = write_task_result(root, "reports/metrics_elf.json", summary)
    return TaskResult("elf", root.root, "completed" if cube else "degraded", summary=summary, artifacts={**artifacts_under(root, "elf"), str(path.relative_to(root.root)): str(path)})


def post_bader(workspace: str | Path, *, executable: str = "bader") -> TaskResult:
    root = ensure_root(workspace)
    cube = _find_first(root.root / "bader", ["*CHG*.cube", "*.cube"])
    diagnostics = {"charge_cube": str(cube) if cube else None, "executable": executable}
    if cube is None:
        summary = {"bader_output": None}
        path = write_task_result(root, "reports/metrics_bader.json", summary)
        return TaskResult("bader", root.root, "degraded", summary=summary, artifacts={str(path.relative_to(root.root)): str(path)}, diagnostics=diagnostics)
    if shutil.which(executable) is None:
        diagnostics["error"] = f"{executable} executable not found"
        summary = {"bader_output": None}
        path = write_task_result(root, "reports/metrics_bader.json", summary)
        return TaskResult("bader", root.root, "degraded", summary=summary, artifacts={str(path.relative_to(root.root)): str(path)}, diagnostics=diagnostics)
    run_dir = root.root / "reports" / "bader"
    run_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run([executable, str(cube)], cwd=run_dir, check=False, capture_output=True, text=True)
    diagnostics.update({"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr})
    summary = {"bader_output": str(run_dir / "ACF.dat") if (run_dir / "ACF.dat").exists() else None}
    path = write_task_result(root, "reports/metrics_bader.json", summary)
    return TaskResult("bader", root.root, "completed" if completed.returncode == 0 else "failed", summary=summary, artifacts={**artifacts_under(root, "bader"), **artifacts_under(root, "reports/bader"), str(path.relative_to(root.root)): str(path)}, diagnostics=diagnostics)


def prepare_workfunc(workspace: str | Path, *, vacuum_axis: str = "auto", dipole_correction: bool = False) -> TaskResult:
    updates: dict[str, Any] = {"out_pot": 2}
    axis = _axis_name(vacuum_axis)
    if dipole_correction:
        updates["dip_cor_flag"] = 1
        if axis != "auto":
            updates["efield_dir"] = axis
    return _prepare_single_property(workspace, task="workfunc", relative="workfunc/scf", updates=updates, summary={"vacuum_axis": axis, "dipole_correction": dipole_correction})


def run_workfunc(workspace: str | Path, **kwargs: Any) -> TaskResult:
    return _run_pack(workspace, "workfunc", "workfunc", **kwargs)


def post_workfunc(workspace: str | Path, *, vacuum_axis: str = "auto") -> TaskResult:
    root = ensure_root(workspace)
    sub = Workspace(root.root / "workfunc" / "scf")
    potential = _find_first(sub.root, ["ElecStaticPot.cube", "*Pot*.cube", "*.cube"])
    diagnostics = {"potential_cube": str(potential) if potential else None}
    if potential is None:
        summary = {"work_function_ev": None}
        path = write_task_result(root, "reports/metrics_workfunc.json", summary)
        return TaskResult("workfunc", root.root, "degraded", summary=summary, artifacts={str(path.relative_to(root.root)): str(path)}, diagnostics=diagnostics)
    axis = _axis_index(vacuum_axis, sub)
    profile = planar_average(potential, axis=axis)
    collected = collect(sub)
    fermi = collected.metrics.get("fermi_energy")
    vacuum_level = max(profile) if profile else None
    work_function = float(vacuum_level - fermi) if vacuum_level is not None and fermi is not None else None
    summary = {
        "vacuum_axis": ["a", "b", "c"][axis],
        "vacuum_level_ev": float(vacuum_level) if vacuum_level is not None else None,
        "fermi_energy_ev": fermi,
        "work_function_ev": work_function,
        "planar_average": profile,
    }
    path = write_task_result(root, "reports/metrics_workfunc.json", summary)
    return TaskResult("workfunc", root.root, "completed" if work_function is not None else "degraded", subtasks=[collected.to_dict()], summary=summary, artifacts={**artifacts_under(root, "workfunc"), str(path.relative_to(root.root)): str(path)}, diagnostics=diagnostics)


def prepare_vacancy(
    workspace: str | Path,
    *,
    vacancy_indices: Sequence[int],
    supercell: Sequence[int] = (1, 1, 1),
) -> TaskResult:
    root = ensure_root(workspace)
    input_params, structure, kpt_payload = require_prepared_inputs(root)
    base_structure = structure.make_supercell(tuple(int(value) for value in supercell))
    pristine = write_subtask(root, "vacancy/pristine", input_params=input_params, structure=base_structure, kpt_payload=kpt_payload, metadata={"task": "vacancy", "role": "pristine"})
    subtasks = [{"workspace": str(pristine.root), "role": "pristine"}]
    for index in vacancy_indices:
        symbol = base_structure.atoms[int(index) - 1].symbol
        defect_structure = modify_stru(base_structure, vacancy_indices=[int(index)])
        sub = write_subtask(
            root,
            f"vacancy/defect_{int(index):03d}",
            input_params=input_params,
            structure=defect_structure,
            kpt_payload=kpt_payload,
            metadata={"task": "vacancy", "role": "defect", "vacancy_index": int(index), "removed_symbol": symbol},
        )
        subtasks.append({"workspace": str(sub.root), "role": "defect", "vacancy_index": int(index), "removed_symbol": symbol})
    path = write_task_result(root, "reports/vacancy_plan.json", {"task": "vacancy", "subtasks": subtasks, "supercell": list(supercell)})
    return TaskResult("vacancy", root.root, "prepared", subtasks=subtasks, summary={"count": len(subtasks) - 1}, artifacts={str(path.relative_to(root.root)): str(path)})


def run_vacancy(workspace: str | Path, **kwargs: Any) -> TaskResult:
    return _run_pack(workspace, "vacancy", "vacancy", **kwargs)


def post_vacancy(workspace: str | Path, *, ref_file: str | Path | None = None) -> TaskResult:
    root = ensure_root(workspace)
    pristine = collect(Workspace(root.root / "vacancy" / "pristine"))
    ref_energies = _read_ref_energies(Path(ref_file) if ref_file else root.root / "vacancy" / "ref_energy.txt")
    formation = []
    subtasks = [pristine.to_dict()]
    for defect_path in sorted((root.root / "vacancy").glob("defect_*")):
        defect = collect(Workspace(defect_path))
        subtasks.append(defect.to_dict())
        metadata = _read_metadata(defect_path)
        symbol = str(metadata.get("removed_symbol", ""))
        ref = ref_energies.get(symbol)
        pristine_energy = pristine.metrics.get("total_energy")
        defect_energy = defect.metrics.get("total_energy")
        value = float(defect_energy - pristine_energy + ref) if None not in {pristine_energy, defect_energy, ref} else None
        formation.append({"defect": defect_path.name, "removed_symbol": symbol, "formation_energy_ev": value})
    summary = {"formation_energies": formation, "reference_energies": ref_energies}
    path = write_task_result(root, "reports/metrics_vacancy.json", summary)
    return TaskResult("vacancy", root.root, "completed" if formation and all(item["formation_energy_ev"] is not None for item in formation) else "degraded", subtasks=subtasks, summary=summary, artifacts={**artifacts_under(root, "vacancy"), str(path.relative_to(root.root)): str(path)})


def prepare_bec(
    workspace: str | Path,
    *,
    atom_indices: Sequence[int],
    displacement: float = 0.01,
    directions: Sequence[str] = ("x", "y", "z"),
) -> TaskResult:
    root = ensure_root(workspace)
    input_params, structure, kpt_payload = require_prepared_inputs(root)
    params = {**input_params, "berry_phase": 1}
    org = write_subtask(root, "bec/org", input_params=params, structure=structure, kpt_payload=kpt_payload, metadata={"task": "bec", "role": "org"})
    subtasks = [{"workspace": str(org.root), "role": "org"}]
    for atom_index in atom_indices:
        for direction in directions:
            axis = _direction_axis(direction)
            for sign, label in ((1.0, "plus"), (-1.0, "minus")):
                atoms = structure.atoms.copy()
                positions = atoms.get_positions()
                positions[int(atom_index) - 1, axis] += sign * float(displacement)
                atoms.set_positions(positions)
                displaced = AbacusStructure(atoms, source_format=structure.source_format)
                sub = write_subtask(
                    root,
                    f"bec/disp_atom{int(atom_index):03d}_{direction}_{label}",
                    input_params=params,
                    structure=displaced,
                    kpt_payload=kpt_payload,
                    metadata={"task": "bec", "role": "displacement", "atom_index": int(atom_index), "direction": direction, "sign": label, "displacement": float(displacement)},
                )
                subtasks.append({"workspace": str(sub.root), "atom_index": int(atom_index), "direction": direction, "sign": label})
    path = write_task_result(root, "reports/bec_plan.json", {"task": "bec", "subtasks": subtasks, "displacement": float(displacement)})
    return TaskResult("bec", root.root, "prepared", subtasks=subtasks, summary={"count": len(subtasks)}, artifacts={str(path.relative_to(root.root)): str(path)})


def run_bec(workspace: str | Path, **kwargs: Any) -> TaskResult:
    return _run_pack(workspace, "bec", "bec", **kwargs)


def post_bec(workspace: str | Path) -> TaskResult:
    root = ensure_root(workspace)
    tensors: dict[str, list[list[float] | None]] = {}
    subtasks = []
    for plus_path in sorted((root.root / "bec").glob("disp_atom*_plus")):
        metadata = _read_metadata(plus_path)
        atom = int(metadata["atom_index"])
        direction = str(metadata["direction"])
        displacement = float(metadata["displacement"])
        minus_path = plus_path.with_name(plus_path.name.replace("_plus", "_minus"))
        plus = _read_polarization(plus_path)
        minus = _read_polarization(minus_path)
        subtasks.extend([{"workspace": str(plus_path), "polarization": plus}, {"workspace": str(minus_path), "polarization": minus}])
        if plus is None or minus is None:
            continue
        key = f"atom{atom:03d}"
        tensors.setdefault(key, [None, None, None])
        axis = _direction_axis(direction)
        tensors[key][axis] = [float((plus[i] - minus[i]) / (2.0 * displacement)) for i in range(3)]
    summary = {"bec_tensors": tensors}
    path = write_task_result(root, "reports/metrics_bec.json", summary)
    complete = bool(tensors) and all(any(row is not None for row in tensor) for tensor in tensors.values())
    return TaskResult("bec", root.root, "completed" if complete else "degraded", subtasks=subtasks, summary=summary, artifacts={**artifacts_under(root, "bec"), str(path.relative_to(root.root)): str(path)})


def _prepare_single_property(
    workspace: str | Path,
    *,
    task: str,
    relative: str,
    updates: dict[str, Any],
    summary: dict[str, Any] | None = None,
) -> TaskResult:
    root = ensure_root(workspace)
    input_params, structure, kpt_payload = require_prepared_inputs(root)
    sub = write_subtask(root, relative, input_params={**input_params, **updates}, structure=structure, kpt_payload=kpt_payload, metadata={"task": task})
    path = write_task_result(root, f"reports/{task.replace('-', '_')}_plan.json", {"task": task, "workspace": str(sub.root), "updates": updates})
    return TaskResult(task, root.root, "prepared", subtasks=[{"workspace": str(sub.root)}], summary=summary or {"count": 1}, artifacts={str(path.relative_to(root.root)): str(path)})


def _run_pack(workspace: str | Path, task: str, directory: str, **kwargs: Any) -> TaskResult:
    root = ensure_root(workspace)
    subtasks = sorted(path for path in (root.root / directory).glob("*") if path.is_dir())
    return run_subtasks(task, root, subtasks, **kwargs)


def _find_first(base: Path, patterns: Sequence[str]) -> Path | None:
    for pattern in patterns:
        for path in sorted(base.rglob(pattern)):
            if path.is_file():
                return path
    return None


def _axis_name(value: str) -> str:
    normalized = str(value).strip().lower()
    if normalized in {"auto", "a", "b", "c", "x", "y", "z"}:
        return {"x": "a", "y": "b", "z": "c"}.get(normalized, normalized)
    raise ValueError("vacuum_axis must be auto, a, b, c, x, y, or z")


def _axis_index(value: str, workspace: Workspace) -> int:
    axis = _axis_name(value)
    if axis != "auto":
        return {"a": 0, "b": 1, "c": 2}[axis]
    stru = workspace.inputs_dir / "STRU"
    if not stru.exists():
        return 2
    lengths = AbacusStructure.from_input(stru, structure_format="stru").atoms.cell.lengths()
    return int(np.argmax(lengths))


def _direction_axis(value: str) -> int:
    normalized = str(value).strip().lower()
    if normalized not in {"x", "y", "z", "a", "b", "c"}:
        raise ValueError("direction must be x, y, z, a, b, or c")
    return {"x": 0, "a": 0, "y": 1, "b": 1, "z": 2, "c": 2}[normalized]


def _read_metadata(workspace: Path) -> dict[str, Any]:
    meta = workspace / "meta.json"
    if not meta.exists():
        return {}
    payload = json.loads(meta.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_ref_energies(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    values: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            values[parts[0]] = float(parts[1])
    return values


def _read_polarization(workspace: Path) -> list[float] | None:
    path = workspace / "reports" / "polarization.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = payload.get("polarization")
    if not isinstance(values, list) or len(values) != 3:
        return None
    return [float(value) for value in values]
