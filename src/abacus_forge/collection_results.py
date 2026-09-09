"""Shared factual projection and source containment for typed collection."""

from __future__ import annotations

from dataclasses import replace
import math
from pathlib import Path
from typing import Any, Mapping

from abacus_forge.contracts import ForgeResultEnvelope, Observation, OperationStatus
from abacus_forge.result import CollectionResult


_CONVERGENCE_NAMES = frozenset({"converged", "converge"})


def is_internal_artifact(relative: str) -> bool:
    normalized = relative.replace("\\", "/")
    return (
        normalized == "reports/forge-workspace.json"
        or normalized in {"reports/.forge-operation.lock", "reports/.forge-workspace.lock"}
        or normalized.startswith(("reports/events/", "reports/claims/"))
    )


def contained_source(root: Path, raw_path: str | Path) -> Path | None:
    """Resolve an existing domain file while rejecting lexical/resolved audit aliases."""
    root = root.resolve()
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        lexical = candidate.relative_to(root).as_posix()
        resolved = candidate.resolve()
        relative = resolved.relative_to(root).as_posix()
        if is_internal_artifact(lexical) or is_internal_artifact(relative):
            return None
        return resolved if resolved.is_file() else None
    except (OSError, RuntimeError, ValueError):
        return None


def projection_artifacts(result: CollectionResult) -> dict[str, str]:
    projected: dict[str, str] = {}
    root = result.workspace.resolve()
    for relative, raw_path in result.artifacts.items():
        if not isinstance(relative, str) or not isinstance(raw_path, str) or is_internal_artifact(relative):
            continue
        source = contained_source(result.workspace, raw_path)
        if source is not None:
            # Use the canonical name for suffix-driven parsing too: an alias
            # must not hide the report or structure's actual file type.
            projected[source.relative_to(root).as_posix()] = str(source)
    return projected


def electronic_convergence(result: CollectionResult) -> bool | None:
    for key, value in (("matched_nonconverged_markers", False), ("matched_converged_markers", True)):
        markers = result.diagnostics.get(key)
        if isinstance(markers, (str, bytes, list, tuple, set, frozenset)) and markers:
            return value
    return None


def projection_metrics(values: Mapping[str, Any]) -> dict[str, Any]:
    metrics = dict(values)
    relax_metrics = metrics.get("relax_metrics")
    summary = metrics.get("relax_summary")
    if isinstance(summary, Mapping):
        summary_copy = dict(summary)
        if not isinstance(relax_metrics, Mapping) or "converged" not in relax_metrics:
            summary_copy.pop("converged", None)
        metrics["relax_summary"] = summary_copy
    return metrics


def _finite_json(value: Any) -> Any:
    """Represent unparseable numeric facts as missing, retaining array shape."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Mapping):
        return {key: _finite_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite_json(item) for item in value]
    return value


def projection_result(result: CollectionResult) -> CollectionResult:
    metrics = projection_metrics(result.metrics)
    if electronic_convergence(result) is None:
        for name in _CONVERGENCE_NAMES:
            metrics.pop(name, None)
    return replace(result, metrics=_finite_json(metrics), artifacts=projection_artifacts(result))


def collection_status(result: CollectionResult) -> str:
    diagnostics = result.diagnostics
    sources = (
        contained_source(result.workspace, path)
        for name in ("selected_log_path", "output_log_path")
        if isinstance((path := diagnostics.get(name)), str)
    )
    if not any(path is not None and path.read_text(encoding="utf-8", errors="ignore").strip() for path in sources):
        return "missing_output"
    if any(diagnostics.get(name) for name in (
        "log_selection_ambiguous", "output_log_selection_ambiguous",
        "report_json_errors", "time_json_error",
        "parser_errors", "parse_error", "md_dump_error",
    )):
        return "partial"
    energy = result.metrics.get("total_energy")
    if not isinstance(energy, (int, float)) or isinstance(energy, bool) or not math.isfinite(float(energy)):
        return "partial"
    return "complete"


def collection_envelope(result: CollectionResult, workspace_rel: str) -> ForgeResultEnvelope:
    projected = projection_result(result)
    legacy = projected.to_envelope()
    return replace(
        legacy, workspace_rel=workspace_rel,
        status=OperationStatus(execution="not_run", scientific="unassessed", collection=collection_status(result)),
        checks=legacy.checks if electronic_convergence(result) is not None else (),
        diagnostics=legacy.to_dict()["diagnostics"],
    )


def collection_observations(result: CollectionResult) -> tuple[Observation, ...]:
    projected = projection_result(result)
    observations = [
        Observation(name=str(name), value=value, source="parser")
        for name, value in projected.metrics.items() if name not in _CONVERGENCE_NAMES
    ]
    convergence = electronic_convergence(projected)
    if convergence is not None:
        observations.append(Observation(name="electronic_convergence", value=convergence, source="parser"))
    for name, snapshot in (
        ("structure_snapshot", projected.structure_snapshot),
        ("final_structure_snapshot", projected.final_structure_snapshot),
    ):
        if not isinstance(snapshot, Mapping) or "parse_error" in snapshot:
            continue
        source = snapshot.get("source")
        path = contained_source(projected.workspace, source) if isinstance(source, str) else None
        if path is None:
            continue
        relative = path.relative_to(projected.workspace.resolve()).as_posix()
        if name == "final_structure_snapshot" and relative.startswith(("inputs/", "reports/")):
            continue
        observations.append(Observation(name=name, value=_finite_json(dict(snapshot)), source="file"))
    return tuple(observations)
