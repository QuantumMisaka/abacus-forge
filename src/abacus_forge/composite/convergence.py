"""Local convergence-test property pack."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from abacus_forge.composite.common import artifacts_under, collect_subtasks, ensure_root, require_prepared_inputs, run_subtasks, write_subtask, write_task_result
from abacus_forge.result import TaskResult


def prepare_convergence(
    workspace: str | Path,
    *,
    key: str,
    values: Sequence[str | int | float],
) -> TaskResult:
    root = ensure_root(workspace)
    input_params, structure, kpt_payload = require_prepared_inputs(root)
    if not key:
        raise ValueError("convergence key is required")
    if not values:
        raise ValueError("convergence values are required")

    subtasks = []
    for raw_value in values:
        value = str(raw_value)
        params = dict(input_params)
        params[str(key)] = value
        relative = f"convergence/{_safe_component(key)}_{_safe_component(value)}"
        sub = write_subtask(
            root,
            relative,
            input_params=params,
            structure=structure,
            kpt_payload=kpt_payload,
            metadata={"task": "convergence", "key": str(key), "value": value},
        )
        subtasks.append({"workspace": str(sub.root), "key": str(key), "value": value})

    path = write_task_result(root, "reports/convergence_plan.json", {"task": "convergence", "key": str(key), "subtasks": subtasks})
    return TaskResult(
        task="convergence",
        workspace=root.root,
        status="prepared",
        subtasks=subtasks,
        summary={"key": str(key), "count": len(subtasks)},
        artifacts={str(path.relative_to(root.root)): str(path)},
    )


def run_convergence(workspace: str | Path, **kwargs: Any) -> TaskResult:
    root = ensure_root(workspace)
    subtasks = sorted((root.root / "convergence").glob("*"))
    return run_subtasks("convergence", root, subtasks, **kwargs)


def post_convergence(workspace: str | Path, *, key: str | None = None) -> TaskResult:
    root = ensure_root(workspace)
    base = root.root / "convergence"
    paths = sorted(path for path in base.glob("*") if path.is_dir())
    rows = collect_subtasks(paths)
    points = []
    for row in rows:
        metadata = _read_metadata(Path(row["workspace"]))
        value = metadata.get("value") or _value_from_name(Path(row["workspace"]).name)
        point = {
            "workspace": row["workspace"],
            "value": str(value),
            "total_energy": row["metrics"].get("total_energy"),
            "energy_per_atom": row["metrics"].get("energy_per_atom"),
        }
        points.append(point)
    summary = {"key": key or _key_from_rows(rows), "points": points, "count": len(points)}
    path = write_task_result(root, "reports/metrics_convergence.json", summary)
    return TaskResult(
        task="convergence",
        workspace=root.root,
        status="completed" if points else "degraded",
        subtasks=rows,
        summary=summary,
        artifacts={**artifacts_under(root, "convergence"), str(path.relative_to(root.root)): str(path)},
    )


def _read_metadata(workspace: Path) -> dict[str, Any]:
    meta = workspace / "meta.json"
    if not meta.exists():
        return {}
    import json

    payload = json.loads(meta.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _safe_component(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in str(value))


def _value_from_name(name: str) -> str:
    return name.split("_", 1)[1] if "_" in name else name


def _key_from_rows(rows: list[dict[str, Any]]) -> str | None:
    for row in rows:
        metadata = _read_metadata(Path(row["workspace"]))
        if metadata.get("key"):
            return str(metadata["key"])
    return None
