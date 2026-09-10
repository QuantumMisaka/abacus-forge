"""Factual result projection for typed Relax collection services."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from dataclasses import replace

from abacus_forge.contracts import ForgeResultEnvelope, Observation
from abacus_forge import collection_results as common
from abacus_forge.result import CollectionResult
from abacus_forge.structure import AbacusStructure


_FINAL_STRUCTURE_SUFFIXES = ("STRU_ION_D", "STRU_NOW.cif", "STRU.cif", "STRU")


def collection_envelope(result: CollectionResult, workspace_rel: str) -> ForgeResultEnvelope:
    """Add Relax's final-output requirement to the common factual projection."""
    projected = _projection_result(result)
    envelope = common.collection_envelope(projected, workspace_rel)
    return replace(
        envelope, status=replace(envelope.status, collection=_collection_status(projected, envelope)),
        diagnostics=envelope.to_dict()["diagnostics"],
    )


def collection_observations(result: CollectionResult) -> tuple[Observation, ...]:
    return common.collection_observations(_projection_result(result))


def _projection_result(result: CollectionResult) -> CollectionResult:
    final_structure_snapshot, final_structure_diagnostics = _project_final_structure(result)
    diagnostics = dict(result.diagnostics)
    diagnostics.update(final_structure_diagnostics)
    metrics = common.projection_metrics(result.metrics)
    relax_summary = metrics.get("relax_summary")
    if isinstance(relax_summary, Mapping):
        summary_copy = dict(relax_summary)
        summary_copy["final_structure_path"] = final_structure_diagnostics["final_structure_path"]
        metrics["relax_summary"] = summary_copy
    return CollectionResult(
        workspace=result.workspace,
        status=result.status,
        metrics=metrics,
        artifacts=common.projection_artifacts(result),
        diagnostics=diagnostics,
        inputs_snapshot=dict(result.inputs_snapshot),
        structure_snapshot=result.structure_snapshot,
        final_structure_snapshot=final_structure_snapshot,
        metric_origins=dict(result.metric_origins),
        derived_metrics=set(result.derived_metrics),
    )


def _project_final_structure(
    result: CollectionResult,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Select and parse one contained output structure independently.

    ``api.collect`` intentionally keeps its legacy first-suffix selection.  A
    Relax projection must not mistake ``inputs/STRU`` for a final output, so
    it selects from the contained, non-input artifact index again.
    """
    candidates = _final_structure_candidates(result)
    diagnostics: dict[str, Any] = {
        "final_structure_candidates": [str(path) for _, path in candidates],
        "final_structure_selection_ambiguous": len(candidates) > 1,
    }
    if len(candidates) != 1:
        diagnostics["final_structure_path"] = None
        return None, diagnostics

    relative, path = candidates[0]
    diagnostics["final_structure_path"] = str(path)
    suffix = next(
        suffix for suffix in _FINAL_STRUCTURE_SUFFIXES if relative.endswith(suffix)
    )
    diagnostics["final_structure_selected_suffix"] = suffix
    try:
        structure_format = "stru" if suffix in {"STRU_ION_D", "STRU"} else None
        structure = AbacusStructure.from_input(path, structure_format=structure_format)
        snapshot = structure.metadata().to_dict()
        snapshot["source"] = str(path)
        return snapshot, diagnostics
    except Exception as error:
        diagnostics["final_structure_parse_error"] = str(error)
        return {"source": str(path), "parse_error": str(error)}, diagnostics


def _collection_status(result: CollectionResult, envelope: ForgeResultEnvelope) -> str:
    status = common.collection_status(result)
    if status != "complete":
        return status
    if _final_structure_selection_is_ambiguous(result):
        return "partial"

    final_snapshot = result.final_structure_snapshot
    if not isinstance(final_snapshot, Mapping) or "parse_error" in final_snapshot:
        return "partial"
    if not _final_structure_artifact_is_contained(result, envelope):
        return "partial"

    return "complete"


def _final_structure_selection_is_ambiguous(result: CollectionResult) -> bool:
    """Ignore the initial ``inputs/STRU`` and count contained outputs."""
    return len(_final_structure_candidates(result)) > 1


def _final_structure_candidates(result: CollectionResult) -> tuple[tuple[str, Path], ...]:
    """Return unique, contained output candidates in suffix priority order."""
    root = Path(result.workspace).resolve()
    by_relative: dict[str, Path] = {}
    for raw_relative, raw_path in result.artifacts.items():
        if not isinstance(raw_relative, str) or not isinstance(raw_path, str):
            continue
        lexical = raw_relative.replace("\\", "/")
        # Inputs and reports are not domain output candidates.  A root-level
        # STRU remains valid for the legacy flat layout.
        if lexical.startswith("inputs/") or lexical.startswith("reports/"):
            continue
        if not lexical.endswith(_FINAL_STRUCTURE_SUFFIXES):
            continue
        candidate = Path(raw_path)
        try:
            resolved = candidate.resolve()
            relative = resolved.relative_to(root).as_posix()
        except (OSError, RuntimeError, ValueError):
            continue
        if (
            relative == "."
            or relative.startswith("inputs/")
            or relative.startswith("reports/")
            or not resolved.is_file()
            or not relative.endswith(_FINAL_STRUCTURE_SUFFIXES)
        ):
            continue
        by_relative.setdefault(relative, resolved)

    return tuple(
        (relative, by_relative[relative])
        for suffix in _FINAL_STRUCTURE_SUFFIXES
        for relative in sorted(by_relative)
        if relative.endswith(suffix)
    )


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


__all__ = ["collection_envelope", "collection_observations"]
