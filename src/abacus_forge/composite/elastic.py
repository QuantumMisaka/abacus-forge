"""Elastic local composite task pack."""

from __future__ import annotations

import json
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
    plan = json.loads((root.root / "reports/elastic_plan.json").read_text(encoding="utf-8"))
    strain_by_name = {
        Path(item["workspace"]).name: item.get("strain")
        for item in plan.get("subtasks", [])
    }
    stress_rows = [
        {
            "workspace": row["workspace"],
            "name": Path(row["workspace"]).name,
            "strain": strain_by_name.get(Path(row["workspace"]).name),
            "stress": row["metrics"].get("stress"),
        }
        for row in rows
        if row["metrics"].get("stress") is not None
    ]
    fit = _fit_elastic(stress_rows)
    summary = {
        "stress_count": len(stress_rows),
        "stress_rows": stress_rows,
        "elastic_fit": "available" if fit is not None else "unavailable",
    }
    json_payload = {**summary, **({"fit": fit} if fit is not None else {})}
    json_path = write_task_result(root, "reports/metrics_elastic.json", json_payload)
    csv_path = root.write_text("reports/metrics_elastic.csv", _elastic_csv(stress_rows))
    artifacts = {
        **artifacts_under(root, "elastic"),
        str(json_path.relative_to(root.root)): str(json_path),
        str(csv_path.relative_to(root.root)): str(csv_path),
    }
    if fit is not None:
        tensor_path = root.write_text(
            "reports/elastic_tensor.json",
            json.dumps(
                {"unit": "GPa", "elastic_tensor_GPa": fit["elastic_tensor_GPa"]},
                indent=2,
                sort_keys=True,
                allow_nan=False,
            ) + "\n",
        )
        fit_path = root.write_text(
            "reports/elastic_fit.json",
            json.dumps(
                {key: value for key, value in fit.items() if key != "elastic_tensor_GPa"},
                indent=2,
                sort_keys=True,
                allow_nan=False,
            ) + "\n",
        )
        artifacts[str(tensor_path.relative_to(root.root))] = str(tensor_path)
        artifacts[str(fit_path.relative_to(root.root))] = str(fit_path)
    return TaskResult(
        task="elastic",
        workspace=root.root,
        status="completed" if fit is not None or stress_rows else "degraded",
        subtasks=rows,
        summary=summary,
        artifacts=artifacts,
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


def _strain_voigt(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype=float)
    return np.array([
        values[0, 0], values[1, 1], values[2, 2],
        2 * values[1, 2], 2 * values[0, 2], 2 * values[0, 1],
    ])


def _stress_voigt(value: np.ndarray) -> np.ndarray:
    values = np.asarray(value, dtype=float)
    if values.size == 6:
        return values.reshape(6)
    if values.size != 9:
        raise ValueError("stress must contain 6 Voigt or 9 tensor components")
    matrix = values.reshape((3, 3))
    return np.array([
        matrix[0, 0], matrix[1, 1], matrix[2, 2],
        matrix[1, 2], matrix[0, 2], matrix[0, 1],
    ])


def _fit_elastic(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Fit an elastic tensor from strain and Forge-collected kbar stress pairs.

    Forge collector stress is raw ABACUS kbar.  Legacy elastic fitting uses
    ``Stress(-0.1 * kbar)`` to obtain GPa and the thermodynamic sign convention.
    """
    complete = [
        row for row in rows
        if row.get("strain") is not None and row.get("stress") is not None
    ]
    base_rows = [
        row for row in complete
        if np.allclose(np.asarray(row["strain"], dtype=float), np.zeros((3, 3)))
    ]
    deformed = [
        row for row in complete
        if not np.allclose(np.asarray(row["strain"], dtype=float), np.zeros((3, 3)))
    ]
    if len(base_rows) != 1 or len(deformed) < 6:
        return None

    strain_rows = np.asarray([_strain_voigt(row["strain"]) for row in deformed])
    stress_rows = np.asarray([
        np.asarray(_stress_voigt(row["stress"]), dtype=float) * -0.1
        for row in deformed
    ])
    voigt, *_ = np.linalg.lstsq(strain_rows, stress_rows, rcond=None)
    if not np.isfinite(voigt).all():
        return None
    bulk = (voigt[0, 0] + voigt[1, 1] + voigt[2, 2] + 2 * (
        voigt[0, 1] + voigt[0, 2] + voigt[1, 2]
    )) / 9
    # Reuss shear for the general 6x6 Voigt compliance is intentionally not
    # approximated here; Hill moduli require the full rank-4 tensor.
    shear = float(np.mean(np.diag(voigt)[3:]))
    young_numerator = 9 * bulk * shear
    young_denominator = 3 * bulk + shear
    young = young_numerator / young_denominator if young_denominator else float("nan")
    poisson = (3 * bulk - 2 * shear) / (6 * bulk + 2 * shear) if young_denominator else float("nan")
    return {
        "elastic_tensor_GPa": voigt.tolist(),
        "bulk_modulus_GPa": float(bulk),
        "shear_modulus_GPa": shear,
        "young_modulus_GPa": float(young),
        "poisson_ratio": float(poisson),
    }
