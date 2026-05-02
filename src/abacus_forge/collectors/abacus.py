"""ABACUS-oriented metric extraction."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from abacus_forge.band_data import BandData
from abacus_forge.collectors.registry import MetricRegistry
from abacus_forge.dos_data import DOSData, DOSFamilyData, LocalDOSData, PDOSData

_REGISTRY = MetricRegistry()
_KBAR_TO_EV_PER_ANGSTROM3 = 3.398927420868445e-6 * 27.211396132 / 0.52917721092**3
_KS_SOLVER_LIST = {"DA", "DS", "GE", "GV", "BP", "CG", "CU", "PE", "LA"}
_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"

_METRIC_PATTERNS = {
    "total_energy": re.compile(rf"TOTAL\s+ENERGY\s*=\s*({_NUMBER})", re.IGNORECASE),
    "fermi_energy": re.compile(rf"FERMI\s+ENERGY\s*=\s*({_NUMBER})", re.IGNORECASE),
    "band_gap": re.compile(rf"BAND\s+GAP\s*=\s*({_NUMBER})", re.IGNORECASE),
    "pressure": re.compile(rf"PRESSURE\s*=\s*({_NUMBER})", re.IGNORECASE),
    "scf_steps": re.compile(r"SCF\s+STEPS?\s*=\s*(\d+)", re.IGNORECASE),
    "version": re.compile(r"(?:ABACUS\s+)?VERSION\s*[:=]\s*([^\s]+)", re.IGNORECASE),
    "natom": re.compile(r"(?:NATOM|TOTAL\s+ATOM\s+NUMBER)\s*[:=]\s*(\d+)", re.IGNORECASE),
    "nelec": re.compile(rf"(?:NELEC|electron\s+number)\s*[:=]\s*({_NUMBER})", re.IGNORECASE),
    "volume": re.compile(rf"(?:VOLUME|cell\s+volume)\s*[:=]\s*({_NUMBER})", re.IGNORECASE),
    "energy_per_atom": re.compile(rf"(?:ENERGY\s+PER\s+ATOM|E_PER_ATOM)\s*[:=]\s*({_NUMBER})", re.IGNORECASE),
    "relax_steps": re.compile(r"(?:RELAX\s+STEPS?|ION\s+STEPS?)\s*[:=]\s*(\d+)", re.IGNORECASE),
    "largest_gradient": re.compile(rf"(?:LARGEST\s+GRADIENT|largest\s+force)\s*[:=]\s*({_NUMBER})", re.IGNORECASE),
    "drho_last": re.compile(rf"(?:DRHO_LAST|final\s+drho|drho)\s*[:=]\s*({_NUMBER})", re.IGNORECASE),
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
        if key == "version":
            metrics[key] = value
        elif key in {"scf_steps", "natom", "relax_steps"}:
            metrics[key] = int(value)
        else:
            metrics[key] = float(value)
    positive_matches, negative_matches = _collect_convergence_matches(content)
    metrics["converged"] = bool(positive_matches) and not negative_matches
    metrics["converge"] = metrics["converged"]
    metrics["normal_end"] = bool(re.search(r"\b(?:NORMAL\s+END|TOTAL\s+TIME)\b", content, re.IGNORECASE))
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
    if "energy_per_atom" not in metrics and metrics.get("total_energy") is not None and metrics.get("natom"):
        try:
            metrics["energy_per_atom"] = float(metrics["total_energy"]) / int(metrics["natom"])
        except Exception:
            diagnostics["warnings"].append("Failed to derive energy_per_atom from total_energy/natom.")

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
    total_dos = DOSData.from_paths(dos_files) if dos_files else None
    if dos_files:
        metrics["dos_summary"] = total_dos.summary() if total_dos is not None else {}
        metrics["dos_artifacts"] = [str(path) for path in dos_files]
        diagnostics["dos_canonical_artifact"] = str(dos_files[0])
    dos_metrics = _load_json_artifact(artifacts, "metrics_dos.json", diagnostics=diagnostics)
    if dos_metrics is not None:
        metrics["dos_metrics"] = dos_metrics

    pdos_file = _artifact_path(artifacts, "PDOS")
    tdos_file = _artifact_path(artifacts, "TDOS")
    diagnostics["dos_family_projected_artifact_candidates"] = [
        str(path)
        for path in (pdos_file, tdos_file)
        if path is not None
    ]
    projected_dos = PDOSData.from_path(pdos_file, tdos_path=tdos_file) if pdos_file else None
    dos_family_artifacts = [str(path) for path in [*dos_files, pdos_file, tdos_file] if path is not None]
    if total_dos is not None or projected_dos is not None:
        dos_family = DOSFamilyData(
            total_dos=total_dos,
            projected_dos=projected_dos,
            local_dos=LocalDOSData(),
            metadata={},
        )
        metrics["dos_family_summary"] = dos_family.summary()
        metrics["dos_family_artifacts"] = dos_family_artifacts
        diagnostics["dos_family_canonical_artifact"] = str(dos_files[0] if dos_files else (pdos_file or tdos_file))
    if pdos_file or tdos_file:
        diagnostics["dos_family_projected_canonical_artifact"] = str(pdos_file or tdos_file)
    dos_family_metrics = _load_json_artifact(artifacts, "metrics_dos_family.json", diagnostics=diagnostics)
    if dos_family_metrics is not None:
        metrics["dos_family_metrics"] = dos_family_metrics

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

    md_dump = _artifact_path(artifacts, "MD_dump")
    if md_dump is not None and md_dump.exists():
        try:
            metrics["md_dump_summary"] = _md_dump_summary(md_dump)
            metrics["md_steps"] = metrics["md_dump_summary"]["steps"]
            if metrics["md_dump_summary"].get("last_temperature") is not None:
                metrics["md_last_temperature"] = metrics["md_dump_summary"]["last_temperature"]
            if metrics["md_dump_summary"].get("last_total_energy") is not None:
                metrics["md_last_total_energy"] = metrics["md_dump_summary"]["last_total_energy"]
            diagnostics["md_dump"] = str(md_dump)
        except Exception:
            diagnostics["warnings"].append("Failed to parse MD_dump.")
            diagnostics["md_dump_error"] = str(md_dump)

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


def _md_dump_summary(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    steps: list[int] = []
    temperatures: list[float] = []
    energies: list[float] = []
    for line in text.splitlines():
        step_match = re.search(r"(?:STEP|MDSTEP|istep)\s*[:=]?\s*(\d+)", line, re.IGNORECASE)
        if step_match:
            steps.append(int(step_match.group(1)))
        temp_match = re.search(rf"(?:TEMP|temperature)\s*[:=]?\s*({_NUMBER})", line, re.IGNORECASE)
        if temp_match:
            temperatures.append(float(temp_match.group(1)))
        energy_match = re.search(rf"(?:ETOT|TOTAL\s+ENERGY|energy)\s*[:=]?\s*({_NUMBER})", line, re.IGNORECASE)
        if energy_match:
            energies.append(float(energy_match.group(1)))
    inferred_steps = len(steps) if steps else len([line for line in text.splitlines() if line.strip()])
    return {
        "steps": inferred_steps,
        "last_step": steps[-1] if steps else None,
        "last_temperature": temperatures[-1] if temperatures else None,
        "last_total_energy": energies[-1] if energies else None,
        "path": str(path),
    }


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
    for key in ("band_metrics", "dos_metrics", "dos_family_metrics", "relax_metrics"):
        payload = metrics.get(key)
        if isinstance(payload, dict) and payload.get("workflow_goal"):
            return str(payload["workflow_goal"])
    return None
