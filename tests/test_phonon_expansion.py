from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest
from ase import Atoms

from abacus_forge.api import prepare
from abacus_forge.composite import phonon
from abacus_forge.structure import AbacusStructure

pytestmark = [pytest.mark.composite, pytest.mark.experimental]


def _workspace(tmp_path: Path) -> Path:
    root = tmp_path / "phonon-case"
    prepare(
        root,
        structure=Atoms(
            "Si2",
            scaled_positions=[[0.0, 0.0, 0.0], [0.23, 0.31, 0.37]],
            cell=[[4.0, 0.0, 0.0], [0.2, 4.7, 0.0], [0.1, 0.3, 5.1]],
            pbc=True,
        ),
        task="scf",
    )
    return root


def _force_records(root: Path) -> list[dict]:
    from phonopy import load

    plan = json.loads((root / "reports/phonon_plan.json").read_text())
    model = load(root / plan["phonopy_file"], produce_fc=False)
    equilibrium = np.asarray(model.supercell.positions)
    records = []
    for unit in plan["subtasks"]:
        cell = model.supercells_with_displacements[unit["displacement_index"]]
        delta = np.asarray(cell.positions) - equilibrium
        # Pair spring: F0 = -2(u0-u1), F1 = -F0; its three translations are zero modes.
        force = np.asarray([-2.0 * (delta[0] - delta[1]), 2.0 * (delta[0] - delta[1])])
        records.append({
            "task": "phonon", "unit_id": unit["unit_id"],
            "workspace_rel": unit["workspace_rel"], "input_digest": unit["input_digest"],
            "status": "completed",
            "metrics": {"normal_end": True, "converge": True, "force": force.tolist()},
        })
    return records


def test_prepare_phonon_expands_real_displacements_with_reloadable_relative_plan(tmp_path: Path):
    pytest.importorskip("phonopy")
    root = _workspace(tmp_path)
    original = (root / "inputs/STRU").read_bytes()
    prepared = phonon.prepare_phonon(root, supercell=(1, 1, 1), displacement_stepsize=0.02)
    plan = json.loads((root / "reports/phonon_plan.json").read_text())

    assert prepared.status == "prepared"
    assert prepared.summary["count"] > 1
    assert len({unit["unit_id"] for unit in plan["subtasks"]}) == prepared.summary["count"]
    assert (root / plan["phonopy_file"]).is_file()
    for unit in plan["subtasks"]:
        assert not Path(unit["workspace_rel"]).is_absolute()
        assert (root / unit["workspace_rel"] / "inputs/STRU").read_bytes() != original
    assert (root / "inputs/STRU").read_bytes() == original
    assert "reports/phonon_plan.json" in {artifact.path_rel for artifact in prepared.to_envelope().artifacts}


def test_prepare_phonon_missing_executable_does_not_create_undisplaced_unit(tmp_path: Path):
    root = _workspace(tmp_path)
    prepared = phonon.prepare_phonon(root, phonopy="definitely-missing-phonopy")

    assert prepared.status == "degraded"
    assert prepared.subtasks == []
    assert prepared.diagnostics["optional_dependency_missing"] == "phonopy"
    assert not (root / "phonon/ABACUS-001").exists()
    assert not (root / "reports/phonon_plan.json").exists()


def test_prepare_phonon_rejects_existing_plan_before_mutating_units(tmp_path: Path):
    pytest.importorskip("phonopy")
    root = _workspace(tmp_path)
    prepared = phonon.prepare_phonon(root, supercell=(1, 1, 1))
    child = Path(prepared.subtasks[0]["workspace"]) / "inputs/STRU"
    before = child.read_bytes()
    plan_before = (root / "reports/phonon_plan.json").read_bytes()

    with pytest.raises(FileExistsError, match="plan"):
        phonon.prepare_phonon(root, supercell=(2, 1, 1))

    assert child.read_bytes() == before
    assert (root / "reports/phonon_plan.json").read_bytes() == plan_before


