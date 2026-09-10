"""Facts-only result projection for typed ABACUS molecular dynamics collection."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from abacus_forge import collection_results as common
from abacus_forge.contracts import ForgeResultEnvelope, OperationStatus, Observation
from abacus_forge.result import CollectionResult


def _md_collection_status(result: CollectionResult) -> str:
    diagnostics = result.diagnostics
    running = diagnostics.get("selected_log_path")
    running_name = Path(running).name if isinstance(running, str) else ""
    native_complete = diagnostics.get("native_md_block_complete") is True
    if running_name == "running_md.log" and native_complete and not diagnostics.get("log_selection_ambiguous"):
        return "complete"
    root = Path(result.workspace).resolve()
    has_domain_output = False
    for raw_path in result.artifacts.values():
        if not isinstance(raw_path, str):
            continue
        try:
            relative = Path(raw_path).resolve().relative_to(root).as_posix()
        except (OSError, RuntimeError, ValueError):
            continue
        if relative.startswith(("inputs/", "reports/")):
            continue
        if Path(raw_path).is_file() and Path(raw_path).read_text(encoding="utf-8", errors="ignore").strip():
            has_domain_output = True
            break
    return "partial" if has_domain_output else "missing_output"


def collection_envelope(result: CollectionResult, workspace_rel: str) -> ForgeResultEnvelope:
    projected = _projection_result(result)
    envelope = common.collection_envelope(projected, workspace_rel)
    return replace(
        envelope,
        status=replace(envelope.status, collection=_md_collection_status(result)),
        diagnostics=envelope.to_dict()["diagnostics"],
    )


def collection_observations(result: CollectionResult) -> tuple[Observation, ...]:
    return common.collection_observations(_projection_result(result))


def _projection_result(result: CollectionResult) -> CollectionResult:
    """Expose MD thermodynamics only when sourced from native running_md.log."""
    projected = common.projection_result(result)
    selected = result.diagnostics.get("selected_log_path")
    native = (
        isinstance(selected, str) and Path(selected).name == "running_md.log"
        and result.diagnostics.get("native_md_block_complete") is True
    )
    if native:
        return projected
    metrics = dict(projected.metrics)
    for name in tuple(metrics):
        if name.startswith("md_last_") or (name.startswith("md_") and name.endswith("_series")):
            metrics.pop(name, None)
    return replace(projected, metrics=metrics)


__all__ = ["collection_envelope", "collection_observations"]
