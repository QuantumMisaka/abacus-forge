import builtins
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


def test_xyz_reader_uses_v12_common_element_masses(tmp_path):
    trajectory = tmp_path / "masses.xyz"
    trajectory.write_text(
        "3\nframe\nCl 0 0 0\nNa 1 0 0\nZn 2 0 0\n",
        encoding="utf-8",
    )

    frame = md._read_xyz(trajectory)[0]

    assert frame.masses == pytest.approx([35.45, 22.990, 65.38])


def test_load_frames_rejects_unknown_xyz_element_when_ase_is_unavailable(tmp_path, monkeypatch):
    trajectory = tmp_path / "fallback-masses.xyz"
    trajectory.write_text(
        "4\nframe\nCl 0 0 0\nNa 1 0 0\nZn 2 0 0\nXx 3 0 0\n",
        encoding="utf-8",
    )
    real_import = builtins.__import__

    def without_ase(name, *args, **kwargs):
        if name == "ase.io":
            raise ImportError("ASE unavailable for fallback test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_ase)

    with pytest.raises(ValueError, match="unsupported chemical symbol.*Xx"):
        load_frames(trajectory)


def test_xyz_fallback_supports_the_full_periodic_table(tmp_path, monkeypatch):
    trajectory = tmp_path / "full-periodic-table.xyz"
    symbols = [
        "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
        "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca",
        "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
        "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Y", "Zr",
        "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn",
        "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd",
        "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb",
        "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt", "Au", "Hg",
        "Tl", "Pb", "Bi", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Th",
        "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm",
        "Md", "No", "Lr", "Rf", "Db", "Sg", "Bh", "Hs", "Mt", "Ds",
        "Rg", "Cn", "Nh", "Fl", "Mc", "Lv", "Ts", "Og",
    ]
    rows = [str(len(symbols)), "frame"]
    rows.extend(f"{symbol} {index} 0 0" for index, symbol in enumerate(symbols))
    trajectory.write_text("\n".join(rows) + "\n", encoding="utf-8")
    real_import = builtins.__import__

    def without_ase(name, *args, **kwargs):
        if name == "ase.io":
            raise ImportError("ASE unavailable for fallback test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_ase)

    frame = load_frames(trajectory)[0]

    assert len(frame.masses) == len(symbols)
    assert np.isfinite(frame.masses).all()
    assert np.all(frame.masses > 0)


def test_load_frames_falls_back_when_ase_masses_are_invalid(tmp_path, monkeypatch):
    class InvalidMassAtoms:
        def get_chemical_symbols(self):
            return ["Cl", "Na"]

        def get_positions(self):
            return np.zeros((2, 3))

        def get_cell(self):
            return np.zeros((3, 3))

        def get_pbc(self):
            return np.zeros(3, dtype=bool)

        def get_masses(self):
            return np.array([float("nan"), 0.0])

        def get_velocities(self):
            return None

    from ase import io as ase_io

    trajectory = tmp_path / "invalid-masses.traj"
    trajectory.touch()
    monkeypatch.setattr(ase_io, "read", lambda *args, **kwargs: [InvalidMassAtoms()])

    frames = load_frames(trajectory)

    assert frames[0].masses == pytest.approx([35.45, 22.990])


def test_validate_analysis_is_canonical():
    assert validate_analysis(["rdf", "bond_angle"]) == ("rdf", "bond_angle")
    with pytest.raises(ValueError):
        validate_analysis(["msd"])


def test_analyze_trajectory_rejects_empty_frame_sequences():
    with pytest.raises(ValueError, match="at least one frame"):
        analyze_trajectory([], ["msd_diffusion"], timestep=1.0)


def test_frame_normalizes_symbols_and_rejects_empty_or_non_string_symbols():
    symbols = ["H", "O"]
    frame = Frame(
        np.zeros((2, 3)), symbols, np.zeros((3, 3)), np.zeros(3, bool), np.ones(2)
    )
    symbols.append("C")
    assert frame.symbols == ("H", "O")
    with pytest.raises(ValueError, match="non-empty sequence of strings"):
        Frame(np.zeros((0, 3)), (), np.zeros((3, 3)), np.zeros(3, bool), np.ones(0))
    with pytest.raises(ValueError, match="non-empty sequence of strings"):
        Frame(np.zeros((1, 3)), (1,), np.zeros((3, 3)), np.zeros(3, bool), np.ones(1))
    with pytest.raises(ValueError, match="non-empty sequence of strings"):
        Frame(np.zeros((2, 3)), "HO", np.zeros((3, 3)), np.zeros(3, bool), np.ones(2))


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


def test_run_rejects_output_symlink_before_writing_any_analysis_file(tmp_path):
    trajectory = _xyz(tmp_path / "traj.xyz")
    output = tmp_path / "out"
    output.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")
    (output / "msd.txt").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        run_md_postprocess(
            trajectory,
            ["msd_diffusion"],
            output_dir=output,
            parameters={"timestep": 1.0, "save_data": True, "save_plot": False},
        )
    assert outside.read_text(encoding="utf-8") == "keep"
    assert not (output / "analysis.json").exists()


def test_run_rejects_symlink_output_directory(tmp_path):
    trajectory = _xyz(tmp_path / "traj.xyz")
    target = tmp_path / "real-out"
    target.mkdir()
    alias = tmp_path / "alias-out"
    try:
        alias.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError, match="output_dir must not be a symlink"):
        run_md_postprocess(
            trajectory,
            ["msd_diffusion"],
            output_dir=alias,
            parameters={"timestep": 1.0, "save_data": False, "save_plot": False},
        )


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


def test_plot_failure_does_not_produce_png_and_reports_safe_diagnostic(tmp_path, monkeypatch):
    trajectory = _xyz(tmp_path / "traj.xyz")
    import matplotlib.pyplot as plt
    monkeypatch.setattr(plt, "subplots", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("render failure")))
    output = tmp_path / "out"
    result = run_md_postprocess(trajectory, ["msd_diffusion"], output_dir=output, parameters={"timestep": 1.0, "save_data": False, "save_plot": True})
    assert not (output / "msd.png").exists()
    assert "msd.png" not in result.generated_files
    assert result.diagnostics["plot_failures"] == [
        {"mode": "msd_diffusion", "artifact": "msd.png", "reason": "render_failure"}
    ]
    assert all("/" not in str(value) for value in result.diagnostics["plot_failures"][0].values())


