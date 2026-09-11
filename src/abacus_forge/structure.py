"""Structure input, conversion, and normalization helpers."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from ase import Atoms
from ase.data import chemical_symbols
from ase.io import read as ase_read

from abacus_forge.errors import ForgeRequestError
from abacus_forge.structure_recognition import StructureMetadata, detect_structure_format, get_structure_metadata

BOHR_TO_ANG = 0.529177210903
_NATIVE_LATTICE_CONSTANT_BOHR = 1.0 / BOHR_TO_ANG


class UnsupportedCoordinateModeError(ForgeRequestError):
    """The STRU coordinate mode is not supported by the Forge reader."""


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

        if isinstance(value, str) and detect_structure_format("inline", text=value) == "stru":
            return cls(_read_stru_text(value), source_format="stru")

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
        return self._standardize(symprec, conventional=True)

    def conventional_to_primitive(self, symprec: float = 1e-3) -> "AbacusStructure":
        return self._standardize(symprec, conventional=False)

    def _standardize(self, symprec: float, *, conventional: bool) -> "AbacusStructure":
        try:
            from pymatgen.io.ase import AseAtomsAdaptor
            from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
        except Exception as exc:
            raise RuntimeError("pymatgen is required for primitive/conventional conversion") from exc
        _validate_standardization_metadata(self.atoms)
        structure = AseAtomsAdaptor.get_structure(self.atoms)
        analyzer = SpacegroupAnalyzer(structure, symprec=symprec)
        standardized = (
            analyzer.get_conventional_standard_structure(keep_site_properties=True)
            if conventional
            else analyzer.find_primitive(keep_site_properties=True)
        )
        converted = self.atoms.copy() if standardized is None else AseAtomsAdaptor.get_atoms(standardized)
        # Pymatgen retains site arrays but standardization discards Structure.properties.
        converted.info["abacus_species_meta"] = deepcopy(_species_metadata(self.atoms))
        converted.info["abacus_move_flags"] = [[1, 1, 1] for _ in converted]
        return AbacusStructure(converted, source_format=self.source_format)

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
        repeated = self.atoms.repeat(repeats)
        source_move_flags = self.atoms.info.get("abacus_move_flags")
        if isinstance(source_move_flags, list) and len(source_move_flags) == len(self.atoms):
            repeated.info["abacus_move_flags"] = [
                list(flag)
                for _ in range(int(np.prod(repeats)))
                for flag in source_move_flags
            ]
        source_labels = self.atoms.info.get("abacus_atom_labels")
        if isinstance(source_labels, list) and len(source_labels) == len(self.atoms):
            repeated.info["abacus_atom_labels"] = [
                label
                for _ in range(int(np.prod(repeats)))
                for label in source_labels
            ]
        return AbacusStructure(repeated, source_format=self.source_format)

    def to_stru(
        self,
        *,
        pp_map: dict[str, str] | None = None,
        orb_map: dict[str, str] | None = None,
    ) -> str:
        atoms = self.atoms
        order = np.argsort(atoms.get_atomic_numbers(), kind="stable")
        symbols = [atoms[idx].symbol for idx in order]
        labels_info = atoms.info.get("abacus_atom_labels")
        if isinstance(labels_info, list) and len(labels_info) == len(atoms):
            labels = [str(labels_info[idx]) for idx in order]
        else:
            labels = symbols.copy()
        species = list(OrderedDict.fromkeys(labels))
        species_meta = _species_metadata(atoms)
        masses: dict[str, float] = {}
        element_by_label = dict(zip(labels, symbols, strict=False))
        for label, atom in zip(labels, (atoms[idx] for idx in order), strict=False):
            masses.setdefault(label, float(atom.mass))
        pp_values = {
            label: _resolved_species_value(
                label, "pp", pp_map, species_meta, element=element_by_label[label]
            )
            for label in species
        }
        orbital_values = {
            label: _resolved_species_value(
                label, "orb", orb_map, species_meta, element=element_by_label[label]
            )
            for label in species
        }
        if any(orbital_values.values()) and not all(orbital_values.values()):
            raise ForgeRequestError(
                "NUMERICAL_ORBITAL requires an orbital reference for every species"
            )
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
        for label in species:
            pp = pp_values[label]
            lines.append(f"{label} {masses[label]:.6f} {pp}".rstrip())
        if all(orbital_values.values()) and orbital_values:
            lines.extend(["", "NUMERICAL_ORBITAL"])
            for label in species:
                lines.append(orbital_values[label])

        lines.extend(
            [
                "",
                "LATTICE_CONSTANT",
                f"{_NATIVE_LATTICE_CONSTANT_BOHR:.12f}",
                "",
                "LATTICE_VECTORS",
            ]
        )
        for vector in atoms.get_cell():
            lines.append(" ".join(f"{float(component):.12f}" for component in vector))

        lines.extend(["", "ATOMIC_POSITIONS", "Direct"])
        for label in species:
            idxs = [idx for idx, atom_label in enumerate(labels) if atom_label == label]
            species_magmoms = [float(magmoms[idx]) for idx in idxs]
            write_site_magmoms = bool(species_magmoms) and not np.allclose(
                species_magmoms,
                np.full(len(species_magmoms), species_magmoms[0]),
            )
            lines.append(label)
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


def _validate_standardization_metadata(atoms: Atoms) -> None:
    """Reject metadata that geometric symmetry may merge or rotate ambiguously."""
    labels = atoms.info.get("abacus_atom_labels")
    if isinstance(labels, list) and len(labels) == len(atoms):
        if any(str(label) != atom.symbol for label, atom in zip(labels, atoms, strict=False)):
            raise ForgeRequestError("standardization cannot preserve ABACUS atom labels")
    if atoms.constraints:
        raise ForgeRequestError("standardization cannot preserve ASE constraints")
    move_flags = atoms.info.get("abacus_move_flags")
    if move_flags is not None:
        flags = np.asarray(move_flags)
        if flags.shape != (len(atoms), 3) or not np.all(flags == 1):
            raise ForgeRequestError("standardization requires all-movable move flags")

    symbols = np.asarray(atoms.get_chemical_symbols())
    for name, values in (
        ("masses", atoms.get_masses()),
        ("magnetic moments", atoms.get_initial_magnetic_moments()),
    ):
        for symbol in dict.fromkeys(symbols):
            species_values = values[symbols == symbol]
            # Pymatgen chooses one representative per species, even for AFM input.
            # Exact equality avoids silently rounding away supplied site differences.
            if not np.all(species_values == species_values[0]):
                raise ForgeRequestError(
                    f"standardization cannot preserve different {name} for species {symbol}"
                )


def _species_metadata(atoms: Atoms) -> dict[str, Mapping[str, str | float]]:
    metadata = atoms.info.get("abacus_species_meta")
    if not isinstance(metadata, Mapping):
        return {}
    return {
        str(symbol): values
        for symbol, values in metadata.items()
        if isinstance(values, Mapping)
    }


def _resolved_species_value(
    symbol: str,
    field: str,
    overrides: Mapping[str, str] | None,
    metadata: Mapping[str, Mapping[str, str | float]],
    *,
    element: str | None = None,
) -> str:
    if overrides is not None:
        override = overrides.get(symbol)
        if override is None and element is not None:
            override = overrides.get(element)
        if override is not None and str(override).strip():
            return str(override)
    source_value = metadata.get(symbol, {}).get(field, "")
    if source_value in (None, "") and element is not None:
        source_value = metadata.get(element, {}).get(field, "")
    return str(source_value) if source_value is not None else ""


def _infer_element_from_label(label: str) -> str:
    """Resolve an ABACUS atom-type label to its ASE chemical element."""

    if len(label) >= 2 and "A" <= label[0] <= "Z" and "a" <= label[1] <= "z":
        candidate = label[:2]
        if candidate in chemical_symbols and candidate != "X":
            return candidate
        raise ValueError(f"cannot determine element for ABACUS atom label {label!r}")
    if not label or not "A" <= label[0] <= "Z":
        raise ValueError(f"cannot determine element for ABACUS atom label {label!r}")
    candidate = label[:1]
    if candidate in chemical_symbols and candidate != "X":
        return candidate
    raise ValueError(f"cannot determine element for ABACUS atom label {label!r}")


def _read_stru(path: Path) -> Atoms:
    return _read_stru_text(path.read_text(encoding="utf-8", errors="ignore"))


def _read_stru_text(text: str) -> Atoms:
    lines = [line.rstrip("\n") for line in text.splitlines()]
    species_meta: dict[str, dict[str, str | float]] = {}
    lattice_constant = 1.0
    lattice_unit = "bohr"
    lattice_vectors: list[list[float]] = []
    coordinate_mode = "direct"
    positions: list[list[float]] = []
    symbols: list[str] = []
    atom_labels: list[str] = []
    magmoms: list[float] = []
    move_flags: list[list[int]] = []

    index = 0
    while index < len(lines):
        # ABACUS native output annotates section headers (for example
        # ``LATTICE_VECTORS  # in units of lat0``).  Parse the directive
        # before the comment; atom labels are handled in the positional block.
        stripped = _first_token(lines[index])
        if not stripped or stripped.startswith("#"):
            index += 1
            continue

        if stripped == "ATOMIC_SPECIES":
            index += 1
            while index < len(lines):
                parts = _tokens_before_comment(lines[index], min_fields=2)
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
                parts = _tokens_before_comment(lines[index], min_fields=1)
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
            lattice_constant = float(_tokens_before_comment(lines[index + 1], min_fields=1)[0])
            index += 2
            continue

        if stripped == "LATTICE_CONSTANT_UNIT":
            lattice_unit = _tokens_before_comment(lines[index + 1], min_fields=1)[0].lower()
            index += 2
            continue

        if stripped == "LATTICE_VECTORS":
            lattice_vectors = []
            for offset in range(1, 4):
                lattice_vectors.append(
                    [
                        float(token)
                        for token in _tokens_before_comment(lines[index + offset], min_fields=3)[:3]
                    ]
                )
            index += 4
            continue

        if stripped == "ATOMIC_POSITIONS":
            coordinate_tokens = _tokens_before_comment(lines[index + 1], min_fields=1)
            coordinate_mode = coordinate_tokens[0].lower() if coordinate_tokens else ""
            index += 2
            while index < len(lines):
                symbol = _first_token(lines[index])
                if not symbol:
                    index += 1
                    continue
                if symbol.isupper() and symbol in {"LATTICE_CONSTANT", "LATTICE_VECTORS", "NUMERICAL_ORBITAL"}:
                    break
                species_mag = float(_tokens_before_comment(lines[index + 1], min_fields=1)[0])
                count = int(float(_tokens_before_comment(lines[index + 2], min_fields=1)[0]))
                index += 3
                for _ in range(count):
                    parts = _tokens_before_comment(lines[index], min_fields=3)
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
                    atom_labels.append(symbol)
                    symbols.append(_infer_element_from_label(symbol))
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
    if coordinate_mode == "cartesian_angstrom":
        atoms = Atoms(symbols=symbols, positions=coords, cell=cell, pbc=[True, True, True])
    elif coordinate_mode == "cartesian_au":
        atoms = Atoms(symbols=symbols, positions=coords * BOHR_TO_ANG, cell=cell, pbc=[True, True, True])
    elif coordinate_mode == "cartesian":
        atoms = Atoms(symbols=symbols, positions=coords * scale, cell=cell, pbc=[True, True, True])
    elif coordinate_mode == "direct":
        atoms = Atoms(symbols=symbols, scaled_positions=coords, cell=cell, pbc=[True, True, True])
    else:
        raise UnsupportedCoordinateModeError(
            f"unsupported coordinate mode: {coordinate_mode or '<empty>'}"
        )
    atoms.set_masses([float(species_meta[label]["mass"]) for label in atom_labels])
    atoms.set_initial_magnetic_moments(magmoms)
    atoms.info["abacus_move_flags"] = move_flags
    atoms.info["abacus_atom_labels"] = atom_labels
    atoms.info["abacus_species_meta"] = species_meta
    return atoms


def _first_token(line: str) -> str:
    """Return the first field, treating standalone comment lines as empty."""

    parts = line.split()
    if not parts or _is_comment_start(parts[0]):
        return ""
    return parts[0]


def _tokens_before_comment(line: str, *, min_fields: int) -> list[str]:
    """Keep fields before an inline comment without rewriting asset tokens.

    ``min_fields`` protects the fields whose contents may legitimately contain
    ``#`` or ``//`` (for example ``Si#test.orb`` and ``pp//Si.upf``).  Comment
    markers are recognized only after those fields have been read.
    """

    parts = line.split()
    if not parts or _is_comment_start(parts[0]):
        return []
    for index, token in enumerate(parts):
        if index >= min_fields and _is_comment_start(token):
            return parts[:index]
    return parts


def _is_comment_start(token: str) -> bool:
    return token.startswith("#") or token.startswith("//")


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