def test_prepare_phonon_cli_failure_does_not_reuse_stale_displacements(tmp_path: Path):
    root = _workspace(tmp_path)
    stale = root / "STRU-001"
    stale.write_bytes((root / "inputs/STRU").read_bytes())
    setting = root / "setting.conf"
    setting.write_text("DIM = 1 1 1\n")
    executable = tmp_path / "failed-phonopy"
    executable.write_text("#!/bin/sh\nexit 7\n")
    executable.chmod(0o755)

    prepared = phonon.prepare_phonon(root, phonopy=str(executable), setting_file=str(setting))

    assert prepared.status == "failed"
    assert prepared.subtasks == []
    assert prepared.diagnostics["phonopy_prepare_returncode"] == 7
    assert not (root / "reports/phonon_plan.json").exists()


def test_prepare_phonon_compatibility_executable_uses_new_dataset_and_actual_distance(tmp_path: Path):
    pytest.importorskip("phonopy")
    executable = Path(sys.executable).with_name("phonopy")
    if not executable.is_file():
        pytest.skip("installed phonopy CLI unavailable")
    root = _workspace(tmp_path)
    setting = root / "setting.conf"
    setting.write_text("DIM = 1 1 1\nDISPLACEMENT_DISTANCE = 0.03\n")
    (root / "STRU-999").write_bytes((root / "inputs/STRU").read_bytes())

    result = phonon.prepare_phonon(root, phonopy=str(executable))

    assert result.status == "prepared", result.diagnostics
    plan = json.loads((root / "reports/phonon_plan.json").read_text())
    # phonopy's ABACUS initializer takes its displacement distance in bohr.
    assert plan["displacement_stepsize"] == pytest.approx(0.01587531622271844)
    assert all("999" not in unit["workspace_rel"] for unit in plan["subtasks"])
    assert phonon.post_phonon(root, results=_force_records(root)).status == "completed"


def test_prepare_phonon_cli_uses_custom_structure_selector(tmp_path: Path):
    library = pytest.importorskip("phonopy")
    executable = Path(sys.executable).with_name("phonopy")
    if not executable.is_file():
        pytest.skip("installed phonopy CLI unavailable")
    root = _workspace(tmp_path)
    selected = AbacusStructure.from_input(root / "inputs/STRU", structure_format="stru")
    fractional = selected.atoms.get_scaled_positions()
    fractional[1, 0] = 0.13
    selected.atoms.set_scaled_positions(fractional)
    (root / "inputs/selected.stru").write_text(selected.to_stru())
    input_file = root / "inputs/INPUT"
    input_file.write_text(input_file.read_text() + "\nstru_file selected.stru\n")
    (root / "setting.conf").write_text("DIM = 1 1 1\n")

    result = phonon.prepare_phonon(root, phonopy=str(executable))

    assert result.status == "prepared", result.diagnostics
    plan = json.loads((root / "reports/phonon_plan.json").read_text())
    model = library.load(root / plan["phonopy_file"], produce_fc=False)
    np.testing.assert_allclose(model.unitcell.scaled_positions, fractional, rtol=0.0, atol=1e-8)


def test_phonon_cli_and_python_preserve_angstrom_geometry_and_harmonic_response(tmp_path: Path):
    pytest.importorskip("phonopy")
    from phonopy.file_IO import parse_FORCE_CONSTANTS

    executable = Path(sys.executable).with_name("phonopy")
    if not executable.is_file():
        pytest.skip("installed phonopy CLI unavailable")
    cli_root = _workspace(tmp_path / "cli")
    python_root = _workspace(tmp_path / "python")
    (cli_root / "setting.conf").write_text(
        "DIM = 1 1 1\nDISPLACEMENT_DISTANCE = 0.03779452249251541\n"
    )
    cli = phonon.prepare_phonon(cli_root, phonopy=str(executable))
    python = phonon.prepare_phonon(python_root, supercell=(1, 1, 1), displacement_stepsize=0.02)
    assert cli.status == python.status == "prepared"
    source = AbacusStructure.from_input(python_root / "inputs/STRU", structure_format="stru").atoms
    for root, result in ((cli_root, cli), (python_root, python)):
        plan = json.loads((root / "reports/phonon_plan.json").read_text())
        assert plan["displacement_stepsize"] == pytest.approx(0.02)
        for unit in result.subtasks:
            atoms = AbacusStructure.from_input(Path(unit["workspace"]) / "inputs/STRU", structure_format="stru").atoms
            np.testing.assert_allclose(atoms.cell, source.cell, rtol=0.0, atol=1e-7)
            displacement = atoms.positions - source.positions
            displacement -= np.rint(displacement @ np.linalg.inv(atoms.cell)) @ atoms.cell
            assert np.linalg.norm(displacement) == pytest.approx(0.02, abs=1e-7)
    cli_post = phonon.post_phonon(cli_root, results=_force_records(cli_root))
    python_post = phonon.post_phonon(python_root, results=_force_records(python_root))
    cli_fc = parse_FORCE_CONSTANTS(cli_root / "reports/FORCE_CONSTANTS")
    python_fc = parse_FORCE_CONSTANTS(python_root / "reports/FORCE_CONSTANTS")
    np.testing.assert_allclose(cli_fc, python_fc, rtol=0.0, atol=1e-8)
    np.testing.assert_allclose(cli_fc[0, 0], 2.0 * np.eye(3), rtol=0.0, atol=1e-8)
    np.testing.assert_allclose(cli_post.summary["frequencies_THz"], python_post.summary["frequencies_THz"], rtol=1e-7, atol=1e-5)


