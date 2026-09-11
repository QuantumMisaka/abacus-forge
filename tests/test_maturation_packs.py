from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from ase import Atoms
from ase.io import write as ase_write

import abacus_forge.composite.properties as property_module
from abacus_forge.api import prepare
from abacus_forge.cli import main
from abacus_forge.composite import (
    post_bec,
    post_charge_density,
    post_charge_diff,
    post_convergence,
    post_spin_density,
    post_vacancy,
    post_workfunc,
    prepare_bec,
    prepare_charge_diff,
    prepare_charge_density,
    prepare_convergence,
    prepare_spin_density,
    prepare_vacancy,
    prepare_workfunc,
)
from abacus_forge.cube import CubeData, subtract_cubes
from abacus_forge.input_io import read_input, write_input
from abacus_forge.modify import modify_stru
from abacus_forge.structure import AbacusStructure


def test_modify_stru_supports_vacancy_indices_and_cli_supercell(tmp_path: Path, capsys) -> None:
    atoms = Atoms(
        symbols=["Fe", "O", "O"],
        positions=[[0.0, 0.0, 0.0], [1.2, 1.2, 1.2], [2.0, 2.0, 2.0]],
        cell=[4.0, 4.0, 4.0],
        pbc=True,
    )
    modified = modify_stru(atoms, vacancy_indices=[2])
    assert modified.atoms.get_chemical_symbols() == ["Fe", "O"]
    assert np.allclose(modified.atoms.get_positions()[1], [2.0, 2.0, 2.0])

    source = tmp_path / "FeOO.xyz"
    output = tmp_path / "STRU.super"
    ase_write(source, atoms)
    assert (
        main(
            [
                "modify-stru",
                str(source),
                "--output",
                str(output),
                "--structure-format",
                "xyz",
                "--supercell",
                "2",
                "1",
                "1",
                "--vacancy-index",
                "2",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["natoms"] == 5
    recovered = AbacusStructure.from_input(output, structure_format="stru")
    assert recovered.atoms.get_chemical_symbols().count("Fe") == 2
    assert recovered.atoms.get_chemical_symbols().count("O") == 3


def test_convergence_prepare_and_postprocess_collects_points(tmp_path: Path) -> None:
    workspace = _prepared_workspace(tmp_path / "conv-root")

    result = prepare_convergence(workspace.root, key="ecutwfc", values=["60", "80"])
    assert result.status == "prepared"
    assert result.summary == {"key": "ecutwfc", "count": 2}
    assert read_input(workspace.root / "convergence" / "ecutwfc_60" / "inputs" / "INPUT")["ecutwfc"] == "60"

    _write_completed_stdout(workspace.root / "convergence" / "ecutwfc_60", energy=-6.0)
    _write_completed_stdout(workspace.root / "convergence" / "ecutwfc_80", energy=-6.2)
    posted = post_convergence(workspace.root, key="ecutwfc")

    assert posted.status == "completed"
    assert posted.summary["key"] == "ecutwfc"
    assert posted.summary["points"] == [
        {"workspace": str(workspace.root / "convergence" / "ecutwfc_60"), "value": "60", "total_energy": -6.0, "energy_per_atom": None},
        {"workspace": str(workspace.root / "convergence" / "ecutwfc_80"), "value": "80", "total_energy": -6.2, "energy_per_atom": None},
    ]
    assert "reports/metrics_convergence.json" in posted.artifacts


def test_cube_subtraction_and_spin_density_postprocess(tmp_path: Path) -> None:
    up = _write_cube(tmp_path / "up.cube", [3.0, 4.0])
    down = _write_cube(tmp_path / "down.cube", [1.0, 1.5])
    diff = subtract_cubes(up, down)

    assert diff.data.reshape(-1).tolist() == [2.0, 2.5]

    workspace = _prepared_workspace(tmp_path / "spin-root")
    prepared = prepare_spin_density(workspace.root)
    assert prepared.status == "prepared"
    spin_dir = workspace.root / "spin-density" / "scf"
    _write_cube(spin_dir / "outputs" / "SPIN1_CHG.cube", [3.0, 4.0])
    _write_cube(spin_dir / "outputs" / "SPIN2_CHG.cube", [1.0, 1.5])
    posted = post_spin_density(workspace.root)

    assert posted.status == "completed"
    assert posted.summary["spin_density_file"].endswith("spin_density.cube")
    assert CubeData.from_file(workspace.root / "reports" / "spin_density.cube").data.reshape(-1).tolist() == [2.0, 2.5]
    manifest = posted.diagnostics["property_manifest"]
    assert manifest["schema_version"] == "forge.property-manifest/v1"
    assert {entry["spin"] for entry in manifest["inputs"]} == {"up", "down"}
    derived = next(entry for entry in manifest["outputs"] if entry["kind"] == "cube")
    assert derived["path_rel"] == "reports/spin_density.cube"
    assert len(derived["source_artifact_ids"]) == 2
    assert derived["source_artifact_ids"] == [entry["artifact_id"] for entry in manifest["inputs"]]


def test_spin_density_postprocess_accepts_native_chgs_names(tmp_path: Path) -> None:
    workspace = _prepared_workspace(tmp_path / "native-spin-root")
    prepare_spin_density(workspace.root)
    spin_dir = workspace.root / "spin-density" / "scf"
    _write_cube(spin_dir / "outputs" / "chgs1.cube", [3.0, 4.0])
    _write_cube(spin_dir / "outputs" / "chgs2.cube", [1.0, 1.5])

    posted = post_spin_density(workspace.root)

    assert posted.status == "completed"
    assert posted.summary["spin_density_file"].endswith("spin_density.cube")
    assert posted.diagnostics["spin_up"].endswith("chgs1.cube")
    assert posted.diagnostics["spin_down"].endswith("chgs2.cube")
    assert CubeData.from_file(workspace.root / "reports" / "spin_density.cube").data.reshape(-1).tolist() == [2.0, 2.5]


def test_property_post_does_not_read_escaped_cube_symlinks(tmp_path: Path) -> None:
    workspace = _prepared_workspace(tmp_path / "escaped-spin-root")
    prepare_spin_density(workspace.root)
    outside_up = tmp_path / "outside-up.cube"
    outside_down = tmp_path / "outside-down.cube"
    _write_cube(outside_up, [3.0, 4.0])
    _write_cube(outside_down, [1.0, 1.5])
    output_dir = workspace.root / "spin-density" / "scf" / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        (output_dir / "SPIN1_CHG.cube").symlink_to(outside_up)
        (output_dir / "SPIN2_CHG.cube").symlink_to(outside_down)
    except OSError:
        pytest.skip("symlinks unavailable")

    posted = post_spin_density(workspace.root)

    assert posted.status == "degraded"
    assert posted.summary["spin_density_file"] is None
    assert not (workspace.root / "reports" / "spin_density.cube").exists()
    manifest = posted.diagnostics["property_manifest"]
    cube_reasons = {entry["reason"] for entry in manifest["missing"] if entry["kind"] == "cube"}
    assert "escaped" in cube_reasons


def test_charge_density_manifest_records_canonical_missing_source(tmp_path: Path) -> None:
    workspace = _prepared_workspace(tmp_path / "charge-root")
    prepare_charge_density(workspace.root)

    posted = post_charge_density(workspace.root)

    assert posted.status == "degraded"
    manifest = posted.diagnostics["property_manifest"]
    assert manifest["inputs"] == []
    assert manifest["missing"] == [
        {
            "path_rel": "charge-density/scf/inputs/OUT.ABACUS/SPIN1_CHG.cube",
            "kind": "cube",
            "role": "input",
            "origin": "source",
            "spin": "unknown",
            "reason": "missing",
        }
    ]
    assert any(entry["path_rel"] == "reports/metrics_charge_density.json" for entry in manifest["outputs"])


@pytest.mark.parametrize(
    ("suffix", "expected_suffix"),
    (("CUSTOM", "CUSTOM"), ("../escape", "ABACUS"), ("", "ABACUS")),
)
def test_property_manifest_canonical_suffix_is_safe_and_deterministic(
    tmp_path: Path, suffix: str, expected_suffix: str
) -> None:
    workspace = _prepared_workspace(tmp_path / "suffix-root")
    parameters = read_input(workspace.root / "inputs" / "INPUT")
    parameters["suffix"] = suffix
    write_input(workspace.root / "inputs" / "INPUT", parameters)
    prepare_charge_density(workspace.root)

    posted = post_charge_density(workspace.root)

    assert posted.diagnostics["property_manifest"]["missing"][0]["path_rel"] == (
        f"charge-density/scf/inputs/OUT.{expected_suffix}/SPIN1_CHG.cube"
    )


def test_charge_diff_manifest_links_three_sources_to_derived_cube(tmp_path: Path) -> None:
    workspace = _prepared_workspace(tmp_path / "diff-root")
    prepare_charge_diff(workspace.root)
    for name, values in (("full", [4.0, 5.0]), ("subsystem1", [1.0, 1.5]), ("subsystem2", [2.0, 2.5])):
        _write_cube(workspace.root / "charge-diff" / name / "outputs" / "SPIN1_CHG.cube", values)

    posted = post_charge_diff(workspace.root)

    assert posted.status == "completed"
    manifest = posted.diagnostics["property_manifest"]
    source_paths = {entry["path_rel"] for entry in manifest["inputs"]}
    assert source_paths == {
        "charge-diff/full/outputs/SPIN1_CHG.cube",
        "charge-diff/subsystem1/outputs/SPIN1_CHG.cube",
        "charge-diff/subsystem2/outputs/SPIN1_CHG.cube",
    }
    derived = next(entry for entry in manifest["outputs"] if entry["kind"] == "cube")
    assert derived["source_artifact_ids"] == [entry["artifact_id"] for entry in manifest["inputs"]]


def test_spin_density_api_and_legacy_cli_share_property_manifest(tmp_path: Path, capsys) -> None:
    workspace = _prepared_workspace(tmp_path / "spin-parity")
    prepare_spin_density(workspace.root)
    for filename, values in (("SPIN1_CHG.cube", [3.0, 4.0]), ("SPIN2_CHG.cube", [1.0, 1.5])):
        _write_cube(workspace.root / "spin-density" / "scf" / "outputs" / filename, values)
    direct = post_spin_density(workspace.root)

    assert main(["spin-density", "post", str(workspace.root), "--json"]) == 0
    cli = json.loads(capsys.readouterr().out)

    assert cli["diagnostics"]["property_manifest"] == direct.diagnostics["property_manifest"]
    assert cli["status"] == direct.status
    assert cli["summary"] == direct.summary
    assert cli["artifacts"] == direct.artifacts
    assert cli["diagnostics"] == direct.diagnostics
    assert set(direct.to_dict()) == {"task", "workspace", "status", "subtasks", "summary", "artifacts", "diagnostics"}


def test_charge_density_api_and_legacy_cli_share_property_manifest(tmp_path: Path, capsys) -> None:
    workspace = _prepared_workspace(tmp_path / "charge-parity")
    prepare_charge_density(workspace.root)
    _write_cube(workspace.root / "charge-density" / "scf" / "outputs" / "SPIN1_CHG.cube", [3.0, 4.0])
    direct = post_charge_density(workspace.root)

    assert main(["charge-density", "post", str(workspace.root), "--json"]) == 0
    cli = json.loads(capsys.readouterr().out)

    assert cli["diagnostics"]["property_manifest"] == direct.diagnostics["property_manifest"]
    assert cli["status"] == direct.status
    assert cli["summary"] == direct.summary
    assert cli["artifacts"] == direct.artifacts
    assert cli["diagnostics"] == direct.diagnostics


def test_charge_diff_api_and_legacy_cli_share_property_manifest(tmp_path: Path, capsys) -> None:
    workspace = _prepared_workspace(tmp_path / "charge-diff-parity")
    prepare_charge_diff(workspace.root)
    for name, values in (("full", [4.0, 5.0]), ("subsystem1", [1.0, 1.5]), ("subsystem2", [2.0, 2.5])):
        _write_cube(workspace.root / "charge-diff" / name / "outputs" / "SPIN1_CHG.cube", values)
    direct = post_charge_diff(workspace.root)

    assert main(["charge-diff", "post", str(workspace.root), "--json"]) == 0
    cli = json.loads(capsys.readouterr().out)

    assert cli["diagnostics"]["property_manifest"] == direct.diagnostics["property_manifest"]
    assert cli["status"] == direct.status
    assert cli["summary"] == direct.summary
    assert cli["artifacts"] == direct.artifacts
    assert cli["diagnostics"] == direct.diagnostics


def test_property_manifest_projection_failure_preserves_legacy_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _prepared_workspace(tmp_path / "projection-failure")
    prepare_spin_density(workspace.root)
    _write_cube(workspace.root / "spin-density" / "scf" / "outputs" / "SPIN1_CHG.cube", [3.0, 4.0])
    _write_cube(workspace.root / "spin-density" / "scf" / "outputs" / "SPIN2_CHG.cube", [1.0, 1.5])

    def fail_manifest(*args: object, **kwargs: object) -> None:
        raise RuntimeError("injected projection failure")

    monkeypatch.setattr(property_module, "build_property_manifest", fail_manifest)
    result = post_spin_density(workspace.root)

    assert result.status == "completed"
    assert result.summary["spin_density_file"].endswith("spin_density.cube")
    assert "reports/spin_density.cube" in result.artifacts
    assert "property_manifest" not in result.diagnostics
    assert any("projection unavailable" in warning for warning in result.diagnostics["warnings"])
    json.dumps(result.to_dict(), allow_nan=False)


def test_workfunc_prepare_and_postprocess(tmp_path: Path) -> None:
    workspace = _prepared_workspace(tmp_path / "workfunc-root")
    prepared = prepare_workfunc(workspace.root, vacuum_axis="c", dipole_correction=True)
    assert prepared.status == "prepared"
    subdir = workspace.root / "workfunc" / "scf"
    params = read_input(subdir / "inputs" / "INPUT")
    assert params["out_pot"] == "2"
    assert params["dip_cor_flag"] == "1"

    _write_completed_stdout(subdir, energy=-1.0, fermi=4.0)
    _write_cube(subdir / "outputs" / "ElecStaticPot.cube", [8.0, 10.0])
    posted = post_workfunc(workspace.root, vacuum_axis="c")

    assert posted.status == "completed"
    assert posted.summary["vacuum_level_ev"] == 10.0
    assert posted.summary["work_function_ev"] == 6.0


def test_vacancy_prepare_and_postprocess(tmp_path: Path) -> None:
    workspace = _prepared_workspace(tmp_path / "vacancy-root")
    prepared = prepare_vacancy(workspace.root, vacancy_indices=[2], supercell=[1, 1, 1])
    assert prepared.status == "prepared"
    assert (workspace.root / "vacancy" / "pristine" / "inputs" / "STRU").exists()
    defect = AbacusStructure.from_input(workspace.root / "vacancy" / "defect_002" / "inputs" / "STRU", structure_format="stru")
    assert len(defect.atoms) == 1

    _write_completed_stdout(workspace.root / "vacancy" / "pristine", energy=-10.0)
    _write_completed_stdout(workspace.root / "vacancy" / "defect_002", energy=-6.0)
    (workspace.root / "vacancy" / "ref_energy.txt").write_text("Fe -2.5\n", encoding="utf-8")
    posted = post_vacancy(workspace.root)

    assert posted.status == "completed"
    assert posted.summary["formation_energies"] == [
        {"defect": "defect_002", "removed_symbol": "Fe", "formation_energy_ev": 1.5}
    ]


def test_bec_prepare_and_postprocess(tmp_path: Path) -> None:
    workspace = _prepared_workspace(tmp_path / "bec-root")
    prepared = prepare_bec(workspace.root, atom_indices=[1], displacement=0.02, directions=["x"])
    assert prepared.status == "prepared"
    assert (workspace.root / "bec" / "org" / "inputs" / "INPUT").exists()
    assert (workspace.root / "bec" / "disp_atom001_x_plus" / "inputs" / "STRU").exists()
    assert (workspace.root / "bec" / "disp_atom001_x_minus" / "inputs" / "STRU").exists()

    _write_polarization(workspace.root / "bec" / "disp_atom001_x_plus", [1.2, 0.0, 0.0])
    _write_polarization(workspace.root / "bec" / "disp_atom001_x_minus", [0.8, 0.0, 0.0])
    posted = post_bec(workspace.root)

    assert posted.status == "completed"
    assert posted.summary["bec_tensors"]["atom001"][0] == pytest.approx([10.0, 0.0, 0.0])


def test_new_property_packs_are_exposed_by_cli(tmp_path: Path, capsys) -> None:
    workspace = _prepared_workspace(tmp_path / "cli-root")

    assert main(["convergence", "prepare", str(workspace.root), "--key", "ecutwfc", "--value", "60", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "prepared"

    assert main(["spin-density", "prepare", str(workspace.root), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["task"] == "spin-density"

    assert main(["workfunc", "prepare", str(workspace.root), "--vacuum-axis", "c", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["task"] == "workfunc"


def _prepared_workspace(path: Path):
    return prepare(
        path,
        task="scf",
        structure=Atoms(
            symbols=["Fe", "O"],
            positions=[[0.0, 0.0, 0.0], [1.5, 1.5, 1.5]],
            cell=[4.0, 4.0, 4.0],
            pbc=True,
        ),
        parameters={"ecutwfc": 60, "suffix": "ABACUS"},
        kpoints=[1, 1, 1],
    )


def _write_completed_stdout(workspace: Path, *, energy: float, fermi: float | None = None) -> None:
    outputs = workspace / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    lines = [f"TOTAL ENERGY = {energy}", "SCF CONVERGED"]
    if fermi is not None:
        lines.insert(1, f"FERMI ENERGY = {fermi}")
    (outputs / "stdout.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (outputs / "stderr.log").write_text("", encoding="utf-8")


def _write_cube(path: Path, values: list[float]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(
        [
            "Forge cube fixture",
            "OUTER LOOP: X, MIDDLE LOOP: Y, INNER LOOP: Z",
            "1 0.0 0.0 0.0",
            f"1 1.0 0.0 0.0",
            f"1 0.0 1.0 0.0",
            f"{len(values)} 0.0 0.0 1.0",
            "1 0.0 0.0 0.0 0.0",
            " ".join(str(value) for value in values),
        ]
    )
    path.write_text(text + "\n", encoding="utf-8")
    return path


def _write_polarization(workspace: Path, values: list[float]) -> None:
    reports = workspace / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "polarization.json").write_text(json.dumps({"polarization": values}), encoding="utf-8")
