from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from abacus_forge.cube import CubeData, subtract_cubes


def _cube(
    path: Path,
    *,
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
    natoms: int = 1,
    first_count: int = 1,
    value: str = "1.0",
) -> Path:
    path.write_text(
        "\n".join(
            [
                "Forge cube fixture",
                "OUTER LOOP: X, MIDDLE LOOP: Y, INNER LOOP: Z",
                f"{natoms} {origin[0]} {origin[1]} {origin[2]}",
                f"{first_count} 1.0 0.0 0.0",
                "1 0.0 1.0 0.0",
                "1 0.0 0.0 1.0",
                "1 0.0 0.0 0.0 0.0",
                value,
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_cube_arithmetic_requires_matching_origin_and_grid_units(tmp_path: Path):
    left = _cube(tmp_path / "left.cube")
    shifted = _cube(tmp_path / "shifted.cube", origin=(0.1, 0.0, 0.0))
    with pytest.raises(ValueError, match="origin"):
        subtract_cubes(left, shifted)

    angstrom_grid = _cube(tmp_path / "angstrom.cube", first_count=-1)
    with pytest.raises(ValueError, match="grid"):
        subtract_cubes(left, angstrom_grid)


def test_cube_reader_rejects_nonfinite_and_zero_grid_data(tmp_path: Path):
    with pytest.raises(ValueError, match="finite"):
        CubeData.from_file(_cube(tmp_path / "nan.cube", value="nan"))
    with pytest.raises(ValueError, match="grid"):
        CubeData.from_file(_cube(tmp_path / "zero.cube", first_count=0))


def test_cube_with_data_rejects_nonfinite_values(tmp_path: Path):
    cube = CubeData.from_file(_cube(tmp_path / "base.cube"))
    with pytest.raises(ValueError, match="finite"):
        cube.with_data(np.array([float("inf")]))


def test_cube_reader_rejects_unsupported_orbital_datasets(tmp_path: Path):
    with pytest.raises(ValueError, match="orbital"):
        CubeData.from_file(_cube(tmp_path / "orbital.cube", natoms=-1))