@pytest.mark.parametrize("interface", ["python", "cli"])
def test_phonon_preserves_single_species_label_resources_and_mass_in_supercell(tmp_path: Path, interface):
    library = pytest.importorskip("phonopy")
    root = _workspace(tmp_path)
    source = AbacusStructure.from_input(root / "inputs/STRU", structure_format="stru")
    source.atoms.set_masses([30.0, 30.0])
    source.atoms.info["abacus_atom_labels"] = ["Si1", "Si1"]
    source.atoms.info["abacus_species_meta"] = {"Si1": {"mass": 30.0, "pp": "isotope.upf", "orb": "isotope.orb"}}
    (root / "inputs/STRU").write_text(source.to_stru())
    (root / "inputs/isotope.upf").write_text("offline pseudo fixture")
    (root / "inputs/isotope.orb").write_text("offline orbital fixture")

    if interface == "cli":
        executable = Path(sys.executable).with_name("phonopy")
        if not executable.is_file():
            pytest.skip("installed phonopy CLI unavailable")
        (root / "setting.conf").write_text("DIM = 2 1 1\n")
        result = phonon.prepare_phonon(root, phonopy=str(executable))
    else:
        result = phonon.prepare_phonon(root, supercell=(2, 1, 1))
    assert result.status == "prepared", result.diagnostics

    plan = json.loads((root / "reports/phonon_plan.json").read_text())
    model = library.load(root / plan["phonopy_file"], produce_fc=False)
    np.testing.assert_array_equal(model.unitcell.masses, [30.0, 30.0])
    for unit in result.subtasks:
        path = Path(unit["workspace"])
        atoms = AbacusStructure.from_input(path / "inputs/STRU", structure_format="stru").atoms
        assert atoms.info["abacus_atom_labels"] == ["Si1"] * 4
        assert atoms.info["abacus_species_meta"]["Si1"]["pp"] == "isotope.upf"
        assert atoms.info["abacus_species_meta"]["Si1"]["orb"] == "isotope.orb"
        np.testing.assert_array_equal(atoms.get_masses(), [30.0] * 4)
        assert (path / "inputs/isotope.upf").is_file()
        assert (path / "inputs/isotope.orb").is_file()


def test_phonon_rejects_multiple_abacus_species_for_same_element_before_expansion(tmp_path: Path):
    pytest.importorskip("phonopy")
    root = _workspace(tmp_path)
    atoms = Atoms("Fe2", positions=[[0, 0, 0], [1, 1, 1]], cell=[4, 4, 4], pbc=True, masses=[55.0, 57.0])
    atoms.info["abacus_atom_labels"] = ["Fe1", "Fe2"]
    atoms.info["abacus_species_meta"] = {
        "Fe1": {"mass": 55.0, "pp": "FeA.upf", "orb": "FeA.orb"},
        "Fe2": {"mass": 57.0, "pp": "FeB.upf", "orb": "FeB.orb"},
    }
    (root / "inputs/STRU").write_text(AbacusStructure.from_input(atoms).to_stru())

    with pytest.raises(ValueError, match="species"):
        phonon.prepare_phonon(root, supercell=(1, 1, 1))
    assert not (root / "phonon").exists()
    assert not (root / "reports/phonon_plan.json").exists()


