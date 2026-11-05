"""Shared helpers for local composite task packs."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from abacus_forge.api import collect
from abacus_forge.input_io import read_input, read_kpt, write_input, write_kpt
from abacus_forge.result import TaskResult
from abacus_forge.runner import LocalRunner, run_many
from abacus_forge.structure import AbacusStructure
from abacus_forge.workspace import Workspace


def ensure_root(workspace: str | Path | Workspace) -> Workspace:
    ws = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace))
    ws.root.mkdir(parents=True, exist_ok=True)
    return ws


def require_prepared_inputs(root: Workspace) -> tuple[dict[str, str], AbacusStructure, dict[str, Any] | None]:
    input_path = root.inputs_dir / "INPUT"
    if not input_path.is_file():
        raise FileNotFoundError("composite prepare requires inputs/INPUT")
    parameters = read_input(input_path)
    stru_path = root.resolve_relative(Path("inputs") / parameters.get("stru_file", "STRU"))
    if not stru_path.is_file():
        raise FileNotFoundError("composite prepare requires the structure selected by inputs/INPUT")
    kpt_payload = None
    kpt_path = root.resolve_relative(Path("inputs") / parameters.get("kpoint_file", "KPT"))
    if kpt_path.exists():
        kpt_payload = read_kpt(kpt_path)
    return parameters, AbacusStructure.from_input(stru_path, structure_format="stru"), kpt_payload


def write_subtask(
    root: Workspace,
    relative: str,
    *,
    input_params: dict[str, Any],
    structure: AbacusStructure,
    kpt_payload: dict[str, Any] | None,
    metadata: dict[str, Any],
    copy_reference_outputs: bool = True,
) -> Workspace:
    sub = Workspace(root.root / relative)
    sub.ensure_layout()
    # Generated units use their own STRU, not a copied parent selector which
    # would silently make every displacement/strain run the reference input.
    parameters = {key: value for key, value in input_params.items() if key not in {"stru_file", "kpoint_file"}}
    write_input(sub.inputs_dir / "INPUT", parameters)
    sub.write_text("inputs/STRU", structure.to_stru())
    if kpt_payload is not None:
        write_kpt(sub.inputs_dir / "KPT", kpt_payload)
    _copy_auxiliary_inputs(root.inputs_dir, sub.inputs_dir, copy_reference_outputs=copy_reference_outputs)
    sub.record_metadata({"kind": "abacus-forge.composite-subtask", **metadata})
    return sub


def run_subtasks(
    task: str,
    root: Workspace,
    subtasks: Iterable[str | Path | Workspace],
    *,
    executable: str = "abacus",
    mpi: int = 1,
    omp: int = 1,
    timeout_seconds: float | None = None,
    max_workers: int = 1,
    skip_completed: bool = True,
) -> TaskResult:
    runner = LocalRunner(executable=executable, mpi_ranks=mpi, omp_threads=omp, timeout_seconds=timeout_seconds)
    results = run_many(list(subtasks), runner=runner, max_workers=max_workers, skip_completed=skip_completed)
    status = "completed" if all(result.status in {"completed", "skipped"} for result in results) else "failed"
    return TaskResult(
        task=task,
        workspace=root.root,
        status=status,
        subtasks=[result.to_dict() for result in results],
        summary={
            "total": len(results),
            "completed": sum(1 for result in results if result.status == "completed"),
            "skipped": sum(1 for result in results if result.status == "skipped"),
            "failed": sum(1 for result in results if result.status == "failed"),
        },
        diagnostics={"skip_completed": skip_completed, "max_workers": max_workers},
    )


def collect_subtasks(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        result = collect(Workspace(path))
        rows.append(
            {
                "workspace": str(path),
                "status": result.status,
                "metrics": result.metrics,
                "diagnostics": result.diagnostics,
            }
        )
    return rows


def write_task_result(root: Workspace, relative_path: str, payload: dict[str, Any]) -> Path:
    return root.write_json(relative_path, payload)


def artifacts_under(root: Workspace, relative: str) -> dict[str, str]:
    base = root.root / relative
    artifacts: dict[str, str] = {}
    if not base.exists():
        return artifacts
    for path in sorted(base.rglob("*")):
        if path.is_file():
            artifacts[str(path.relative_to(root.root))] = str(path)
    return artifacts


def scaled_structure(structure: AbacusStructure, volume_scale: float) -> AbacusStructure:
    atoms = structure.atoms.copy()
    atoms.set_cell(np.asarray(atoms.cell) * float(volume_scale) ** (1.0 / 3.0), scale_atoms=True)
    return AbacusStructure(atoms, source_format=structure.source_format)


def strained_structure(structure: AbacusStructure, strain: np.ndarray) -> AbacusStructure:
    atoms = structure.atoms.copy()
    cell = np.asarray(atoms.cell)
    # ASE stores lattice vectors as rows. A Cartesian deformation F acts as
    # cell @ F.T; left multiplication instead mixes lattice vectors and gives
    # the wrong shear for unequal or oblique lattice vectors.
    atoms.set_cell(np.dot(cell, (np.eye(3) + strain).T), scale_atoms=True)
    return AbacusStructure(atoms, source_format=structure.source_format)


def displaced_structure(structure: AbacusStructure, atom_index: int, axis: int, delta: float) -> AbacusStructure:
    atoms = structure.atoms.copy()
    positions = atoms.get_positions()
    positions[atom_index, axis] += float(delta)
    atoms.set_positions(positions)
    return AbacusStructure(atoms, source_format=structure.source_format)


def _copy_auxiliary_inputs(source: Path, target: Path, *, copy_reference_outputs: bool = True) -> None:
    for path in source.iterdir():
        if path.name in {"INPUT", "STRU", "KPT"}:
            continue
        # Displaced/strained units opt out of inherited reference results.
        # Legacy property packs still copy outputs used as restart inputs.
        if not copy_reference_outputs and (path.name.startswith("OUT.") or path.name in {"stdout.log", "stderr.log"}):
            continue
        destination = target / path.name
        if path.is_file():
            shutil.copyfile(path, destination)
        elif path.is_dir():
            shutil.copytree(path, destination, dirs_exist_ok=True)
