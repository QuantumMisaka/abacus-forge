import json
from pathlib import Path

import numpy as np
import pytest

from abacus_forge.md_postprocess import (
    Frame,
    analyze_trajectory,
    load_frames,
    run_md_postprocess,
    validate_analysis,
)
import abacus_forge.md_postprocess as md


def _xyz(path: Path) -> Path:
    path.write_text(
        "2\nframe 0\nH 0 0 0\nO 1 0 0\n"
        "2\nframe 1\nH 0.1 0 0\nO 1.1 0 0\n"
        "2\nframe 2\nH 0.2 0 0\nO 1.2 0 0\n",
        encoding="utf-8",
    )
    return path


def test_xyz_reader_sampling(tmp_path):
    frames = load_frames(_xyz(tmp_path / "traj.xyz"), start=1, end=3, stride=2)
    assert len(frames) == 1
    assert frames.source_end == 3
    assert frames[0].symbols == ("H", "O")


def test_validate_analysis_is_canonical():
    assert validate_analysis(["rdf", "bond_angle"]) == ("rdf", "bond_angle")
    with pytest.raises(ValueError):
        validate_analysis(["msd"])


def test_geometry_msd_and_vacf_are_finite(tmp_path):
    frames = load_frames(_xyz(tmp_path / "traj.xyz"))
    result = analyze_trajectory(frames, ["msd_diffusion", "vacf_vdos"], timestep=1.0)
    assert result["msd_diffusion"]["msd_angstrom2"][0] == pytest.approx(0)
    assert np.isfinite(result["vacf_vdos"]["vacf"]).all()
    json.dumps(result, allow_nan=False, default=lambda value: value.tolist())


def test_run_writes_deterministic_analysis_and_controls(tmp_path):
    trajectory = _xyz(tmp_path / "traj.xyz")
    output = tmp_path / "out"
    result = run_md_postprocess(
        trajectory, ["msd_diffusion"], output_dir=output, parameters={"timestep": 1.0, "save_data": True, "save_plot": False}
    )
    assert result.sampling["frame_count"] == 3
    assert "analysis.json" in result.generated_files
    assert (output / "analysis.json").is_file()
    assert (output / "msd.txt").is_file()
    assert not (output / "msd.png").exists()
    json.loads((output / "analysis.json").read_text(encoding="utf-8"))


def test_periodic_geometry_and_one_based_selection():
    frame = Frame(
        np.array([[1.0, 0, 0], [0.0, 0, 0], [0.0, 1.0, 0]]),
        ("H", "O", "H"), np.diag([2.0, 2.0, 2.0]), np.array([True, True, True]),
        np.array([1.0, 16.0, 1.0]),
    )
    result = analyze_trajectory([frame], ["bond_angle"], selection={"angles": ["H-O-H"], "indices": [1, 2, 3]})
    assert result["bond_angle"]["angles_deg"]["H-O-H"] == pytest.approx([90.0])


def test_rdf_pair_and_parameter_boundaries(tmp_path):
    trajectory = _xyz(tmp_path / "traj.xyz")
    with pytest.raises(ValueError):
        run_md_postprocess(trajectory, ["rdf"], output_dir=tmp_path / "out", parameters={"elements": ["H-../escape"]})
    with pytest.raises(ValueError):
        run_md_postprocess(trajectory, ["rdf"], output_dir=tmp_path / "out", parameters={"elements": ["H/O"]})
    with pytest.raises(ValueError):
        run_md_postprocess(trajectory, ["rdf"], output_dir=tmp_path / "out", parameters={"rmax": float("inf")})


def test_trajectory_symbols_cannot_escape_rdf_output_directory(tmp_path):
    trajectory = tmp_path / "unsafe.xyz"
    trajectory.write_text("2\nframe\n../ 0 0 0\nO 1 0 0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="chemical symbols"):
        run_md_postprocess(trajectory, ["rdf"], output_dir=tmp_path / "out", parameters={"elements": None})


def test_plot_failure_still_produces_png(tmp_path, monkeypatch):
    trajectory = _xyz(tmp_path / "traj.xyz")
    import matplotlib.pyplot as plt
    monkeypatch.setattr(plt, "subplots", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("render failure")))
    output = tmp_path / "out"
    run_md_postprocess(trajectory, ["msd_diffusion"], output_dir=output, parameters={"timestep": 1.0, "save_data": False, "save_plot": True})
    assert (output / "msd.png").is_file()


