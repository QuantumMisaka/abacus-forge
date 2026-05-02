"""Equation-of-state local composite task pack."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from abacus_forge.composite.common import artifacts_under, collect_subtasks, ensure_root, require_prepared_inputs, run_subtasks, scaled_structure, write_subtask, write_task_result
from abacus_forge.result import TaskResult


def prepare_eos(
    workspace: str | Path,
    *,
    start: float = 0.9,
    end: float = 1.1,
    step: float = 0.025,
    calculation: str | None = None,
) -> TaskResult:
    root = ensure_root(workspace)
    input_params, structure, kpt_payload = require_prepared_inputs(root)
    scales = _volume_scales(start=start, end=end, step=step)
    subtasks = []
    for index, scale in enumerate(scales):
        params = dict(input_params)
        if calculation is not None:
            params["calculation"] = calculation
        sub = write_subtask(
            root,
            f"eos/eos{index:02d}",
            input_params=params,
            structure=scaled_structure(structure, scale),
            kpt_payload=kpt_payload,
            metadata={"task": "eos", "volume_scale": scale, "subtask_index": index},
        )
        subtasks.append({"workspace": str(sub.root), "volume_scale": scale})
    payload = {"task": "eos", "subtasks": subtasks, "start": start, "end": end, "step": step}
    path = write_task_result(root, "reports/eos_plan.json", payload)
    return TaskResult(
        task="eos",
        workspace=root.root,
        status="prepared",
        subtasks=subtasks,
        summary={"count": len(subtasks)},
        artifacts={str(path.relative_to(root.root)): str(path)},
    )


def run_eos(workspace: str | Path, **kwargs: Any) -> TaskResult:
    root = ensure_root(workspace)
    subtasks = sorted((root.root / "eos").glob("eos*"))
    return run_subtasks("eos", root, subtasks, **kwargs)


def post_eos(workspace: str | Path) -> TaskResult:
    root = ensure_root(workspace)
    paths = sorted((root.root / "eos").glob("eos*"))
    rows = collect_subtasks(paths)
    points = []
    for row in rows:
        metrics = row["metrics"]
        volume = metrics.get("volume")
        energy_per_atom = metrics.get("energy_per_atom")
        if volume is not None and energy_per_atom is not None:
            points.append({"workspace": row["workspace"], "volume": volume, "energy_per_atom": energy_per_atom})
    summary = {"points": points, "count": len(points)}
    if len({item["volume"] for item in points}) >= 3:
        coeff = np.polyfit([item["volume"] for item in points], [item["energy_per_atom"] for item in points], 2)
        min_volume = float(-coeff[1] / (2 * coeff[0])) if coeff[0] != 0 else None
        summary["quadratic_fit"] = {"coefficients": [float(value) for value in coeff], "minimum_volume": min_volume}
    path = write_task_result(root, "reports/metrics_eos.json", summary)
    return TaskResult(
        task="eos",
        workspace=root.root,
        status="completed" if points else "degraded",
        subtasks=rows,
        summary=summary,
        artifacts={**artifacts_under(root, "eos"), str(path.relative_to(root.root)): str(path)},
    )


def _volume_scales(*, start: float, end: float, step: float) -> list[float]:
    if step <= 0:
        raise ValueError("EOS step must be positive")
    values = [1.0]
    offset = step
    while 1.0 - offset >= start or 1.0 + offset <= end:
        if 1.0 - offset >= start:
            values.append(1.0 - offset)
        if 1.0 + offset <= end:
            values.append(1.0 + offset)
        offset += step
    return values
