"""Prepare/run/collect/export primitives for ABACUS workspaces."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from ase import Atoms

from abacus_forge.assets import collect_assets, stage_assets
from abacus_forge.collectors.abacus import collect_abacus_metrics
from abacus_forge.contracts import ArtifactRecord, ForgeResultEnvelope, OperationStatus
from abacus_forge.input_io import read_input, read_kpt, write_input, write_kpt_line_mode, write_kpt_mesh
from abacus_forge.modify import modify_input, modify_kpt, modify_stru
from abacus_forge.prepare_profiles import build_task_parameters
from abacus_forge.result import CollectionResult, RunResult, TaskResult
from abacus_forge.runner import LocalRunner
from abacus_forge.structure import AbacusStructure
from abacus_forge.workspace import Workspace
from abacus_forge.validation import validate_inputs


@dataclass(slots=True)
class UnitSpec:
    """Description of one atomic ABACUS/PyATB unit operation."""

    task: str
    workdir: str | Path | Workspace
    engine: str = "abacus"
    unit: str = "default"
    structure: str | Path | AbacusStructure | Atoms | Any | None = None
    structure_format: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    input_overrides: dict[str, Any] = field(default_factory=dict)
    remove_parameters: Iterable[str] | None = None
    kpoints: Iterable[int] | None = None
    line_kpoints: Iterable[dict[str, Any] | tuple[Iterable[float], str | None]] | None = None
    line_segments: int = 20
    metadata: dict[str, Any] = field(default_factory=dict)
    pseudo_path: str | Path | None = None
    orbital_path: str | Path | None = None
    asset_mode: str = "link"
    ensure_pbc: bool = False
    structure_standardization: str | None = None
    magmom_by_element: dict[str, float] | None = None
    source_workdir: str | Path | Workspace | None = None
    command: list[str] | None = None
    executable: str | None = None
    mpi: int = 1
    omp: int = 1
    timeout_seconds: float | None = None
    env_overrides: dict[str, str] = field(default_factory=dict)
    layout: str = "forge"
    output_log: str | Path | None = None
    postprocess: bool = True
    save_plot: bool = True
    save_data: bool = True
    include_tdos: bool = True
    include_pdos: bool = True
    pdos_mode: str = "species"
    pdos_atom_indices: list[int] | None = None
    plot_emin: float = -10.0
    plot_emax: float = 10.0
    suffix: str | None = None


@dataclass(slots=True)
class UnitPrepareResult:
    """Prepared workspace for one atomic unit."""

    workspace: Workspace
    task: str
    unit: str
    engine: str
    manifest: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace": str(self.workspace.root),
            "task": self.task,
            "unit": self.unit,
            "engine": self.engine,
            "manifest": self.manifest,
        }


@dataclass(slots=True)
class UnitModifySpec:
    """Workspace-aware input modification request for one atomic unit."""

    task: str
    workdir: str | Path | Workspace
    engine: str = "abacus"
    unit: str = "default"
    layout: str = "forge"
    input_updates: dict[str, Any] = field(default_factory=dict)
    remove_parameters: Iterable[str] | None = None
    kpt_mode: str | None = None
    mesh: Iterable[int] | None = None
    shifts: Iterable[int] | None = None
    line_kpoints: Iterable[dict[str, Any] | tuple[Iterable[float], str | None]] | None = None
    line_segments: int | None = None
    magmom_by_element: dict[str, float] | None = None
    magmoms: Iterable[float] | None = None
    afm: bool = False
    afm_elements: Iterable[str] | None = None
    supercell: tuple[int, int, int] | list[int] | None = None
    vacancy_indices: Iterable[int] | None = None
    ensure_pbc: bool = False
    vacuum: float = 10.0
    structure_standardization: str | None = None


@dataclass(slots=True)
class UnitModifyResult:
    """Outcome of one workspace-aware input modification."""

    workspace: Path
    task: str
    unit: str
    engine: str
    status: str
    modified_files: list[str] = field(default_factory=list)
    changes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace": str(self.workspace),
            "task": self.task,
            "unit": self.unit,
            "engine": self.engine,
            "status": self.status,
            "modified_files": self.modified_files,
            "changes": self.changes,
        }


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
            pseudo_map = collect_assets(pseudo_path, family="pseudo")
            orbital_map = collect_assets(orbital_path, family="orbital")
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


def execute(workspace: str | Path | Workspace, *, runner: LocalRunner | None = None, check: bool = False) -> RunResult:
    """Execute one prepared workspace.

    ``execute`` is the canonical primitive name; ``run`` remains the
    compatibility alias for existing callers.
    """

    return run(workspace, runner=runner, check=check)


def prepare_unit(spec: UnitSpec, *, record_event: bool = True) -> UnitPrepareResult:
    """Prepare one explicit ABACUS/PyATB task unit."""

    task = _normalize_task(spec.task)
    unit = _normalize_unit(task, spec.unit)
    engine = _normalize_engine(spec.engine, unit)
    ws = spec.workdir if isinstance(spec.workdir, Workspace) else Workspace(Path(spec.workdir))
    source_ws = _workspace_or_none(spec.source_workdir)

    if engine == "pyatb" or unit == "pyatb":
        if source_ws is None:
            raise ValueError("pyatb unit requires source_workdir")
        from abacus_forge.pyatb import prepare_pyatb_band

        workspace = prepare_pyatb_band(
            ws,
            scf_workspace=source_ws,
            line_kpoints=_normalize_line_kpoints_for_unit(spec.line_kpoints),
            line_segments=spec.line_segments,
            efermi=spec.parameters.get("efermi"),
        )
    else:
        if unit == "nscf" and source_ws is None:
            raise ValueError(f"{task}.{unit} prepare requires source_workdir")
        calculation_task = _calculation_task_for_unit(task, unit)
        structure = spec.structure
        structure_format = spec.structure_format
        if structure is None and source_ws is not None:
            source_structure = _source_structure_path(source_ws)
            if source_structure is not None:
                structure = source_structure
                structure_format = _structure_format_for_path(source_structure)
        workspace = prepare(
            ws,
            structure=structure,
            structure_format=structure_format,
            task=calculation_task,
            parameters=_unit_parameters(task, unit, spec.parameters),
            input_overrides=spec.input_overrides,
            remove_parameters=spec.remove_parameters,
            kpoints=spec.kpoints,
            kpt_mode="line" if task == "band" and unit == "nscf" else "mesh",
            line_kpoints=_normalize_line_kpoints_for_unit(spec.line_kpoints),
            metadata={"unit": unit, **dict(spec.metadata or {})},
            pseudo_path=spec.pseudo_path,
            orbital_path=spec.orbital_path,
            asset_mode=spec.asset_mode,
            ensure_pbc=spec.ensure_pbc,
            structure_standardization=spec.structure_standardization,
            magmom_by_element=spec.magmom_by_element,
        )
        if task == "band" and unit == "nscf":
            if not spec.line_kpoints:
                raise ValueError("band.nscf prepare requires line_kpoints")
            write_kpt_line_mode(
                workspace.inputs_dir / "KPT",
                _normalize_line_kpoints_for_unit(spec.line_kpoints),
                segments=int(spec.line_segments),
            )
        if source_ws is not None:
            _stage_source_out_dirs(source_ws, workspace, link=spec.asset_mode == "link")

    manifest = _unit_manifest(spec, task=task, unit=unit, engine=engine, prepared=True)
    workspace.write_json("forge-unit.json", manifest)
    result = UnitPrepareResult(workspace=workspace, task=task, unit=unit, engine=engine, manifest=manifest)
    if record_event:
        _record_operation_event(workspace, ForgeResultEnvelope(
            operation="prepare", workspace_rel=".",
            status=OperationStatus(execution="not_run", scientific="unassessed", collection="not_collected"),
            artifacts=_manifest_artifact(workspace, "forge-unit.json"),
            diagnostics={"task": task, "unit": unit, "engine": engine},
        ))
    return result


def execute_unit(spec: UnitSpec) -> RunResult:
    """Execute one explicit ABACUS/PyATB task unit without collecting it."""

    unit = _normalize_unit(_normalize_task(spec.task), spec.unit)
    engine = _normalize_engine(spec.engine, unit)
    if engine == "pyatb":
        from abacus_forge.pyatb import run_pyatb

        result = run_pyatb(
            spec.workdir,
            executable=spec.executable or (spec.command[0] if spec.command else "pyatb"),
            omp=spec.omp,
            timeout_seconds=spec.timeout_seconds,
        )
    else:
        command = list(spec.command or [])
        runner = LocalRunner(
            executable=spec.executable or (command[0] if command else "abacus"),
            extra_args=command[1:] if command else (),
            mpi_ranks=spec.mpi,
            omp_threads=spec.omp,
            timeout_seconds=spec.timeout_seconds,
            env_overrides=dict(spec.env_overrides or {}),
        )
        result = execute(spec.workdir, runner=runner)
    _workspace(spec.workdir).write_json(
        "forge-result.json",
        {
            "step": "execute",
            "task": _normalize_task(spec.task),
            "unit": unit,
            "engine": engine,
            "status": result.status,
            "returncode": result.returncode,
            "command": result.command,
        },
    )
    _record_operation_event(_workspace(spec.workdir), result.to_envelope())
    return result


def modify_unit(spec: UnitModifySpec, *, record_event: bool = True) -> UnitModifyResult:
    """Modify prepared workspace inputs for one explicit unit."""

    task = _normalize_task(spec.task)
    unit = _normalize_unit(task, spec.unit)
    engine = _normalize_engine(spec.engine, unit)
    if engine != "abacus":
        raise ValueError("modify_unit currently supports ABACUS workspaces only")
    if spec.layout != "forge":
        raise ValueError("modify_unit currently supports forge layout only")

    ws = _workspace(spec.workdir)
    inputs_dir = ws.inputs_dir
    modified_files: list[str] = []
    changes: dict[str, Any] = {}

    if _input_modification_requested(spec):
        input_path = _require_input_file(inputs_dir / "INPUT", "INPUT")
        modify_input(
            input_path,
            updates=spec.input_updates,
            remove_keys=spec.remove_parameters,
            destination=input_path,
        )
        modified_files.append("INPUT")
        changes["INPUT"] = {
            "updates": dict(spec.input_updates or {}),
            "removed": [str(key) for key in spec.remove_parameters or ()],
        }

    if _kpt_modification_requested(spec):
        kpt_path = _require_input_file(inputs_dir / "KPT", "KPT")
        points = _normalize_line_kpoints_for_unit(spec.line_kpoints) if spec.line_kpoints is not None else None
        modify_kpt(
            kpt_path,
            mode=spec.kpt_mode,
            mesh=spec.mesh,
            shifts=spec.shifts,
            points=points,
            segments=spec.line_segments,
            destination=kpt_path,
        )
        modified_files.append("KPT")
        changes["KPT"] = {
            "mode": spec.kpt_mode,
            "mesh": [int(value) for value in spec.mesh] if spec.mesh is not None else None,
            "shifts": [int(value) for value in spec.shifts] if spec.shifts is not None else None,
            "points": points,
            "segments": spec.line_segments,
        }

    if _structure_modification_requested(spec):
        stru_path = _require_input_file(inputs_dir / "STRU", "STRU")
        modify_stru(
            stru_path,
            supercell=spec.supercell,
            vacancy_indices=spec.vacancy_indices,
            ensure_pbc=spec.ensure_pbc,
            vacuum=spec.vacuum,
            standardization=spec.structure_standardization,
            magmoms=spec.magmoms,
            magmom_by_element=spec.magmom_by_element,
            afm=spec.afm,
            afm_elements=spec.afm_elements,
            destination=stru_path,
        )
        modified_files.append("STRU")
        changes["STRU"] = {
            "magmom_by_element": dict(spec.magmom_by_element or {}),
            "magmoms": [float(value) for value in spec.magmoms] if spec.magmoms is not None else None,
            "afm": bool(spec.afm),
            "afm_elements": [str(value) for value in spec.afm_elements or ()],
            "supercell": [int(value) for value in spec.supercell] if spec.supercell is not None else None,
            "vacancy_indices": [int(value) for value in spec.vacancy_indices or ()],
            "ensure_pbc": bool(spec.ensure_pbc),
            "vacuum": float(spec.vacuum),
            "structure_standardization": spec.structure_standardization,
        }

    result = UnitModifyResult(
        workspace=ws.root,
        task=task,
        unit=unit,
        engine=engine,
        status="completed",
        modified_files=modified_files,
        changes=changes,
    )
    ws.write_json(
        "forge-result.json",
        {
            "step": "modify",
            **result.to_dict(),
        },
    )
    if record_event:
        _record_operation_event(ws, ForgeResultEnvelope(
            operation="modify", workspace_rel=".",
            status=OperationStatus(execution="completed", scientific="unassessed", collection="not_collected"),
            artifacts=tuple(
                ArtifactRecord(id=f"artifact-{name.lower()}", path_rel=f"inputs/{name}", role="input", stage="modify")
                for name in modified_files if (ws.inputs_dir / name).is_file()
            ),
            diagnostics={"task": task, "unit": unit, "engine": engine, "modified_files": modified_files},
        ))
    return result


def collect_unit(spec: UnitSpec) -> CollectionResult:
    """Collect one explicit ABACUS/PyATB task unit without executing it."""

    task = _normalize_task(spec.task)
    unit = _normalize_unit(task, spec.unit)
    engine = _normalize_engine(spec.engine, unit)
    postprocess_diagnostics = _postprocess_unit_before_collect(spec, task=task, unit=unit, engine=engine)
    if engine == "pyatb":
        from abacus_forge.pyatb import collect_pyatb

        result = collect_pyatb(spec.workdir)
    else:
        result = collect(spec.workdir, output_log=spec.output_log, layout=spec.layout)
    if postprocess_diagnostics:
        result.diagnostics["unit_postprocess"] = postprocess_diagnostics
    _workspace(spec.workdir).write_json(
        "forge-result.json",
        {
            "step": "collect",
            "task": task,
            "unit": unit,
            "engine": engine,
            "status": result.status,
            "metrics": result.metrics,
            "artifacts": result.artifacts,
            "diagnostics": result.diagnostics,
        },
    )
    _record_operation_event(_workspace(spec.workdir), result.to_envelope())
    return result


def _manifest_artifact(workspace: Workspace, relative: str) -> tuple[ArtifactRecord, ...]:
    path = workspace.root / relative
    if not path.is_file():
        return ()
    import hashlib
    return (ArtifactRecord(id="provenance_manifest", path_rel=relative, role="provenance_manifest", stage="prepare", sha256=hashlib.sha256(path.read_bytes()).hexdigest(), size_bytes=path.stat().st_size),)


def _record_operation_event(workspace: Workspace, envelope: ForgeResultEnvelope) -> None:
    workspace.append_operation_event(envelope.operation, envelope.to_dict())


def _postprocess_unit_before_collect(spec: UnitSpec, *, task: str, unit: str, engine: str) -> dict[str, Any]:
    if not spec.postprocess:
        return {"status": "skipped", "reason": "postprocess-disabled"}
    if engine == "pyatb" and task == "band" and unit == "pyatb":
        from abacus_forge.unit_postprocess import postprocess_pyatb_band

        return postprocess_pyatb_band(spec.workdir, save_plot=spec.save_plot)
    if engine != "abacus":
        return {}
    if task == "band" and unit == "nscf":
        from abacus_forge.unit_postprocess import postprocess_abacus_band

        return postprocess_abacus_band(
            spec.workdir,
            plot_emin=float(spec.plot_emin),
            plot_emax=float(spec.plot_emax),
            save_plot=bool(spec.save_plot),
            save_data=bool(spec.save_data),
        )
    if task == "dos" and unit in {"nscf", "postprocess"}:
        from abacus_forge.unit_postprocess import postprocess_abacus_dos

        return postprocess_abacus_dos(
            spec.workdir,
            include_tdos=bool(spec.include_tdos),
            include_pdos=bool(spec.include_pdos),
            pdos_mode=spec.pdos_mode,  # type: ignore[arg-type]
            pdos_atom_indices=spec.pdos_atom_indices,
            plot_emin=float(spec.plot_emin),
            plot_emax=float(spec.plot_emax),
            save_plot=bool(spec.save_plot),
            save_data=bool(spec.save_data),
            suffix=spec.suffix,
        )
    return {}


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

    ws = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace))
    normalized_layout = _normalize_layout(ws, layout)
    artifacts = _collect_artifacts(ws, layout=normalized_layout)
    inputs_snapshot = _inputs_snapshot(ws, layout=normalized_layout)
    log_selection = _select_log_sources(ws, artifacts, inputs_snapshot=inputs_snapshot, output_log=output_log, layout=normalized_layout)
    main_log_path = log_selection["main_log_path"]
    output_log_path = log_selection["output_log_path"]
    main_log_text = _read_text_if_exists(main_log_path)
    output_log_text = _read_text_if_exists(output_log_path)
    stderr_path = _stderr_path(ws, layout=normalized_layout)
    structure_snapshot = _structure_snapshot(_input_path(ws, "STRU", layout=normalized_layout))
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
    diagnostics["layout"] = normalized_layout
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


def export(result: RunResult | CollectionResult | TaskResult, destination: str | Path | None = None, *, pretty: bool = True) -> str:
    """Serialize a structured result as JSON and optionally write it to disk."""

    payload = result.to_dict()
    text = json.dumps(payload, indent=2 if pretty else None, sort_keys=True)
    if destination is not None:
        Path(destination).write_text(text + ("\n" if pretty else ""), encoding="utf-8")
    return text


def _workspace(value: str | Path | Workspace) -> Workspace:
    return value if isinstance(value, Workspace) else Workspace(Path(value))


def _workspace_or_none(value: str | Path | Workspace | None) -> Workspace | None:
    if value is None:
        return None
    return _workspace(value)


def _require_input_file(path: Path, name: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"{name} file not found: {path}")
    return path


def _input_modification_requested(spec: UnitModifySpec) -> bool:
    return bool(spec.input_updates) or bool(list(spec.remove_parameters or ()))


def _kpt_modification_requested(spec: UnitModifySpec) -> bool:
    return any(
        value is not None
        for value in (
            spec.kpt_mode,
            spec.mesh,
            spec.shifts,
            spec.line_kpoints,
            spec.line_segments,
        )
    )


def _structure_modification_requested(spec: UnitModifySpec) -> bool:
    return any(
        (
            spec.magmom_by_element,
            spec.magmoms is not None,
            spec.afm,
            spec.afm_elements,
            spec.supercell,
            spec.vacancy_indices,
            spec.ensure_pbc,
            spec.structure_standardization,
        )
    )


def _normalize_task(task: str) -> str:
    normalized = str(task).strip().lower()
    if normalized not in {"scf", "relax", "cell-relax", "md", "band", "dos"}:
        raise ValueError(f"unsupported unit task: {task!r}")
    return normalized


def _normalize_unit(task: str, unit: str | None) -> str:
    normalized = str(unit or "default").strip().lower()
    if normalized == "default":
        return "default" if task not in {"band", "dos"} else ("nscf" if task == "dos" else "scf")
    allowed = {
        "scf": {"default"},
        "relax": {"default"},
        "cell-relax": {"default"},
        "md": {"default"},
        "band": {"scf", "nscf", "pyatb"},
        "dos": {"scf", "nscf", "postprocess"},
    }[task]
    if normalized not in allowed:
        raise ValueError(f"unsupported unit {normalized!r} for task {task!r}")
    return normalized


def _normalize_engine(engine: str, unit: str) -> str:
    normalized = "pyatb" if unit == "pyatb" else str(engine).strip().lower()
    if normalized not in {"abacus", "pyatb"}:
        raise ValueError(f"unsupported unit engine: {engine!r}")
    return normalized


def _calculation_task_for_unit(task: str, unit: str) -> str:
    if unit == "scf":
        return "scf"
    if unit == "nscf":
        return task
    return task


def _unit_parameters(task: str, unit: str, parameters: dict[str, Any]) -> dict[str, Any]:
    payload = dict(parameters or {})
    if unit == "scf" and task in {"band", "dos"}:
        payload.setdefault("out_chg", 1)
    if unit == "nscf" and task == "band":
        payload.setdefault("symmetry", 0)
    if unit == "nscf" and task == "dos":
        payload.setdefault("out_chg", -1)
    return payload


def _normalize_line_kpoints_for_unit(points: Iterable[dict[str, Any] | tuple[Iterable[float], str | None]] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for point in points or []:
        if isinstance(point, dict):
            coords = [float(value) for value in point["coords"]]
            label = point.get("label")
            npoints = point.get("npoints")
        else:
            coords_raw, label = point
            coords = [float(value) for value in coords_raw]
            npoints = None
        payload: dict[str, Any] = {"coords": coords, "label": str(label) if label is not None else None}
        if npoints is not None:
            payload["npoints"] = int(npoints)
        normalized.append(payload)
    return normalized


def _source_structure_path(source: Workspace) -> Path | None:
    for candidate in (
        source.outputs_dir / "OUT.ABACUS" / "STRU_ION_D",
        source.inputs_dir / "OUT.ABACUS" / "STRU_ION_D",
        source.inputs_dir / "STRU",
        source.root / "STRU",
    ):
        if candidate.exists():
            return candidate
    return None


def _structure_format_for_path(path: Path) -> str | None:
    return "stru" if path.name in {"STRU", "STRU_ION_D"} else None


def _stage_source_out_dirs(source: Workspace, destination: Workspace, *, link: bool = False) -> list[str]:
    destination.ensure_layout()
    staged: list[str] = []
    for base in (source.inputs_dir, source.outputs_dir, source.root):
        if not base.exists():
            continue
        for out_dir in sorted(path for path in base.glob("OUT.*") if path.is_dir()):
            target = destination.inputs_dir / out_dir.name
            if target.exists() or target.is_symlink():
                if target.is_dir() and not target.is_symlink():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            if link:
                target.symlink_to(out_dir.resolve(), target_is_directory=True)
            else:
                shutil.copytree(out_dir, target)
            staged.append(str(target))
    return staged


def _unit_manifest(spec: UnitSpec, *, task: str, unit: str, engine: str, prepared: bool) -> dict[str, Any]:
    return {
        "kind": "abacus-forge.unit",
        "task": task,
        "unit": unit,
        "engine": engine,
        "prepared": prepared,
        "source_workdir": str(_workspace(spec.source_workdir).root) if spec.source_workdir is not None else None,
        "metadata": dict(spec.metadata or {}),
    }


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

    fixed_candidates = [candidate for candidate in _fallback_log_paths(workspace, layout=layout) if candidate.exists() and candidate.is_file()]
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


def _inputs_snapshot(workspace: Workspace, *, layout: str = "forge") -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    input_path = _input_path(workspace, "INPUT", layout=layout)
    if input_path.exists():
        snapshot["INPUT"] = read_input(input_path)
    kpt_path = _input_path(workspace, "KPT", layout=layout)
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
