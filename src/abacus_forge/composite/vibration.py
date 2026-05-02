"""Finite-displacement vibration local composite task pack."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from abacus_forge.composite.common import artifacts_under, collect_subtasks, displaced_structure, ensure_root, require_prepared_inputs, run_subtasks, write_subtask, write_task_result
from abacus_forge.result import TaskResult


def prepare_vibration(
    workspace: str | Path,
    *,
    stepsize: float = 0.01,
    atom_indices: list[int] | None = None,
) -> TaskResult:
    root = ensure_root(workspace)
    input_params, structure, kpt_payload = require_prepared_inputs(root)
    if stepsize <= 0:
        raise ValueError("vibration stepsize must be positive")
    natoms = len(structure.atoms)
    selected = [index - 1 for index in atom_indices] if atom_indices else list(range(natoms))
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
                )
                subtasks.append({"workspace": str(sub.root), "atom_index": atom_index + 1, "axis": axis_name, "delta": sign * stepsize})
    path = write_task_result(root, "reports/vibration_plan.json", {"task": "vibration", "stepsize": stepsize, "subtasks": subtasks})
    return TaskResult(
        task="vibration",
        workspace=root.root,
        status="prepared",
        subtasks=subtasks,
        summary={"count": len(subtasks), "stepsize": stepsize},
        artifacts={str(path.relative_to(root.root)): str(path)},
    )


def run_vibration(workspace: str | Path, **kwargs: Any) -> TaskResult:
    root = ensure_root(workspace)
    subtasks = sorted(path for path in (root.root / "vibration").iterdir() if path.is_dir())
    return run_subtasks("vibration", root, subtasks, **kwargs)


def post_vibration(workspace: str | Path) -> TaskResult:
    root = ensure_root(workspace)
    paths = sorted(path for path in (root.root / "vibration").iterdir() if path.is_dir())
    rows = collect_subtasks(paths)
    force_norms = []
    for row in rows:
        force = row["metrics"].get("force")
        if force:
            force_norms.append(float(np.linalg.norm(np.asarray(force, dtype=float))))
    summary = {
        "force_samples": len(force_norms),
        "max_force_norm": max(force_norms) if force_norms else None,
        "frequencies": [],
        "zpe": None,
    }
    path = write_task_result(root, "reports/metrics_vibration.json", summary)
    return TaskResult(
        task="vibration",
        workspace=root.root,
        status="completed" if force_norms else "degraded",
        subtasks=rows,
        summary=summary,
        artifacts={**artifacts_under(root, "vibration"), str(path.relative_to(root.root)): str(path)},
        diagnostics={"thermochemistry": "not-computed-in-minimal-pack"},
    )
