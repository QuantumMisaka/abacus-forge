"""Facts-only result projection for typed ABACUS molecular dynamics collection."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from abacus_forge import collection_results as common
from abacus_forge.contracts import ForgeResultEnvelope, OperationStatus, Observation
from abacus_forge.result import CollectionResult


def _md_collection_status(result: CollectionResult) -> str:
    diagnostics = result.diagnostics
    native_complete = diagnostics.get("native_md_block_complete") is True
    if _canonical_native_log(result) is not None and native_complete and not diagnostics.get("log_selection_ambiguous"):
        return "complete"
    has_domain_output = any(_is_domain_source(result, path) for path in _candidate_sources(result))
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
    metrics = dict(projected.metrics)
    summary = metrics.get("md_dump_summary")
    if isinstance(summary, dict):
        summary = dict(summary)
        raw_path = summary.get("path")
        relative = _contained_relative(result, raw_path)
        summary["path"] = relative if relative is not None and Path(relative).name == "MD_dump" else None
        metrics["md_dump_summary"] = summary
    selected = result.diagnostics.get("selected_log_path")
    native = _canonical_native_log(result) is not None and result.diagnostics.get("native_md_block_complete") is True
    if native:
        return replace(projected, metrics=metrics)
    for name in tuple(metrics):
        if name.startswith("md_last_") or (name.startswith("md_") and name.endswith("_series")):
            metrics.pop(name, None)
    return replace(projected, metrics=metrics)


def _contained_relative(result: CollectionResult, raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    root = Path(result.workspace).resolve()
    try:
        path = Path(raw).resolve()
        relative = path.relative_to(root).as_posix()
    except (OSError, RuntimeError, ValueError):
        return None
    if not path.is_file() or relative.startswith("reports/"):
        return None
    if relative.startswith("inputs/") and not _is_input_out_artifact(relative):
        return None
    return relative


def _canonical_native_log(result: CollectionResult) -> Path | None:
    selected = result.diagnostics.get("selected_log_path")
    relative = _contained_relative(result, selected)
    if relative is None or Path(relative).name != "running_md.log":
        return None
    # ABACUS is launched with ``inputs/`` as its working directory by the
    # local runner, so its native OUT directory can remain under
    # ``inputs/OUT.*``.  Keep the domain boundary explicit: a bare input log
    # (or a report alias) is not a native result source.
    if relative != "running_md.log" and not (
        relative.startswith("outputs/") or _is_input_out_artifact(relative)
    ):
        return None
    return Path(result.workspace).resolve() / relative


def _is_input_out_artifact(relative: str) -> bool:
    parts = Path(relative).parts
    return len(parts) == 3 and parts[0] == "inputs" and parts[1].startswith("OUT.")


def _candidate_sources(result: CollectionResult) -> tuple[object, ...]:
    diagnostics = result.diagnostics
    candidates: list[object] = [diagnostics.get("selected_log_path"), diagnostics.get("output_log_path")]
    for relative, raw_path in result.artifacts.items():
        if isinstance(relative, str) and (Path(relative).name == "MD_dump" or Path(relative).name.startswith("running_")):
            candidates.append(raw_path)
    return tuple(candidates)


def _is_domain_source(result: CollectionResult, raw: object) -> bool:
    relative = _contained_relative(result, raw)
    if relative is None:
        return False
    name = Path(relative).name
    if name == "MD_dump" or name.startswith("running_"):
        return bool(Path(raw).read_text(encoding="utf-8", errors="ignore").strip())  # type: ignore[arg-type]
    return raw == result.diagnostics.get("output_log_path") and bool(Path(raw).read_text(encoding="utf-8", errors="ignore").strip())  # type: ignore[arg-type]


__all__ = ["collection_envelope", "collection_observations"]
