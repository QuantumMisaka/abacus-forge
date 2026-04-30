"""ABACUS INPUT/KPT read-write helpers."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Iterable


def read_input(path: str | Path) -> dict[str, str]:
    """Read an ABACUS ``INPUT`` file into a flat string mapping."""
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
    """Write a flat parameter mapping to an ABACUS ``INPUT`` file."""
    lines = [header]
    for key, value in sorted(parameters.items()):
        lines.append(f"{key} {value}")
    target = Path(path)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def write_kpt_mesh(path: str | Path, mesh: Iterable[int], shifts: Iterable[int] | None = None) -> Path:
    """Write a mesh-mode ABACUS ``KPT`` file."""
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
    """Write a line-mode ABACUS ``KPT`` file from points and optional labels."""
    rows = ["K_POINTS", str(segments), "Line"]
    for coords, label in points:
        suffix = f" #{label}" if label else ""
        rows.append(f"{' '.join(f'{float(value):.8f}' for value in coords)}{suffix}")
    target = Path(path)
    target.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return target


def read_kpt(path: str | Path) -> dict[str, Any]:
    """Parse a mesh- or line-mode ABACUS ``KPT`` file into a structured payload."""
    lines = [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) < 4 or lines[0].upper() != "K_POINTS":
        raise ValueError(f"{path} is not a supported ABACUS KPT file")

    mode = lines[2].lower()
    if mode == "gamma":
        values = [int(part) for part in lines[3].split()]
        if len(values) != 6:
            raise ValueError(f"{path} mesh-mode KPT must contain 6 integers, got {len(values)}")
        return {
            "mode": "mesh",
            "mesh": values[:3],
            "shifts": values[3:6],
        }
    if mode == "line":
        points: list[dict[str, Any]] = []
        for line in lines[3:]:
            coords_text, _, label_text = line.partition("#")
            coords = [float(value) for value in coords_text.split()]
            if len(coords) != 3:
                raise ValueError(f"{path} line-mode KPT point must have 3 coordinates, got {len(coords)}")
            label = label_text.strip() or None
            points.append({"coords": coords, "label": label})
        return {
            "mode": "line",
            "segments": int(lines[1]),
            "points": points,
        }
    raise ValueError(f"{path} unsupported KPT mode {lines[2]!r}")


def write_kpt(path: str | Path, payload: Mapping[str, Any]) -> Path:
    """Dispatch a structured KPT payload to the appropriate ABACUS writer."""
    mode = str(payload.get("mode", "")).lower()
    if mode == "mesh":
        return write_kpt_mesh(path, payload["mesh"], payload.get("shifts"))
    if mode == "line":
        points = [
            (point["coords"], point.get("label"))
            for point in payload.get("points", [])
        ]
        return write_kpt_line_mode(path, points, segments=int(payload.get("segments", 20)))
    raise ValueError(f"Unsupported KPT payload mode: {payload.get('mode')!r}")
