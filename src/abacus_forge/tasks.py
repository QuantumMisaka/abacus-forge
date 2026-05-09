"""Task-oriented single-workspace helpers built from Forge primitives."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ase import Atoms

from abacus_forge.api import collect, export, prepare, run
from abacus_forge.result import CollectionResult, TaskResult
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
    timeout_seconds: float | None = None,
    env_overrides: Mapping[str, str] | None = None,
    dry_run: bool = False,
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

    runner = LocalRunner(
        executable=executable,
        mpi_ranks=mpi,
        omp_threads=omp,
        timeout_seconds=timeout_seconds,
        env_overrides=dict(env_overrides or {}),
    )
    if dry_run:
        collected = collect(ws, output_log=output_log)
        collected.status = "dry-run"
        collected.diagnostics.setdefault("task", normalized_task)
        collected.diagnostics["dry_run"] = True
        collected.diagnostics["command_preview"] = runner.preview(ws)
        collected.diagnostics["expected_artifacts"] = _expected_artifacts(normalized_task)
        if export_destination is not None:
            export(collected, destination=Path(export_destination))
            collected.diagnostics["export_destination"] = str(Path(export_destination))
        return collected

    run_result = run(ws, runner=runner)
    postprocess_diagnostics: dict[str, Any] = {}
    if normalized_task == "dos":
        postprocess_diagnostics = _postprocess_dos_outputs(ws)
    collected = collect(ws, output_log=output_log)
    collected.diagnostics.setdefault("task", normalized_task)
    if postprocess_diagnostics:
        collected.diagnostics["dos_postprocess"] = postprocess_diagnostics
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


def run_cell_relax(workspace: str | Path | Workspace, **kwargs: Any) -> CollectionResult:
    """Run one cell-relax task end-to-end."""

    return run_task(workspace, task="cell-relax", **kwargs)


def run_md(
    workspace: str | Path | Workspace,
    *,
    md_type: str | None = None,
    md_nstep: int | None = None,
    md_dt: float | None = None,
    md_tfirst: float | None = None,
    md_tlast: float | None = None,
    md_dumpfreq: int | None = None,
    **kwargs: Any,
) -> CollectionResult:
    """Run one molecular dynamics task end-to-end."""

    parameters = dict(kwargs.pop("parameters", {}) or {})
    for key, value in {
        "md_type": md_type,
        "md_nstep": md_nstep,
        "md_dt": md_dt,
        "md_tfirst": md_tfirst,
        "md_tlast": md_tlast,
        "md_dumpfreq": md_dumpfreq,
    }.items():
        if value is not None:
            parameters[key] = value
    return run_task(workspace, task="md", parameters=parameters, **kwargs)


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


def run_band_sequence(
    workspace: str | Path | Workspace,
    *,
    line_kpoints: Sequence[Mapping[str, Any] | tuple[Iterable[float], str | None]],
    line_segments: int = 20,
    **kwargs: Any,
) -> TaskResult:
    """Run a local SCF -> NSCF band sequence and return a pack-level result."""

    return _run_scf_nscf_sequence(
        workspace,
        sequence_task="band_sequence",
        nscf_task="band",
        line_kpoints=line_kpoints,
        line_segments=line_segments,
        **kwargs,
    )


def run_dos_sequence(workspace: str | Path | Workspace, **kwargs: Any) -> TaskResult:
    """Run a local SCF -> NSCF DOS sequence and return a pack-level result."""

    return _run_scf_nscf_sequence(
        workspace,
        sequence_task="dos_sequence",
        nscf_task="dos",
        **kwargs,
    )


def _normalize_line_kpoints(
    points: Sequence[Mapping[str, Any] | tuple[Iterable[float], str | None]] | None,
) -> list[dict[str, Any]] | None:
    if not points:
        return None
    normalized: list[dict[str, Any]] = []
    for point in points:
        if isinstance(point, Mapping):
            coords = [float(value) for value in point["coords"]]
            label = point.get("label")
            npoints = point.get("npoints")
        else:
            coords, label = point
            coords = [float(value) for value in coords]
            npoints = None
        if len(coords) != 3:
            raise ValueError(f"line-mode KPT point requires 3 coordinates, got {coords!r}")
        payload = {"coords": coords, "label": str(label) if label is not None else None}
        if npoints is not None:
            payload["npoints"] = int(npoints)
        normalized.append(payload)
    return normalized


def _read_workspace_metadata(workspace: Workspace) -> dict[str, Any]:
    if not workspace.meta_path.exists():
        return {}
    import json

    payload = json.loads(workspace.meta_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _run_scf_nscf_sequence(
    workspace: str | Path | Workspace,
    *,
    sequence_task: str,
    nscf_task: str,
    structure: str | Path | AbacusStructure | Atoms | Any | None = None,
    structure_format: str | None = None,
    parameters: Mapping[str, Any] | None = None,
    scf_parameters: Mapping[str, Any] | None = None,
    nscf_parameters: Mapping[str, Any] | None = None,
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
    timeout_seconds: float | None = None,
    env_overrides: Mapping[str, str] | None = None,
    dry_run: bool = False,
    export_destination: str | Path | None = None,
) -> TaskResult:
    root = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace))
    root.ensure_layout()
    base_parameters = dict(parameters or {})
    scf_ws = Workspace(root.root / "scf")
    nscf_ws = Workspace(root.root / "nscf")
    common = {
        "structure": structure,
        "structure_format": structure_format,
        "remove_parameters": remove_parameters,
        "kpoints": kpoints,
        "metadata": dict(metadata or {}),
        "pseudo_path": pseudo_path,
        "orbital_path": orbital_path,
        "asset_mode": asset_mode,
        "ensure_pbc": ensure_pbc,
        "structure_standardization": structure_standardization,
        "magmom_by_element": dict(magmom_by_element or {}) or None,
    }
    prepare(
        scf_ws,
        task="scf",
        parameters={**base_parameters, **dict(scf_parameters or {})},
        **common,
    )
    prepare(
        nscf_ws,
        task=nscf_task,
        parameters={**base_parameters, **dict(nscf_parameters or {})},
        kpt_mode="line" if nscf_task == "band" else "mesh",
        line_kpoints=_normalize_line_kpoints(line_kpoints),
        **common,
    )
    if nscf_task == "band":
        if not line_kpoints:
            raise ValueError("band sequence requires explicit line-mode KPT points")
        from abacus_forge.input_io import write_kpt_line_mode

        write_kpt_line_mode(nscf_ws.inputs_dir / "KPT", _normalize_line_kpoints(line_kpoints) or [], segments=line_segments)

    runner = LocalRunner(
        executable=executable,
        mpi_ranks=mpi,
        omp_threads=omp,
        timeout_seconds=timeout_seconds,
        env_overrides=dict(env_overrides or {}),
    )
    run_results = []
    if dry_run:
        scf_collected = collect(scf_ws)
        nscf_collected = collect(nscf_ws)
    else:
        run_results = [run(scf_ws, runner=runner), run(nscf_ws, runner=runner)]
        postprocess_diagnostics = _postprocess_dos_outputs(nscf_ws) if nscf_task == "dos" else {}
        scf_collected = collect(scf_ws)
        nscf_collected = collect(nscf_ws)
        if postprocess_diagnostics:
            nscf_collected.diagnostics["dos_postprocess"] = postprocess_diagnostics
    subtasks = [
        _collection_subtask_payload("scf", scf_collected),
        _collection_subtask_payload(nscf_task, nscf_collected),
    ]
    if run_results:
        for payload, run_result in zip(subtasks, run_results, strict=False):
            payload["run"] = run_result.to_dict()
    status = "completed" if all(item["status"] == "completed" for item in subtasks) else "failed"
    if dry_run:
        status = "dry-run"
    result = TaskResult(
        task=sequence_task,
        workspace=root.root,
        status=status,
        subtasks=subtasks,
        summary={
            "scf_status": scf_collected.status,
            "nscf_status": nscf_collected.status,
            "nscf_metrics": nscf_collected.metrics,
        },
        artifacts={f"scf/{key}": value for key, value in scf_collected.artifacts.items()}
        | {f"nscf/{key}": value for key, value in nscf_collected.artifacts.items()},
        diagnostics={"runner": runner.preview(nscf_ws), "dry_run": dry_run},
    )
    if export_destination is not None:
        export(result, destination=Path(export_destination))
        result.diagnostics["export_destination"] = str(Path(export_destination))
    return result


def _collection_subtask_payload(task: str, result: CollectionResult) -> dict[str, Any]:
    return {
        "task": task,
        "workspace": str(result.workspace),
        "status": result.status,
        "metrics": result.metrics,
        "diagnostics": result.diagnostics,
    }


def _postprocess_dos_outputs(workspace: Workspace) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {"searched_dirs": [str(path) for path in _dos_output_dirs(workspace)]}
    try:
        from abacus_forge.dos_data import DOSData, PDOSData
        from abacus_forge.dos_postprocess import postprocess_dos_family

        metadata = _read_workspace_metadata(workspace).get("metadata", {})
        controls = dict(metadata.get("dos_family_controls", {})) if isinstance(metadata, dict) else {}
        dos_files = _find_dos_artifacts(workspace, "DOS*_smearing.dat")
        diagnostics["dos_files"] = [str(path) for path in dos_files]
        total_dos = DOSData.from_paths(dos_files) if dos_files and controls.get("include_tdos", True) else None
        pdos_path = _find_first_dos_artifact(workspace, "PDOS")
        tdos_path = _find_first_dos_artifact(workspace, "TDOS")
        diagnostics["pdos_path"] = str(pdos_path) if pdos_path is not None else None
        diagnostics["tdos_path"] = str(tdos_path) if tdos_path is not None else None
        projected_dos = (
            PDOSData.from_path(pdos_path, tdos_path=tdos_path)
            if pdos_path is not None and controls.get("include_pdos", True)
            else None
        )
        if total_dos is None and (projected_dos is None or not projected_dos.projected_dos):
            diagnostics["status"] = "skipped"
            return diagnostics
        artifacts = postprocess_dos_family(
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
        diagnostics["status"] = "completed"
        diagnostics["artifacts"] = artifacts
        return diagnostics
    except Exception as exc:
        diagnostics["status"] = "failed"
        diagnostics["error"] = str(exc)
        workspace.write_json("reports/dos_postprocess_diagnostics.json", diagnostics)
        return diagnostics


def _dos_output_dirs(workspace: Workspace) -> list[Path]:
    candidates: list[Path] = []
    for base in (workspace.inputs_dir, workspace.outputs_dir):
        if base.exists():
            candidates.extend(path for path in sorted(base.glob("OUT.*")) if path.is_dir())
    candidates.append(workspace.outputs_dir)
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        if path not in seen:
            unique.append(path)
            seen.add(path)
    return unique


def _find_dos_artifacts(workspace: Workspace, pattern: str) -> list[Path]:
    matches: list[Path] = []
    for directory in _dos_output_dirs(workspace):
        matches.extend(sorted(path for path in directory.glob(pattern) if path.is_file()))
    return matches


def _find_first_dos_artifact(workspace: Workspace, name: str) -> Path | None:
    for directory in _dos_output_dirs(workspace):
        candidate = directory / name
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _expected_artifacts(task: str) -> list[str]:
    common = ["outputs/stdout.log", "outputs/stderr.log", "reports/metrics.json"]
    if task == "band":
        return [*common, "outputs/BANDS_1.dat", "outputs/band.png"]
    if task == "dos":
        return [*common, "outputs/DOS1_smearing.dat", "outputs/PDOS", "outputs/TDOS"]
    if task in {"relax", "cell-relax"}:
        return [*common, "outputs/OUT.ABACUS/STRU_ION_D"]
    if task == "md":
        return [*common, "outputs/MD_dump"]
    return common
