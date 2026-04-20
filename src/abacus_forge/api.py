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

    metrics: dict[str, float | bool | str] = {}
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
