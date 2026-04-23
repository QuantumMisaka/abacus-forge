"""Thin prepare/run/collect/export primitives."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Iterable

from abacus_forge.result import CollectionResult, RunResult
from abacus_forge.runner import LocalRunner
from abacus_forge.workspace import Workspace

_METRIC_PATTERNS = {
    "total_energy": re.compile(r"TOTAL\s+ENERGY\s*=\s*([-+]?\d+(?:\.\d+)?)", re.IGNORECASE),
    "fermi_energy": re.compile(r"FERMI\s+ENERGY\s*=\s*([-+]?\d+(?:\.\d+)?)", re.IGNORECASE),
    "band_gap": re.compile(r"BAND\s+GAP\s*=\s*([-+]?\d+(?:\.\d+)?)", re.IGNORECASE),
}


def prepare(
    workspace: str | Path | Workspace,
    *,
    structure: str | Path | None = None,
    parameters: dict[str, Any] | None = None,
    kpoints: Iterable[int] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Workspace:
    """Create a minimal run workspace with canonical input files."""

    ws = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace))
    ws.ensure_layout()

    if structure is not None:
        source = Path(structure)
        shutil.copyfile(source, ws.inputs_dir / "STRU")

    params = parameters or {}
    lines = ["INPUT_PARAMETERS"]
    lines.extend(f"{key} {value}" for key, value in sorted(params.items()))
    ws.write_text("inputs/INPUT", "\n".join(lines) + "\n")

    mesh = list(kpoints or [1, 1, 1])
    ws.write_text(
        "inputs/KPT",
        f"K_POINTS\n0\nGamma\n{' '.join(str(value) for value in mesh)} 0 0 0\n",
    )

    ws.record_metadata(
        {
            "kind": "abacus-forge.workspace",
            "structure": str(Path(structure)) if structure is not None else None,
            "parameters": params,
            "kpoints": mesh,
            "metadata": metadata or {},
        }
    )
    return ws


def run(workspace: str | Path | Workspace, *, runner: LocalRunner | None = None, check: bool = False) -> RunResult:
    """Execute one prepared workspace with a local runner."""

    ws = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace))
    return (runner or LocalRunner()).run(ws, check=check)


def collect(workspace: str | Path | Workspace) -> CollectionResult:
    """Parse basic metrics and artifacts from one workspace."""

    ws = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace))
    stdout_path = ws.outputs_dir / "stdout.log"
    stderr_path = ws.outputs_dir / "stderr.log"
    content = stdout_path.read_text(encoding="utf-8") if stdout_path.exists() else ""

    metrics: dict[str, Any] = {}
    for key, pattern in _METRIC_PATTERNS.items():
        match = pattern.search(content)
        if match:
            metrics[key] = float(match.group(1))

    lowered = content.lower()
    metrics["converged"] = "converged" in lowered

    status = "completed"
    if stderr_path.exists() and stderr_path.read_text(encoding="utf-8").strip():
        status = "failed"
    elif not content:
        status = "missing-output"
    elif not metrics["converged"]:
        status = "unfinished"

    artifacts = _collect_artifacts(ws)
    metrics.update(_collect_task_summaries(ws, artifacts, metrics))
    return CollectionResult(workspace=ws.root, status=status, metrics=metrics, artifacts=artifacts)


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


def _artifact_path(artifacts: dict[str, str], suffix: str) -> Path | None:
    for relative, path in artifacts.items():
        if relative.endswith(suffix):
            return Path(path)
    return None


def _read_numeric_table(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            rows.append([float(token) for token in stripped.split()])
        except ValueError:
            continue
    return rows


def _collect_task_summaries(
    workspace: Workspace,
    artifacts: dict[str, str],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    summaries: dict[str, Any] = {}

    band_file = _artifact_path(artifacts, "BANDS_1.dat")
    if band_file is not None and band_file.exists():
        rows = _read_numeric_table(band_file)
        summaries["band_summary"] = {
            "band_file": str(band_file),
            "num_kpoints": len(rows),
            "num_columns": len(rows[0]) if rows else 0,
            "band_gap": metrics.get("band_gap"),
        }
    metrics_band_path = _artifact_path(artifacts, "metrics_band.json")
    if metrics_band_path is not None and metrics_band_path.exists():
        summaries["band_metrics"] = json.loads(metrics_band_path.read_text(encoding="utf-8"))

    dos1_file = _artifact_path(artifacts, "DOS1_smearing.dat")
    dos2_file = _artifact_path(artifacts, "DOS2_smearing.dat")
    if dos1_file is not None or dos2_file is not None:
        dos_files = [path for path in (dos1_file, dos2_file) if path is not None and path.exists()]
        energies: list[float] = []
        for path in dos_files:
            for row in _read_numeric_table(path):
                if row:
                    energies.append(row[0])
        summaries["dos_summary"] = {
            "dos_files": [str(path) for path in dos_files],
            "points": sum(len(_read_numeric_table(path)) for path in dos_files),
            "energy_min": min(energies) if energies else None,
            "energy_max": max(energies) if energies else None,
        }
    metrics_dos_path = _artifact_path(artifacts, "metrics_dos.json")
    if metrics_dos_path is not None and metrics_dos_path.exists():
        summaries["dos_metrics"] = json.loads(metrics_dos_path.read_text(encoding="utf-8"))

    pdos_file = _artifact_path(artifacts, "PDOS")
    tdos_file = _artifact_path(artifacts, "TDOS")
    if pdos_file is not None or tdos_file is not None:
        summaries["pdos_summary"] = {
            "pdos_file": str(pdos_file) if pdos_file is not None and pdos_file.exists() else None,
            "tdos_file": str(tdos_file) if tdos_file is not None and tdos_file.exists() else None,
        }
    metrics_pdos_path = _artifact_path(artifacts, "metrics_pdos.json")
    if metrics_pdos_path is not None and metrics_pdos_path.exists():
        summaries["pdos_metrics"] = json.loads(metrics_pdos_path.read_text(encoding="utf-8"))

    if summaries:
        summaries["workspace"] = str(workspace.root)
    return summaries
