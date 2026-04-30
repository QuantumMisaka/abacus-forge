"""Prepare/run/collect/export primitives for ABACUS workspaces."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from ase import Atoms

from abacus_forge.assets import collect_assets, stage_assets
from abacus_forge.collectors.abacus import collect_abacus_metrics
from abacus_forge.input_io import read_input, read_kpt, write_input, write_kpt_line_mode, write_kpt_mesh
from abacus_forge.prepare_profiles import build_task_parameters
from abacus_forge.result import CollectionResult, RunResult
from abacus_forge.runner import LocalRunner
from abacus_forge.structure import AbacusStructure
from abacus_forge.workspace import Workspace
from abacus_forge.validation import validate_inputs


def prepare(
    workspace: str | Path | Workspace,
    *,
    structure: str | Path | AbacusStructure | Atoms | Any | None = None,
    structure_format: str | None = None,
    task: str | None = None,
    parameters: dict[str, Any] | None = None,
    input_overrides: dict[str, Any] | None = None,
    remove_parameters: Iterable[str] | None = None,
    kpoints: Iterable[int] | None = None,
    kpt_mode: str = "mesh",
    line_kpoints: Iterable[tuple[Iterable[float], str | None]] | None = None,
    metadata: dict[str, Any] | None = None,
    pseudo_path: str | Path | None = None,
    orbital_path: str | Path | None = None,
    asset_mode: str = "link",
    ensure_pbc: bool = False,
    structure_standardization: str | None = None,
    magmom_by_element: dict[str, float] | None = None,
) -> Workspace:
    """Create a prepared workspace with canonical ABACUS inputs."""

    ws = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace))
    ws.ensure_layout()

    structure_payload = None
    structure_info: dict[str, Any] | None = None
    if structure is not None:
        try:
            structure_payload = AbacusStructure.from_input(structure, structure_format=structure_format)
        except Exception:
            structure_payload = None
            if not _write_structure_fallback(ws, structure):
                raise
        if structure_payload is not None:
            if ensure_pbc:
                structure_payload = structure_payload.ensure_3d_pbc()
            if structure_standardization == "conventional":
                structure_payload = structure_payload.primitive_to_conventional()
            elif structure_standardization == "primitive":
                structure_payload = structure_payload.conventional_to_primitive()
            elif structure_standardization == "swap-layer-to-c":
                meta = structure_payload.metadata()
                if meta.structure_class == "layer" and meta.layer_info and meta.layer_info["long_axis"] != 2:
                    structure_payload = structure_payload.swap_axes(meta.layer_info["long_axis"], 2)
                elif meta.structure_class == "string" and meta.string_info and meta.string_info["extension_axis"] != 2:
                    structure_payload = structure_payload.swap_axes(meta.string_info["extension_axis"], 2)
            if magmom_by_element:
                atoms = structure_payload.atoms.copy()
                initial_magmoms = [
                    float(magmom_by_element.get(symbol, 0.0))
                    for symbol in atoms.get_chemical_symbols()
                ]
                atoms.set_initial_magnetic_moments(initial_magmoms)
                structure_payload = AbacusStructure(atoms, source_format=structure_payload.source_format)
            pseudo_map = collect_assets(pseudo_path)
            orbital_map = collect_assets(orbital_path)
            ws.write_text("inputs/STRU", structure_payload.to_stru(pp_map=_basename_map(pseudo_map), orb_map=_basename_map(orbital_map)))
            stage_assets(ws.inputs_dir, pseudo_map=pseudo_map, orbital_map=orbital_map, mode=asset_mode)
            structure_info = structure_payload.metadata().to_dict()

    params = build_task_parameters(task, metadata=structure_payload.metadata() if structure_payload is not None else None, parameters=parameters)
    if input_overrides:
        params.update(input_overrides)
    for key in remove_parameters or ():
        params.pop(str(key), None)
    write_input(ws.inputs_dir / "INPUT", params)

    mesh = list(kpoints or [1, 1, 1])
    if kpt_mode == "line" and line_kpoints:
        write_kpt_line_mode(ws.inputs_dir / "KPT", list(line_kpoints))
    else:
        write_kpt_mesh(ws.inputs_dir / "KPT", mesh)

    ws.record_metadata(
        {
            "kind": "abacus-forge.workspace",
            "task": task or "scf",
            "structure": str(Path(structure)) if isinstance(structure, (str, Path)) else None,
            "structure_format": structure_payload.source_format if structure_payload is not None else structure_format,
            "structure_metadata": structure_info,
            "parameters": params,
            "kpoints": mesh,
            "metadata": metadata or {},
            "validation": validate_inputs(ws.inputs_dir),
        }
    )
    return ws


def run(workspace: str | Path | Workspace, *, runner: LocalRunner | None = None, check: bool = False) -> RunResult:
    """Execute one prepared workspace with a local runner."""

    ws = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace))
    return (runner or LocalRunner()).run(ws, check=check)


_OUTPUT_BANNER_MARKERS = (
    "Atomic-orbital Based Ab-initio",
)


def collect(
    workspace: str | Path | Workspace,
    *,
    output_log: str | Path | None = None,
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

    ws = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace))
    artifacts = _collect_artifacts(ws)
    inputs_snapshot = _inputs_snapshot(ws)
    log_selection = _select_log_sources(ws, artifacts, inputs_snapshot=inputs_snapshot, output_log=output_log)
    main_log_path = log_selection["main_log_path"]
    output_log_path = log_selection["output_log_path"]
    main_log_text = _read_text_if_exists(main_log_path)
    output_log_text = _read_text_if_exists(output_log_path)
    stderr_path = ws.outputs_dir / "stderr.log"
    structure_snapshot = _structure_snapshot(ws.inputs_dir / "STRU")
    final_structure_snapshot, final_structure_diagnostics = _final_structure_snapshot(artifacts)
    metrics, diagnostics = collect_abacus_metrics(
        main_log_text=main_log_text,
        output_log_text=output_log_text,
        artifacts=artifacts,
        workspace_root=ws.root,
        structure_volume=_snapshot_volume(final_structure_snapshot) or _snapshot_volume(structure_snapshot),
    )
    diagnostics.update(log_selection["diagnostics"])
    diagnostics.update(final_structure_diagnostics)
    diagnostics["log_paths"] = [
        str(path)
        for path in (main_log_path, output_log_path)
        if path is not None
    ]
    diagnostics["stderr_nonempty"] = bool(
        stderr_path.exists() and stderr_path.read_text(encoding="utf-8", errors="ignore").strip()
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
    status = _determine_status(
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
    )


def export(result: RunResult | CollectionResult, destination: str | Path | None = None, *, pretty: bool = True) -> str:
    """Serialize a structured result as JSON and optionally write it to disk."""

    payload = result.to_dict()
    text = json.dumps(payload, indent=2 if pretty else None, sort_keys=True)
    if destination is not None:
        Path(destination).write_text(text + ("\n" if pretty else ""), encoding="utf-8")
    return text


def _collect_artifacts(workspace: Workspace) -> dict[str, str]:
    artifacts: dict[str, str] = {}
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
    for candidate in (
        workspace.outputs_dir / "stdout.log",
        workspace.outputs_dir / "out.log",
    ):
        if candidate.exists():
            fallback_candidates.append(candidate)

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
    if stderr_path.exists() and stderr_path.read_text(encoding="utf-8", errors="ignore").strip():
        return "failed"
    if not any(blob.strip() for blob in text_blobs):
        return "missing-output"
    if not metrics.get("converged", False):
        return "unfinished"
    return "completed"


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
) -> dict[str, Any]:
    override_requested = str(explicit_output_log) if explicit_output_log is not None else None
    override_missing = False
    if explicit_output_log is not None:
        explicit_path = _resolve_workspace_path(workspace, explicit_output_log)
        if explicit_path.exists() and explicit_path.is_file():
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

    fixed_candidates = [
        candidate
        for candidate in (
            workspace.outputs_dir / "stdout.log",
            workspace.outputs_dir / "out.log",
        )
        if candidate.exists() and candidate.is_file()
    ]
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

    content_candidates = _candidate_output_logs(workspace)
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


def _candidate_output_logs(workspace: Workspace) -> list[Path]:
    candidates: list[Path] = []
    for base in (workspace.root, workspace.outputs_dir):
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


def _inputs_snapshot(workspace: Workspace) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    input_path = workspace.inputs_dir / "INPUT"
    if input_path.exists():
        snapshot["INPUT"] = read_input(input_path)
    kpt_path = workspace.inputs_dir / "KPT"
    if kpt_path.exists():
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
        "STRU_ION_D",
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
        fmt = "stru" if selected_suffix.endswith("STRU") or selected_suffix == "STRU_ION_D" else None
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


def _basename_map(mapping: dict[str, Path]) -> dict[str, str]:
    return {element: path.name for element, path in mapping.items()}


def _write_structure_fallback(workspace: Workspace, structure: Any) -> bool:
    if isinstance(structure, Path):
        if structure.exists() and structure.is_file():
            workspace.write_text("inputs/STRU", structure.read_text(encoding="utf-8", errors="ignore"))
            return True
        return False
    if isinstance(structure, str):
        path = _existing_path(structure)
        if path is not None:
            workspace.write_text("inputs/STRU", path.read_text(encoding="utf-8", errors="ignore"))
            return True
        if _looks_like_stru_text(structure):
            workspace.write_text("inputs/STRU", structure if structure.endswith("\n") else structure + "\n")
            return True
    return False


def _existing_path(value: str) -> Path | None:
    try:
        candidate = Path(value)
    except OSError:
        return None
    try:
        if candidate.exists() and candidate.is_file():
            return candidate
    except OSError:
        return None
    return None


def _looks_like_stru_text(payload: str) -> bool:
    markers = ("ATOMIC_SPECIES", "ATOMIC_POSITIONS", "LATTICE_VECTORS")
    return sum(marker in payload for marker in markers) >= 2
