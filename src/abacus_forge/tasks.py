"""Task-oriented single-workspace helpers built from Forge primitives."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ase import Atoms

from abacus_forge.api import collect, export, prepare, run
from abacus_forge.result import CollectionResult
from abacus_forge.runner import LocalRunner
from abacus_forge.structure import AbacusStructure
from abacus_forge.workspace import Workspace


def run_task(
    workspace: str | Path | Workspace,
    *,
    task: str,
    structure: str | Path | AbacusStructure | Atoms | Any | None = None,
    structure_format: str | None = None,
    parameters: Mapping[str, Any] | None = None,
    remove_parameters: Iterable[str] | None = None,
    kpoints: Iterable[int] | None = None,
    line_kpoints: Sequence[Mapping[str, Any] | tuple[Iterable[float], str | None]] | None = None,
    line_segments: int = 20,
    metadata: Mapping[str, Any] | None = None,
    pseudo_path: str | Path | None = None,
    orbital_path: str | Path | None = None,
    asset_mode: str = "link",
    ensure_pbc: bool = False,
    structure_standardization: str | None = None,
    magmom_by_element: Mapping[str, float] | None = None,
    executable: str = "abacus",
    mpi: int = 1,
    omp: int = 1,
    output_log: str | Path | None = None,
    export_destination: str | Path | None = None,
) -> CollectionResult:
    """Run one Forge task end-to-end within a single workspace."""

    normalized_task = str(task).strip().lower()
    normalized_line_kpoints = _normalize_line_kpoints(line_kpoints)
    if normalized_task == "band" and not normalized_line_kpoints:
        raise ValueError("band task requires explicit line-mode KPT points")

    ws = prepare(
        workspace,
        structure=structure,
        structure_format=structure_format,
        task=normalized_task,
        parameters=dict(parameters or {}),
        remove_parameters=remove_parameters,
        kpoints=kpoints,
        kpt_mode="line" if normalized_line_kpoints else "mesh",
        line_kpoints=normalized_line_kpoints,
        metadata=dict(metadata or {}),
        pseudo_path=pseudo_path,
        orbital_path=orbital_path,
        asset_mode=asset_mode,
        ensure_pbc=ensure_pbc,
        structure_standardization=structure_standardization,
        magmom_by_element=dict(magmom_by_element or {}) or None,
    )
    if normalized_line_kpoints:
        ws.record_metadata(
            {
                **_read_workspace_metadata(ws),
                "task_line_segments": int(line_segments),
            }
        )
        from abacus_forge.input_io import write_kpt_line_mode

        write_kpt_line_mode(ws.inputs_dir / "KPT", normalized_line_kpoints, segments=int(line_segments))

    runner = LocalRunner(executable=executable, mpi_ranks=mpi, omp_threads=omp)
    run_result = run(ws, runner=runner)
    collected = collect(ws, output_log=output_log)
    collected.diagnostics.setdefault("task", normalized_task)
    collected.diagnostics.setdefault("task_runner", {})
    collected.diagnostics["task_runner"].update(
        {
            "status": run_result.status,
            "returncode": run_result.returncode,
            "command": run_result.command,
            "stdout_path": str(run_result.stdout_path),
            "stderr_path": str(run_result.stderr_path),
        }
    )
    if export_destination is not None:
        export(collected, destination=Path(export_destination))
        collected.diagnostics["export_destination"] = str(Path(export_destination))
    return collected


def run_scf(workspace: str | Path | Workspace, **kwargs: Any) -> CollectionResult:
    """Run one SCF task end-to-end."""

    return run_task(workspace, task="scf", **kwargs)


def run_relax(workspace: str | Path | Workspace, **kwargs: Any) -> CollectionResult:
    """Run one relax task end-to-end."""

    return run_task(workspace, task="relax", **kwargs)


def run_band(
    workspace: str | Path | Workspace,
    *,
    line_kpoints: Sequence[Mapping[str, Any] | tuple[Iterable[float], str | None]],
    line_segments: int = 20,
    **kwargs: Any,
) -> CollectionResult:
    """Run one band task with explicit line-mode K points."""

    return run_task(
        workspace,
        task="band",
        line_kpoints=line_kpoints,
        line_segments=line_segments,
        **kwargs,
    )


def run_dos(workspace: str | Path | Workspace, **kwargs: Any) -> CollectionResult:
    """Run one DOS task that also enables PDOS outputs."""

    return run_task(workspace, task="dos", **kwargs)


def _normalize_line_kpoints(
    points: Sequence[Mapping[str, Any] | tuple[Iterable[float], str | None]] | None,
) -> list[tuple[list[float], str | None]] | None:
    if not points:
        return None
    normalized: list[tuple[list[float], str | None]] = []
    for point in points:
        if isinstance(point, Mapping):
            coords = [float(value) for value in point["coords"]]
            label = point.get("label")
        else:
            coords, label = point
            coords = [float(value) for value in coords]
        if len(coords) != 3:
            raise ValueError(f"line-mode KPT point requires 3 coordinates, got {coords!r}")
        normalized.append((coords, str(label) if label is not None else None))
    return normalized


def _read_workspace_metadata(workspace: Workspace) -> dict[str, Any]:
    if not workspace.meta_path.exists():
        return {}
    import json

    payload = json.loads(workspace.meta_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}