def test_default_phonon_post_rejects_changed_unit_inputs_before_collection(tmp_path: Path):
    pytest.importorskip("phonopy")
    root = _workspace(tmp_path)
    result = phonon.prepare_phonon(root, supercell=(1, 1, 1))
    input_path = Path(result.subtasks[0]["workspace"]) / "inputs/INPUT"
    input_path.write_text(input_path.read_text() + "\n# changed after prepare\n")

    with pytest.raises(ValueError, match="inputs changed"):
        phonon.post_phonon(root)


def test_prepare_and_post_phonon_accept_relative_workspace(tmp_path: Path, monkeypatch):
    pytest.importorskip("phonopy")
    root = _workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = phonon.prepare_phonon(Path("phonon-case"), supercell=(1, 1, 1))
    assert result.workspace == root
    assert phonon.post_phonon(Path("phonon-case"), results=_force_records(root)).status == "completed"


def test_post_phonon_explicit_shuffled_forces_produce_modes_without_collect_or_execute(tmp_path: Path, monkeypatch):
    pytest.importorskip("phonopy")
    root = _workspace(tmp_path)
    phonon.prepare_phonon(root, supercell=(1, 1, 1))
    records = _force_records(root)

    def forbidden(*args, **kwargs):
        pytest.fail("explicit phonon post must not collect or execute")

    monkeypatch.setattr("abacus_forge.composite.plan.collect_subtask", forbidden)
    monkeypatch.setattr(phonon.subprocess, "run", forbidden)
    result = phonon.post_phonon(root, results=list(reversed(records)), qpoints=[[0.0, 0.0, 0.0]])

    assert result.status == "completed"
    frequencies = np.asarray(result.summary["frequencies_THz"])
    assert frequencies.shape == (1, 6)
    assert np.abs(frequencies[0, :3]).max() < 1e-5
    assert (frequencies[0, 3:] > 1.0).all()
    assert (root / "reports/FORCE_CONSTANTS").is_file()
    assert [row["unit_id"] for row in result.subtasks] == [row["unit_id"] for row in records]


@pytest.mark.parametrize("explicit_results", [True, False])
def test_post_phonon_consumes_native_collector_flat_force_records(tmp_path: Path, explicit_results):
    pytest.importorskip("phonopy")
    from abacus_forge.composite.plan import collect_subtask

    root = _workspace(tmp_path)
    phonon.prepare_phonon(root, supercell=(1, 1, 1))
    synthetic = _force_records(root)
    collected = []
    for record in synthetic:
        child = root / record["workspace_rel"]
        directory = child / "outputs/OUT.ABACUS"
        directory.mkdir(parents=True)
        force_rows = "\n".join(
            f"Si{index + 1} " + " ".join(str(component) for component in force)
            for index, force in enumerate(record["metrics"]["force"])
        )
        text = f"NATOM = 2\nTOTAL ENERGY = -1.0\nTOTAL-FORCE (eV/Angstrom)\n{force_rows}\n\nSCF CONVERGED\nNORMAL END\n"
        (directory / "running_scf.log").write_text(text)
        (child / "outputs/stdout.log").write_text(text)
        result = collect_subtask(root, "phonon", record["unit_id"])
        assert result["status"] == "completed", result
        assert np.asarray(result["metrics"]["force"]).shape == (6,)
        collected.append(result)

    result = phonon.post_phonon(root, results=list(reversed(collected))) if explicit_results else phonon.post_phonon(root)

    assert result.status == "completed"
    assert np.asarray(result.summary["frequencies_THz"]).shape == (1, 6)


def test_post_phonon_missing_or_bad_force_does_not_publish_completed_spectrum(tmp_path: Path):
    pytest.importorskip("phonopy")
    root = _workspace(tmp_path)
    phonon.prepare_phonon(root, supercell=(1, 1, 1))
    records = _force_records(root)

    missing = phonon.post_phonon(root, results=records[:-1])
    assert missing.status == "degraded"
    assert missing.summary["missing_units"]
    assert not (root / "reports/FORCE_CONSTANTS").exists()

    records[0]["metrics"]["force"] = [[0.0, 0.0, 0.0]]
    bad = phonon.post_phonon(root, results=records)
    assert bad.status == "degraded"
    assert bad.diagnostics["invalid_force_units"] == [records[0]["unit_id"]]
    assert not (root / "reports/FORCE_CONSTANTS").exists()


