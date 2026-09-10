"""Gaussian cube data helpers for Forge property packs."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


@dataclass(slots=True)
class CubeData:
    """Minimal single-field Gaussian cube payload with volumetric data.

    Gaussian cube files with a negative atom count encode orbital metadata and
    are deliberately rejected because this value object represents one scalar
    volumetric field only.
    """

    comments: list[str]
    natoms: int
    origin: list[float]
    grid: list[dict[str, object]]
    atom_lines: list[str]
    data: np.ndarray

    def __post_init__(self) -> None:
        if isinstance(self.natoms, bool) or not isinstance(self.natoms, int):
            raise ValueError("cube natoms must be an integer")
        origin = np.asarray(self.origin, dtype=float)
        if origin.shape != (3,) or not np.isfinite(origin).all():
            raise ValueError("cube origin must contain three finite values")
        if not isinstance(self.grid, (list, tuple)) or len(self.grid) != 3:
            raise ValueError("cube grid must contain three axes")
        normalized_grid: list[dict[str, object]] = []
        shape: list[int] = []
        for item in self.grid:
            if not isinstance(item, Mapping) or "count" not in item or "vector" not in item:
                raise ValueError("cube grid entries require count and vector")
            count = item["count"]
            if isinstance(count, bool) or not isinstance(count, int) or count == 0:
                raise ValueError("cube grid counts must be non-zero integers")
            vector = np.asarray(item["vector"], dtype=float)
            if vector.shape != (3,) or not np.isfinite(vector).all() or np.linalg.norm(vector) <= 0:
                raise ValueError("cube grid vectors must be finite and non-zero")
            normalized_grid.append({"count": count, "vector": [float(value) for value in vector]})
            shape.append(abs(count))
        data = np.asarray(self.data, dtype=float)
        if data.shape != tuple(shape):
            raise ValueError(f"cube data shape mismatch: expected {tuple(shape)}, got {data.shape}")
        if not np.isfinite(data).all():
            raise ValueError("cube data must contain finite values")
        if len(self.atom_lines) < abs(self.natoms):
            raise ValueError("cube atom records are incomplete")
        object.__setattr__(self, "origin", [float(value) for value in origin])
        object.__setattr__(self, "grid", normalized_grid)
        object.__setattr__(self, "data", data)

    @classmethod
    def from_file(cls, path: str | Path) -> "CubeData":
        lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
        if len(lines) < 6:
            raise ValueError(f"cube file is too short: {path}")
        comments = [lines[0], lines[1]]
        origin_parts = lines[2].split()
        if len(origin_parts) < 4:
            raise ValueError("cube origin record is incomplete")
        natoms = _integer_token(origin_parts[0], "cube natoms")
        if natoms < 0:
            raise ValueError("cube orbital datasets with negative natoms are not supported")
        origin = [float(value) for value in origin_parts[1:4]]
        grid = []
        shape = []
        for line in lines[3:6]:
            parts = line.split()
            if len(parts) < 4:
                raise ValueError("cube grid record is incomplete")
            count = _integer_token(parts[0], "cube grid count")
            shape.append(abs(count))
            grid.append({"count": count, "vector": [float(value) for value in parts[1:4]]})
        atom_line_count = abs(natoms)
        if len(lines) < 6 + atom_line_count:
            raise ValueError("cube atom records are incomplete")
        atom_lines = lines[6 : 6 + atom_line_count]
        values: list[float] = []
        for line in lines[6 + atom_line_count :]:
            values.extend(float(token) for token in line.split())
        expected = int(np.prod(shape))
        if len(values) != expected:
            raise ValueError(f"cube data size mismatch: expected {expected}, got {len(values)}")
        return cls(
            comments=comments,
            natoms=natoms,
            origin=origin,
            grid=grid,
            atom_lines=atom_lines,
            data=np.asarray(values, dtype=float).reshape(shape),
        )

    def with_data(self, data: Iterable[float] | np.ndarray) -> "CubeData":
        try:
            array = np.asarray(data, dtype=float).reshape(self.data.shape)
        except (TypeError, ValueError) as error:
            raise ValueError(f"cube data shape mismatch: expected {self.data.shape}") from error
        return CubeData(
            comments=list(self.comments),
            natoms=self.natoms,
            origin=list(self.origin),
            grid=[{"count": item["count"], "vector": list(item["vector"])} for item in self.grid],
            atom_lines=list(self.atom_lines),
            data=array,
        )

    def write(self, path: str | Path) -> Path:
        if not np.isfinite(self.data).all():
            raise ValueError("cube data must contain finite values")
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            self.comments[0] if self.comments else "Forge cube",
            self.comments[1] if len(self.comments) > 1 else "Generated by abacus-forge",
            f"{self.natoms} {' '.join(_fmt(value) for value in self.origin)}",
        ]
        for item in self.grid:
            lines.append(f"{int(item['count'])} {' '.join(_fmt(value) for value in item['vector'])}")
        lines.extend(self.atom_lines)
        flat = self.data.reshape(-1)
        for start in range(0, len(flat), 6):
            lines.append(" ".join(_fmt(value) for value in flat[start : start + 6]))
        destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return destination


def subtract_cubes(left: str | Path | CubeData, right: str | Path | CubeData) -> CubeData:
    """Return ``left - right`` for matching cube grids."""

    left_cube = left if isinstance(left, CubeData) else CubeData.from_file(left)
    right_cube = right if isinstance(right, CubeData) else CubeData.from_file(right)
    _require_same_grid(left_cube, right_cube)
    return left_cube.with_data(left_cube.data - right_cube.data)


def add_cubes(cubes: Iterable[str | Path | CubeData]) -> CubeData:
    """Return the element-wise sum of matching cube grids."""

    iterator = iter(cubes)
    try:
        first = next(iterator)
    except StopIteration as exc:
        raise ValueError("add_cubes requires at least one cube") from exc
    total = first if isinstance(first, CubeData) else CubeData.from_file(first)
    data = total.data.copy()
    for cube_like in iterator:
        cube = cube_like if isinstance(cube_like, CubeData) else CubeData.from_file(cube_like)
        _require_same_grid(total, cube)
        data = data + cube.data
    return total.with_data(data)


def planar_average(cube: str | Path | CubeData, *, axis: int) -> list[float]:
    """Average cube data over the two axes perpendicular to ``axis``."""

    payload = cube if isinstance(cube, CubeData) else CubeData.from_file(cube)
    if axis not in {0, 1, 2}:
        raise ValueError("axis must be 0, 1, or 2")
    reduce_axes = tuple(index for index in range(3) if index != axis)
    return [float(value) for value in np.mean(payload.data, axis=reduce_axes)]


def _require_same_grid(left: CubeData, right: CubeData) -> None:
    if left.data.shape != right.data.shape:
        raise ValueError(f"cube shape mismatch: {left.data.shape} != {right.data.shape}")
    if not np.allclose(left.origin, right.origin):
        raise ValueError("cube origins do not match")
    left_axes = [(item["count"], item["vector"]) for item in left.grid]
    right_axes = [(item["count"], item["vector"]) for item in right.grid]
    if [count for count, _ in left_axes] != [count for count, _ in right_axes]:
        raise ValueError("cube grid counts or units do not match")
    if not np.allclose([vector for _, vector in left_axes], [vector for _, vector in right_axes]):
        raise ValueError("cube grid vectors do not match")


def _fmt(value: object) -> str:
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError("cube values must be finite")
    return f"{converted:.10g}"


def _integer_token(value: str, label: str) -> int:
    try:
        converted = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be an integer") from error
    if not math.isfinite(converted) or not converted.is_integer():
        raise ValueError(f"{label} must be an integer")
    integer = int(converted)
    if label == "cube grid count" and integer == 0:
        raise ValueError("cube grid counts must be non-zero integers")
    return integer
