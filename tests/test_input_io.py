from __future__ import annotations

from pathlib import Path

from abacus_forge.input_io import read_input, read_kpt, write_input, write_kpt, write_kpt_line_mode, write_kpt_mesh
from abacus_forge.modify import modify_kpt
from abacus_forge.validation import validate_inputs

def test_input_read_write(tmp_path: Path) -> None:
    params = {"ecutwfc": "80", "calculation": "scf"}
    path = tmp_path / "INPUT"
    write_input(path, params)
    
    read_params = read_input(path)
    assert read_params["ecutwfc"] == "80"
    assert read_params["calculation"] == "scf"

def test_kpt_mesh_write(tmp_path: Path) -> None:
    path = tmp_path / "KPT"
    write_kpt_mesh(path, [2, 2, 2], [1, 1, 1])
    text = path.read_text()
    assert "2 2 2 1 1 1" in text
    payload = read_kpt(path)
    assert payload == {"mode": "mesh", "mesh": [2, 2, 2], "shifts": [1, 1, 1]}

def test_kpt_line_mode_write(tmp_path: Path) -> None:
    path = tmp_path / "KPT_LINE"
    points = [([0.0, 0.0, 0.0], "Gamma"), ([0.5, 0.5, 0.5], "L")]
    write_kpt_line_mode(path, points, segments=10)
    text = path.read_text()
    assert "Line" in text
    assert "10" in text
    assert "Gamma" in text
    assert "L" in text
    payload = read_kpt(path)
    assert payload["mode"] == "line"
    assert payload["segments"] == 10
    assert payload["points"][0] == {"coords": [0.0, 0.0, 0.0], "label": "Gamma"}
    assert payload["points"][1] == {"coords": [0.5, 0.5, 0.5], "label": "L"}


def test_write_kpt_from_payload_and_modify_mesh(tmp_path: Path) -> None:
    path = tmp_path / "KPT"
    write_kpt(path, {"mode": "mesh", "mesh": [4, 4, 2], "shifts": [0, 1, 0]})

    modified = modify_kpt(path, mesh=[6, 6, 1], shifts=[1, 1, 1], destination=tmp_path / "KPT.modified")

    assert modified == {"mode": "mesh", "mesh": [6, 6, 1], "shifts": [1, 1, 1]}
    assert read_kpt(tmp_path / "KPT.modified") == modified


def test_modify_kpt_line_mode_from_mapping(tmp_path: Path) -> None:
    modified = modify_kpt(
        {
            "mode": "line",
            "segments": 12,
            "points": [
                {"coords": [0.0, 0.0, 0.0], "label": "G"},
                {"coords": [0.5, 0.0, 0.0], "label": "X"},
            ],
        },
        segments=20,
        points=[
            {"coords": [0.0, 0.0, 0.0], "label": "Gamma"},
            {"coords": [0.5, 0.5, 0.0], "label": "M"},
        ],
        destination=tmp_path / "KPT.line",
    )

    assert modified["mode"] == "line"
    assert modified["segments"] == 20
    assert modified["points"][1] == {"coords": [0.5, 0.5, 0.0], "label": "M"}
    assert read_kpt(tmp_path / "KPT.line") == modified

def test_validation(tmp_path: Path) -> None:
    (tmp_path / "INPUT").write_text("test")
    (tmp_path / "STRU").write_text("test")
    
    result = validate_inputs(tmp_path)
    assert result["valid"] is False
    assert "KPT" in result["missing"]
    
    (tmp_path / "KPT").write_text("test")
    result = validate_inputs(tmp_path)
    assert result["valid"] is True
    assert not result["missing"]
