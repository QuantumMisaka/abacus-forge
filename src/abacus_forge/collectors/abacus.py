"""ABACUS-oriented metric extraction."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from abacus_forge.band_data import BandData
from abacus_forge.collectors.registry import MetricRegistry
from abacus_forge.dos_data import DOSData, PDOSData

_REGISTRY = MetricRegistry()

_METRIC_PATTERNS = {
    "total_energy": re.compile(r"TOTAL\s+ENERGY\s*=\s*([-+]?\d+(?:\.\d+)?)", re.IGNORECASE),
    "fermi_energy": re.compile(r"FERMI\s+ENERGY\s*=\s*([-+]?\d+(?:\.\d+)?)", re.IGNORECASE),
    "band_gap": re.compile(r"BAND\s+GAP\s*=\s*([-+]?\d+(?:\.\d+)?)", re.IGNORECASE),
    "pressure": re.compile(r"PRESSURE\s*=\s*([-+]?\d+(?:\.\d+)?)", re.IGNORECASE),
    "scf_steps": re.compile(r"SCF\s+STEPS?\s*=\s*(\d+)", re.IGNORECASE),
}


def _regex_metrics(content: str) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for key, pattern in _METRIC_PATTERNS.items():
        match = pattern.search(content)
        if not match:
            continue
        value = match.group(1)
        metrics[key] = int(value) if key == "scf_steps" else float(value)
    lowered = content.lower()
    metrics["converged"] = "converged" in lowered and "not converged" not in lowered
    return metrics


_REGISTRY.register(_regex_metrics)


def collect_abacus_metrics(
    *,
    text_blobs: list[str],
    artifacts: dict[str, str],
    workspace_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Collect metrics and diagnostics from logs and artifacts."""

    combined = "\n".join(blob for blob in text_blobs if blob)
    metrics = _REGISTRY.extract(combined)
    diagnostics: dict[str, Any] = {"log_sources": len([blob for blob in text_blobs if blob])}

    time_path = _artifact_path(artifacts, "time.json")
    if time_path and time_path.exists():
        try:
            payload = json.loads(time_path.read_text(encoding="utf-8"))
            metrics["total_time"] = payload.get("total")
            diagnostics["time_json"] = str(time_path)
        except Exception:
            diagnostics["time_json_error"] = str(time_path)

    band_files = _artifact_paths_matching(artifacts, "BANDS_", ".dat")
    if band_files:
        metrics["band_summary"] = BandData.from_paths(band_files).summary()
        metrics["band_artifacts"] = [str(path) for path in band_files]
    band_metrics = _load_json_artifact(artifacts, "metrics_band.json", diagnostics=diagnostics)
    if band_metrics is not None:
        metrics["band_metrics"] = band_metrics

    dos_files = _artifact_paths_matching(artifacts, "DOS", "_smearing.dat")
    if dos_files:
        metrics["dos_summary"] = DOSData.from_paths(dos_files).summary()
        metrics["dos_artifacts"] = [str(path) for path in dos_files]
    dos_metrics = _load_json_artifact(artifacts, "metrics_dos.json", diagnostics=diagnostics)
    if dos_metrics is not None:
        metrics["dos_metrics"] = dos_metrics

    pdos_file = _artifact_path(artifacts, "PDOS")
    tdos_file = _artifact_path(artifacts, "TDOS")
    if pdos_file or tdos_file:
        metrics["pdos_summary"] = PDOSData(pdos_path=pdos_file, tdos_path=tdos_file).summary()
        metrics["pdos_artifacts"] = [str(path) for path in (pdos_file, tdos_file) if path is not None]
    pdos_metrics = _load_json_artifact(artifacts, "metrics_pdos.json", diagnostics=diagnostics)
    if pdos_metrics is not None:
        metrics["pdos_metrics"] = pdos_metrics

    relax_metrics = _load_json_artifact(artifacts, "metrics_relax.json", diagnostics=diagnostics)
    if relax_metrics is not None:
        metrics["relax_metrics"] = relax_metrics

    workflow_goal = _workflow_goal(metrics)
    if workflow_goal is not None:
        metrics["workflow_goal"] = workflow_goal

    diagnostics["workspace"] = str(workspace_root)
    return metrics, diagnostics


def _artifact_path(artifacts: dict[str, str], suffix: str) -> Path | None:
    for relative, path in artifacts.items():
        if relative.endswith(suffix):
            return Path(path)
    return None


def _artifact_paths_matching(artifacts: dict[str, str], contains: str, suffix: str) -> list[Path]:
    matches: list[Path] = []
    for relative, path in artifacts.items():
        normalized = relative.replace("\\", "/")
        if "/aiida/" in normalized:
            continue
        if contains in Path(relative).name and relative.endswith(suffix):
            matches.append(Path(path))
    return sorted(matches)


def _load_json_artifact(
    artifacts: dict[str, str],
    suffix: str,
    *,
    diagnostics: dict[str, Any],
) -> dict[str, Any] | None:
    path = _artifact_path(artifacts, suffix)
    if path is None or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        diagnostics.setdefault("report_json_errors", []).append(str(path))
        return None
    diagnostics.setdefault("report_json_files", []).append(str(path))
    return payload if isinstance(payload, dict) else {"value": payload}


def _workflow_goal(metrics: dict[str, Any]) -> str | None:
    for key in ("band_metrics", "dos_metrics", "pdos_metrics", "relax_metrics"):
        payload = metrics.get(key)
        if isinstance(payload, dict) and payload.get("workflow_goal"):
            return str(payload["workflow_goal"])
    return None
