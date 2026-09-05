"""Factual result projection for typed Relax collection services."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping

from abacus_forge.contracts import (
    ForgeResultEnvelope,
    Observation,
    OperationStatus,
)
from abacus_forge.result import CollectionResult


_LEGACY_CONVERGENCE_NAMES = frozenset({"converged", "converge"})
_ELECTRONIC_CONVERGENCE_NAME = "electronic_convergence"
_FINAL_STRUCTURE_SUFFIXES = ("STRU_ION_D", "STRU_NOW.cif", "STRU.cif", "STRU")


def collection_envelope(result: CollectionResult, workspace_rel: str) -> ForgeResultEnvelope:
    """Project one parsed Relax result without deriving scientific policy.

    ``CollectionResult.to_envelope`` remains the compatibility projection for
    legacy and SCF callers.  Relax uses a detached, sanitized copy so the
    collector's historical ``relax_summary.converged`` fallback cannot turn
    electronic convergence into an ionic observation.
    """
    projected = _projection_result(result)
    legacy_envelope = projected.to_envelope()
    electronic_convergence = _electronic_convergence(result)

    metrics = legacy_envelope.metrics
    checks = legacy_envelope.checks
    if electronic_convergence is None:
        metrics = tuple(
            metric for metric in metrics if metric.name not in _LEGACY_CONVERGENCE_NAMES
        )
        checks = tuple(check for check in checks if check.name != "converged")

    envelope = ForgeResultEnvelope(
        operation="collect",
        workspace_rel=workspace_rel,
        status=OperationStatus(
            execution="not_run",
            scientific="unassessed",
            collection="not_collected",
        ),
        artifacts=legacy_envelope.artifacts,
        metrics=metrics,
        checks=checks,
        warnings=legacy_envelope.warnings,
        diagnostics=_projection_diagnostics(
            result, legacy_envelope.to_dict()["diagnostics"]  # type: ignore[arg-type]
        ),
    )
    return _with_collection_status(envelope, _collection_status(result, envelope))


def collection_observations(result: CollectionResult) -> tuple[Observation, ...]:
    """Return parser/file facts that do not fit the scalar result records."""
    observations: list[Observation] = []
    metrics = _projection_metrics(result.metrics)

    for name, value in metrics.items():
        if name in _LEGACY_CONVERGENCE_NAMES:
            continue
        observations.append(Observation(name=str(name), value=value, source="parser"))

    electronic_convergence = _electronic_convergence(result)
    if electronic_convergence is not None:
        observations.append(
            Observation(
                name=_ELECTRONIC_CONVERGENCE_NAME,
                value=electronic_convergence,
                source="parser",
            )
        )

    for name, snapshot in (
        ("structure_snapshot", result.structure_snapshot),
        ("final_structure_snapshot", result.final_structure_snapshot),
    ):
        if (
            not isinstance(snapshot, Mapping)
            or "parse_error" in snapshot
            or not _snapshot_source_is_contained(result, snapshot)
        ):
            continue
        if name == "final_structure_snapshot" and not _final_snapshot_is_output(result, snapshot):
            continue
        observations.append(Observation(name=name, value=dict(snapshot), source="file"))

    return tuple(observations)


def _projection_result(result: CollectionResult) -> CollectionResult:
    return CollectionResult(
        workspace=result.workspace,
        status=result.status,
        metrics=_projection_metrics(result.metrics),
        artifacts=dict(result.artifacts),
        diagnostics=dict(result.diagnostics),
        inputs_snapshot=dict(result.inputs_snapshot),
        structure_snapshot=result.structure_snapshot,
        final_structure_snapshot=result.final_structure_snapshot,
    )


def _projection_metrics(values: Mapping[str, Any]) -> dict[str, Any]:
    """Copy metrics and remove only synthesized ionic convergence."""
    metrics = dict(values)
    relax_metrics = metrics.get("relax_metrics")
    summary = metrics.get("relax_summary")
    if isinstance(summary, Mapping):
        summary_copy = dict(summary)
        if not isinstance(relax_metrics, Mapping) or "converged" not in relax_metrics:
            summary_copy.pop("converged", None)
        metrics["relax_summary"] = summary_copy
    return metrics


def _electronic_convergence(result: CollectionResult) -> bool | None:
    diagnostics = result.diagnostics
    positive = _marker_values(diagnostics.get("matched_converged_markers"))
    negative = _marker_values(diagnostics.get("matched_nonconverged_markers"))
    if negative:
        return False
    if positive:
        return True
    return None


def _marker_values(value: object) -> tuple[object, ...]:
    if isinstance(value, (str, bytes)):
        return (value,) if value else ()
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(value)
    return ()


def _collection_status(result: CollectionResult, envelope: ForgeResultEnvelope) -> str:
    diagnostics = result.diagnostics
    log_sources = diagnostics.get("log_sources")
    if not isinstance(log_sources, (int, float)) or isinstance(log_sources, bool) or log_sources <= 0:
        return "missing_output"

    if diagnostics.get("log_selection_ambiguous") is True:
        return "partial"
    if diagnostics.get("output_log_selection_ambiguous") is True:
        return "partial"
    if _final_structure_selection_is_ambiguous(result):
        return "partial"
    if diagnostics.get("final_structure_parse_error"):
        return "partial"
    if diagnostics.get("report_json_errors"):
        return "partial"

    total_energy = result.metrics.get("total_energy")
    if (
        not isinstance(total_energy, (int, float))
        or isinstance(total_energy, bool)
        or not math.isfinite(float(total_energy))
    ):
        return "partial"

    final_snapshot = result.final_structure_snapshot
    if not isinstance(final_snapshot, Mapping) or "parse_error" in final_snapshot:
        return "partial"
    if not _final_structure_artifact_is_contained(result, envelope):
        return "partial"

    return "complete"


def _projection_diagnostics(
    result: CollectionResult, diagnostics: Mapping[str, Any]
) -> dict[str, Any]:
    projected = dict(diagnostics)
    if "final_structure_selection_ambiguous" in projected:
        projected["final_structure_selection_ambiguous"] = _final_structure_selection_is_ambiguous(result)
    return projected


def _final_structure_selection_is_ambiguous(result: CollectionResult) -> bool:
    """Ignore the initial ``inputs/STRU`` and count every indexed output."""
    artifact_candidates = _final_structure_artifact_candidates(result)
    if artifact_candidates:
        return len(artifact_candidates) > 1
    return result.diagnostics.get("final_structure_selection_ambiguous") is True


def _final_structure_artifact_candidates(result: CollectionResult) -> tuple[str, ...]:
    candidates: set[str] = set()
    for relative in result.artifacts:
        if not isinstance(relative, str):
            continue
        normalized = relative.replace("\\", "/")
        if normalized.startswith("inputs/"):
            continue
        if normalized.endswith(_FINAL_STRUCTURE_SUFFIXES):
            candidates.add(normalized)
    return tuple(sorted(candidates))


def _final_structure_artifact_is_contained(
    result: CollectionResult, envelope: ForgeResultEnvelope
) -> bool:
    diagnostics = result.diagnostics
    raw_path = diagnostics.get("final_structure_path")
    if not isinstance(raw_path, str) or not raw_path:
        return False

    root = Path(result.workspace).resolve()
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve()
        relative = resolved.relative_to(root).as_posix()
    except (OSError, RuntimeError, ValueError):
        return False

    # ``api.collect`` falls back to an input STRU when no output structure is
    # present.  That is an initial snapshot, not evidence of a final Relax
    # structure for collection completeness.
    if relative.startswith("inputs/") or relative == "." or not resolved.is_file():
        return False
    return any(artifact.path_rel == relative for artifact in envelope.artifacts)


def _snapshot_source_is_contained(result: CollectionResult, snapshot: Mapping[str, Any]) -> bool:
    raw_source = snapshot.get("source")
    if not isinstance(raw_source, str) or not raw_source:
        return False
    root = Path(result.workspace).resolve()
    candidate = Path(raw_source)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return False
    return resolved.is_file()


def _final_snapshot_is_output(result: CollectionResult, snapshot: Mapping[str, Any]) -> bool:
    """Ensure the collector's fallback input STRU is not called final output."""
    raw_source = snapshot.get("source")
    if not isinstance(raw_source, str) or not raw_source:
        return False
    root = Path(result.workspace).resolve()
    source = Path(raw_source)
    if not source.is_absolute():
        source = root / source
    try:
        relative = source.resolve().relative_to(root).as_posix()
    except (OSError, RuntimeError, ValueError):
        return False
    if relative == "." or relative.startswith("inputs/"):
        return False
    return any(
        _artifact_relative_path(root, raw_path) == relative
        for raw_path in result.artifacts.values()
        if isinstance(raw_path, str)
    )


def _artifact_relative_path(root: Path, raw_path: str) -> str | None:
    try:
        return Path(raw_path).resolve().relative_to(root).as_posix()
    except (OSError, RuntimeError, ValueError):
        return None


def _with_collection_status(
    envelope: ForgeResultEnvelope, collection: str
) -> ForgeResultEnvelope:
    return ForgeResultEnvelope(
        operation=envelope.operation,
        workspace_rel=envelope.workspace_rel,
        status=OperationStatus(
            execution=envelope.status.execution,
            scientific=envelope.status.scientific,
            collection=collection,  # type: ignore[arg-type]
        ),
        artifacts=envelope.artifacts,
        metrics=envelope.metrics,
        checks=envelope.checks,
        warnings=envelope.warnings,
        diagnostics=envelope.to_dict()["diagnostics"],  # type: ignore[arg-type]
    )


__all__ = ["collection_envelope", "collection_observations"]
