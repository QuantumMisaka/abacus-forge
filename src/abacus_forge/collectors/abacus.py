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
_KBAR_TO_EV_PER_ANGSTROM3 = 3.398927420868445e-6 * 27.211396132 / 0.52917721092**3
_KS_SOLVER_LIST = {"DA", "DS", "GE", "GV", "BP", "CG", "CU", "PE", "LA"}

_METRIC_PATTERNS = {
    "total_energy": re.compile(r"TOTAL\s+ENERGY\s*=\s*([-+]?\d+(?:\.\d+)?)", re.IGNORECASE),
    "fermi_energy": re.compile(r"FERMI\s+ENERGY\s*=\s*([-+]?\d+(?:\.\d+)?)", re.IGNORECASE),
    "band_gap": re.compile(r"BAND\s+GAP\s*=\s*([-+]?\d+(?:\.\d+)?)", re.IGNORECASE),
    "pressure": re.compile(r"PRESSURE\s*=\s*([-+]?\d+(?:\.\d+)?)", re.IGNORECASE),
    "scf_steps": re.compile(r"SCF\s+STEPS?\s*=\s*(\d+)", re.IGNORECASE),
}

_POSITIVE_CONVERGENCE_PATTERNS = {
    "scf_converged": re.compile(r"\bSCF\s+CONVERGED\b", re.IGNORECASE),
    "charge_density_converged": re.compile(r"charge density convergence is achieved", re.IGNORECASE),
}

_NEGATIVE_CONVERGENCE_PATTERNS = {
    "scf_not_converged": re.compile(r"\bSCF\s+NOT\s+CONVERGED\b", re.IGNORECASE),
    "not_converged": re.compile(r"\bnot\s+converged\b", re.IGNORECASE),
}


def _regex_metrics(content: str) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for key, pattern in _METRIC_PATTERNS.items():
        match = pattern.search(content)
        if not match:
            continue
        value = match.group(1)
        metrics[key] = int(value) if key == "scf_steps" else float(value)
    positive_matches, negative_matches = _collect_convergence_matches(content)
    metrics["converged"] = bool(positive_matches) and not negative_matches
    return metrics


_REGISTRY.register(_regex_metrics)


