"""Prepare/run/collect/export primitives for ABACUS workspaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from ase import Atoms

from abacus_forge.assets import collect_assets, stage_assets
from abacus_forge.collectors.abacus import collect_abacus_metrics
from abacus_forge.input_io import read_input, write_input, write_kpt_line_mode, write_kpt_mesh
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


def collect(workspace: str | Path | Workspace) -> CollectionResult:
    """Parse metrics, structures, and artifacts from one workspace."""

    ws = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace))
    artifacts = _collect_artifacts(ws)
    log_paths = _log_paths(ws, artifacts)
    text_blobs = [path.read_text(encoding="utf-8", errors="ignore") for path in log_paths if path.exists()]
    stderr_path = ws.outputs_dir / "stderr.log"
    metrics, diagnostics = collect_abacus_metrics(text_blobs=text_blobs, artifacts=artifacts, workspace_root=ws.root)
    status = _determine_status(metrics, stderr_path=stderr_path, text_blobs=text_blobs)
    inputs_snapshot = _inputs_snapshot(ws)
    structure_snapshot = _structure_snapshot(ws.inputs_dir / "STRU")
    final_structure_snapshot = _final_structure_snapshot(artifacts)
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


def _log_paths(workspace: Workspace, artifacts: dict[str, str]) -> list[Path]:
    paths: list[Path] = []
    for preferred in (
        workspace.outputs_dir / "stdout.log",
        workspace.outputs_dir / "stderr.log",
    ):
        if preferred.exists():
            paths.append(preferred)
    for relative, path in sorted(artifacts.items()):
        if Path(relative).name.startswith("running_") and relative.endswith(".log"):
            paths.append(Path(path))
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path not in seen:
            unique.append(path)
            seen.add(path)
    return unique


def _determine_status(metrics: dict[str, Any], *, stderr_path: Path, text_blobs: list[str]) -> str:
    if stderr_path.exists() and stderr_path.read_text(encoding="utf-8", errors="ignore").strip():
        return "failed"
    if not any(blob.strip() for blob in text_blobs):
        return "missing-output"
    if not metrics.get("converged", False):
        return "unfinished"
    return "completed"


def _inputs_snapshot(workspace: Workspace) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    input_path = workspace.inputs_dir / "INPUT"
    if input_path.exists():
        snapshot["INPUT"] = read_input(input_path)
    kpt_path = workspace.inputs_dir / "KPT"
    if kpt_path.exists():
        snapshot["KPT"] = kpt_path.read_text(encoding="utf-8")
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


def _final_structure_snapshot(artifacts: dict[str, str]) -> dict[str, Any] | None:
    candidates = (
        "STRU_ION_D",
        "STRU_NOW.cif",
        "STRU.cif",
        "STRU",
    )
    for candidate in candidates:
        path = _artifact_from_suffix(artifacts, candidate)
        if path is None or not path.exists():
            continue
        try:
            fmt = "stru" if candidate.endswith("STRU") or candidate == "STRU_ION_D" else None
            structure = AbacusStructure.from_input(path, structure_format=fmt)
            payload = structure.metadata().to_dict()
            payload["source"] = str(path)
            return payload
        except Exception as exc:
            return {
                "source": str(path),
                "parse_error": str(exc),
            }
    return None


def _artifact_from_suffix(artifacts: dict[str, str], suffix: str) -> Path | None:
    for relative, path in artifacts.items():
        if relative.endswith(suffix):
            return Path(path)
    return None


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