def test_plot_import_failure_does_not_produce_png_and_reports_safe_diagnostic(tmp_path, monkeypatch):
    trajectory = _xyz(tmp_path / "traj.xyz")
    real_import = builtins.__import__

    def without_matplotlib(name, *args, **kwargs):
        if name == "matplotlib.pyplot":
            raise ImportError("matplotlib unavailable at /private/secret")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_matplotlib)
    output = tmp_path / "out"

    result = run_md_postprocess(trajectory, ["msd_diffusion"], output_dir=output, parameters={"timestep": 1.0, "save_data": False, "save_plot": True})

    assert not (output / "msd.png").exists()
    assert "msd.png" not in result.generated_files
    assert result.diagnostics["plot_failures"] == [
        {"mode": "msd_diffusion", "artifact": "msd.png", "reason": "matplotlib_unavailable"}
    ]


def test_variable_cell_unwrap_uses_raw_wrapped_delta():
    frames = [Frame(np.array([[9.0, 0, 0]]), ("H",), np.diag([10., 10., 10.]), np.ones(3, bool), np.array([1.])), Frame(np.array([[1.0, 0, 0]]), ("H",), np.diag([11., 11., 11.]), np.ones(3, bool), np.array([1.])), Frame(np.array([[3.0, 0, 0]]), ("H",), np.diag([12., 12., 12.]), np.ones(3, bool), np.array([1.]))]
    assert md._unwrap(frames)[:, 0, 0].tolist() == pytest.approx([9.0, 12.0, 14.0])


def test_triclinic_minimum_image_is_not_componentwise_fractional_rounding():
    cell = np.array([[1.0, 0.0, 0.0], [0.99, 0.1, 0.0], [0.0, 0.0, 10.0]])
    current = np.array([0.49, 0.49, 0.0]) @ cell
    frame = Frame(
        np.array([[0.0, 0.0, 0.0], current]),
        ("H", "H"),
        cell,
        np.ones(3, bool),
        np.ones(2),
    )

    minimum = md._mi(current, frame)
    unwrapped = md._unwrap([
        Frame(np.zeros((1, 3)), ("H",), cell, np.ones(3, bool), np.ones(1)),
        Frame(current[None, :], ("H",), cell, np.ones(3, bool), np.ones(1)),
    ])

    assert np.linalg.norm(minimum) == pytest.approx(np.linalg.norm(current - cell[1]))
    assert minimum == pytest.approx(current - cell[1])
    assert unwrapped[1, 0] == pytest.approx(current - cell[1])


def test_triclinic_geometry_uses_the_same_minimum_image_kernel():
    cell = np.array([[1.0, 0.0, 0.0], [0.99, 0.1, 0.0], [0.0, 0.0, 10.0]])
    current = np.array([0.49, 0.49, 0.0]) @ cell
    frame = Frame(
        np.array([[0.0, 0.0, 0.0], current]),
        ("H", "O"),
        cell,
        np.ones(3, bool),
        np.array([1.0, 16.0]),
    )

    result = analyze_trajectory([frame], ["bond_length"], selection=["H-O"])

    assert result["bond_length"]["lengths_angstrom"]["H-O"] == pytest.approx([
        np.linalg.norm(current - cell[1])
    ])


def test_partial_pbc_minimum_image_works_with_zero_nonperiodic_cell_vector():
    cell = np.array([[1.0, 0.0, 0.0], [0.4, 1.0, 0.0], [0.0, 0.0, 0.0]])
    delta = np.array([0.49, 0.49, 1.0]) @ cell + np.array([0.0, 0.0, 2.0])
    frame = Frame(
        np.array([[0.0, 0.0, 0.0], delta]),
        ("H", "O"),
        cell,
        np.array([True, True, False]),
        np.array([1.0, 16.0]),
    )

    minimum = md._mi(delta, frame)

    assert minimum == pytest.approx(np.array([0.49, 0.49, 1.0]) @ cell - cell[0] + np.array([0.0, 0.0, 2.0]))


def test_full_pbc_minimum_image_is_invariant_under_large_lattice_translation():
    cell = np.eye(3)
    frame = Frame(
        np.array([[0.0, 0.0, 0.0], [0.1, 0.2, 0.3]]),
        ("H", "O"),
        cell,
        np.ones(3, bool),
        np.ones(2),
    )
    displacement = np.array([0.1, 0.2, 0.3])
    translated = displacement + np.array([1_000_000, 0, 0]) @ cell

    assert md._mi(translated, frame) == pytest.approx(displacement)


def test_partial_pbc_minimum_image_is_invariant_under_large_active_translation():
    cell = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 2.0]])
    frame = Frame(
        np.array([[0.0, 0.0, 0.0], [0.1, 3.25, 0.2]]),
        ("H", "O"),
        cell,
        np.array([True, False, True]),
        np.ones(2),
    )
    displacement = np.array([0.1, 3.25, 0.2])
    translated = displacement + np.array([1_000_000, 0, 500_000]) @ cell

    assert md._mi(translated, frame) == pytest.approx(displacement)


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
