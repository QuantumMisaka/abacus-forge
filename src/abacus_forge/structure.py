"""Structure input, conversion, and normalization helpers."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from ase import Atoms
from ase.io import read as ase_read

from abacus_forge.structure_recognition import StructureMetadata, detect_structure_format, get_structure_metadata

BOHR_TO_ANG = 0.529177210903


@dataclass(slots=True)
class AbacusStructure:
    """Normalized structure wrapper for Forge."""

    atoms: Atoms
    source_format: str

    @classmethod
    def from_input(
        cls,
        value: str | Path | Atoms | "AbacusStructure" | Any,
        *,
        structure_format: str | None = None,
    ) -> "AbacusStructure":
        if isinstance(value, AbacusStructure):
            return value
        if isinstance(value, Atoms):
            return cls(value.copy(), source_format=structure_format or "ase")

        if hasattr(value, "__class__") and value.__class__.__name__ == "Structure":
            try:
                from pymatgen.io.ase import AseAtomsAdaptor

                return cls(AseAtomsAdaptor.get_atoms(value), source_format=structure_format or "pymatgen")
            except Exception as exc:
                raise ValueError("failed to convert pymatgen Structure to ASE Atoms") from exc

        if isinstance(value, Mapping):
            if "cell" in value and "sites" in value:
                cell = value["cell"]
                sites = value["sites"]
                atoms = Atoms(
                    symbols=[site["symbol"] for site in sites],
                    positions=[site["position"] for site in sites],
                    cell=cell,
                    pbc=[True, True, True],
                )
                return cls(atoms, source_format=structure_format or "mapping")

        path = Path(value)
        fmt = (structure_format or detect_structure_format(path)).lower()
        if fmt == "stru":
            return cls(_read_stru(path), source_format="stru")
        if fmt in {"poscar", "cif", "xyz"}:
            return cls(ase_read(path), source_format=fmt)
        raise ValueError(f"unsupported structure format: {fmt}")

    def metadata(
        self,
        *,
        vacuum_detect_thr: float = 6.0,
        cubic_min_length: float = 9.8,
        symprec_decimal: int = 2,
    ) -> StructureMetadata:
        return get_structure_metadata(
            self.atoms,
            vacuum_detect_thr=vacuum_detect_thr,
            cubic_min_length=cubic_min_length,
            symprec_decimal=symprec_decimal,
        )

    def ensure_3d_pbc(self, vacuum: float = 10.0) -> "AbacusStructure":
        boxed = self.atoms.copy()
        boxed.set_pbc([True, True, True])
        boxed.center(vacuum=float(vacuum / 2.0))
        return AbacusStructure(boxed, source_format=self.source_format)

    def primitive_to_conventional(self, symprec: float = 1e-3) -> "AbacusStructure":
        try:
            from pymatgen.io.ase import AseAtomsAdaptor
            from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
        except Exception as exc:
            raise RuntimeError("pymatgen is required for primitive/conventional conversion") from exc
        structure = AseAtomsAdaptor.get_structure(self.atoms)
        analyzer = SpacegroupAnalyzer(structure, symprec=symprec)
        converted = AseAtomsAdaptor.get_atoms(analyzer.get_conventional_standard_structure())
        return AbacusStructure(converted, source_format=self.source_format)

    def conventional_to_primitive(self, symprec: float = 1e-3) -> "AbacusStructure":
        try:
            from pymatgen.io.ase import AseAtomsAdaptor
            from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
        except Exception as exc:
            raise RuntimeError("pymatgen is required for primitive/conventional conversion") from exc
        structure = AseAtomsAdaptor.get_structure(self.atoms)
        analyzer = SpacegroupAnalyzer(structure, symprec=symprec)
        primitive = analyzer.find_primitive()
        if primitive is None:
            return AbacusStructure(self.atoms.copy(), source_format=self.source_format)
        return AbacusStructure(AseAtomsAdaptor.get_atoms(primitive), source_format=self.source_format)

    def swap_axes(self, axis_a: int, axis_b: int) -> "AbacusStructure":
        if axis_a == axis_b:
            return AbacusStructure(self.atoms.copy(), source_format=self.source_format)
        swapped = self.atoms.copy()
        cellpar = swapped.get_cell().cellpar()
        new_cellpar = cellpar.copy()
        new_cellpar[axis_a], new_cellpar[axis_b] = cellpar[axis_b], cellpar[axis_a]
        new_cellpar[axis_a + 3], new_cellpar[axis_b + 3] = cellpar[axis_b + 3], cellpar[axis_a + 3]
        scaled = swapped.get_scaled_positions()
        new_scaled = scaled.copy()
        new_scaled[:, axis_a], new_scaled[:, axis_b] = scaled[:, axis_b], scaled[:, axis_a].copy()
        swapped.set_cell(new_cellpar)
        swapped.set_scaled_positions(new_scaled)
        return AbacusStructure(swapped, source_format=self.source_format)

    def make_supercell(self, repeats: tuple[int, int, int] | list[int]) -> "AbacusStructure":
        return AbacusStructure(self.atoms.repeat(repeats), source_format=self.source_format)

    def to_stru(
        self,
        *,
        pp_map: dict[str, str] | None = None,
        orb_map: dict[str, str] | None = None,
    ) -> str:
        atoms = self.atoms
        order = np.argsort(atoms.get_atomic_numbers(), kind="stable")
        symbols = [atoms[idx].symbol for idx in order]
        species = list(OrderedDict.fromkeys(symbols))
        masses = {atom.symbol: atom.mass for atom in atoms}
        scaled_positions = atoms.get_scaled_positions(wrap=False)[order]
        magmoms = (
            atoms.get_initial_magnetic_moments()[order]
            if atoms.has("initial_magmoms")
            else np.zeros(len(atoms))
        )
        source_move_flags = atoms.info.get("abacus_move_flags")
        if not isinstance(source_move_flags, list) or len(source_move_flags) != len(atoms):
            source_move_flags = [[1, 1, 1] for _ in range(len(atoms))]
        move_flags = [source_move_flags[idx] for idx in order]

        lines = [
            "ATOMIC_SPECIES",
        ]
        for symbol in species:
            lines.append(f"{symbol} {masses[symbol]:.6f} {pp_map.get(symbol, '') if pp_map else ''}".rstrip())

        lines.extend(
            [
                "",
                "LATTICE_CONSTANT",
                "1.0",
                "LATTICE_CONSTANT_UNIT",
                "Angstrom",
                "",
                "LATTICE_VECTORS",
            ]
        )
        for vector in atoms.get_cell():
            lines.append(" ".join(f"{float(component):.12f}" for component in vector))

        lines.extend(["", "ATOMIC_POSITIONS", "Direct"])
        for symbol in species:
            idxs = [idx for idx, atom_symbol in enumerate(symbols) if atom_symbol == symbol]
            species_magmoms = [float(magmoms[idx]) for idx in idxs]
            write_site_magmoms = bool(species_magmoms) and not np.allclose(
                species_magmoms,
                np.full(len(species_magmoms), species_magmoms[0]),
            )
            lines.append(symbol)
            lines.append(f"{0.0 if write_site_magmoms else (species_magmoms[0] if species_magmoms else 0.0):.8f}")
            lines.append(str(len(idxs)))
            for idx in idxs:
                coords = " ".join(f"{float(component):.12f}" for component in scaled_positions[idx])
                flags = " ".join(str(int(value)) for value in move_flags[idx])
                extras = [f"m {flags}"]
                if write_site_magmoms:
                    extras.append(f"mag {float(magmoms[idx]):.8f}")
                lines.append(f"{coords} {' '.join(extras)}")
        return "\n".join(lines) + "\n"


def _read_stru(path: Path) -> Atoms:
    lines = [line.rstrip("\n") for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()]
    species_meta: dict[str, dict[str, str | float]] = {}
    lattice_constant = 1.0
    lattice_unit = "bohr"
    lattice_vectors: list[list[float]] = []
    coordinate_mode = "direct"
    positions: list[list[float]] = []
    symbols: list[str] = []
    magmoms: list[float] = []
    move_flags: list[list[int]] = []

    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue

        if stripped == "ATOMIC_SPECIES":
            index += 1
            while index < len(lines):
                parts = lines[index].split()
                if not parts:
                    index += 1
                    continue
                if parts[0].isupper() and parts[0] in {"NUMERICAL_ORBITAL", "LATTICE_CONSTANT", "LATTICE_VECTORS", "ATOMIC_POSITIONS", "LATTICE_CONSTANT_UNIT"}:
                    break
                if len(parts) >= 2:
                    symbol = parts[0]
                    mass = float(parts[1])
                    pp = parts[2] if len(parts) >= 3 else ""
                    species_meta[symbol] = {"mass": mass, "pp": pp}
                index += 1
            continue

        if stripped == "NUMERICAL_ORBITAL":
            index += 1
            orbitals = list(species_meta)
            orbital_idx = 0
            while index < len(lines):
                parts = lines[index].split()
                if not parts:
                    index += 1
                    continue
                if parts[0].isupper() and parts[0] in {"LATTICE_CONSTANT", "LATTICE_VECTORS", "ATOMIC_POSITIONS", "LATTICE_CONSTANT_UNIT"}:
                    break
                if orbital_idx < len(orbitals):
                    species_meta[orbitals[orbital_idx]]["orb"] = parts[0]
                    orbital_idx += 1
                index += 1
            continue

        if stripped == "LATTICE_CONSTANT":
            lattice_constant = float(lines[index + 1].split()[0])
            index += 2
            continue

        if stripped == "LATTICE_CONSTANT_UNIT":
            lattice_unit = lines[index + 1].split()[0].lower()
            index += 2
            continue

        if stripped == "LATTICE_VECTORS":
            lattice_vectors = []
            for offset in range(1, 4):
                lattice_vectors.append([float(token) for token in lines[index + offset].split()[:3]])
            index += 4
            continue

        if stripped == "ATOMIC_POSITIONS":
            coordinate_mode = lines[index + 1].strip().lower()
            index += 2
            while index < len(lines):
                symbol = lines[index].strip()
                if not symbol:
                    index += 1
                    continue
                if symbol.isupper() and symbol in {"LATTICE_CONSTANT", "LATTICE_VECTORS", "NUMERICAL_ORBITAL"}:
                    break
                species_mag = float(lines[index + 1].split()[0])
                count = int(float(lines[index + 2].split()[0]))
                index += 3
                for _ in range(count):
                    parts = lines[index].split()
                    coords = [float(token) for token in parts[:3]]
                    move = [1, 1, 1]
                    atom_mag = species_mag
                    cursor = 3
                    while cursor < len(parts):
                        token = parts[cursor].lower()
                        if token == "m" and cursor + 3 < len(parts):
                            move = [int(float(value)) for value in parts[cursor + 1 : cursor + 4]]
                            cursor += 4
                            continue
                        if token in {"mag", "magmom"} and cursor + 1 < len(parts):
                            if cursor + 3 < len(parts) and all(_is_float(value) for value in parts[cursor + 1 : cursor + 4]):
                                cursor += 4
                                continue
                            atom_mag = float(parts[cursor + 1])
                            cursor += 2
                            continue
                        if cursor + 2 < len(parts) and all(_is_int_like(value) for value in parts[cursor : cursor + 3]):
                            move = [int(float(value)) for value in parts[cursor : cursor + 3]]
                            cursor += 3
                            continue
                        cursor += 1
                    positions.append(coords)
                    symbols.append(symbol)
                    magmoms.append(atom_mag)
                    move_flags.append(move)
                    index += 1
            continue

        index += 1

    if lattice_unit.startswith("ang"):
        scale = lattice_constant
    else:
        scale = lattice_constant * BOHR_TO_ANG
    cell = np.array(lattice_vectors, dtype=float) * scale
    coords = np.array(positions, dtype=float)
    if coordinate_mode.startswith("cartesian_angstrom"):
        atoms = Atoms(symbols=symbols, positions=coords, cell=cell, pbc=[True, True, True])
    elif coordinate_mode.startswith("cartesian"):
        atoms = Atoms(symbols=symbols, positions=coords * BOHR_TO_ANG, cell=cell, pbc=[True, True, True])
    else:
        atoms = Atoms(symbols=symbols, scaled_positions=coords, cell=cell, pbc=[True, True, True])
    atoms.set_initial_magnetic_moments(magmoms)
    atoms.info["abacus_move_flags"] = move_flags
    atoms.info["abacus_species_meta"] = species_meta
    return atoms


def _is_float(token: str) -> bool:
    try:
        float(token)
        return True
    except Exception:
        return False


def _is_int_like(token: str) -> bool:
    try:
        value = float(token)
    except Exception:
        return False
    return value.is_integer()
