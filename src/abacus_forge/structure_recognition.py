"""Structure format detection and metadata helpers."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from ase import Atoms

ZERO_WIDTH_CHARS = ("\ufeff", "\u200b", "\u200c", "\u200d", "\u2060")


@dataclass(slots=True)
class StructureMetadata:
    """Normalized structure facts used by prepare and collect."""

    structure_class: str
    formula: str
    elements: list[str]
    species_counts: dict[str, int]
    atom_count: int
    pbc: list[bool]
    cell_parameters: dict[str, float] | None
    volume: float | None
    density: float | None
    symmetry: dict[str, Any]
    vacuum_axes: list[int]
    vacuum_thickness: dict[int, float]
    layer_info: dict[str, int] | None
    string_info: dict[str, int] | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def clean_text(text: str) -> str:
    """Remove invisible characters and normalize newlines."""

    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    for char in ZERO_WIDTH_CHARS:
        cleaned = cleaned.replace(char, "")
    return cleaned


def _read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig"):
        try:
            return clean_text(path.read_text(encoding=encoding))
        except UnicodeDecodeError:
            continue
    return clean_text(path.read_text(encoding="utf-8", errors="ignore"))


def detect_structure_format(path: str | Path, text: str | None = None) -> str:
    """Infer the structure format from path and content."""

    candidate = Path(path)
    payload = text if text is not None else (_read_text(candidate) if candidate.is_file() else "")
    name_upper = candidate.name.upper()
    suffix = candidate.suffix.lower()

    if name_upper == "STRU" or suffix == ".stru":
        return "stru"
    if name_upper in {"POSCAR", "CONTCAR"} or suffix in {".vasp", ".poscar", ".contcar"}:
        return "poscar"
    if suffix == ".cif":
        return "cif"
    if suffix == ".xyz":
        return "xyz"

    lines = [line.strip() for line in payload.splitlines() if line.strip()]
    if not lines:
        return "unknown"

    markers = ("LATTICE_CONSTANT", "ATOMIC_SPECIES", "LATTICE_VECTORS", "ATOMIC_POSITIONS")
    if sum(marker in payload for marker in markers) >= 3:
        return "stru"

    if any(line.lower().startswith("data_") for line in lines[:20]) or "_atom_site_" in payload:
        return "cif"

    if len(lines) >= 7 and _is_float(lines[1]):
        cell_lines = lines[2:5]
        if all(len(parts := line.split()) >= 3 and all(_is_float(token) for token in parts[:3]) for line in cell_lines):
            return "poscar"

    return "unknown"


def detect_vacuum_info(atoms: Atoms, vacuum_detect_thr: float = 6.0) -> tuple[dict[int, float], list[bool], np.ndarray]:
    """Detect vacuum thickness along each crystal axis."""

    centered = atoms.copy()
    centered.center()
    cell = np.array(centered.get_cell())
    lengths = np.linalg.norm(cell, axis=1)
    positions = centered.get_positions()
    spans = np.array([positions[:, axis].max() - positions[:, axis].min() for axis in range(3)])
    vacuum_axes = [bool(spans[idx] <= (lengths[idx] - vacuum_detect_thr)) for idx in range(3)]
    vacuum_map = {idx: float(lengths[idx] - spans[idx]) for idx, is_vacuum in enumerate(vacuum_axes) if is_vacuum}
    return vacuum_map, vacuum_axes, lengths


def get_structure_metadata(
    atoms: Atoms,
    *,
    vacuum_detect_thr: float = 6.0,
    cubic_min_length: float = 9.8,
    symprec_decimal: int = 2,
) -> StructureMetadata:
    """Extract normalized structure facts from an ASE structure."""

    symbols = atoms.get_chemical_symbols()
    counts = Counter(symbols)
    pbc = [bool(value) for value in atoms.get_pbc()]
    volume = float(atoms.get_volume()) if all(pbc) else None
    molar_mass = float(sum(atom.mass for atom in atoms))
    density = float((molar_mass * 1.66054) / volume) if volume else None
    cellpar = atoms.cell.cellpar()
    cell_parameters = None
    if np.linalg.norm(atoms.get_cell()) > 0:
        cell_parameters = {
            "a": float(cellpar[0]),
            "b": float(cellpar[1]),
            "c": float(cellpar[2]),
            "alpha": float(cellpar[3]),
            "beta": float(cellpar[4]),
            "gamma": float(cellpar[5]),
        }

    vacuum_map: dict[int, float] = {}
    layer_info: dict[str, int] | None = None
    string_info: dict[str, int] | None = None
    structure_class = "unknown"

    if all(pbc):
        vacuum_map, vacuum_axes, lengths = detect_vacuum_info(atoms, vacuum_detect_thr=vacuum_detect_thr)
        vacuum_count = sum(vacuum_axes)
        if vacuum_count == 0:
            structure_class = "bulk"
        elif vacuum_count == 1:
            structure_class = "layer"
            vacuum_axis = [idx for idx, is_vacuum in enumerate(vacuum_axes) if is_vacuum][0]
            in_plane = [idx for idx, is_vacuum in enumerate(vacuum_axes) if not is_vacuum]
            if len(in_plane) == 2:
                len_a, len_b = float(lengths[in_plane[0]]), float(lengths[in_plane[1]])
                long_axis, short_axis = (in_plane[0], in_plane[1]) if len_a >= len_b else (in_plane[1], in_plane[0])
                layer_info = {"vacuum_axis": vacuum_axis, "long_axis": long_axis, "short_axis": short_axis}
        elif vacuum_count == 2:
            structure_class = "string"
            extension_axis = [idx for idx, is_vacuum in enumerate(vacuum_axes) if not is_vacuum]
            if len(extension_axis) == 1:
                string_info = {"extension_axis": extension_axis[0]}
        elif vacuum_count == 3:
            structure_class = "cluster"
            if _is_cubic_cluster(lengths, np.array(atoms.get_cell()), cubic_min_length, symprec_decimal):
                structure_class = "cubic_cluster"
    else:
        vacuum_axes = [False, False, False]

    symmetry = {
        "spacegroup_number": None,
        "spacegroup_symbol": None,
        "crystal_system": None,
        "point_group": None,
    }
    try:
        from pymatgen.io.ase import AseAtomsAdaptor
        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

        structure = AseAtomsAdaptor.get_structure(
            Atoms(
                symbols=atoms.get_chemical_symbols(),
                positions=atoms.get_positions(),
                cell=atoms.get_cell(),
                pbc=atoms.get_pbc(),
            )
        )
        analyzer = SpacegroupAnalyzer(structure, symprec=10 ** (-symprec_decimal))
        symmetry = {
            "spacegroup_number": analyzer.get_space_group_number(),
            "spacegroup_symbol": analyzer.get_space_group_symbol(),
            "crystal_system": analyzer.get_crystal_system(),
            "point_group": analyzer.get_point_group_symbol(),
        }
    except Exception:
        pass

    return StructureMetadata(
        structure_class=structure_class,
        formula=atoms.get_chemical_formula(),
        elements=sorted(counts),
        species_counts=dict(sorted(counts.items())),
        atom_count=len(atoms),
        pbc=pbc,
        cell_parameters=cell_parameters,
        volume=volume,
        density=density,
        symmetry=symmetry,
        vacuum_axes=sorted(vacuum_map),
        vacuum_thickness=vacuum_map,
        layer_info=layer_info,
        string_info=string_info,
    )


def _is_cubic_cluster(lengths: np.ndarray, cell: np.ndarray, min_length: float, decimals: int) -> bool:
    diagonal = np.diag(cell)
    return (
        round(float(diagonal[0]), decimals) == round(float(diagonal[1]), decimals) == round(float(diagonal[2]), decimals)
        and round(float(np.min(np.abs(cell[np.triu_indices(3, 1)]))), decimals) == 0.0
        and float(np.min(lengths)) >= float(min_length)
    )


def _is_float(token: str) -> bool:
    try:
        float(token)
        return True
    except Exception:
        return False