def test_post_phonon_plan_and_results_survive_root_relocation(tmp_path: Path):
    pytest.importorskip("phonopy")
    root = _workspace(tmp_path)
    phonon.prepare_phonon(root, supercell=(1, 1, 1))
    records = _force_records(root)
    moved = tmp_path / "relocated"
    shutil.copytree(root, moved)
    result = phonon.post_phonon(moved, results=records)

    assert result.status == "completed"
    assert result.workspace == moved
    assert (moved / "reports/FORCE_CONSTANTS").is_file()


def test_post_phonon_only_needs_plan_dataset_and_explicit_facts(tmp_path: Path):
    pytest.importorskip("phonopy")
    root = _workspace(tmp_path)
    phonon.prepare_phonon(root, supercell=(1, 1, 1))
    records = _force_records(root)
    analysis = tmp_path / "cpu-analysis"
    shutil.copytree(root / "reports", analysis / "reports")

    result = phonon.post_phonon(analysis, results=records)

    assert result.status == "completed"
    assert (analysis / "reports/FORCE_CONSTANTS").is_file()
    assert not (analysis / "inputs").exists()
    assert not (analysis / "phonon").exists()


def test_post_phonon_rejects_changed_displacement_dataset_before_fitting(tmp_path: Path):
    library = pytest.importorskip("phonopy")
    root = _workspace(tmp_path)
    phonon.prepare_phonon(root, supercell=(1, 1, 1))
    records = _force_records(root)
    plan = json.loads((root / "reports/phonon_plan.json").read_text())
    path = root / plan["phonopy_file"]
    model = library.load(path, produce_fc=False)
    dataset = model.dataset
    dataset["first_atoms"] = list(reversed(dataset["first_atoms"]))
    model.dataset = dataset
    model.save(filename=path, settings={"force_sets": False, "force_constants": False})

    with pytest.raises(ValueError, match="displacement"):
        phonon.post_phonon(root, results=records)
    assert not (root / "reports/FORCE_CONSTANTS").exists()


@pytest.mark.parametrize("returncode", [0, 7])
def test_post_phonon_only_plot_preserves_explicit_cpu_command_and_failure_status(tmp_path: Path, monkeypatch, returncode):
    root = _workspace(tmp_path)
    (root / "custom.conf").write_text("BAND = 0 0 0 0.5 0 0\n")
    executable = tmp_path / "plot-phonopy"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import json, pathlib, sys\n"
        "pathlib.Path('plot-args.json').write_text(json.dumps(sys.argv[1:]))\n"
        "pathlib.Path('band.pdf').write_text('offline plot fixture')\n"
        f"raise SystemExit({returncode})\n"
    )
    executable.chmod(0o755)

    def forbidden(*args, **kwargs):
        pytest.fail("only_plot must not collect or run ABACUS")

    monkeypatch.setattr("abacus_forge.composite.plan.collect_subtask", forbidden)
    monkeypatch.setattr(phonon, "run_subtasks", forbidden)
    result = phonon.post_phonon(root, phonopy=str(executable), setting_file="custom.conf", only_plot=True)

    assert result.status == ("completed" if returncode == 0 else "failed")
    assert result.diagnostics["phonopy_post_returncode"] == returncode
    assert json.loads((root / "plot-args.json").read_text()) == ["-p", "custom.conf", "--abacus", "-s"]
    assert "band.pdf" in result.artifacts


@pytest.mark.parametrize("kwargs", [{"results": []}, {"qpoints": [[0.0, 0.0, 0.0]]}])
def test_post_phonon_only_plot_rejects_mixed_analysis_requests(tmp_path: Path, kwargs):
    root = _workspace(tmp_path)
    with pytest.raises(ValueError, match="only_plot"):
        phonon.post_phonon(root, only_plot=True, **kwargs)


@pytest.mark.parametrize("supercell, stepsize", [((0, 1, 1), 0.01), ((1, True, 1), 0.01), ((1, 1, 1), float("nan")), ((1, 1, 1), -0.01)])
def test_prepare_phonon_rejects_invalid_displacement_inputs(tmp_path: Path, supercell, stepsize):
    pytest.importorskip("phonopy")
    root = _workspace(tmp_path)
    with pytest.raises(ValueError):
        phonon.prepare_phonon(root, supercell=supercell, displacement_stepsize=stepsize)
    assert not (root / "reports/phonon_plan.json").exists()
