"""Elastic local composite task pack."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from abacus_forge.composite.common import artifacts_under, collect_subtasks, ensure_root, require_prepared_inputs, run_subtasks, strained_structure, write_subtask, write_task_result
from abacus_forge.result import TaskResult


def prepare_elastic(
    workspace: str | Path,
    *,
    normal_strain: float = 0.01,
    shear_strain: float = 0.01,
    relax_atoms: bool = True,
) -> TaskResult:
    root = ensure_root(workspace)
    input_params, structure, kpt_payload = require_prepared_inputs(root)
    strains = _strain_set(normal_strain=normal_strain, shear_strain=shear_strain)
    subtasks = []
    for index, strain in enumerate(strains):
        params = dict(input_params)
        params["calculation"] = "relax" if relax_atoms else "scf"
        params["cal_stress"] = 1
        sub = write_subtask(
            root,
            f"elastic/deformed_{index:02d}",
            input_params=params,
            structure=strained_structure(structure, strain),
            kpt_payload=kpt_payload,
            metadata={"task": "elastic", "subtask_index": index, "strain": strain.tolist()},
        )
        subtasks.append({"workspace": str(sub.root), "strain": strain.tolist()})
    path = write_task_result(root, "reports/elastic_plan.json", {"task": "elastic", "subtasks": subtasks})
    return TaskResult(
        task="elastic",
        workspace=root.root,
        status="prepared",
        subtasks=subtasks,
        summary={"count": len(subtasks)},
        artifacts={str(path.relative_to(root.root)): str(path)},
    )


def run_elastic(workspace: str | Path, **kwargs: Any) -> TaskResult:
    root = ensure_root(workspace)
    subtasks = sorted((root.root / "elastic").glob("deformed_*"))
    return run_subtasks("elastic", root, subtasks, **kwargs)


def post_elastic(workspace: str | Path) -> TaskResult:
    root = ensure_root(workspace)
    paths = sorted((root.root / "elastic").glob("deformed_*"))
    rows = collect_subtasks(paths)
    stress_rows = [
        {"workspace": row["workspace"], "stress": row["metrics"].get("stress")}
        for row in rows
        if row["metrics"].get("stress") is not None
    ]
    summary = {"stress_count": len(stress_rows), "stress_rows": stress_rows}
    json_path = write_task_result(root, "reports/metrics_elastic.json", summary)
    csv_path = root.write_text("reports/metrics_elastic.csv", _elastic_csv(stress_rows))
    return TaskResult(
        task="elastic",
        workspace=root.root,
        status="completed" if stress_rows else "degraded",
        subtasks=rows,
        summary=summary,
        artifacts={
            **artifacts_under(root, "elastic"),
            str(json_path.relative_to(root.root)): str(json_path),
            str(csv_path.relative_to(root.root)): str(csv_path),
        },
    )


def _strain_set(*, normal_strain: float, shear_strain: float) -> list[np.ndarray]:
    strains = [np.zeros((3, 3))]
    for axis in range(3):
        for sign in (-1.0, 1.0):
            strain = np.zeros((3, 3))
            strain[axis, axis] = sign * normal_strain
            strains.append(strain)
    for left, right in ((0, 1), (0, 2), (1, 2)):
        for sign in (-1.0, 1.0):
            strain = np.zeros((3, 3))
            strain[left, right] = sign * shear_strain
            strain[right, left] = sign * shear_strain
            strains.append(strain)
    return strains


def _elastic_csv(rows: list[dict[str, Any]]) -> str:
    lines = ["workspace,stress"]
    for row in rows:
        lines.append(f"{row['workspace']},{' '.join(str(value) for value in row['stress'])}")
    return "\n".join(lines) + "\n"
