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
_NATIVE_FINAL_ETOT = re.compile(rf"!FINAL_ETOT_IS\s*[=:]*\s*({_NUMBER})\s*eV", re.IGNORECASE)
_NATIVE_FERMI = re.compile(rf"\bE_Fermi\s+({_NUMBER})\s+({_NUMBER})", re.IGNORECASE)
_MD_THERMO_HEADER = re.compile(
    r"Energy(?:\s*\(Ry\))?\s+Potential(?:\s*\(Ry\))?\s+Kinetic(?:\s*\(Ry\))?\s+"
    r"Temperature(?:\s*\(K\))?(?:\s+Pressure(?:\s*\(kbar\))?)?",
    re.IGNORECASE,
)
_MD_ENERGY_HEADER = re.compile(r"Energy(?:\s*\(Ry\))?\s+Potential(?:\s*\(Ry\))?\s+Kinetic(?:\s*\(Ry\))?", re.IGNORECASE)
_MD_TEMPERATURE_HEADER = re.compile(r"Temperature(?:\s*\(K\))?(?:\s+Pressure(?:\s*\(kbar\))?)?", re.IGNORECASE)
_RY_TO_EV = 13.605698

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
    "relax_steps": re.compile(
        r"(?:RELAX\s+STEPS?|ION\s+STEPS?|STEP\s+OF\s+RELAXATION)\s*[:=]\s*(\d+)",
        re.IGNORECASE,
    ),
    "largest_gradient": re.compile(rf"(?:LARGEST\s+GRADIENT|largest\s+force)\s*[:=]\s*({_NUMBER})", re.IGNORECASE),
    "drho_last": re.compile(rf"(?:DRHO_LAST|final\s+drho|drho)\s*[:=]\s*({_NUMBER})", re.IGNORECASE),
}

