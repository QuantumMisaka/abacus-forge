"""Finite-difference Born effective charge from caller-selected Berry facts.

No calculation, path selection, or scientific acceptance is performed here.
Automatic branch continuity is conditional on a caller asserted step bound.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from abacus_forge.structure import BOHR_TO_ANG


_AXES = {"x": 0, "y": 1, "z": 2}
_ROW_Q = "(e/Omega).bohr"
_ROW_P = "e/bohr^2"
_ROW_SI = "C/m^2"
_SOURCE_SI_FACTOR = 1.60097e-19 / (5.29177e-11) ** 2
_PRINT_TOL = 1.2e-7  # two seven-decimal displayed values plus roundoff
_GEOMETRY_TOL_ANG = 2e-7


class _ColumnProblem(Exception):
    def __init__(self, status: str, reason: str):
        self.status = status
        self.reason = reason
        super().__init__(reason)


def calculate_bec(
    columns: Sequence[dict],
    facts: Mapping[str, dict],
    *,
    branch_mode: str,
    max_step_fraction: float | None,
) -> dict:
    """Compute requested Cartesian tensor columns, retaining independent failures.

    ``facts`` is keyed by the request's workspace-relative fact path. Missing
    keys produce per-column ``missing`` results. The JSON facts are validated
    before numerical use, including geometry, INPUT identity and printed units.
    """
    if not isinstance(columns, Sequence) or isinstance(columns, (str, bytes)) or not columns:
        raise ValueError("BEC requires nonempty columns")
    if not isinstance(facts, Mapping):
        raise ValueError("facts must be a mapping")
    requested: list[dict] = []
    details: list[dict] = []
    computed: list[dict] = []
    baseline_global: dict | None = None
    atom_count: int | None = None
    seen_columns: set[tuple[Any, Any]] = set()
    for column in columns:
        atom_index = column.get("atom_index") if isinstance(column, Mapping) else None
        direction = column.get("direction") if isinstance(column, Mapping) else None
        identity = {"atom_index": atom_index, "direction": direction}
        requested.append(identity)
        entry = {**identity, "status": "invalid", "reason": None, "values": None, "branch_trace": []}
        details.append(entry)
        try:
            if (atom_index, direction) in seen_columns:
                raise _ColumnProblem("invalid", "duplicate requested column")
            seen_columns.add((atom_index, direction))
            values, trace, baseline = _calculate_column(column, facts, branch_mode, max_step_fraction)
            if baseline_global is not None and not _same_baseline(baseline_global, baseline):
                raise _ColumnProblem("invalid", "requested columns describe different structures")
            baseline_global = baseline
            atom_count = len(baseline["positions"])
            entry.update(status="computed", values=values, branch_trace=trace)
            computed.append({**identity, "values": values, "unit": "e"})
        except _ColumnProblem as exc:
            entry.update(status=exc.status, reason=exc.reason)
        except (TypeError, ValueError, KeyError, IndexError, OverflowError) as exc:
            entry.update(status="invalid", reason=f"invalid fact or column: {exc}")
    tensor: list[list[list[float | None]]] = [
        [[None for _ in range(3)] for _ in range(3)] for _ in range(atom_count or 0)
    ]
    for item in computed:
        axis = _AXES[item["direction"]]
        for alpha, value in enumerate(item["values"]):
            tensor[item["atom_index"] - 1][alpha][axis] = value
    requested_complete = len(computed) == len(columns)
    return {
        "schema_version": "forge.bec/v1",
        "requested_columns": requested,
        "computed_columns": computed,
        "columns": details,
        "tensor": tensor,
        "requested_complete": requested_complete,
        "full_tensor_complete": bool(tensor) and all(
            value is not None for atom in tensor for polarization_axis in atom for value in polarization_axis
        ),
        "unit": "e",
        "branch_mode": branch_mode,
        "max_step_fraction": max_step_fraction,
        "scientific": "unassessed",
    }


def _calculate_column(column: Mapping, facts: Mapping, mode: str, bound: float | None) -> tuple[list[float], list[dict], dict]:
    if not isinstance(column, Mapping):
        raise _ColumnProblem("invalid", "column must be an object")
    atom_index, direction = column.get("atom_index"), column.get("direction")
    if type(atom_index) is not int or atom_index < 1 or direction not in _AXES:
        raise _ColumnProblem("invalid", "invalid atom_index or Cartesian direction")
    if mode not in ("auto", "explicit"):
        raise _ColumnProblem("invalid", "branch_mode must be auto or explicit")
    if mode == "auto" and (not _number(bound) or not 0 < bound < 0.5):
        raise _ColumnProblem("invalid", "auto requires 0 < max_step_fraction < 0.5")
    samples = column.get("samples")
    if not isinstance(samples, list) or len(samples) < 2:
        raise _ColumnProblem("missing", "at least symmetric plus/minus samples are required")
    parsed: list[dict] = []
    for sample in samples:
        if not isinstance(sample, Mapping) or not _number(sample.get("displacement_angstrom")):
            raise _ColumnProblem("invalid", "sample displacement must be finite")
        displacement = float(sample["displacement_angstrom"])
        paths = sample.get("polarization_paths_rel")
        if not isinstance(paths, list) or len(paths) != 3 or any(not isinstance(p, str) or not p for p in paths):
            raise _ColumnProblem("missing", "sample requires three polarization fact paths")
        if len(set(paths)) != 3:
            raise _ColumnProblem("invalid", "duplicate polarization fact paths in sample")
        missing_paths = [path for path in paths if path not in facts]
        if missing_paths:
            raise _ColumnProblem("missing", f"missing polarization facts: {missing_paths}")
        by_gdir: dict[int, dict] = {}
        for path in paths:
            fact = _validate_fact(facts[path])
            gdir = fact["gdir"]
            if gdir in by_gdir:
                raise _ColumnProblem("invalid", f"duplicate gdir {gdir} in sample")
            fact["path"] = path
            by_gdir[gdir] = fact
        if set(by_gdir) != {1, 2, 3}:
            raise _ColumnProblem("missing", "sample lacks gdir 1, 2 or 3")
        _same_sample_facts(by_gdir)
        offsets = sample.get("branch_offsets")
        if mode == "explicit":
            if not isinstance(offsets, Mapping) or set(offsets) != {"1", "2", "3"} or any(type(v) is not int for v in offsets.values()):
                raise _ColumnProblem("invalid", "explicit mode requires integer offsets 1, 2 and 3 for every sample")
        parsed.append({"displacement": displacement, "facts": by_gdir, "offsets": offsets})
    parsed.sort(key=lambda item: item["displacement"])
    displacements = [item["displacement"] for item in parsed]
    if any(abs(b - a) <= 1e-12 for a, b in zip(displacements, displacements[1:])):
        raise _ColumnProblem("invalid", "duplicate sample displacement")
    delta = displacements[-1]
    if delta <= 0 or not math.isclose(displacements[0], -delta, abs_tol=1e-10, rel_tol=1e-8):
        raise _ColumnProblem("missing", "symmetric negative and positive endpoints are required")
    zero = next((item for item in parsed if abs(item["displacement"]) <= 1e-12), None)
    if mode == "auto" and zero is None:
        raise _ColumnProblem("missing", "auto requires a zero-displacement reference")
    baseline = _validate_path_geometry(parsed, atom_index, _AXES[direction])
    _validate_quantum_path(parsed)
    trace = _offsets_auto(parsed, zero, float(bound)) if mode == "auto" else _offsets_explicit(parsed)
    endpoint_vectors = []
    for item in (parsed[0], parsed[-1]):
        vector = np.zeros(3)
        for gdir in (1, 2, 3):
            fact = item["facts"][gdir]
            vector += fact["vector"] + item["selected_offsets"][gdir] * fact["quantum"] * fact["unit_vector"]
        endpoint_vectors.append(vector)
    values = ((endpoint_vectors[1] - endpoint_vectors[0]) / (2 * delta / BOHR_TO_ANG)).tolist()
    return values, trace, baseline


def _validate_fact(raw: Any) -> dict:
    if not isinstance(raw, Mapping) or raw.get("schema_version") != "forge.polarization/v1":
        raise _ColumnProblem("invalid", "fact schema_version must be forge.polarization/v1")
    gdir = raw.get("gdir")
    if type(gdir) is not int or gdir not in (1, 2, 3):
        raise _ColumnProblem("invalid", "fact has invalid gdir")
    geometry = raw.get("geometry")
    if not isinstance(geometry, Mapping):
        raise _ColumnProblem("invalid", "fact has no geometry")
    cell = _array(geometry.get("cell_angstrom"), (3, 3), "cell")
    positions = np.asarray(geometry.get("positions_angstrom"), dtype=float)
    if positions.ndim != 2 or positions.shape[1] != 3 or not len(positions) or not np.isfinite(positions).all():
        raise _ColumnProblem("invalid", "fact has invalid atom positions")
    if abs(float(np.linalg.det(cell))) < 1e-8:
        raise _ColumnProblem("invalid", "fact cell is singular")
    count = len(positions)
    symbols = geometry.get("symbols")
    labels = geometry.get("atom_labels")
    moves = geometry.get("move_flags")
    species = geometry.get("species_meta")
    if not all(isinstance(v, list) and len(v) == count for v in (symbols, labels, moves)) or not isinstance(species, Mapping):
        raise _ColumnProblem("invalid", "fact has incomplete atom identity")
    if any(not isinstance(v, str) or not v for v in symbols + labels):
        raise _ColumnProblem("invalid", "fact has invalid atom identity")
    if any(not isinstance(v, list) or len(v) != 3 or any(type(x) is not int for x in v) for v in moves):
        raise _ColumnProblem("invalid", "fact has invalid movement flags")
    if any(label not in species for label in labels):
        raise _ColumnProblem("invalid", "fact lacks species references")
    params = raw.get("input")
    if not isinstance(params, Mapping) or not all(isinstance(k, str) and isinstance(v, str) for k, v in params.items()):
        raise _ColumnProblem("invalid", "fact has invalid INPUT mapping")
    if params.get("gdir") != str(gdir) or params.get("berry_phase") != "1" or params.get("nspin", "1") not in ("1", "2"):
        raise _ColumnProblem("invalid", "fact INPUT gdir/berry_phase/nspin is inconsistent")
    rows = raw.get("rows")
    if not isinstance(rows, Mapping) or set(rows) != {_ROW_Q, _ROW_P, _ROW_SI}:
        raise _ColumnProblem("invalid", "fact requires exactly three native polarization unit rows")
    q = _validate_row(rows[_ROW_Q], _ROW_Q)
    p = _validate_row(rows[_ROW_P], _ROW_P)
    si = _validate_row(rows[_ROW_SI], _ROW_SI)
    cell_bohr = cell / BOHR_TO_ANG
    volume = abs(float(np.linalg.det(cell_bohr)))
    lattice = cell_bohr[gdir - 1]
    norm = float(np.linalg.norm(lattice))
    unit_vector = lattice / norm
    # Producer modulus is one or two lattice-vector lengths, depending on
    # occupancy parity and spin. The parity itself is not in the printout.
    allowed_multiples = (1,) if params.get("nspin", "1") == "2" else (1, 2)
    if min(abs(q["modulus"] - multiple * norm) for multiple in allowed_multiples) > max(_PRINT_TOL, norm * 2e-7):
        raise _ColumnProblem("invalid", "printed quantum disagrees with lattice direction")
    if np.max(np.abs(q["cartesian"] - q["scalar"] * unit_vector)) > max(_PRINT_TOL, abs(q["scalar"]) * 2e-7):
        raise _ColumnProblem("invalid", "printed Cartesian vector disagrees with scalar and lattice direction")
    if abs(p["scalar"] - q["scalar"] / volume) > max(_PRINT_TOL, abs(p["scalar"]) * 2e-7):
        raise _ColumnProblem("invalid", "e/bohr^2 scalar disagrees with first unit row and volume")
    if abs(p["modulus"] - q["modulus"] / volume) > max(_PRINT_TOL, abs(p["modulus"]) * 2e-7):
        raise _ColumnProblem("invalid", "e/bohr^2 modulus disagrees with first unit row and volume")
    if np.max(np.abs(p["cartesian"] - q["cartesian"] / volume)) > max(_PRINT_TOL, np.max(np.abs(p["cartesian"])) * 2e-7):
        raise _ColumnProblem("invalid", "e/bohr^2 Cartesian row disagrees with first unit row and volume")
    si_tolerance = _SOURCE_SI_FACTOR * _PRINT_TOL + _PRINT_TOL
    if (abs(si["scalar"] - q["scalar"] / volume * _SOURCE_SI_FACTOR) > si_tolerance
            or abs(si["modulus"] - q["modulus"] / volume * _SOURCE_SI_FACTOR) > si_tolerance
            or np.max(np.abs(si["cartesian"] - q["cartesian"] / volume * _SOURCE_SI_FACTOR)) > si_tolerance):
        raise _ColumnProblem("invalid", "C/m^2 row disagrees with printed first unit row")
    return {"gdir": gdir, "cell": cell, "positions": positions, "symbols": symbols,
            "labels": labels, "moves": moves, "species": dict(species), "input": dict(params),
            "scalar": q["scalar"], "quantum": q["modulus"], "vector": q["cartesian"],
            "unit_vector": unit_vector}


def _validate_row(raw: Any, unit: str) -> dict:
    if not isinstance(raw, Mapping) or raw.get("unit") != unit:
        raise _ColumnProblem("invalid", f"fact has mislabeled {unit} row")
    scalar, modulus = raw.get("scalar"), raw.get("modulus")
    if not _number(scalar) or not _number(modulus) or modulus <= 0:
        raise _ColumnProblem("invalid", f"fact has invalid {unit} scalar or modulus")
    return {"scalar": float(scalar), "modulus": float(modulus),
            "cartesian": _array(raw.get("cartesian"), (3,), f"{unit} Cartesian vector")}


def _same_sample_facts(facts: Mapping[int, dict]) -> None:
    reference = facts[1]
    for fact in (facts[2], facts[3]):
        if not _same_identity(reference, fact) or np.max(np.abs(reference["positions"] - fact["positions"])) > _GEOMETRY_TOL_ANG:
            raise _ColumnProblem("invalid", "gdir facts within a sample describe different structure or INPUT")


def _validate_path_geometry(samples: list[dict], atom_index: int, axis: int) -> dict:
    first = samples[0]["facts"][1]
    if atom_index > len(first["positions"]):
        raise _ColumnProblem("invalid", "atom_index exceeds structure atom count")
    origin = first["positions"].copy()
    origin[atom_index - 1, axis] -= samples[0]["displacement"]
    for item in samples:
        fact = item["facts"][1]
        if not _same_identity(first, fact):
            raise _ColumnProblem("invalid", "samples differ in cell, atom order, species references or INPUT")
        expected = origin.copy()
        expected[atom_index - 1, axis] += item["displacement"]
        if np.max(np.abs(expected - fact["positions"])) > _GEOMETRY_TOL_ANG:
            raise _ColumnProblem("invalid", "sample geometry differs beyond declared Cartesian displacement")
    return {"cell": first["cell"], "positions": origin, "symbols": first["symbols"],
            "labels": first["labels"], "moves": first["moves"], "species": first["species"],
            "input": {k: v for k, v in first["input"].items() if k != "gdir"}}


def _validate_quantum_path(samples: list[dict]) -> None:
    for gdir in (1, 2, 3):
        reference = samples[0]["facts"][gdir]["quantum"]
        for item in samples[1:]:
            candidate = item["facts"][gdir]["quantum"]
            if abs(candidate - reference) > max(_PRINT_TOL, reference * 2e-7):
                raise _ColumnProblem("invalid", f"gdir {gdir} printed quantum changes across path")


def _offsets_explicit(samples: list[dict]) -> list[dict]:
    trace = []
    for item in samples:
        item["selected_offsets"] = {gdir: item["offsets"][str(gdir)] for gdir in (1, 2, 3)}
        for gdir in (1, 2, 3):
            trace.append({"displacement_angstrom": item["displacement"], "gdir": gdir,
                          "fact_path_rel": item["facts"][gdir]["path"],
                          "offset": item["selected_offsets"][gdir], "method": "manual_offsets",
                          "reference_displacement_angstrom": None, "bound_fraction": None})
    return trace


def _offsets_auto(samples: list[dict], zero: dict, bound: float) -> list[dict]:
    zero["selected_offsets"] = {1: 0, 2: 0, 3: 0}
    trace = [{"displacement_angstrom": 0.0, "gdir": gdir,
              "fact_path_rel": zero["facts"][gdir]["path"], "offset": 0,
              "method": "conditional_continuity", "reference_displacement_angstrom": None,
              "bound_fraction": bound} for gdir in (1, 2, 3)]
    for branch in (
        sorted((item for item in samples if item["displacement"] < 0), key=lambda i: -i["displacement"]),
        sorted((item for item in samples if item["displacement"] > 0), key=lambda i: i["displacement"]),
    ):
        previous = zero
        for item in branch:
            item["selected_offsets"] = {}
            for gdir in (1, 2, 3):
                fact = item["facts"][gdir]
                prior = previous["facts"][gdir]
                quantum = fact["quantum"]
                prior_corrected = prior["scalar"] + previous["selected_offsets"][gdir] * prior["quantum"]
                center = (prior_corrected - fact["scalar"]) / quantum
                nearest = math.floor(center + 0.5)
                candidates = []
                near_boundary = False
                for offset in range(nearest - 2, nearest + 3):
                    change = fact["scalar"] + offset * quantum - prior_corrected
                    precision = (2 + abs(offset) + abs(previous["selected_offsets"][gdir])) * _PRINT_TOL
                    if abs(change) < bound * quantum - precision:
                        candidates.append(offset)
                    elif abs(change) <= bound * quantum + precision:
                        near_boundary = True
                if near_boundary or len(candidates) != 1:
                    raise _ColumnProblem("ambiguous", f"gdir {gdir} branch step from {previous['displacement']} to {item['displacement']} has no unique offset within caller bound")
                offset = candidates[0]
                item["selected_offsets"][gdir] = offset
                trace.append({"displacement_angstrom": item["displacement"], "gdir": gdir,
                              "fact_path_rel": fact["path"], "offset": offset,
                              "method": "conditional_continuity",
                              "reference_displacement_angstrom": previous["displacement"],
                              "bound_fraction": bound})
            previous = item
    return trace


def _same_identity(a: dict, b: dict) -> bool:
    return (a["cell"].shape == b["cell"].shape
            and np.max(np.abs(a["cell"] - b["cell"])) <= _GEOMETRY_TOL_ANG
            and a["positions"].shape == b["positions"].shape
            and a["symbols"] == b["symbols"] and a["labels"] == b["labels"]
            and a["species"] == b["species"] and a["moves"] == b["moves"]
            and {k: v for k, v in a["input"].items() if k != "gdir"}
            == {k: v for k, v in b["input"].items() if k != "gdir"})


def _same_baseline(a: dict, b: dict) -> bool:
    return (_same_identity(a, b) and np.max(np.abs(a["positions"] - b["positions"])) <= _GEOMETRY_TOL_ANG)


def _array(value: Any, shape: tuple[int, ...], label: str) -> np.ndarray:
    try:
        array = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise _ColumnProblem("invalid", f"invalid {label}") from exc
    if array.shape != shape or not np.isfinite(array).all():
        raise _ColumnProblem("invalid", f"invalid {label}")
    return array


def _number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)
