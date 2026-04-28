from __future__ import annotations

from pathlib import Path
from abacus_forge.input_io import read_input, write_input, write_kpt_mesh, write_kpt_line_mode
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

def test_kpt_line_mode_write(tmp_path: Path) -> None:
    path = tmp_path / "KPT_LINE"
    points = [([0.0, 0.0, 0.0], "Gamma"), ([0.5, 0.5, 0.5], "L")]
    write_kpt_line_mode(path, points, segments=10)
    text = path.read_text()
    assert "Line" in text
    assert "10" in text
    assert "Gamma" in text
    assert "L" in text

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
