"""Finite-displacement vibration local composite task pack."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import numpy as np

from abacus_forge.composite.common import artifacts_under, displaced_structure, ensure_root, require_prepared_inputs, run_subtasks, write_subtask, write_task_result
from abacus_forge.composite.plan import collect_subtask, gather_subtasks, input_digest, load_plan, save_plan
from abacus_forge.result import TaskResult
from abacus_forge.workspace import Workspace


def prepare_vibration(
    workspace: str | Path,
    *,
    stepsize: float = 0.01,
    atom_indices: list[int] | None = None,
) -> TaskResult:
    root = ensure_root(Path(workspace).expanduser().resolve())
    if (root.reports_dir / "vibration_plan.json").exists():
        raise FileExistsError("vibration plan already exists; prepare in a new workspace")
    input_params, structure, kpt_payload = require_prepared_inputs(root)
    if isinstance(stepsize, bool) or not isinstance(stepsize, (int, float)) or not np.isfinite(stepsize) or stepsize <= 0:
        raise ValueError("vibration stepsize must be a finite positive number")
    natoms = len(structure.atoms)
    if atom_indices is None:
        selected = list(range(natoms))
    else:
        if not atom_indices or any(isinstance(index, bool) or not isinstance(index, int) or not 1 <= index <= natoms for index in atom_indices):
            raise ValueError("atom_indices must contain valid one-based atom indices")
        if len(set(atom_indices)) != len(atom_indices):
            raise ValueError("atom_indices must not contain duplicates")
        selected = sorted(index - 1 for index in atom_indices)
    subtasks = []
    eq_params = dict(input_params)
    eq_params["calculation"] = "scf"
    eq_params["cal_force"] = 1
    eq = write_subtask(
        root,
        "vibration/eq",
        input_params=eq_params,
        structure=structure,
        kpt_payload=kpt_payload,
        metadata={"task": "vibration", "subtask_index": 0, "kind": "equilibrium"},
        copy_reference_outputs=False,
    )
    subtasks.append({"workspace": str(eq.root), "kind": "equilibrium"})
    for atom_index in selected:
        for axis, axis_name in enumerate(("x", "y", "z")):
            for sign, sign_name in ((1.0, "plus"), (-1.0, "minus")):
                relative = f"vibration/disp_{atom_index + 1}_{axis_name}_{sign_name}"
                sub = write_subtask(
                    root,
                    relative,
                    input_params=eq_params,
                    structure=displaced_structure(structure, atom_index, axis, sign * stepsize),
                    kpt_payload=kpt_payload,
                    metadata={
                        "task": "vibration",
                        "atom_index": atom_index + 1,
                        "axis": axis_name,
                        "delta": sign * stepsize,
                    },
                    copy_reference_outputs=False,
                )
                subtasks.append({"workspace": str(sub.root), "atom_index": atom_index + 1, "axis": axis_name, "delta": sign * stepsize})
    path = save_plan(root, "vibration", subtasks, stepsize=stepsize, atom_indices=[index + 1 for index in selected])
    subtasks = load_plan(root, "vibration")["subtasks"]
    return TaskResult(
        task="vibration",
        workspace=root.root,
        status="prepared",
        subtasks=subtasks,
        summary={"count": len(subtasks), "stepsize": stepsize},
        artifacts={str(path.relative_to(root.root)): str(path)},
    )


def run_vibration(workspace: str | Path, **kwargs: Any) -> TaskResult:
    root = ensure_root(Path(workspace).expanduser().resolve())
    subtasks = [Path(item["workspace"]) for item in load_plan(root, "vibration")["subtasks"]]
    return run_subtasks("vibration", root, subtasks, **kwargs)


def post_vibration(workspace: str | Path, *, results: Iterable[dict[str, Any]] | None = None) -> TaskResult:
    """Analyze explicit finite-displacement forces without rerunning units."""
    root = ensure_root(Path(workspace).expanduser().resolve())
    plan = load_plan(root, "vibration")
    if results is None:
        results = [
            collect_subtask(root, "vibration", item["unit_id"])
            for item in plan["subtasks"]
        ]
    gathered = gather_subtasks(root, "vibration", results)
    rows = gathered.subtasks
    reference = next(item for item in plan["subtasks"] if item.get("kind") == "equilibrium")
    if input_digest(reference["workspace"]) != reference["input_digest"]:
        raise ValueError("vibration reference inputs changed since prepare")
    _, structure, _ = require_prepared_inputs(Workspace(Path(reference["workspace"])))
    selected = [index - 1 for index in plan["atom_indices"]]
    force_norms = []
    forces = {}
    invalid_units = []
    for row in rows:
        metrics = row.get("metrics", {})
        try:
            force = np.asarray(metrics.get("force"), dtype=float).reshape((-1, 3))
            valid = force.shape == (len(structure.atoms), 3) and np.isfinite(force).all()
        except (TypeError, ValueError):
            valid = False
        if not valid or metrics.get("converge") is not True or metrics.get("normal_end") is not True:
            invalid_units.append(row["unit_id"])
            continue
        force_norms.append(float(np.linalg.norm(force)))
        key = "eq" if row.get("kind") == "equilibrium" else (row["atom_index"] - 1, row["axis"], np.sign(row["delta"]))
        forces[key] = force
    summary = {
        "force_samples": len(force_norms),
        "max_force_norm": max(force_norms) if force_norms else None,
        "frequencies": [],
        "zpe": None,
        "missing_units": gathered.summary.get("missing_units", []),
        "failed_units": gathered.summary.get("failed_units", []),
        "invalid_units": invalid_units,
    }
    if gathered.status == "completed" and not invalid_units:
        from ase.vibrations import VibrationsData

        hessian_rows = []
        for atom_index in selected:
            for axis in ("x", "y", "z"):
                difference = forces[(atom_index, axis, -1)] - forces[(atom_index, axis, 1)]
                hessian_rows.append((difference[selected] / (2 * plan["stepsize"])).reshape(-1))
        hessian = np.asarray(hessian_rows)
        # Force derivatives from numerical SCF data may differ by rounding;
        # the physical Hessian is the symmetric part of the derivative matrix.
        hessian = (hessian + hessian.T) / 2
        data = VibrationsData.from_2d(structure.atoms, hessian, indices=selected)
        frequencies = data.get_frequencies()
        signed_frequencies = [float(-abs(value.imag) if abs(value.imag) > 1e-8 else value.real) for value in frequencies]
        zpe = float(data.get_zero_point_energy())
        if np.isfinite(signed_frequencies).all() and np.isfinite(zpe):
            summary.update({
                "frequencies": signed_frequencies,
                "frequency_unit": "cm^-1",
                "imaginary_modes": sum(value < 0 for value in signed_frequencies),
                "zpe": zpe,
                "zpe_unit": "eV",
                "hessian_eV_A2": hessian.tolist(),
                "atom_indices": plan["atom_indices"],
            })
    path = write_task_result(root, "reports/metrics_vibration.json", summary)
    return TaskResult(
        task="vibration",
        workspace=root.root,
        status="completed" if summary["frequencies"] else "degraded",
        subtasks=rows,
        summary=summary,
        artifacts={**artifacts_under(root, "vibration"), str(path.relative_to(root.root)): str(path)},
        diagnostics={"method": "ase-vibrations-central-finite-difference", "nfree": 2},
    )
