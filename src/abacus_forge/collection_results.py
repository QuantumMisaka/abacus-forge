"""Shared factual projection and source containment for typed collection."""

from __future__ import annotations

from dataclasses import replace
import math
from pathlib import Path
from typing import Any, Mapping

from abacus_forge.contracts import ArtifactRecord, ForgeResultEnvelope, MetricRecord, Observation, OperationStatus
from abacus_forge.result import CollectionResult


_CONVERGENCE_NAMES = frozenset({"converged", "converge"})
_DERIVED_METRIC_NAMES = frozenset({"energy_per_atom", "pressure"})
_RUNTIME_METRIC_NAMES = frozenset({"returncode", "omp_threads"})
_COUNT_UNITS = {
    "natom": "atoms",
    "nelec": "electrons",
    "scf_steps": "steps",
    "relax_steps": "steps",
    "md_steps": "steps",
    "md_dump_steps": "steps",
    "md_dump_frames": "frames",
}
_NATIVE_MD_ENERGY_NAMES = frozenset({
    "md_last_total_energy",
    "md_last_potential_energy",
    "md_last_kinetic_energy",
})
_NATIVE_MD_TEMPERATURE_NAMES = frozenset({"md_last_temperature"})
_NATIVE_MD_PRESSURE_NAMES = frozenset({"md_last_pressure"})


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
    typed_metrics = _typed_metric_records(projected, legacy.metrics, legacy.artifacts)
    return replace(
        legacy, workspace_rel=workspace_rel,
        status=OperationStatus(execution="not_run", scientific="unassessed", collection=collection_status(result)),
        metrics=typed_metrics,
        checks=legacy.checks if electronic_convergence(result) is not None else (),
        diagnostics=legacy.to_dict()["diagnostics"],
    )


def _typed_metric_records(
    result: CollectionResult,
    legacy_metrics: tuple[MetricRecord, ...] | list[MetricRecord],
    artifacts: tuple[ArtifactRecord, ...],
) -> tuple[MetricRecord, ...]:
    """Attach only grammar-confirmed metadata to the typed projection.

    ``CollectionResult.to_envelope`` remains the legacy compatibility
    projection.  This helper is deliberately called only by the typed
    collection boundary and rebuilds records using the existing
    ``MetricRecord`` fields.
    """
    artifact_ids = _artifact_ids_by_contained_path(result, artifacts)
    native_md = result.diagnostics.get("native_md_block_complete") is True
    native_final_energy = bool(result.diagnostics.get("native_final_energy_markers"))
    native_fermi = bool(result.diagnostics.get("native_fermi_markers"))
    total_energy_unit = "eV" if native_final_energy else None
    records: list[MetricRecord] = []
    for legacy in legacy_metrics:
        name = legacy.name
        kind = "runtime" if name in _RUNTIME_METRIC_NAMES else (
            "derived" if name in _DERIVED_METRIC_NAMES and name in result.derived_metrics else "reported"
        )
        unit = _typed_metric_unit(
            result,
            name,
            native_md=native_md,
            total_energy_unit=total_energy_unit,
            native_fermi=native_fermi,
            kind=kind,
        )
        source_artifact_id = _source_artifact_id(result, name, artifact_ids)
        records.append(
            MetricRecord(
                name=name,
                value=legacy.value,
                unit=unit,
                kind=kind,
                source_artifact_id=source_artifact_id,
            )
        )
    return tuple(records)


def _typed_metric_unit(
    result: CollectionResult,
    name: str,
    *,
    native_md: bool,
    total_energy_unit: str | None,
    native_fermi: bool,
    kind: str,
) -> str | None:
    if name == "total_energy":
        return total_energy_unit
    if name == "fermi_energy":
        return "eV" if native_fermi else None
    if name in _NATIVE_MD_ENERGY_NAMES:
        return "eV" if native_md else None
    if name in _NATIVE_MD_TEMPERATURE_NAMES:
        return "K" if native_md else None
    if name in _NATIVE_MD_PRESSURE_NAMES:
        return "kbar" if native_md else None
    if name in _COUNT_UNITS:
        return _COUNT_UNITS[name]
    if name == "total_time":
        origin = result.metric_origins.get(name)
        time_json = result.diagnostics.get("time_json")
        if isinstance(origin, str) and isinstance(time_json, str) and _same_contained_path(result.workspace, origin, time_json):
            return "s"
        return None
    if name == "energy_per_atom":
        return "eV/atom" if kind == "derived" and total_energy_unit == "eV" else None
    if name == "pressure":
        return "kbar" if kind == "derived" else None
    return None


def _artifact_ids_by_contained_path(
    result: CollectionResult,
    artifacts: tuple[ArtifactRecord, ...],
) -> dict[str, tuple[str, ...]]:
    by_path: dict[str, list[str]] = {}
    root = result.workspace.resolve()
    for artifact in artifacts:
        try:
            relative = Path(artifact.path_rel).as_posix()
            # ArtifactRecord paths are already relative by contract, but
            # normalize them through the same root boundary used for source
            # resolution so an invalid/escaped sidecar cannot gain a ref.
            resolved = (root / relative).resolve()
            if resolved.relative_to(root).as_posix() != relative:
                continue
        except (OSError, RuntimeError, ValueError):
            continue
        by_path.setdefault(relative, []).append(artifact.id)
    return {path: tuple(ids) for path, ids in by_path.items()}


def _source_artifact_id(
    result: CollectionResult,
    name: str,
    artifact_ids: Mapping[str, tuple[str, ...]],
) -> str | None:
    raw_origin = result.metric_origins.get(name)
    if not isinstance(raw_origin, str):
        return None
    source = contained_source(result.workspace, raw_origin)
    if source is None:
        return None
    try:
        relative = source.relative_to(result.workspace.resolve()).as_posix()
    except (OSError, RuntimeError, ValueError):
        return None
    ids = artifact_ids.get(relative, ())
    return ids[0] if len(ids) == 1 else None


def _same_contained_path(root: Path, first: str, second: str) -> bool:
    first_path = contained_source(root, first)
    second_path = contained_source(root, second)
    return first_path is not None and first_path == second_path


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
