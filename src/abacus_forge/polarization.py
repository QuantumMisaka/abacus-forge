"""Parse one native ABACUS Berry-phase block into source-bound facts.

The parser preserves the three printed unit rows. It does not select a
polarization branch or decide whether the underlying calculation converged.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np

from abacus_forge.input_io import read_input
from abacus_forge.structure import AbacusStructure


_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"
_DIRECTION = re.compile(r"The calculated polarization direction is in R(\d+) direction", re.I)
_IONIC = re.compile(rf"The Ionic Phase:\s*({_NUMBER})", re.I)
_ELECTRONIC = re.compile(rf"Electronic Phase:\s*({_NUMBER})", re.I)
_ROW = re.compile(
    rf"^\s*P\s*=\s*({_NUMBER})\s*\(mod\s*({_NUMBER})\)\s*"
    rf"\(\s*({_NUMBER})\s*,\s*({_NUMBER})\s*,\s*({_NUMBER})\s*\)\s*"
    r"(\(e/Omega\)\.bohr|e/bohr\^2|C/m\^2)\s*$",
    re.I,
)
_UNITS = ("(e/Omega).bohr", "e/bohr^2", "C/m^2")


def collect_polarization_facts(log_path: Path, structure_path: Path, input_path: Path) -> dict:
    """Read admitted log/STRU/INPUT paths and return one JSON-safe fact record.

    Path containment and artifact provenance belong to the calling service.
    Missing files raise ``OSError`` and malformed data raise ``ValueError``.
    """
    log_path = Path(log_path)
    text = log_path.read_text(encoding="utf-8")
    markers = list(re.finditer(r"\bVALUES OF POLARIZATION\b", text, flags=re.I))
    if len(markers) != 1:
        raise ValueError("expected exactly one VALUES OF POLARIZATION block")
    block = text[markers[0].end():]
    direction = _one(_DIRECTION, block, "gdir")
    gdir = int(direction)
    if gdir not in (1, 2, 3):
        raise ValueError(f"unsupported polarization gdir {gdir}")
    ionic = _finite(_one(_IONIC, block, "ionic phase"), "ionic phase")
    electronic = _finite(_one(_ELECTRONIC, block, "electronic phase"), "electronic phase")

    rows: dict[str, dict] = {}
    printed_rows = 0
    for line in block.splitlines():
        if re.match(r"^\s*P\s*=", line):
            printed_rows += 1
        match = _ROW.fullmatch(line)
        if match is None:
            continue
        scalar, modulus, x, y, z, printed_unit = match.groups()
        unit = next((candidate for candidate in _UNITS if candidate.lower() == printed_unit.lower()), None)
        if unit is None or unit in rows:
            raise ValueError("duplicate or unsupported polarization unit row")
        rows[unit] = {
            "unit": unit,
            "scalar": _finite(scalar, "polarization scalar"),
            "modulus": _finite(modulus, "polarization modulus"),
            "cartesian": [_finite(value, "Cartesian polarization") for value in (x, y, z)],
            "source_log_path": log_path.name,
        }
        if rows[unit]["modulus"] <= 0:
            raise ValueError("polarization modulus must be positive")
    if printed_rows != 3 or set(rows) != set(_UNITS):
        raise ValueError(f"missing or malformed polarization unit row: {sorted(set(_UNITS) - set(rows))}")

    params = read_input(input_path)
    try:
        input_gdir = int(params["gdir"])
        spin = int(params.get("nspin", "1"))
        berry = int(params["berry_phase"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("INPUT requires integer gdir, nspin, berry_phase") from exc
    if input_gdir != gdir:
        raise ValueError("INPUT gdir disagrees with native polarization record")
    if spin not in (1, 2) or berry != 1:
        raise ValueError("polarization requires berry_phase=1 and nspin=1 or 2")

    atoms = AbacusStructure.from_input(Path(structure_path), structure_format="stru").atoms
    cell = np.asarray(atoms.get_cell(), dtype=float)
    positions = np.asarray(atoms.get_positions(), dtype=float)
    if cell.shape != (3, 3) or not np.isfinite(cell).all() or abs(np.linalg.det(cell)) < 1e-8:
        raise ValueError("STRU has invalid or singular cell")
    if positions.shape != (len(atoms), 3) or not len(atoms) or not np.isfinite(positions).all():
        raise ValueError("STRU has invalid atom positions")
    info = atoms.info
    return {
        "schema_version": "forge.polarization/v1",
        "source_log_path": log_path.name,
        "gdir": gdir,
        "ionic_phase": ionic,
        "electronic_phase": electronic,
        "rows": {unit: rows[unit] for unit in _UNITS},
        "geometry": {
            "cell_angstrom": cell.tolist(),
            "positions_angstrom": positions.tolist(),
            "symbols": atoms.get_chemical_symbols(),
            "atom_labels": list(info.get("abacus_atom_labels", atoms.get_chemical_symbols())),
            "species_meta": dict(info.get("abacus_species_meta", {})),
            "move_flags": list(info.get("abacus_move_flags", [[1, 1, 1] for _ in atoms])),
        },
        "input": params,
    }


def _one(pattern: re.Pattern[str], text: str, label: str) -> str:
    matches = pattern.findall(text)
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {label} in polarization block")
    return matches[0]


def _finite(value: str, label: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"nonfinite {label}")
    return result
