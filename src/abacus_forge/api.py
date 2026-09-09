"""Prepare/run/collect/export primitives for ABACUS workspaces."""

from __future__ import annotations

import json
import shutil
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from ase import Atoms

from abacus_forge.contracts import ArtifactRecord, ForgeResultEnvelope, OperationStatus
from abacus_forge.input_io import write_kpt_line_mode
from abacus_forge.preparation import prepare as _prepare
from abacus_forge.collection import collect as _collect
from abacus_forge.compatibility_records import unit_manifest, modification_record
from abacus_forge.modify import modify_input, modify_kpt, modify_stru
from abacus_forge.result import CollectionResult, RunResult, TaskResult
from abacus_forge.runner import LocalRunner
from abacus_forge.structure import AbacusStructure
from abacus_forge.workspace import Workspace


_SUPPRESS_LEGACY_EVENTS: ContextVar[bool] = ContextVar("suppress_legacy_events", default=False)


@contextmanager
def suppress_legacy_events():
    token = _SUPPRESS_LEGACY_EVENTS.set(True)
    try:
        yield
    finally:
        _SUPPRESS_LEGACY_EVENTS.reset(token)


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
        return modification_record(
            workspace=self.workspace, task=self.task, unit=self.unit,
            engine=self.engine, status=self.status,
            modified_files=self.modified_files, changes=self.changes,
        )


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

    return _prepare(
        workspace,
        structure=structure,
        structure_format=structure_format,
        task=task,
        parameters=parameters,
        input_overrides=input_overrides,
        remove_parameters=remove_parameters,
        kpoints=kpoints,
        kpt_mode=kpt_mode,
        line_kpoints=line_kpoints,
        metadata=metadata,
        pseudo_path=pseudo_path,
        orbital_path=orbital_path,
        asset_mode=asset_mode,
        ensure_pbc=ensure_pbc,
        structure_standardization=structure_standardization,
        magmom_by_element=magmom_by_element,
    )


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


def prepare_unit(spec: UnitSpec) -> UnitPrepareResult:
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
    if not _SUPPRESS_LEGACY_EVENTS.get():
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


def modify_unit(spec: UnitModifySpec) -> UnitModifyResult:
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
    if not _SUPPRESS_LEGACY_EVENTS.get():
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


def collect(
    workspace: str | Path | Workspace,
    *,
    output_log: str | Path | None = None,
    layout: str = "forge",
) -> CollectionResult:
    """Parse workspace outputs; relative output_log paths use its root."""
    return _collect(workspace, output_log=output_log, layout=layout)



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
    return unit_manifest(
        task=task, unit=unit, engine=engine, prepared=prepared,
        source_workdir=_workspace(spec.source_workdir).root if spec.source_workdir is not None else None,
        metadata=spec.metadata,
    )
