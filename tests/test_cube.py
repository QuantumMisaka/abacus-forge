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
    atom_line: str = "1 0.0 0.0 0.0 0.0",
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
                atom_line,
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


def test_cube_value_rejects_unsupported_orbital_datasets():
    with pytest.raises(ValueError, match="orbital"):
        CubeData(
            comments=["comment", "comment"],
            natoms=-1,
            origin=[0.0, 0.0, 0.0],
            grid=[
                {"count": 1, "vector": [1.0, 0.0, 0.0]},
                {"count": 1, "vector": [0.0, 1.0, 0.0]},
                {"count": 1, "vector": [0.0, 0.0, 1.0]},
            ],
            atom_lines=["1 0.0 0.0 0.0 0.0"],
            data=np.zeros((1, 1, 1)),
        )


@pytest.mark.parametrize(
    "atom_line",
    [
        "1 0.0 0.0 0.0",
        "not-an-integer 0.0 0.0 0.0 0.0",
        "1 nan 0.0 0.0 0.0",
    ],
)
def test_cube_reader_rejects_malformed_atom_records(tmp_path: Path, atom_line: str):
    with pytest.raises(ValueError, match="atom"):
        CubeData.from_file(_cube(tmp_path / "malformed.cube", atom_line=atom_line))
