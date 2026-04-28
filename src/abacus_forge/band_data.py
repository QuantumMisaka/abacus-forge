"""Band data helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SAMPLE_BAND_TABLES: dict[str, list[list[float]]] = {
    "BANDS_1.dat": [
        [0.0, -1.2, 0.5, 1.7],
        [0.5, -1.0, 0.6, 1.8],
        [1.0, -0.8, 0.7, 1.9],
    ],
    "BANDS_2.dat": [
        [0.0, -1.1, 0.6, 1.8],
        [0.5, -0.9, 0.7, 1.9],
        [1.0, -0.7, 0.8, 2.0],
    ],
}
_MINI_PNG = bytes.fromhex(
    "89504E470D0A1A0A0000000D4948445200000001000000010802000000907753DE0000000C4944415408D763F8FFFF3F0005FE02FEA7E28D5B0000000049454E44AE426082"
)


@dataclass(slots=True)
class BandData:
    paths: list[Path]
    rows: list[list[float]]

    @classmethod
    def from_paths(cls, paths: list[str | Path]) -> "BandData":
        resolved = [Path(path) for path in paths]
        rows: list[list[float]] = []
        for path in resolved:
            rows.extend(_read_numeric_table(path))
        return cls(paths=resolved, rows=rows)

    def summary(self) -> dict[str, Any]:
        num_columns = len(self.rows[0]) if self.rows else 0
        return {
            "band_files": [str(path) for path in self.paths],
            "num_points": len(self.rows),
            "num_kpoints": len(self.rows),
            "num_bands": max(num_columns - 1, 0),
            "num_columns": num_columns,
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


def write_sample_band_artifacts(
    output_dir: str | Path,
    *,
    duplicate_dir: str | Path | None = None,
    include_plot: bool = True,
) -> dict[str, str]:
    base = Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    for filename, rows in _SAMPLE_BAND_TABLES.items():
        path = base / filename
        _write_numeric_table(path, rows)
        written[filename] = str(path)
        if duplicate_dir is not None:
            duplicate_path = Path(duplicate_dir) / filename
            _write_numeric_table(duplicate_path, rows)
            written[f"{Path(duplicate_dir).name}/{filename}"] = str(duplicate_path)
    if include_plot:
        plot_path = base / "band.png"
        plot_path.write_bytes(_MINI_PNG)
        written["band.png"] = str(plot_path)
    return written


def _write_numeric_table(path: Path, rows: list[list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(" ".join(f"{value:g}" for value in row) for row in rows) + "\n", encoding="utf-8")
