"""Event-free ABACUS log, artifact and structure collection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from abacus_forge.collectors.abacus import collect_abacus_metrics
from abacus_forge.collection_results import contained_source, projection_artifacts
from abacus_forge.input_io import read_input, read_kpt
from abacus_forge.result import CollectionResult
from abacus_forge.structure import AbacusStructure
from abacus_forge.workspace import Workspace

_OUTPUT_BANNER_MARKERS = (
    "Atomic-orbital Based Ab-initio",
)


def collect(
    workspace: str | Path | Workspace,
    *,
    output_log: str | Path | None = None,
    layout: str = "forge",
) -> CollectionResult:
    """Parse metrics, structures, and artifacts from one workspace.

    Parameters
    ----------
    workspace:
        Target Forge workspace.
    output_log:
        Optional explicit stdout-like output log path. Relative paths are
        resolved against the workspace root.
    """
    return _collect_workspace(workspace, output_log=output_log, layout=layout)


def collect_contained(workspace: Workspace) -> CollectionResult:
    """Internal typed-service entry; legacy collect keeps its source behavior."""
    return _collect_workspace(workspace, contained=True)


def _collect_workspace(
    workspace: str | Path | Workspace,
    *,
    output_log: str | Path | None = None,
    layout: str = "forge",
    contained: bool = False,
) -> CollectionResult:

    ws = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace))
    normalized_layout = _normalize_layout(ws, layout)
    artifacts = _collect_artifacts(ws, layout=normalized_layout)
    if contained:
        artifacts = projection_artifacts(CollectionResult(ws.root, "unfinished", artifacts=artifacts))
    inputs_snapshot = _inputs_snapshot(ws, layout=normalized_layout, contained=contained)
    log_selection = _select_log_sources(ws, artifacts, inputs_snapshot=inputs_snapshot, output_log=output_log, layout=normalized_layout, contained=contained)
    main_log_path = log_selection["main_log_path"]
    output_log_path = log_selection["output_log_path"]
    main_log_text = _read_text_if_exists(main_log_path)
    output_log_text = _read_text_if_exists(output_log_path)
    stderr_path = _stderr_path(ws, layout=normalized_layout)
    structure_path = _input_path(ws, "STRU", layout=normalized_layout)
    structure_snapshot = _structure_snapshot(structure_path) if not contained or contained_source(ws.root, structure_path) else None
    final_structure_snapshot, final_structure_diagnostics = _final_structure_snapshot(artifacts)
    metrics, diagnostics = collect_abacus_metrics(
        main_log_text=main_log_text,
        output_log_text=output_log_text,
        artifacts=artifacts,
        workspace_root=ws.root,
        structure_volume=_snapshot_volume(final_structure_snapshot) or _snapshot_volume(structure_snapshot),
        main_log_path=main_log_path,
        output_log_path=output_log_path,
    )
    # The collector uses private diagnostic keys as a narrow hand-off for
    # parser provenance.  Consume them before returning the legacy result so
    # neither diagnostics nor wire serialization exposes the sidecar.
    raw_metric_origins = diagnostics.pop("_metric_origins", {})
    raw_derived_metrics = diagnostics.pop("_derived_metrics", ())
    metric_origins = (
        {str(name): str(path) for name, path in raw_metric_origins.items()}
        if isinstance(raw_metric_origins, dict)
        else {}
    )
    derived_metrics = (
        {str(name) for name in raw_derived_metrics}
        if isinstance(raw_derived_metrics, (list, tuple, set, frozenset))
        else set()
    )
    diagnostics.update(log_selection["diagnostics"])
    diagnostics.update(final_structure_diagnostics)
    diagnostics["layout"] = normalized_layout
    diagnostics["log_paths"] = [
        str(path)
        for path in (main_log_path, output_log_path)
        if path is not None
    ]
    diagnostics["stderr_nonempty"] = bool(
        (not contained or contained_source(ws.root, stderr_path))
        and stderr_path.exists() and stderr_path.read_text(encoding="utf-8", errors="ignore").strip()
    )
    if log_selection["warning"] is not None:
        diagnostics.setdefault("warnings", []).append(log_selection["warning"])
    relax_metrics = metrics.get("relax_metrics")
    if isinstance(relax_metrics, dict):
        relax_summary = dict(metrics.get("relax_summary", {}))
        relax_summary.setdefault("converged", bool(relax_metrics.get("converged", metrics.get("converged", False))))
        relax_summary["final_structure_available"] = final_structure_snapshot is not None or bool(
            relax_metrics.get("final_structure_available", False)
        )
        relax_summary["final_structure_path"] = diagnostics.get("final_structure_path")
        metrics["relax_summary"] = relax_summary
    status = "unfinished" if contained else _determine_status(
        metrics,
        stderr_path=stderr_path,
        text_blobs=[text for text in (main_log_text, output_log_text) if text is not None],
    )
    return CollectionResult(
        workspace=ws.root,
        status=status,
        metrics=metrics,
        artifacts=artifacts,
        diagnostics=diagnostics,
        inputs_snapshot=inputs_snapshot,
        structure_snapshot=structure_snapshot,
        final_structure_snapshot=final_structure_snapshot,
        metric_origins=metric_origins,
        derived_metrics=derived_metrics,
    )


def _normalize_layout(workspace: Workspace, layout: str) -> str:
    normalized = str(layout).strip().lower()
    if normalized not in {"forge", "flat", "auto"}:
        raise ValueError(f"unsupported collect layout: {layout!r}")
    if normalized == "auto":
        if workspace.inputs_dir.exists() or workspace.outputs_dir.exists() or workspace.reports_dir.exists():
            return "forge"
        return "flat"
    return normalized


def _collect_artifacts(workspace: Workspace, *, layout: str = "forge") -> dict[str, str]:
    artifacts: dict[str, str] = {}
    if layout == "flat":
        if not workspace.root.exists():
            return artifacts
        for path in sorted(workspace.root.rglob("*")):
            if path.is_file():
                artifacts[str(path.relative_to(workspace.root))] = str(path)
        return artifacts
    for relative in ("inputs", "outputs", "reports"):
        base = workspace.root / relative
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                artifacts[str(path.relative_to(workspace.root))] = str(path)
    return artifacts


def _select_log_sources(
    workspace: Workspace,
    artifacts: dict[str, str],
    *,
    inputs_snapshot: dict[str, Any],
    output_log: str | Path | None = None,
    layout: str = "forge",
    contained: bool = False,
) -> dict[str, Any]:
    input_parameters = inputs_snapshot.get("INPUT", {})
    calculation = str(input_parameters.get("calculation", "")).strip() if isinstance(input_parameters, dict) else ""

    running_candidates: list[tuple[str, Path]] = []
    for relative, path in artifacts.items():
        if Path(relative).name.startswith("running_") and relative.endswith(".log"):
            running_candidates.append((relative, Path(path)))
    running_candidates.sort(key=lambda item: _natural_sort_key(item[0]))

    selected_path: Path | None = None
    selected_reason = "no-log-selected"
    log_strategy = "no-log"
    ambiguous = False
    warning: str | None = None

    if calculation:
        expected_name = f"running_{calculation}.log"
        expected_matches = [path for relative, path in running_candidates if Path(relative).name == expected_name]
        if len(expected_matches) == 1:
            selected_path = expected_matches[0]
            selected_reason = f"matched-input-calculation:{expected_name}"
            log_strategy = "selected-running-log"
        elif len(expected_matches) > 1:
            ambiguous = True
            warning = f"Multiple running logs match calculation={calculation}; no unique main log selected."

    if selected_path is None and len(running_candidates) == 1:
        selected_path = running_candidates[0][1]
        selected_reason = "single-running-log"
        log_strategy = "selected-running-log"
    elif selected_path is None and len(running_candidates) > 1:
        ambiguous = True
        warning = warning or f"Multiple running logs detected without unique match for calculation={calculation or 'unknown'}."

    fallback_candidates: list[Path] = []
    for candidate in _fallback_log_paths(workspace, layout=layout):
        if candidate.exists():
            fallback_candidates.append(candidate)
    if contained:
        fallback_candidates = _contained_unique_sources(workspace, fallback_candidates)

    if selected_path is None:
        if fallback_candidates:
            selected_path = fallback_candidates[0]
            selected_reason = f"fallback:{selected_path.name}"
            log_strategy = "fallback-log"
            if ambiguous:
                warning = warning or f"Falling back to {selected_path.name} because running log selection is ambiguous."
        elif ambiguous:
            log_strategy = "ambiguous-no-selection"

    ignored_log_paths = [
        str(path)
        for _, path in running_candidates
        if selected_path is None or path != selected_path
    ]
    if selected_path is not None:
        ignored_log_paths.extend(str(path) for path in fallback_candidates if path != selected_path)

    output_selection = _discover_output_log(
        workspace,
        explicit_output_log=output_log,
        layout=layout,
        contained=contained,
    )

    return {
        "main_log_path": selected_path,
        "output_log_path": output_selection["selected_path"],
        "warning": warning,
        "diagnostics": {
            "log_strategy": log_strategy,
            "selected_log_path": str(selected_path) if selected_path is not None else None,
            "selected_log_reason": selected_reason,
            "running_log_candidates": [str(path) for _, path in running_candidates],
            "fallback_log_candidates": [str(path) for path in fallback_candidates],
            "ignored_log_paths": ignored_log_paths,
            "log_selection_ambiguous": ambiguous,
            "output_log_path": str(output_selection["selected_path"]) if output_selection["selected_path"] is not None else None,
            "output_log_reason": output_selection["selected_reason"],
            "output_log_candidates": output_selection["candidate_paths"],
            "output_log_selection_ambiguous": output_selection["ambiguous"],
            "output_log_override_requested": output_selection["override_requested"],
            "output_log_override_missing": output_selection["override_missing"],
            "output_log_ignored_paths": output_selection["ignored_paths"],
        },
    }


def _determine_status(metrics: dict[str, Any], *, stderr_path: Path, text_blobs: list[str]) -> str:
    stderr_text = stderr_path.read_text(encoding="utf-8", errors="ignore").strip() if stderr_path.exists() else ""
    if stderr_text and not metrics.get("normal_end", False) and _stderr_looks_fatal(stderr_text):
        return "failed"
    if not any(blob.strip() for blob in text_blobs):
        return "missing-output"
    if not metrics.get("converged", False):
        return "unfinished"
    return "completed"


def _stderr_looks_fatal(text: str) -> bool:
    fatal_patterns = (
        "error:",
        "fatal",
        "traceback",
        "segmentation fault",
        "command timed out",
        "executable not found",
    )
    lowered = text.lower()
    return any(pattern in lowered for pattern in fatal_patterns)


def _natural_sort_key(value: str) -> list[Any]:
    parts = []
    for chunk in value.replace("\\", "/").split("/"):
        for token in __import__("re").split(r"(\d+)", chunk):
            if not token:
                continue
            parts.append(int(token) if token.isdigit() else token)
    return parts


def _discover_output_log(
    workspace: Workspace,
    *,
    explicit_output_log: str | Path | None,
    layout: str = "forge",
    contained: bool = False,
) -> dict[str, Any]:
    override_requested = str(explicit_output_log) if explicit_output_log is not None else None
    override_missing = False
    if explicit_output_log is not None:
        explicit_path = _resolve_workspace_path(workspace, explicit_output_log)
        if explicit_path.exists() and explicit_path.is_file() and (not contained or contained_source(workspace.root, explicit_path)):
            return {
                "selected_path": explicit_path,
                "selected_reason": "override",
                "candidate_paths": [str(explicit_path)],
                "ambiguous": False,
                "override_requested": override_requested,
                "override_missing": False,
                "ignored_paths": [],
            }
        override_missing = True

    fixed_candidates = [candidate for candidate in _fallback_log_paths(workspace, layout=layout) if candidate.exists() and candidate.is_file()]
    if contained:
        fixed_candidates = _contained_unique_sources(workspace, fixed_candidates)
    if fixed_candidates:
        selected = sorted(fixed_candidates, key=lambda path: _natural_sort_key(str(path.relative_to(workspace.root))))[0]
        return {
            "selected_path": selected,
            "selected_reason": f"fixed-candidate:{selected.name}",
            "candidate_paths": [str(path) for path in fixed_candidates],
            "ambiguous": len(fixed_candidates) > 1,
            "override_requested": override_requested,
            "override_missing": override_missing,
            "ignored_paths": [str(path) for path in fixed_candidates if path != selected],
        }

    content_candidates = _candidate_output_logs(workspace, layout=layout)
    if contained:
        content_candidates = _contained_unique_sources(workspace, content_candidates)
    matching_candidates = [path for path in content_candidates if _file_contains_output_banner(path)]
    if not matching_candidates:
        return {
            "selected_path": None,
            "selected_reason": "not-found",
            "candidate_paths": [],
            "ambiguous": False,
            "override_requested": override_requested,
            "override_missing": override_missing,
            "ignored_paths": [],
        }

    selected = matching_candidates[0]
    return {
        "selected_path": selected,
        "selected_reason": "banner-discovery",
        "candidate_paths": [str(path) for path in matching_candidates],
        "ambiguous": len(matching_candidates) > 1,
        "override_requested": override_requested,
        "override_missing": override_missing,
        "ignored_paths": [str(path) for path in matching_candidates if path != selected],
    }


def _contained_unique_sources(workspace: Workspace, candidates: list[Path]) -> list[Path]:
    sources: dict[Path, None] = {}
    for candidate in candidates:
        source = contained_source(workspace.root, candidate)
        if source is not None:
            sources[source] = None
    return list(sources)


def _candidate_output_logs(workspace: Workspace, *, layout: str = "forge") -> list[Path]:
    candidates: list[Path] = []
    bases = (workspace.root,) if layout == "flat" else (workspace.root, workspace.outputs_dir)
    for base in bases:
        if not base.exists():
            continue
        for path in sorted(base.iterdir(), key=lambda item: _natural_sort_key(str(item.relative_to(workspace.root)))):
            if not path.is_file():
                continue
            if path.name == "stderr.log":
                continue
            candidates.append(path)
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        if path not in seen:
            unique.append(path)
            seen.add(path)
    return unique


def _fallback_log_paths(workspace: Workspace, *, layout: str) -> tuple[Path, ...]:
    if layout == "flat":
        return (workspace.root / "stdout.log", workspace.root / "out.log")
    return (workspace.outputs_dir / "stdout.log", workspace.outputs_dir / "out.log")


def _stderr_path(workspace: Workspace, *, layout: str) -> Path:
    return workspace.root / "stderr.log" if layout == "flat" else workspace.outputs_dir / "stderr.log"


def _file_contains_output_banner(path: Path) -> bool:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return any(marker in content for marker in _OUTPUT_BANNER_MARKERS)


def _resolve_workspace_path(workspace: Workspace, raw_path: str | Path) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return workspace.root / candidate


def _read_text_if_exists(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="ignore")


def _input_path(workspace: Workspace, name: str, *, layout: str) -> Path:
    return (workspace.root if layout == "flat" else workspace.inputs_dir) / name


def _inputs_snapshot(workspace: Workspace, *, layout: str = "forge", contained: bool = False) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    input_path = _input_path(workspace, "INPUT", layout=layout)
    if input_path.exists() and (not contained or contained_source(workspace.root, input_path)):
        snapshot["INPUT"] = read_input(input_path)
    kpt_path = _input_path(workspace, "KPT", layout=layout)
    if kpt_path.exists() and (not contained or contained_source(workspace.root, kpt_path)):
        snapshot["KPT"] = kpt_path.read_text(encoding="utf-8")
        try:
            snapshot["KPT_PARSED"] = read_kpt(kpt_path)
        except Exception as exc:
            snapshot["KPT_PARSE_ERROR"] = str(exc)
    return snapshot


def _structure_snapshot(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        structure = AbacusStructure.from_input(path, structure_format="stru")
        payload = structure.metadata().to_dict()
        payload["source"] = str(path)
        return payload
    except Exception as exc:
        return {
            "source": str(path),
            "parse_error": str(exc),
        }


def _final_structure_snapshot(artifacts: dict[str, str]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    candidate_suffixes = (
        "STRU_FINAL",
        "STRU_FINAL.cif",
        "STRU_ION_D",
        "STRU_NOW",
        "STRU_NOW.cif",
        "STRU.cif",
        "STRU",
    )
    candidates: list[tuple[str, Path]] = []
    for suffix in candidate_suffixes:
        path = _artifact_from_suffix(artifacts, suffix)
        if path is None or not path.exists():
            continue
        candidates.append((suffix, path))

    diagnostics: dict[str, Any] = {
        "final_structure_candidates": [str(path) for _, path in candidates],
        "final_structure_selection_ambiguous": len(candidates) > 1,
    }
    if not candidates:
        diagnostics["final_structure_path"] = None
        return None, diagnostics

    selected_suffix, selected_path = candidates[0]
    diagnostics["final_structure_path"] = str(selected_path)
    diagnostics["final_structure_selected_suffix"] = selected_suffix
    try:
        fmt = "stru" if selected_suffix in {"STRU", "STRU_ION_D", "STRU_FINAL", "STRU_NOW"} else None
        structure = AbacusStructure.from_input(selected_path, structure_format=fmt)
        payload = structure.metadata().to_dict()
        payload["source"] = str(selected_path)
        return payload, diagnostics
    except Exception as exc:
        diagnostics["final_structure_parse_error"] = str(exc)
        return {
            "source": str(selected_path),
            "parse_error": str(exc),
        }, diagnostics


def _artifact_from_suffix(artifacts: dict[str, str], suffix: str) -> Path | None:
    for relative, path in artifacts.items():
        if relative.endswith(suffix):
            return Path(path)
    return None


def _snapshot_volume(snapshot: dict[str, Any] | None) -> float | None:
    if not isinstance(snapshot, dict):
        return None
    value = snapshot.get("volume")
    return float(value) if isinstance(value, (int, float)) else None