def collect_abacus_metrics(
    *,
    main_log_text: str | None,
    output_log_text: str | None,
    artifacts: dict[str, str],
    workspace_root: Path,
    structure_volume: float | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Collect metrics and diagnostics from logs and artifacts."""

    main_content = main_log_text or ""
    output_content = output_log_text or ""
    metrics = _REGISTRY.extract(main_content)
    positive_matches, negative_matches = _collect_convergence_matches(main_content)
    diagnostics: dict[str, Any] = {
        "log_sources": len([blob for blob in (main_log_text, output_log_text) if blob]),
        "matched_converged_markers": positive_matches,
        "matched_nonconverged_markers": negative_matches,
        "warnings": [],
        "report_json_absent": [],
    }
    force_metrics = _force_metrics(main_content)
    stress_metrics = _stress_metrics(main_content, volume=structure_volume)
    metrics.update(force_metrics)
    metrics.update(stress_metrics)
    output_metrics = _output_metrics(output_content)
    for key, value in output_metrics.items():
        metrics.setdefault(key, value)
    if structure_volume is not None:
        diagnostics["structure_volume"] = structure_volume
    if not positive_matches:
        diagnostics["warnings"].append("No explicit convergence marker found in logs.")
    if negative_matches:
        diagnostics["warnings"].append("Detected non-converged marker in logs.")
    if output_log_text is None:
        diagnostics["warnings"].append("No stdout-like output log selected.")

    time_path = _artifact_path(artifacts, "time.json")
    if time_path and time_path.exists():
        try:
            payload = json.loads(time_path.read_text(encoding="utf-8"))
            metrics["total_time"] = payload.get("total")
            diagnostics["time_json"] = str(time_path)
        except Exception:
            diagnostics["time_json_error"] = str(time_path)
            diagnostics["warnings"].append("Failed to parse time.json.")
        diagnostics["time_json_absent"] = False
    else:
        diagnostics["time_json_absent"] = True
        diagnostics["warnings"].append("time.json is absent.")

    band_files = _artifact_paths_matching(artifacts, "BANDS_", ".dat")
    diagnostics["band_artifact_candidates"] = [str(path) for path in band_files]
    diagnostics["band_artifact_selection_ambiguous"] = len(band_files) > 1
    if band_files:
        metrics["band_summary"] = BandData.from_paths(band_files).summary()
        metrics["band_artifacts"] = [str(path) for path in band_files]
        diagnostics["band_canonical_artifact"] = str(band_files[0])
    band_metrics = _load_json_artifact(artifacts, "metrics_band.json", diagnostics=diagnostics)
    if band_metrics is not None:
        metrics["band_metrics"] = band_metrics

    dos_files = _artifact_paths_matching(artifacts, "DOS", "_smearing.dat")
    diagnostics["dos_artifact_candidates"] = [str(path) for path in dos_files]
    diagnostics["dos_artifact_selection_ambiguous"] = len(dos_files) > 1
    if dos_files:
        metrics["dos_summary"] = DOSData.from_paths(dos_files).summary()
        metrics["dos_artifacts"] = [str(path) for path in dos_files]
        diagnostics["dos_canonical_artifact"] = str(dos_files[0])
    dos_metrics = _load_json_artifact(artifacts, "metrics_dos.json", diagnostics=diagnostics)
    if dos_metrics is not None:
        metrics["dos_metrics"] = dos_metrics

    pdos_file = _artifact_path(artifacts, "PDOS")
    tdos_file = _artifact_path(artifacts, "TDOS")
    diagnostics["pdos_artifact_candidates"] = [
        str(path)
        for path in (pdos_file, tdos_file)
        if path is not None
    ]
    if pdos_file or tdos_file:
        metrics["pdos_summary"] = PDOSData(pdos_path=pdos_file, tdos_path=tdos_file).summary()
        metrics["pdos_artifacts"] = [str(path) for path in (pdos_file, tdos_file) if path is not None]
        diagnostics["pdos_canonical_artifact"] = str(pdos_file or tdos_file)
    pdos_metrics = _load_json_artifact(artifacts, "metrics_pdos.json", diagnostics=diagnostics)
    if pdos_metrics is not None:
        metrics["pdos_metrics"] = pdos_metrics

    relax_metrics = _load_json_artifact(artifacts, "metrics_relax.json", diagnostics=diagnostics)
    if relax_metrics is not None:
        metrics["relax_metrics"] = relax_metrics
        metrics["relax_summary"] = {
            "converged": bool(relax_metrics.get("converged", metrics.get("converged", False))),
            "final_structure_available": bool(relax_metrics.get("final_structure_available", False)),
            "report_path": next(
                (
                    path
                    for path in diagnostics.get("report_json_files", [])
                    if path.endswith("metrics_relax.json")
                ),
                None,
            ),
        }

    workflow_goal = _workflow_goal(metrics)
    if workflow_goal is not None:
        metrics["workflow_goal"] = workflow_goal

    if not diagnostics["report_json_files"] if "report_json_files" in diagnostics else True:
        diagnostics["warnings"].append("No report JSON artifacts found.")
    diagnostics["workspace"] = str(workspace_root)
    return metrics, diagnostics


def _force_metrics(content: str) -> dict[str, Any]:
    forces: list[list[float]] = []
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if "TOTAL-FORCE (eV/Angstrom)" not in line:
            continue
        values = _parse_force_block(lines, start=index + 1)
        if values:
            forces.append(values)
    if not forces:
        return {}
    return {
        "force": forces[-1],
        "forces": forces,
    }


def _stress_metrics(content: str, *, volume: float | None) -> dict[str, Any]:
    stresses: list[list[float]] = []
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if "TOTAL-STRESS (KBAR)" not in line:
            continue
        values = _parse_stress_block(lines, start=index + 1)
        if values:
            stresses.append(values)
    if not stresses:
        return {}

    pressures = [(stress[0] + stress[4] + stress[8]) / 3.0 for stress in stresses]
    metrics: dict[str, Any] = {
        "stress": stresses[-1],
        "stresses": stresses,
        "pressure": pressures[-1],
        "pressures": pressures,
    }
    if volume is not None:
        virials = [[value * volume * _KBAR_TO_EV_PER_ANGSTROM3 for value in stress] for stress in stresses]
        metrics["virial"] = virials[-1]
        metrics["virials"] = virials
    return metrics


def _output_metrics(content: str) -> dict[str, Any]:
    if not content.strip():
        return {}

    lines = content.splitlines()
    metrics: dict[str, Any] = {}
    for line in lines:
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "total":
            try:
                metrics["total_time"] = float(parts[1])
            except ValueError:
                pass
        elif len(parts) >= 6 and parts[0] == "cal_stress":
            try:
                metrics["stress_time"] = float(parts[-5])
            except ValueError:
                pass
        elif len(parts) >= 6 and parts[0] == "cal_force_nl":
            try:
                metrics["force_time"] = float(parts[-5])
            except ValueError:
                pass
        elif len(parts) >= 6 and parts[0] == "getForceStress":
            try:
                metrics["stress_time"] = float(parts[-5])
            except ValueError:
                pass

    denergy = _parse_output_denergy(lines)
    if denergy:
        metrics["denergy"] = denergy
        metrics["denergy_last"] = denergy[-1]

    scf_time_each_step = _parse_output_scf_times(lines)
    if scf_time_each_step:
        metrics["scf_time_each_step"] = scf_time_each_step
        metrics["scf_time"] = sum(scf_time_each_step)
        metrics["step1_time"] = scf_time_each_step[0]
        metrics.setdefault("scf_steps", len(scf_time_each_step))

    return metrics


def _parse_output_denergy(lines: list[str]) -> list[float]:
    for index, line in enumerate(lines):
        header = line.split()
        if "ITER" not in header or "EDIFF/eV" not in header:
            continue
        ncol = len(header)
        ediff_idx = header.index("EDIFF/eV")
        values: list[float] = []
        for row in lines[index + 1 :]:
            if "----------------------------" in row:
                break
            parts = row.split()
            if not parts or len(parts) != ncol:
                continue
            solver_tag = parts[1] if len(parts) > 1 else ""
            if solver_tag not in _KS_SOLVER_LIST:
                continue
            try:
                values.append(float(parts[ediff_idx]))
            except ValueError:
                continue
        if values:
            return values
    return []


def _parse_output_scf_times(lines: list[str]) -> list[float]:
    scf_times: list[float] = []
    for index, line in enumerate(lines):
        if "ITER" not in line:
            continue
        for row in lines[index + 1 :]:
            if row.startswith(" -----------------------------------"):
                break
            parts = row.split()
            if not parts:
                continue
            solver_tag = None
            if parts[0] in _KS_SOLVER_LIST:
                solver_tag = parts[0]
            elif len(parts) > 1 and parts[1] in _KS_SOLVER_LIST:
                solver_tag = parts[1]
            if solver_tag is None:
                continue
            try:
                scf_times.append(float(parts[-1]))
            except ValueError:
                continue
        if scf_times:
            break
    return scf_times


def _parse_force_block(lines: list[str], *, start: int) -> list[float]:
    pattern = re.compile(
        r"^\s*[A-Z][A-Za-z]?\d+\s+"
        r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+"
        r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+"
        r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*$"
    )
    values: list[float] = []
    seen_first_row = False
    for line in lines[start:]:
        match = pattern.match(line)
        if match:
            seen_first_row = True
            values.extend(float(match.group(idx)) for idx in range(1, 4))
            continue
        if seen_first_row:
            break
    return values


def _parse_stress_block(lines: list[str], *, start: int) -> list[float]:
    pattern = re.compile(
        r"^\s*"
        r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+"
        r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+"
        r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*$"
    )
    values: list[float] = []
    seen_first_row = False
    for line in lines[start:]:
        match = pattern.match(line)
        if match:
            seen_first_row = True
            values.extend(float(match.group(idx)) for idx in range(1, 4))
            continue
        if seen_first_row:
            break
    return values


def _artifact_path(artifacts: dict[str, str], suffix: str) -> Path | None:
    candidates: list[tuple[str, Path]] = []
    for relative, path in artifacts.items():
        if relative.endswith(suffix):
            candidates.append((relative, Path(path)))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0].count("/"), item[0]))
    return candidates[0][1]


def _artifact_paths_matching(artifacts: dict[str, str], contains: str, suffix: str) -> list[Path]:
    matches: list[tuple[str, Path]] = []
    for relative, path in artifacts.items():
        normalized = relative.replace("\\", "/")
        if "/aiida/" in normalized:
            continue
        if contains in Path(relative).name and relative.endswith(suffix):
            matches.append((relative, Path(path)))

    selected: dict[str, tuple[str, Path]] = {}
    for relative, path in sorted(matches, key=lambda item: (Path(item[0]).name, item[0].count("/"), item[0])):
        basename = Path(relative).name
        selected.setdefault(basename, (relative, path))
    return [path for _, path in sorted(selected.values(), key=lambda item: item[0])]


def _load_json_artifact(
    artifacts: dict[str, str],
    suffix: str,
    *,
    diagnostics: dict[str, Any],
) -> dict[str, Any] | None:
    path = _artifact_path(artifacts, suffix)
    if path is None or not path.exists():
        diagnostics.setdefault("report_json_absent", []).append(suffix)
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        diagnostics.setdefault("report_json_errors", []).append(str(path))
        return None
    diagnostics.setdefault("report_json_files", []).append(str(path))
    return payload if isinstance(payload, dict) else {"value": payload}


def _collect_convergence_matches(content: str) -> tuple[list[str], list[str]]:
    positive_matches = [
        name
        for name, pattern in _POSITIVE_CONVERGENCE_PATTERNS.items()
        if pattern.search(content)
    ]
    negative_matches = [
        name
        for name, pattern in _NEGATIVE_CONVERGENCE_PATTERNS.items()
        if pattern.search(content)
    ]
    return positive_matches, negative_matches


def _workflow_goal(metrics: dict[str, Any]) -> str | None:
    for key in ("band_metrics", "dos_metrics", "pdos_metrics", "relax_metrics"):
        payload = metrics.get(key)
        if isinstance(payload, dict) and payload.get("workflow_goal"):
            return str(payload["workflow_goal"])
    return None
