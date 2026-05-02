"""Analysis helpers for ABACUS DOS-family artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
import re
import xml.etree.ElementTree as ET

import numpy as np

L_MAP = ["s", "p", "d", "f", "g"]
ORBITAL_NAMES: dict[tuple[int, int], str] = {
    (0, 0): "s",
    (1, 0): "p_z",
    (1, 1): "p_x",
    (1, 2): "p_y",
    (2, 0): "d_z2",
    (2, 1): "d_xz",
    (2, 2): "d_yz",
    (2, 3): "d_x2-y2",
    (2, 4): "d_xy",
    (3, 0): "f_z3",
    (3, 1): "f_xz2",
    (3, 2): "f_yz2",
    (3, 3): "f_zx2-zy2",
    (3, 4): "f_xyz",
    (3, 5): "f_x3-3xy2",
    (3, 6): "f_3yx2-y3",
    (4, 0): "g_1",
    (4, 1): "g_2",
    (4, 2): "g_3",
    (4, 3): "g_4",
    (4, 4): "g_5",
    (4, 5): "g_6",
    (4, 6): "g_7",
    (4, 7): "g_8",
    (4, 8): "g_9",
}

_SAMPLE_DOS_TABLES: dict[str, list[list[float]]] = {
    "DOS1_smearing.dat": [[-10.0, 0.0], [-5.0, 0.3], [0.0, 1.2], [5.0, 0.4]],
    "DOS2_smearing.dat": [[-10.0, 0.0], [-5.0, 0.2], [0.0, 1.0], [5.0, 0.5]],
}
_SAMPLE_TDOS_TEXT = "# total DOS\n-1.0 0.1\n0.0 1.0\n1.0 0.2\n"
_SAMPLE_PDOS_XML = """<pdos>
<nspin>1</nspin>
<norbitals>4</norbitals>
<energy_values units="eV">
-1.0
0.0
1.0
</energy_values>
<orbital index="1" atom_index="1" species="Ni" l="0" m="0" z="1">
<data>
0.1
0.2
0.1
</data>
</orbital>
<orbital index="2" atom_index="1" species="Ni" l="1" m="0" z="1">
<data>
0.2
0.3
0.2
</data>
</orbital>
<orbital index="3" atom_index="2" species="O" l="0" m="0" z="1">
<data>
0.05
0.10
0.05
</data>
</orbital>
<orbital index="4" atom_index="2" species="O" l="1" m="1" z="1">
<data>
0.15
0.20
0.15
</data>
</orbital>
</pdos>
"""


@dataclass(slots=True)
class DOSData:
    """Total DOS table data.

    ``rows`` and ``paths`` preserve the original lightweight API. ``energy`` and
    ``dosdata`` provide the analysis-level shape used by postprocessing.
    """

    paths: list[Path] = field(default_factory=list)
    rows: list[list[float]] = field(default_factory=list)
    energy: np.ndarray | None = None
    dosdata: np.ndarray | None = None
    efermi: float | None = None

    def __post_init__(self) -> None:
        if self.energy is None and self.rows:
            self.energy = np.asarray([row[0] for row in self.rows if row], dtype=float)
        if self.dosdata is None and self.rows:
            values = [row[1:] for row in self.rows if len(row) > 1]
            if values:
                self.dosdata = np.asarray(values, dtype=float)
        if self.energy is not None and self.efermi is not None:
            self.energy = np.asarray(self.energy, dtype=float) - float(self.efermi)
        if self.dosdata is not None and self.dosdata.ndim == 1:
            self.dosdata = self.dosdata.reshape((-1, 1))

    @classmethod
    def from_paths(cls, paths: list[str | Path]) -> "DOSData":
        resolved = [Path(path) for path in paths]
        rows: list[list[float]] = []
        for path in resolved:
            rows.extend(_read_numeric_table(path))
        return cls(paths=resolved, rows=rows)

    @classmethod
    def from_arrays(cls, energy: Iterable[float], dosdata: Iterable[Iterable[float]], *, efermi: float | None = None) -> "DOSData":
        return cls(energy=np.asarray(list(energy), dtype=float), dosdata=np.asarray(list(dosdata), dtype=float), efermi=efermi)

    def summary(self) -> dict[str, Any]:
        energies = self.energy.tolist() if self.energy is not None else [row[0] for row in self.rows if row]
        channels = int(self.dosdata.shape[1]) if self.dosdata is not None and self.dosdata.ndim == 2 else 0
        return {
            "dos_files": [str(path) for path in self.paths],
            "points": len(energies),
            "energy_min": min(energies) if energies else None,
            "energy_max": max(energies) if energies else None,
            "spin_channels": channels,
        }


@dataclass(slots=True)
class PDOSData:
    """Projected DOS data parsed from ABACUS PDOS XML."""

    energy: np.ndarray | None = None
    projected_dos: list[dict[str, Any]] = field(default_factory=list)
    efermi: float | None = None
    pdos_path: Path | None = None
    tdos_path: Path | None = None
    nspin: int | None = None

    def __post_init__(self) -> None:
        if self.energy is not None:
            self.energy = np.asarray(self.energy, dtype=float)
            if self.efermi is not None:
                self.energy = self.energy - float(self.efermi)
        for orbital in self.projected_dos:
            data = np.asarray(orbital["data"], dtype=float)
            if data.ndim == 1:
                data = data.reshape((-1, 1))
            orbital["data"] = data
            orbital.setdefault("atomic_orbital_name", ORBITAL_NAMES.get((int(orbital["l"]), int(orbital["m"])), f"m{orbital['m']}"))
        if self.nspin is None and self.projected_dos:
            self.nspin = int(self.projected_dos[0]["data"].shape[1])

    @classmethod
    def from_path(cls, path: str | Path, *, efermi: float | None = None, tdos_path: str | Path | None = None) -> "PDOSData":
        pdos_path = Path(path)
        text = pdos_path.read_text(encoding="utf-8", errors="ignore")
        if "<pdos" not in text.lower():
            return cls(pdos_path=pdos_path, tdos_path=Path(tdos_path) if tdos_path else None)
        root = ET.fromstring(_normalize_abacus_xml(text))
        energy_node = root.find("energy_values")
        energy = _numbers_from_text(energy_node.text if energy_node is not None else "")
        nspin_node = root.find("nspin")
        nspin = int(float((nspin_node.text or "1").strip())) if nspin_node is not None else 1
        orbitals: list[dict[str, Any]] = []
        for orbital_node in root.findall("orbital"):
            data_node = orbital_node.find("data")
            data_values = _numbers_from_text(data_node.text if data_node is not None else "")
            data = np.asarray(data_values, dtype=float)
            if nspin > 1:
                data = data.reshape((-1, nspin))
            else:
                data = data.reshape((-1, 1))
            orbital = {
                "index": _int_attr(orbital_node, "index"),
                "atom_index": _int_attr(orbital_node, "atom_index"),
                "species": str(orbital_node.attrib.get("species", "")),
                "l": _int_attr(orbital_node, "l"),
                "m": _int_attr(orbital_node, "m"),
                "z": _int_attr(orbital_node, "z"),
                "data": data,
            }
            orbitals.append(orbital)
        return cls(
            energy=np.asarray(energy, dtype=float),
            projected_dos=orbitals,
            efermi=efermi,
            pdos_path=pdos_path,
            tdos_path=Path(tdos_path) if tdos_path else None,
            nspin=nspin,
        )

    def summary(self) -> dict[str, Any]:
        return {
            "pdos_file": str(self.pdos_path) if self.pdos_path else None,
            "tdos_file": str(self.tdos_path) if self.tdos_path else None,
            "points": int(len(self.energy)) if self.energy is not None else 0,
            "orbitals": len(self.projected_dos),
            "species": self.get_species() if self.projected_dos else [],
            "spin_channels": self.nspin or 0,
        }

    def get_pdos_by_species(self, species: str, sum_only: bool = True) -> np.ndarray | list[dict[str, Any]]:
        return self._select(sum_only, lambda orbital: orbital["species"] == species)

    def get_pdos_by_species_shell(self, species: str, l: int | str, sum_only: bool = True) -> np.ndarray | list[dict[str, Any]]:
        shell = _shell_index(l)
        return self._select(sum_only, lambda orbital: orbital["species"] == species and orbital["l"] == shell)

    def get_pdos_by_species_orbital(self, species: str, l: int | str | None, m: int | str, sum_only: bool = True) -> np.ndarray | list[dict[str, Any]]:
        return self._select(sum_only, lambda orbital: orbital["species"] == species and _orbital_matches(orbital, l, m))

    def get_pdos_by_atom(self, atom_index: int, sum_only: bool = True) -> np.ndarray | list[dict[str, Any]]:
        return self._select(sum_only, lambda orbital: orbital["atom_index"] == atom_index)

    def get_pdos_by_atom_shell(self, atom_index: int, l: int | str, sum_only: bool = True) -> np.ndarray | list[dict[str, Any]]:
        shell = _shell_index(l)
        return self._select(sum_only, lambda orbital: orbital["atom_index"] == atom_index and orbital["l"] == shell)

    def get_pdos_by_atom_orbital(self, atom_index: int, l: int | str | None, m: int | str, sum_only: bool = True) -> np.ndarray | list[dict[str, Any]]:
        return self._select(sum_only, lambda orbital: orbital["atom_index"] == atom_index and _orbital_matches(orbital, l, m))

    def get_species(self) -> list[str]:
        return sorted({str(orbital["species"]) for orbital in self.projected_dos})

    def get_species_shell(self, species: str) -> list[int]:
        return sorted({int(orbital["l"]) for orbital in self.projected_dos if orbital["species"] == species})

    def get_species_shell_orbital(self, species: str, l: int | str) -> list[int]:
        shell = _shell_index(l)
        return sorted({int(orbital["m"]) for orbital in self.projected_dos if orbital["species"] == species and orbital["l"] == shell})

    def get_atom_species(self, atom_index: int) -> str:
        species = sorted({str(orbital["species"]) for orbital in self.projected_dos if orbital["atom_index"] == atom_index})
        if len(species) != 1:
            raise ValueError(f"atom_index={atom_index} maps to {len(species)} species")
        return species[0]

    def get_atom_shell(self, atom_index: int) -> list[int]:
        return sorted({int(orbital["l"]) for orbital in self.projected_dos if orbital["atom_index"] == atom_index})

    def get_atom_shell_orbital(self, atom_index: int, l: int | str) -> list[int]:
        shell = _shell_index(l)
        return sorted({int(orbital["m"]) for orbital in self.projected_dos if orbital["atom_index"] == atom_index and orbital["l"] == shell})

    def _select(self, sum_only: bool, predicate) -> np.ndarray | list[dict[str, Any]]:
        selected = [orbital for orbital in self.projected_dos if predicate(orbital)]
        if sum_only:
            return self.sum_pdos_data(selected)
        return selected

    @staticmethod
    def sum_pdos_data(pdos_datas: list[dict[str, Any]]) -> np.ndarray:
        if not pdos_datas:
            raise ValueError("No PDOS data provided")
        summed = np.zeros_like(np.asarray(pdos_datas[0]["data"], dtype=float))
        for pdos_data in pdos_datas:
            summed += np.asarray(pdos_data["data"], dtype=float)
        return summed


@dataclass(slots=True)
class LocalDOSData:
    """Reserved LDOS data slot for the unified DOS-family contract."""

    paths: list[Path] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {"ldos_files": [str(path) for path in self.paths], "implemented": False}


@dataclass(slots=True)
class DOSFamilyData:
    total_dos: DOSData | None = None
    projected_dos: PDOSData | None = None
    local_dos: LocalDOSData | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            "total_dos": self.total_dos.summary() if self.total_dos else None,
            "projected_dos": self.projected_dos.summary() if self.projected_dos else None,
            "local_dos": self.local_dos.summary() if self.local_dos else None,
            "metadata": dict(self.metadata),
        }


def _read_numeric_table(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            rows.append([float(token) for token in stripped.split()])
        except ValueError:
            continue
    return rows


def write_sample_dos_artifacts(output_dir: str | Path, *, duplicate_dir: str | Path | None = None) -> dict[str, str]:
    base = Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    for filename, rows in _SAMPLE_DOS_TABLES.items():
        path = base / filename
        _write_numeric_table(path, rows)
        written[filename] = str(path)
        if duplicate_dir is not None:
            duplicate_path = Path(duplicate_dir) / filename
            _write_numeric_table(duplicate_path, rows)
            written[f"{Path(duplicate_dir).name}/{filename}"] = str(duplicate_path)
    return written


def write_sample_dos_family_artifacts(output_dir: str | Path, *, duplicate_dir: str | Path | None = None) -> dict[str, str]:
    written = write_sample_dos_artifacts(output_dir, duplicate_dir=duplicate_dir)
    base = Path(output_dir)
    written["PDOS"] = _write_text_artifact(base / "PDOS", _SAMPLE_PDOS_XML)
    written["TDOS"] = _write_text_artifact(base / "TDOS", _SAMPLE_TDOS_TEXT)
    if duplicate_dir is not None:
        duplicate = Path(duplicate_dir)
        written[f"{duplicate.name}/PDOS"] = _write_text_artifact(duplicate / "PDOS", _SAMPLE_PDOS_XML)
        written[f"{duplicate.name}/TDOS"] = _write_text_artifact(duplicate / "TDOS", _SAMPLE_TDOS_TEXT)
    return written


def _write_numeric_table(path: Path, rows: list[list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(" ".join(f"{value:g}" for value in row) for row in rows) + "\n", encoding="utf-8")


def _write_text_artifact(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def _numbers_from_text(text: str | None) -> list[float]:
    if not text:
        return []
    return [float(token) for token in text.split()]


def _int_attr(node: ET.Element, name: str) -> int:
    return int(float(str(node.attrib.get(name, "0")).strip()))


def _shell_index(l: int | str | None) -> int | None:
    if l is None:
        return None
    if isinstance(l, str) and l in L_MAP:
        return L_MAP.index(l)
    return int(l)


def _orbital_matches(orbital: dict[str, Any], l: int | str | None, m: int | str) -> bool:
    if isinstance(m, str):
        return orbital.get("atomic_orbital_name") == m
    shell = _shell_index(l)
    return (shell is None or orbital["l"] == shell) and orbital["m"] == int(m)


def _normalize_abacus_xml(text: str) -> str:
    """Handle ABACUS PDOS files with attributes split onto standalone lines."""

    text = re.sub(r"<orbital\s+([^>]*)>", lambda match: "<orbital " + _normalize_attrs(match.group(1)) + ">", text, flags=re.MULTILINE)
    text = text.replace("&", "&amp;")
    return text


def _normalize_attrs(raw: str) -> str:
    return " ".join(part.strip() for part in raw.splitlines() if part.strip())
