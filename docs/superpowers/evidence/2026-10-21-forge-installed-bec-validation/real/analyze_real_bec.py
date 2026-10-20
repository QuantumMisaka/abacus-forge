"""Reproducible offline analysis of already collected MgO polarization facts.

Example:
  /home/james/scratch/forge-release-validation-20261021/venv/bin/python -I \
    /home/james/scratch/forge-real-bec-20261021/analyze_real_bec.py \
    --case mesh4 --delta 0.01 \
    --output-dir /home/james/scratch/forge-real-bec-20261021/analysis-mesh4-001

This script never starts ABACUS. It copies the nine existing facts and their
log/STRU/INPUT sources into a fresh analysis workspace, preserving each fact's
stage-relative source_log_path. It invokes only installed Forge bec/postprocess.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
BOHR_TO_ANG = 0.529177210903
SI_FACTOR = 1.60097e-19 / (5.29177e-11) ** 2  # inspected ABACUS producer
DISPLAY_TOL = 1.2e-7
GDIRS = (1, 2, 3)
DISPLACEMENTS = ("minus", "zero", "plus")


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stage_rel(case: str, displacement: float, gdir: int) -> Path:
    return Path(case) / f"d{displacement:+.4f}" / f"g{gdir}"


def _fact_rel(case: str, displacement: float, gdir: int) -> Path:
    return _stage_rel(case, displacement, gdir) / "facts/polarization.json"


def _within(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def _load_sources(root: Path, case: str, delta: float) -> tuple[dict[str, dict[int, dict]], dict[str, dict[int, str]], list[str]]:
    facts: dict[str, dict[int, dict]] = {}
    paths: dict[str, dict[int, str]] = {}
    missing: list[str] = []
    for label, displacement in (("minus", -delta), ("zero", 0.0), ("plus", delta)):
        facts[label], paths[label] = {}, {}
        for gdir in GDIRS:
            relative = _fact_rel(case, displacement, gdir)
            path = root / relative
            if not path.is_file():
                missing.append(str(relative))
                continue
            fact = json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            if fact.get("schema_version") != "forge.polarization/v1" or fact.get("gdir") != gdir:
                raise ValueError(f"invalid fact schema/gdir: {relative}")
            facts[label][gdir] = fact
            paths[label][gdir] = relative.as_posix()
    return facts, paths, missing


def _source_manifest(root: Path, workspace: Path, paths: dict[str, dict[int, str]], facts: dict[str, dict[int, dict]]) -> list[dict]:
    copied: list[dict] = []
    for label in DISPLACEMENTS:
        for gdir in GDIRS:
            fact_rel = Path(paths[label][gdir])
            stage_rel = fact_rel.parent.parent
            stage_source = root / stage_rel
            fact = facts[label][gdir]
            log_rel = Path(fact["source_log_path"])
            if log_rel.is_absolute() or not _within(stage_source / log_rel, stage_source):
                raise ValueError(f"unsafe source_log_path in {fact_rel}: {log_rel}")
            for row in fact["rows"].values():
                if row["source_log_path"] != log_rel.as_posix():
                    raise ValueError(f"row source_log_path disagrees with top level: {fact_rel}")
            for local_rel in (Path("facts/polarization.json"), Path("inputs/STRU"), Path("inputs/INPUT"), log_rel):
                source = stage_source / local_rel
                if not source.is_file():
                    raise FileNotFoundError(f"missing fact/source file: {source}")
                destination = workspace / stage_rel / local_rel
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                if _sha(source) != _sha(destination):
                    raise AssertionError(f"copy hash mismatch: {source}")
                copied.append({"path_rel": (stage_rel / local_rel).as_posix(), "sha256": _sha(source)})
    return copied


def _check_native_units(facts: dict[str, dict[int, dict]]) -> list[dict]:
    checks: list[dict] = []
    for label in DISPLACEMENTS:
        for gdir in GDIRS:
            fact = facts[label][gdir]
            geometry = fact["geometry"]
            cell = np.asarray(geometry["cell_angstrom"], dtype=float) / BOHR_TO_ANG
            volume = abs(float(np.linalg.det(cell)))
            length = float(np.linalg.norm(cell[gdir - 1]))
            unit = cell[gdir - 1] / length
            rows = fact["rows"]
            q, p, si = (rows[name] for name in ("(e/Omega).bohr", "e/bohr^2", "C/m^2"))
            qvec = np.asarray(q["cartesian"], dtype=float)
            pvec = np.asarray(p["cartesian"], dtype=float)
            sivec = np.asarray(si["cartesian"], dtype=float)
            quantum_error = abs(float(q["modulus"]) - 2 * length)
            scalar_unit_error = abs(float(p["scalar"]) - float(q["scalar"]) / volume)
            modulus_unit_error = abs(float(p["modulus"]) - float(q["modulus"]) / volume)
            vector_error = float(np.max(np.abs(qvec - float(q["scalar"]) * unit)))
            p_vector_error = float(np.max(np.abs(pvec - qvec / volume)))
            si_vector_error = float(np.max(np.abs(sivec - qvec / volume * SI_FACTOR)))
            if quantum_error > 3e-6 or scalar_unit_error > DISPLAY_TOL or modulus_unit_error > DISPLAY_TOL:
                raise AssertionError(f"quantum/row unit mismatch at {label}/g{gdir}")
            if vector_error > 5e-7 or p_vector_error > DISPLAY_TOL or si_vector_error > 1e-5:
                raise AssertionError(f"Cartesian unit row mismatch at {label}/g{gdir}")
            checks.append({"sample": label, "gdir": gdir, "volume_bohr3": volume,
                           "lattice_length_bohr": length, "printed_quantum": q["modulus"],
                           "two_lattice_lengths": 2 * length, "quantum_error": quantum_error,
                           "q_to_p_scalar_error": scalar_unit_error,
                           "q_to_p_modulus_error": modulus_unit_error,
                           "q_vector_error": vector_error, "p_vector_error": p_vector_error,
                           "si_vector_error": si_vector_error})
    return checks


def _identify_displaced_atom(facts: dict[str, dict[int, dict]], delta: float) -> tuple[int, str]:
    zero = facts["zero"][1]["geometry"]
    baseline = np.asarray(zero["positions_angstrom"], dtype=float)
    labels = zero["atom_labels"]
    if labels != ["O", "Mg"]:
        raise AssertionError(f"unexpected serialized MgO atom order: {labels}")
    displaced: list[int] = []
    for atom in range(len(labels)):
        minus = np.asarray(facts["minus"][1]["geometry"]["positions_angstrom"], dtype=float)[atom] - baseline[atom]
        plus = np.asarray(facts["plus"][1]["geometry"]["positions_angstrom"], dtype=float)[atom] - baseline[atom]
        expected_minus = np.array([-delta, 0.0, 0.0])
        expected_plus = -expected_minus
        if np.max(np.abs(minus - expected_minus)) < 2e-7 and np.max(np.abs(plus - expected_plus)) < 2e-7:
            displaced.append(atom + 1)
        elif np.max(np.abs(minus)) > 2e-7 or np.max(np.abs(plus)) > 2e-7:
            raise AssertionError(f"unexpected movement of serialized atom {atom + 1}: {minus}, {plus}")
    if displaced != [1]:
        raise AssertionError(f"expected serialized O atom 1 to move, got {displaced}")
    return 1, "O"


def _request(case: str, delta: float, paths: dict[str, dict[int, str]], atom_index: int,
             *, mode: str, offsets: dict[str, dict[int, int]] | None = None) -> dict:
    samples = []
    for label, displacement in (("minus", -delta), ("zero", 0.0), ("plus", delta)):
        sample = {"displacement_angstrom": displacement,
                  "polarization_paths_rel": [paths[label][g] for g in GDIRS]}
        if offsets is not None:
            sample["branch_offsets"] = {str(g): offsets[label][g] for g in GDIRS}
        samples.append(sample)
    return {"schema_version": "forge.request/v1", "operation_id": str(uuid.uuid4()),
            "workspace_rel": ".", "capability": "bec", "operation": "postprocess",
            "columns": [{"atom_index": atom_index, "direction": "x", "samples": samples}],
            "branch_mode": mode, "max_step_fraction": 0.25 if mode == "auto" else None,
            "output_path_rel": f"outputs/bec-{mode}.json"}


def _call_cli(python: Path, workspace: Path, out: Path, request: dict, label: str) -> dict:
    _write(out / f"{label}-request.json", request)
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [str(python), "-I", "-m", "abacus_forge.cli", "operation", "postprocess", "--stdin"]
    process = subprocess.run(command, input=json.dumps(request), text=True,
                             capture_output=True, cwd=workspace, env=environment, timeout=60)
    (out / f"{label}-response.json").write_text(process.stdout, encoding="utf-8")
    (out / f"{label}-stderr.txt").write_text(process.stderr, encoding="utf-8")
    _write(out / f"{label}-command.json", {"argv": command, "cwd": str(workspace), "exit_code": process.returncode})
    if process.returncode != 0:
        raise RuntimeError(f"installed CLI {label} failed; inspect {label}-response.json / stderr")
    response = json.loads(process.stdout)
    if response["envelope"]["status"]["collection"] != "complete":
        raise AssertionError(f"installed CLI {label} did not complete requested column")
    result = json.loads((workspace / request["output_path_rel"]).read_text(encoding="utf-8"))
    _write(out / f"{label}-result.json", result)
    if result["requested_complete"] is not True or result["full_tensor_complete"] is not False:
        raise AssertionError(f"installed CLI {label} completeness flags are wrong for one-column MgO")
    return result


def _independent_offsets(facts: dict[str, dict[int, dict]], bound: float) -> tuple[dict[str, dict[int, int]], list[dict]]:
    """Infer offsets from raw displayed scalar/modulus only; never read CLI trace."""
    offsets = {label: {} for label in DISPLACEMENTS}
    table = []
    for gdir in GDIRS:
        reference = facts["zero"][gdir]["rows"]["(e/Omega).bohr"]
        q0, quantum = float(reference["scalar"]), float(reference["modulus"])
        offsets["zero"][gdir] = 0
        for label in ("minus", "plus"):
            row = facts[label][gdir]["rows"]["(e/Omega).bohr"]
            raw, sample_quantum = float(row["scalar"]), float(row["modulus"])
            if abs(sample_quantum - quantum) > DISPLAY_TOL:
                raise AssertionError(f"gdir {gdir} quantum changes from zero to {label}")
            nearest = math.floor((q0 - raw) / sample_quantum + 0.5)
            candidates = [k for k in range(nearest - 2, nearest + 3)
                          if abs(raw + k * sample_quantum - q0) < bound * sample_quantum - 3 * DISPLAY_TOL]
            if len(candidates) != 1:
                raise AssertionError(f"independent {label}/g{gdir} branch ambiguous under f={bound}: {candidates}")
            offset = candidates[0]
            offsets[label][gdir] = offset
            corrected = raw + offset * sample_quantum
            table.append({"sample": label, "gdir": gdir, "reference_raw_scalar": q0,
                          "sample_raw_scalar": raw, "printed_modulus": sample_quantum,
                          "raw_change_fraction": (raw - q0) / sample_quantum,
                          "independent_integer_offset": offset,
                          "corrected_change_fraction": (corrected - q0) / sample_quantum,
                          "caller_bound_fraction": bound})
    return offsets, table


def _manual_column(facts: dict[str, dict[int, dict]], offsets: dict[str, dict[int, int]], delta: float) -> dict:
    endpoint_vectors: dict[str, np.ndarray] = {}
    contributions: list[dict] = []
    for label in ("minus", "plus"):
        summed = np.zeros(3)
        for gdir in GDIRS:
            fact = facts[label][gdir]
            row = fact["rows"]["(e/Omega).bohr"]
            lattice = np.asarray(fact["geometry"]["cell_angstrom"], dtype=float)[gdir - 1]
            unit = lattice / np.linalg.norm(lattice)
            raw_vector = np.asarray(row["cartesian"], dtype=float)
            corrected = raw_vector + offsets[label][gdir] * float(row["modulus"]) * unit
            summed += corrected
            contributions.append({"sample": label, "gdir": gdir,
                                  "raw_cartesian_q": raw_vector.tolist(),
                                  "branch_correction_q": (corrected - raw_vector).tolist(),
                                  "corrected_cartesian_q": corrected.tolist()})
        endpoint_vectors[label] = summed
    delta_bohr = delta / BOHR_TO_ANG
    bec = (endpoint_vectors["plus"] - endpoint_vectors["minus"]) / (2 * delta_bohr)
    return {"negative_endpoint_q": endpoint_vectors["minus"].tolist(),
            "positive_endpoint_q": endpoint_vectors["plus"].tolist(),
            "displacement_bohr": delta_bohr, "cartesian_column_e": bec.tolist(),
            "contributions": contributions}


def run(root: Path, case: str, delta: float, output_dir: Path) -> dict:
    if delta not in (0.01, 0.005):
        raise ValueError("delta must be 0.01 or 0.005 angstrom")
    if not case or Path(case).name != case or case in (".", ".."):
        raise ValueError("case must be one directory name")
    if output_dir.exists():
        raise FileExistsError(f"analysis output must be a new directory: {output_dir}")
    provenance = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
    python = Path(provenance["python"])
    if not python.is_file():
        raise FileNotFoundError(f"installed validation Python is missing: {python}")
    facts, paths, missing = _load_sources(root, case, delta)
    if missing:
        raise FileNotFoundError("missing collected polarization facts: " + ", ".join(missing))
    # All checks below consume the original fact values, before any CLI result.
    atom_index, element = _identify_displaced_atom(facts, delta)
    unit_checks = _check_native_units(facts)
    output_dir.mkdir(parents=True)
    workspace = output_dir / "workspace"
    workspace.mkdir()
    _write(output_dir / "input-provenance.json", provenance)
    _write(output_dir / "source-manifest.json", _source_manifest(root, workspace, paths, facts))
    auto_request = _request(case, delta, paths, atom_index, mode="auto")
    auto = _call_cli(python, workspace, output_dir, auto_request, "auto")
    offsets, table = _independent_offsets(facts, 0.25)
    _write(output_dir / "raw-branch-table.json", table)
    auto_offsets = {(round(float(item["displacement_angstrom"]), 4), int(item["gdir"])): int(item["offset"])
                    for item in auto["columns"][0]["branch_trace"]}
    for label, displacement in (("minus", -delta), ("zero", 0.0), ("plus", delta)):
        for gdir in GDIRS:
            if auto_offsets.get((round(displacement, 4), gdir)) != offsets[label][gdir]:
                raise AssertionError(f"auto trace disagrees with independent raw-scalar offset: {label}/g{gdir}")
    explicit_request = _request(case, delta, paths, atom_index, mode="explicit", offsets=offsets)
    explicit = _call_cli(python, workspace, output_dir, explicit_request, "explicit")
    manual = _manual_column(facts, offsets, delta)
    _write(output_dir / "manual-endpoint-difference.json", manual)
    auto_values = np.asarray(auto["computed_columns"][0]["values"], dtype=float)
    explicit_values = np.asarray(explicit["computed_columns"][0]["values"], dtype=float)
    manual_values = np.asarray(manual["cartesian_column_e"], dtype=float)
    auto_explicit_error = float(np.max(np.abs(auto_values - explicit_values)))
    explicit_manual_error = float(np.max(np.abs(explicit_values - manual_values)))
    if auto_explicit_error > 2e-6 or explicit_manual_error > 2e-6:
        raise AssertionError(f"auto/explicit/manual mismatch: {auto_explicit_error}, {explicit_manual_error}")
    # The following is an observation for scientific review, not an oracle.
    magnitude = abs(float(manual_values[0]))
    transverse = float(np.max(np.abs(manual_values[1:])))
    summary = {"case": case, "displacement_angstrom": delta,
               "serialized_displaced_atom_index": atom_index, "serialized_element": element,
               "requested_column": "O: x displacement -> Cartesian polarization x/y/z",
               "auto_column_e": auto_values.tolist(), "explicit_column_e": explicit_values.tolist(),
               "independent_manual_column_e": manual_values.tolist(),
               "max_auto_explicit_error_e": auto_explicit_error,
               "max_explicit_manual_error_e": explicit_manual_error,
               "printed_quantum_and_unit_checks": unit_checks,
               "independent_branch_offsets": {label: {str(g): offsets[label][g] for g in GDIRS} for label in DISPLACEMENTS},
               "sign_of_longitudinal_O_charge": "negative" if manual_values[0] < 0 else "nonnegative",
               "longitudinal_magnitude_e": magnitude, "max_transverse_magnitude_e": transverse,
               "transverse_to_longitudinal_ratio": transverse / magnitude if magnitude else None,
               "scientific": "unassessed",
               "limitation": "One finite-difference column at supplied k mesh/displacement; no convergence or material acceptance claim."}
    _write(output_dir / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="mesh4", help="existing case directory, e.g. mesh4 or mesh8x4x4")
    parser.add_argument("--delta", type=float, choices=(0.01, 0.005), required=True,
                        help="symmetric displacement magnitude in angstrom")
    parser.add_argument("--output-dir", type=Path, required=True, help="new directory for copied sources and analysis")
    args = parser.parse_args()
    try:
        summary = run(ROOT, args.case, args.delta, args.output_dir.expanduser().resolve())
    except Exception as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({"status": "complete", "summary": summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
