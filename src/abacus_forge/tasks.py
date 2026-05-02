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
    if normalized_task == "dos":
        _postprocess_dos_outputs(ws)
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


def run_dos(
    workspace: str | Path | Workspace,
    *,
    include_tdos: bool = True,
    include_pdos: bool = True,
    include_ldos: bool = False,
    pdos_mode: str = "species",
    pdos_atom_indices: Sequence[int] | None = None,
    plot_emin: float = -10.0,
    plot_emax: float = 10.0,
    save_data: bool = True,
    save_plot: bool = True,
    suffix: str | None = None,
    dos_edelta_ev: float | None = None,
    dos_sigma: float | None = None,
    dos_emin_ev: float | None = None,
    dos_emax_ev: float | None = None,
    **kwargs: Any,
) -> CollectionResult:
    """Run one unified DOS-family task."""

    parameters = dict(kwargs.pop("parameters", {}) or {})
    for forbidden in ("dos_scale", "dos_nche"):
        if forbidden in parameters:
            raise ValueError(f"unsupported DOS parameter: {forbidden}")
    parameters.update(
        {
            "include_tdos": include_tdos,
            "include_pdos": include_pdos,
            "include_ldos": include_ldos,
            "pdos_mode": pdos_mode,
            "plot_emin": plot_emin,
            "plot_emax": plot_emax,
            "save_data": save_data,
            "save_plot": save_plot,
        }
    )
    if pdos_atom_indices is not None:
        parameters["pdos_atom_indices"] = list(pdos_atom_indices)
    if suffix is not None:
        parameters["suffix"] = suffix
    for key, value in {
        "dos_edelta_ev": dos_edelta_ev,
        "dos_sigma": dos_sigma,
        "dos_emin_ev": dos_emin_ev,
        "dos_emax_ev": dos_emax_ev,
    }.items():
        if value is not None:
            parameters[key] = value
    metadata = dict(kwargs.pop("metadata", {}) or {})
    metadata["dos_family_controls"] = {
        "include_tdos": include_tdos,
        "include_pdos": include_pdos,
        "include_ldos": include_ldos,
        "pdos_mode": pdos_mode,
        "pdos_atom_indices": list(pdos_atom_indices or []),
        "plot_emin": plot_emin,
        "plot_emax": plot_emax,
        "save_data": save_data,
        "save_plot": save_plot,
        "suffix": suffix,
    }
    return run_task(workspace, task="dos", parameters=parameters, metadata=metadata, **kwargs)


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


def _postprocess_dos_outputs(workspace: Workspace) -> None:
    try:
        from abacus_forge.dos_data import DOSData, PDOSData
        from abacus_forge.dos_postprocess import postprocess_dos_family

        metadata = _read_workspace_metadata(workspace).get("metadata", {})
        controls = dict(metadata.get("dos_family_controls", {})) if isinstance(metadata, dict) else {}
        dos_files = sorted(workspace.outputs_dir.glob("DOS*_smearing.dat"))
        total_dos = DOSData.from_paths(dos_files) if dos_files and controls.get("include_tdos", True) else None
        pdos_path = workspace.outputs_dir / "PDOS"
        projected_dos = (
            PDOSData.from_path(pdos_path, tdos_path=workspace.outputs_dir / "TDOS")
            if pdos_path.exists() and controls.get("include_pdos", True)
            else None
        )
        if total_dos is None and (projected_dos is None or not projected_dos.projected_dos):
            return
        postprocess_dos_family(
            output_dir=workspace.outputs_dir,
            total_dos=total_dos,
            projected_dos=projected_dos if projected_dos and projected_dos.projected_dos else None,
            pdos_mode=controls.get("pdos_mode", "species"),
            pdos_atom_indices=controls.get("pdos_atom_indices") or None,
            plot_emin=float(controls.get("plot_emin", -10.0)),
            plot_emax=float(controls.get("plot_emax", 10.0)),
            save_data=bool(controls.get("save_data", True)),
            save_plot=bool(controls.get("save_plot", True)),
            suffix=controls.get("suffix"),
        )
    except Exception:
        return