def test_variable_cell_unwrap_uses_raw_wrapped_delta():
    frames = [Frame(np.array([[9.0, 0, 0]]), ("H",), np.diag([10., 10., 10.]), np.ones(3, bool), np.array([1.])), Frame(np.array([[1.0, 0, 0]]), ("H",), np.diag([11., 11., 11.]), np.ones(3, bool), np.array([1.])), Frame(np.array([[3.0, 0, 0]]), ("H",), np.diag([12., 12., 12.]), np.ones(3, bool), np.array([1.]))]
    assert md._unwrap(frames)[:, 0, 0].tolist() == pytest.approx([9.0, 12.0, 14.0])


def test_rdf_cutoff_and_pair_plots_are_bounded(tmp_path):
    frame = Frame(np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]]), ("H", "O", "C"), np.diag([4., 4., 4.]), np.ones(3, bool), np.ones(3))
    with pytest.raises(ValueError):
        analyze_trajectory([frame], ["rdf"], elements=["H-C"], rmax=3.0)
    path = tmp_path / "traj.xyz"
    _xyz(path)
    # Non-periodic XYZ cannot run RDF, so assert pair-name validation here.
    with pytest.raises(ValueError):
        run_md_postprocess(path, ["rdf"], output_dir=tmp_path / "out", parameters={"elements": ["H-C", "H/O"]})


def test_selection_list_honors_only_requested_pair_and_angle():
    frame = Frame(np.array([[0., 0, 0], [1., 0, 0], [0., 1., 0.]]), ("H", "O", "H"), np.zeros((3, 3)), np.zeros(3, bool), np.ones(3))
    result = analyze_trajectory([frame], ["bond_length", "bond_angle"], selection=["H-O", "H-O-H"])
    assert list(result["bond_length"]["lengths_angstrom"]) == ["H-O"]
    assert list(result["bond_angle"]["angles_deg"]) == ["H-O-H"]
    with pytest.raises(ValueError): analyze_trajectory([frame], ["bond_length"], selection=["H"])
    with pytest.raises(ValueError): analyze_trajectory([frame], ["bond_length"], selection=[3])


def test_kabsch_rigid_motion_and_vacf_invariants():
    base = np.array([[0., 0, 0], [1., 0, 0], [0., 1., 0.]])
    moved = base @ np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]]) + np.array([4., 3., 0.])
    frames = [Frame(base, ("H", "O", "H"), np.zeros((3, 3)), np.zeros(3, bool), np.ones(3)), Frame(moved, ("H", "O", "H"), np.zeros((3, 3)), np.zeros(3, bool), np.ones(3))]
    msd = analyze_trajectory(frames, ["msd_diffusion"], timestep=1.0)["msd_diffusion"]
    assert msd["msd_angstrom2"][0] == pytest.approx(0.0)
    assert msd["msd_angstrom2"][1] == pytest.approx(0.0, abs=1e-12)
    velocities = [np.ones((3, 3)), np.ones((3, 3)) * 2, np.ones((3, 3)) * 3]
    vacf_frames = [Frame(base + i * .1, ("H", "O", "H"), np.zeros((3, 3)), np.zeros(3, bool), np.ones(3), velocities[i]) for i in range(3)]
    vacf = analyze_trajectory(vacf_frames, ["vacf_vdos"], timestep=1.0)["vacf_vdos"]
    assert vacf["vacf"][0] == pytest.approx(1.0)
    assert len(vacf["frequency_THz"]) == 2


def test_rdf_shell_facts_and_multi_pair_outputs(tmp_path):
    trajectory = tmp_path / "cell.xyz"
    trajectory.write_text(
        '3\nLattice="4 0 0 0 4 0 0 0 4" Properties=species:S:1:pos:R:3 pbc="T T T"\n'
        "H 0 0 0\nO 1 0 0\nC 1.2 0 0\n",
        encoding="utf-8",
    )
    result = run_md_postprocess(trajectory, ["rdf"], output_dir=tmp_path / "out", parameters={"elements": ["H-O", "H-C"], "rmax": 1.5, "nbins": 3})
    assert set(result.results["rdf"]) == {"H-O", "H-C"}
    for pair in ("H_O", "H_C"):
        assert (tmp_path / "out" / f"rdf_{pair}.txt").is_file()
        assert (tmp_path / "out" / f"rdf_{pair}.png").is_file()
    assert np.isfinite(result.results["rdf"]["H-O"]["g_r"]).all()
