"""DOS and PDOS data helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SAMPLE_DOS_TABLES: dict[str, list[list[float]]] = {
    "DOS1_smearing.dat": [
        [-10.0, 0.0],
        [-5.0, 0.3],
        [0.0, 1.2],
        [5.0, 0.4],
    ],
    "DOS2_smearing.dat": [
        [-10.0, 0.0],
        [-5.0, 0.2],
        [0.0, 1.0],
        [5.0, 0.5],
    ],
}
_SAMPLE_PDOS_TEXT = "# species projected DOS\nNi 0.4\nO 0.6\n"
_SAMPLE_TDOS_TEXT = "# total DOS\n-1.0 0.1\n0.0 1.0\n1.0 0.2\n"


@dataclass(slots=True)
class DOSData:
    paths: list[Path]
    rows: list[list[float]]

    @classmethod
    def from_paths(cls, paths: list[str | Path]) -> "DOSData":
        resolved = [Path(path) for path in paths]
        rows: list[list[float]] = []
        for path in resolved:
            rows.extend(_read_numeric_table(path))
        return cls(paths=resolved, rows=rows)

    def summary(self) -> dict[str, Any]:
        energies = [row[0] for row in self.rows if row]
        return {
            "dos_files": [str(path) for path in self.paths],
            "points": len(self.rows),
            "energy_min": min(energies) if energies else None,
            "energy_max": max(energies) if energies else None,
        }


@dataclass(slots=True)
class PDOSData:
    pdos_path: Path | None
    tdos_path: Path | None

    def summary(self) -> dict[str, Any]:
        return {
            "pdos_file": str(self.pdos_path) if self.pdos_path else None,
            "tdos_file": str(self.tdos_path) if self.tdos_path else None,
        }


def _read_numeric_table(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            rows.append([float(token) for token in stripped.split()])
        except ValueError:
            continue
    return rows


def write_sample_dos_artifacts(
    output_dir: str | Path,
    *,
    duplicate_dir: str | Path | None = None,
) -> dict[str, str]:
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


def write_sample_pdos_artifacts(
    output_dir: str | Path,
    *,
    duplicate_dir: str | Path | None = None,
) -> dict[str, str]:
    base = Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)
    written = {
        "PDOS": _write_text_artifact(base / "PDOS", _SAMPLE_PDOS_TEXT),
        "TDOS": _write_text_artifact(base / "TDOS", _SAMPLE_TDOS_TEXT),
    }
    if duplicate_dir is not None:
        duplicate = Path(duplicate_dir)
        written[f"{duplicate.name}/PDOS"] = _write_text_artifact(duplicate / "PDOS", _SAMPLE_PDOS_TEXT)
        written[f"{duplicate.name}/TDOS"] = _write_text_artifact(duplicate / "TDOS", _SAMPLE_TDOS_TEXT)
    return written


def _write_numeric_table(path: Path, rows: list[list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(" ".join(f"{value:g}" for value in row) for row in rows) + "\n", encoding="utf-8")


def _write_text_artifact(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)
