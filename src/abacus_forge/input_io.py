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
    points: Iterable[Mapping[str, Any] | tuple[Iterable[float], str | None]],
    *,
    segments: int = 20,
) -> Path:
    """Write a line-mode ABACUS ``KPT`` file from points and optional labels."""
    normalized = _normalize_line_points(points, segments=segments)
    rows = ["K_POINTS", str(len(normalized)), "Line"]
    for point in normalized:
        coords = point["coords"]
        label = point.get("label")
        npoints = int(point["npoints"])
        suffix = f" #{label}" if label else ""
        rows.append(f"{' '.join(f'{float(value):.8f}' for value in coords)} {npoints}{suffix}")
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
            parts = coords_text.split()
            if len(parts) == 3:
                coords = [float(value) for value in parts]
                npoints = int(lines[1])
            elif len(parts) == 4:
                coords = [float(value) for value in parts[:3]]
                npoints = int(parts[3])
            else:
                raise ValueError(f"{path} line-mode KPT point must have 3 coordinates plus optional npoints, got {len(parts)}")
            label = label_text.strip() or None
            points.append({"coords": coords, "npoints": npoints, "label": label})
        return {
            "mode": "line",
            "segments": points[0]["npoints"] if points else int(lines[1]),
            "points": points,
        }
    raise ValueError(f"{path} unsupported KPT mode {lines[2]!r}")


def write_kpt(path: str | Path, payload: Mapping[str, Any]) -> Path:
    """Dispatch a structured KPT payload to the appropriate ABACUS writer."""
    mode = str(payload.get("mode", "")).lower()
    if mode == "mesh":
        return write_kpt_mesh(path, payload["mesh"], payload.get("shifts"))
    if mode == "line":
        return write_kpt_line_mode(path, payload.get("points", []), segments=int(payload.get("segments", 20)))
    raise ValueError(f"Unsupported KPT payload mode: {payload.get('mode')!r}")


def _normalize_line_points(
    points: Iterable[Mapping[str, Any] | tuple[Iterable[float], str | None]],
    *,
    segments: int,
) -> list[dict[str, Any]]:
    raw_points = list(points)
    normalized: list[dict[str, Any]] = []
    last_index = len(raw_points) - 1
    for index, point in enumerate(raw_points):
        if isinstance(point, Mapping):
            coords = [float(value) for value in point["coords"]]
            label = point.get("label")
            npoints = int(point.get("npoints", 1 if index == last_index else segments))
        else:
            coords_raw, label = point
            coords = [float(value) for value in coords_raw]
            npoints = 1 if index == last_index else int(segments)
        if len(coords) != 3:
            raise ValueError(f"line-mode KPT point requires 3 coordinates, got {coords!r}")
        normalized.append({"coords": coords, "npoints": npoints, "label": str(label) if label is not None else None})
    return normalized
