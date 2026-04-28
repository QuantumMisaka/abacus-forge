"""ABACUS INPUT/KPT read-write helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


def read_input(path: str | Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.upper() == "INPUT_PARAMETERS":
            continue
        parts = stripped.split(None, 1)
        if len(parts) == 2:
            values[parts[0]] = parts[1]
    return values


def write_input(
    path: str | Path,
    parameters: dict[str, Any],
    *,
    header: str = "INPUT_PARAMETERS",
) -> Path:
    lines = [header]
    for key, value in sorted(parameters.items()):
        lines.append(f"{key} {value}")
    target = Path(path)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def write_kpt_mesh(path: str | Path, mesh: Iterable[int], shifts: Iterable[int] | None = None) -> Path:
    grid = list(mesh)
    offsets = list(shifts or [0, 0, 0])
    target = Path(path)
    target.write_text(
        "K_POINTS\n0\nGamma\n"
        f"{' '.join(str(value) for value in grid)} {' '.join(str(value) for value in offsets)}\n",
        encoding="utf-8",
    )
    return target


def write_kpt_line_mode(
    path: str | Path,
    points: Iterable[tuple[Iterable[float], str | None]],
    *,
    segments: int = 20,
) -> Path:
    rows = ["K_POINTS", str(segments), "Line"]
    for coords, label in points:
        suffix = f" #{label}" if label else ""
        rows.append(f"{' '.join(f'{float(value):.8f}' for value in coords)}{suffix}")
    target = Path(path)
    target.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return target
