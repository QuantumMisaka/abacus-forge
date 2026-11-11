"""Elastic local composite task pack."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from abacus_forge.composite.common import artifacts_under, ensure_root, require_prepared_inputs, run_subtasks, strained_structure, write_subtask, write_task_result
from abacus_forge.composite.plan import collect_subtask, gather_subtasks, load_plan, save_plan
from abacus_forge.result import TaskResult


def prepare_elastic(
    workspace: str | Path,
    *,
    normal_strain: float = 0.01,
    shear_strain: float = 0.01,
    relax_atoms: bool = True,
) -> TaskResult:
    root = ensure_root(Path(workspace).expanduser().resolve())
    if (root.reports_dir / "elastic_plan.json").exists():
        raise FileExistsError("elastic plan already exists; prepare in a new workspace")
    for name, value in (("normal_strain", normal_strain), ("shear_strain", shear_strain)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be a finite positive number")
    if not isinstance(relax_atoms, bool):
        raise ValueError("relax_atoms must be a boolean")
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
            copy_reference_outputs=False,
        )
        subtasks.append({"workspace": str(sub.root), "strain": strain.tolist()})
    path = save_plan(root, "elastic", subtasks, normal_strain=normal_strain, shear_strain=shear_strain, relax_atoms=relax_atoms)
    subtasks = load_plan(root, "elastic")["subtasks"]
    return TaskResult(
        task="elastic",
        workspace=root.root,
        status="prepared",
        subtasks=subtasks,
        summary={"count": len(subtasks)},
        artifacts={str(path.relative_to(root.root)): str(path)},
    )


def run_elastic(workspace: str | Path, **kwargs: Any) -> TaskResult:
    root = ensure_root(Path(workspace).expanduser().resolve())
    subtasks = [Path(item["workspace"]) for item in load_plan(root, "elastic")["subtasks"]]
    return run_subtasks("elastic", root, subtasks, **kwargs)


def post_elastic(workspace: str | Path, *, results: Iterable[dict[str, Any]] | None = None) -> TaskResult:
    """Fit explicit stress facts, or collect the prepared plan for convenience."""
    root = ensure_root(Path(workspace).expanduser().resolve())
    plan = load_plan(root, "elastic")
    if results is None:
        results = [
            collect_subtask(root, "elastic", item["unit_id"])
            for item in plan["subtasks"]
        ]
    gathered = gather_subtasks(root, "elastic", results)
    rows = gathered.subtasks
    invalid_units = []
    stress_rows = [
        {
            "workspace": row["workspace"],
            "name": row["unit_id"],
            "strain": row.get("strain"),
            "stress": row["metrics"].get("stress"),
        }
        for row in rows
        if row["metrics"].get("stress") is not None
    ]
    for row in rows:
        metric = row.get("metrics", {})
        try:
            stress = np.asarray(metric.get("stress"), dtype=float)
            valid = stress.size in {6, 9} and np.isfinite(stress).all()
        except (TypeError, ValueError):
            valid = False
        if metric.get("converge") is not True or not valid:
            invalid_units.append(row["unit_id"])
    fit = _fit_elastic(stress_rows) if gathered.status == "completed" and not invalid_units else None
    summary = {
        "stress_count": len(stress_rows),
        "stress_rows": stress_rows,
        "elastic_fit": "available" if fit is not None else "unavailable",
        "missing_units": gathered.summary.get("missing_units", []),
        "failed_units": gathered.summary.get("failed_units", []),
        "invalid_units": invalid_units,
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
        status="completed" if fit is not None else "degraded",
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

    try:
        strain_rows = np.asarray([_strain_voigt(row["strain"]) for row in deformed])
        equilibrium_stress = _stress_voigt(base_rows[0]["stress"]) * -0.1
        stress_rows = np.asarray([
            np.asarray(_stress_voigt(row["stress"]), dtype=float) * -0.1 - equilibrium_stress
            for row in deformed
        ])
    except (TypeError, ValueError):
        return None
    if not np.isfinite(strain_rows).all() or not np.isfinite(stress_rows).all():
        return None
    if np.linalg.matrix_rank(strain_rows) != 6:
        return None
    voigt, *_ = np.linalg.lstsq(strain_rows, stress_rows, rcond=None)
    voigt = voigt.T
    voigt = (voigt + voigt.T) / 2
    if not np.isfinite(voigt).all():
        return None
    bulk = (voigt[0, 0] + voigt[1, 1] + voigt[2, 2] + 2 * (
        voigt[0, 1] + voigt[0, 2] + voigt[1, 2]
    )) / 9
    shear = float((voigt[0, 0] + voigt[1, 1] + voigt[2, 2]
                   - voigt[0, 1] - voigt[0, 2] - voigt[1, 2]
                   + 3 * (voigt[3, 3] + voigt[4, 4] + voigt[5, 5])) / 15)
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