_POSITIVE_CONVERGENCE_PATTERNS = {
    "scf_converged": re.compile(r"\bSCF\s+CONVERGED\b", re.IGNORECASE),
    # Native ABACUS running logs use ``#SCF IS CONVERGED#``.  Keep this as a
    # separate marker so diagnostics preserve the exact source spelling while
    # sharing the existing factual convergence projection.
    "scf_is_converged": re.compile(r"\bSCF\s+IS\s+CONVERGED\b", re.IGNORECASE),
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
    if "fermi_energy" not in metrics:
        native_fermi = _NATIVE_FERMI.findall(content)
        if native_fermi:
            # Native ABACUS prints Rydberg first and eV second; Forge's
            # reported fermi_energy contract is eV, matching the legacy form.
            # Iterative logs repeat the row, so retain the final iteration.
            metrics["fermi_energy"] = float(native_fermi[-1][1])
    positive_matches, negative_matches = _collect_convergence_matches(content)
    metrics["converged"] = bool(positive_matches) and not negative_matches
    metrics["converge"] = metrics["converged"]
    metrics["normal_end"] = bool(re.search(r"\b(?:NORMAL\s+END|TOTAL\s+TIME)\b", content, re.IGNORECASE))
    return metrics


def _common_log_metrics(content: str) -> dict[str, Any]:
    """Extract backend-independent log facts without native numeric parsing."""
    metrics: dict[str, Any] = {}
    # Keep this whitelist explicit.  Calling _regex_metrics and popping owned
    # keys afterwards would still execute the native numeric readers.
    common_fields = (
        "band_gap", "scf_steps", "version", "natom", "nelec", "volume",
        "relax_steps", "largest_gradient", "drho_last",
    )
    for key in common_fields:
        match = _METRIC_PATTERNS[key].search(content)
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
    main_log_path: Path | None = None,
    output_log_path: Path | None = None,
    include_native_numeric: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Collect metrics and diagnostics from logs and artifacts."""

    main_content = main_log_text or ""
    output_content = output_log_text or ""
    metrics = _REGISTRY.extract(main_content) if include_native_numeric else _common_log_metrics(main_content)
    metric_origins: dict[str, str] = {}
    derived_metrics: set[str] = set()
    main_source = str(main_log_path) if main_log_path is not None else None
    output_source = str(output_log_path) if output_log_path is not None else None

    def mark_main(names: object) -> None:
        if main_source is None:
            return
        if isinstance(names, dict):
            names = names.keys()
        try:
            for name in names:  # type: ignore[union-attr]
                if str(name) in metrics:
                    metric_origins[str(name)] = main_source
        except TypeError:
            return

    mark_main(metrics)
    native_fermi = _NATIVE_FERMI.findall(main_content) if include_native_numeric else []
    generic_fermi = _METRIC_PATTERNS["fermi_energy"].search(main_content) if include_native_numeric else None
    native_fermi_used = bool(native_fermi and generic_fermi is None)
    native_final = _NATIVE_FINAL_ETOT.findall(main_content) if include_native_numeric else []
    if native_final:
        metrics["total_energy"] = float(native_final[-1])
        if main_source is not None:
            metric_origins["total_energy"] = main_source
    positive_matches, negative_matches = _collect_convergence_matches(main_content)
    diagnostics: dict[str, Any] = {
        "log_sources": len([blob for blob in (main_log_text, output_log_text) if blob]),
        "matched_converged_markers": positive_matches,
        "matched_nonconverged_markers": negative_matches,
        "warnings": [],
        "report_json_absent": [],
    }
    if native_final:
        diagnostics["native_final_energy_markers"] = len(native_final)
    if native_fermi_used:
        diagnostics["_metric_units"] = {"fermi_energy": "eV"}
    native_md = _native_md_metrics(main_content)
    metrics.update(native_md["metrics"])
    mark_main(native_md["metrics"])
    diagnostics.update(native_md["diagnostics"])
    force_metrics = _force_metrics(main_content) if include_native_numeric else {}
    stress_metrics = _stress_metrics(main_content, volume=structure_volume) if include_native_numeric else {}
    metrics.update(force_metrics)
    metrics.update(stress_metrics)
    mark_main(force_metrics)
    mark_main(stress_metrics)
    if "pressure" in stress_metrics:
        derived_metrics.add("pressure")
    output_metrics = _output_metrics(output_content)
    for key, value in output_metrics.items():
        metrics.setdefault(key, value)
        if key not in metric_origins and output_source is not None and key in metrics:
            metric_origins[key] = output_source
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
            if "total_energy" in metric_origins:
                metric_origins["energy_per_atom"] = metric_origins["total_energy"]
            derived_metrics.add("energy_per_atom")
        except Exception:
            diagnostics["warnings"].append("Failed to derive energy_per_atom from total_energy/natom.")

    time_path = _artifact_path(artifacts, "time.json")
    if time_path and time_path.exists():
        try:
            payload = json.loads(time_path.read_text(encoding="utf-8"))
            metrics["total_time"] = payload.get("total")
            diagnostics["time_json"] = str(time_path)
            if payload.get("total") is not None:
                metric_origins["total_time"] = str(time_path)
            else:
                # The JSON artifact still follows the legacy assignment
                # behavior, but it did not provide a metric value.  Do not
                # leave an earlier output-log provenance attached to None.
                metric_origins.pop("total_time", None)
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
    pyatb_band_files = _artifact_paths_in_band_structure(artifacts)
    diagnostics["pyatb_band_artifact_candidates"] = [str(path) for path in pyatb_band_files]
    if pyatb_band_files:
        metrics["pyatb_band_artifacts"] = [str(path) for path in pyatb_band_files]
    pyatb_band_info = _artifact_path(artifacts, "band_info.dat")
    if pyatb_band_info is not None and pyatb_band_info.exists():
        metrics["pyatb_band_metrics"] = _parse_pyatb_band_info(pyatb_band_info)
        diagnostics["pyatb_band_info"] = str(pyatb_band_info)

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
            metrics["md_dump_frames"] = metrics["md_dump_summary"]["steps"]
            metrics["md_dump_steps"] = metrics["md_dump_summary"].get("last_step")
            if not diagnostics.get("native_md_block_complete") and metrics["md_dump_summary"].get("last_temperature") is not None:
                metrics["md_last_temperature"] = metrics["md_dump_summary"]["last_temperature"]
            if not diagnostics.get("native_md_block_complete") and metrics["md_dump_summary"].get("last_total_energy") is not None:
                metrics["md_last_total_energy"] = metrics["md_dump_summary"]["last_total_energy"]
            for name in ("md_steps", "md_dump_frames", "md_dump_steps"):
                if name in metrics:
                    metric_origins[name] = str(md_dump)
            if not diagnostics.get("native_md_block_complete"):
                for name in ("md_last_temperature", "md_last_total_energy"):
                    if name in metrics:
                        metric_origins[name] = str(md_dump)
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
    # These keys are consumed by collection.py into non-serialized
    # CollectionResult sidecars.  Keeping them private here lets the parser
    # communicate branch provenance without changing the legacy diagnostics.
    diagnostics["_metric_origins"] = metric_origins
    diagnostics["_derived_metrics"] = sorted(derived_metrics)
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
    candidates.sort(key=lambda item: (_artifact_priority(item[0]), item[0].count("/"), item[0]))
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
    for relative, path in sorted(matches, key=lambda item: (Path(item[0]).name, _artifact_priority(item[0]), item[0].count("/"), item[0])):
        basename = Path(relative).name
        selected.setdefault(basename, (relative, path))
    return [path for _, path in sorted(selected.values(), key=lambda item: item[0])]


def _artifact_paths_in_band_structure(artifacts: dict[str, str]) -> list[Path]:
    matches: list[tuple[str, Path]] = []
    for relative, path in artifacts.items():
        normalized = relative.replace("\\", "/")
        if "/Band_Structure/" not in f"/{normalized}":
            continue
        if Path(relative).name in {"band_info.dat", "band_up.dat", "band_dn.dat", "band.pdf", "band.png"}:
            matches.append((relative, Path(path)))
    return [path for _, path in sorted(matches, key=lambda item: item[0])]


def _parse_pyatb_band_info(path: Path) -> dict[str, Any]:
    metrics: dict[str, Any] = {"band_info": str(path)}
    content = path.read_text(encoding="utf-8", errors="ignore")
    matches = re.findall(rf"band\s+gap(?:\s*\([^)]*\))?(?:\s+is)?\s*[:=]?\s*({_NUMBER})", content, re.IGNORECASE)
    if matches:
        metrics["band_gap"] = float(matches[-1])
    return metrics


def _artifact_priority(relative: str) -> int:
    normalized = relative.replace("\\", "/")
    if normalized.startswith("inputs/OUT."):
        return 0
    if normalized.startswith("outputs/OUT."):
        return 1
    if normalized.startswith("outputs/"):
        return 2
    return 3


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


def _native_md_metrics(content: str) -> dict[str, dict[str, Any]]:
    """Parse ABACUS's native MD thermodynamic blocks into factual series."""
    rows: list[dict[str, float]] = []
    lines = content.splitlines()
    def numeric_tokens(row: str) -> list[str] | None:
        tokens = row.split()
        if not tokens or any(re.fullmatch(_NUMBER, token) is None for token in tokens):
            return None
        return tokens
    for index, line in enumerate(lines):
        header = _MD_THERMO_HEADER.search(line)
        energy_header = _MD_ENERGY_HEADER.search(line)
        if not header and not energy_header:
            continue
        has_pressure = "pressure" in line.lower()
        energy_values: list[str] | None = None
        temperature_values: list[str] | None = None
        if header:
            for row in lines[index + 1 : index + 5]:
                values = numeric_tokens(row)
                if values is not None and len(values) >= (5 if has_pressure else 4):
                    energy_values, temperature_values = values[:3], values[3:]
                    break
        else:
            energy_index = next(
                (pos for pos in range(index + 1, min(index + 5, len(lines)))
                 if (tokens := numeric_tokens(lines[pos])) is not None and len(tokens) >= 3), None
            )
            if energy_index is not None:
                energy_values = numeric_tokens(lines[energy_index])[:3]  # type: ignore[index]
                temp_header_index = next(
                    (pos for pos in range(energy_index + 1, min(energy_index + 5, len(lines)))
                     if _MD_TEMPERATURE_HEADER.search(lines[pos])), None
                )
                if temp_header_index is not None:
                    has_pressure = "pressure" in lines[temp_header_index].lower()
                    temp_index = next(
                        (pos for pos in range(temp_header_index + 1, min(temp_header_index + 4, len(lines)))
                         if (tokens := numeric_tokens(lines[pos])) is not None and len(tokens) >= (2 if has_pressure else 1)), None
                    )
                    if temp_index is not None:
                        temperature_values = numeric_tokens(lines[temp_index])[:2]  # type: ignore[index]
        if energy_values is None or temperature_values is None:
            continue
        try:
            item = {
                "total_energy": float(energy_values[0]) * _RY_TO_EV,
                "potential_energy": float(energy_values[1]) * _RY_TO_EV,
                "kinetic_energy": float(energy_values[2]) * _RY_TO_EV,
                "temperature": float(temperature_values[0]),
            }
            if has_pressure:
                if len(temperature_values) < 2:
                    continue
                item["pressure"] = float(temperature_values[1])
        except ValueError:
            continue
        rows.append(item)
    if not rows:
        return {"metrics": {}, "diagnostics": {"native_md_block_present": bool(_MD_ENERGY_HEADER.search(content)), "native_md_block_complete": False, "native_md_rows": 0}}
    last = rows[-1]
    metrics: dict[str, Any] = {
        "md_total_energy_series": [row["total_energy"] for row in rows],
        "md_potential_energy_series": [row["potential_energy"] for row in rows],
        "md_kinetic_energy_series": [row["kinetic_energy"] for row in rows],
        "md_temperature_series": [row["temperature"] for row in rows],
        "md_last_total_energy": last["total_energy"],
        "md_last_potential_energy": last["potential_energy"],
        "md_last_kinetic_energy": last["kinetic_energy"],
        "md_last_temperature": last["temperature"],
    }
    if "pressure" in last:
        metrics["md_pressure_series"] = [row["pressure"] for row in rows if "pressure" in row]
        metrics["md_last_pressure"] = last["pressure"]
    return {"metrics": metrics, "diagnostics": {"native_md_block_present": True, "native_md_block_complete": True, "native_md_rows": len(rows)}}


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
