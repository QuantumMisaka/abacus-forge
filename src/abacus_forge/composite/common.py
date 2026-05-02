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
    stru_path = root.inputs_dir / "STRU"
    if not input_path.exists() or not stru_path.exists():
        raise FileNotFoundError("composite prepare requires an existing Forge workspace with inputs/INPUT and inputs/STRU")
    kpt_payload = None
    kpt_path = root.inputs_dir / "KPT"
    if kpt_path.exists():
        kpt_payload = read_kpt(kpt_path)
    return read_input(input_path), AbacusStructure.from_input(stru_path, structure_format="stru"), kpt_payload


def write_subtask(
    root: Workspace,
    relative: str,
    *,
    input_params: dict[str, Any],
    structure: AbacusStructure,
    kpt_payload: dict[str, Any] | None,
    metadata: dict[str, Any],
) -> Workspace:
    sub = Workspace(root.root / relative)
    sub.ensure_layout()
    write_input(sub.inputs_dir / "INPUT", input_params)
    sub.write_text("inputs/STRU", structure.to_stru())
    if kpt_payload is not None:
        write_kpt(sub.inputs_dir / "KPT", kpt_payload)
    _copy_auxiliary_inputs(root.inputs_dir, sub.inputs_dir)
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
    atoms.set_cell(np.dot(np.eye(3) + strain, cell), scale_atoms=True)
    return AbacusStructure(atoms, source_format=structure.source_format)


def displaced_structure(structure: AbacusStructure, atom_index: int, axis: int, delta: float) -> AbacusStructure:
    atoms = structure.atoms.copy()
    positions = atoms.get_positions()
    positions[atom_index, axis] += float(delta)
    atoms.set_positions(positions)
    return AbacusStructure(atoms, source_format=structure.source_format)


def _copy_auxiliary_inputs(source: Path, target: Path) -> None:
    for path in source.iterdir():
        if path.name in {"INPUT", "STRU", "KPT"}:
            continue
        destination = target / path.name
        if path.is_file():
            shutil.copyfile(path, destination)
        elif path.is_dir():
            shutil.copytree(path, destination, dirs_exist_ok=True)
