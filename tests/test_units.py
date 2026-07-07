from __future__ import annotations

import json
import stat
from pathlib import Path

from ase import Atoms

from abacus_forge.api import UnitModifySpec, UnitSpec, collect_unit, execute_unit, modify_unit, prepare_unit
from abacus_forge.input_io import read_input, read_kpt
from abacus_forge.dos_data import write_sample_dos_family_artifacts
from abacus_forge.workspace import Workspace


def test_prepare_unit_writes_manifest_and_handoffs_source_artifacts(tmp_path: Path) -> None:
    source = tmp_path / "band-scf"
    prepared_source = prepare_unit(
        UnitSpec(
            task="band",
            unit="scf",
            workdir=source,
            structure=Atoms(symbols=["Ni", "O"], positions=[[0, 0, 0], [1, 1, 1]], cell=[4, 4, 4], pbc=True),
            parameters={"out_chg": 1},
        )
    )
    (prepared_source.workspace.inputs_dir / "OUT.ABACUS").mkdir()
    (prepared_source.workspace.inputs_dir / "OUT.ABACUS" / "ABACUS-CHARGE-DENSITY.restart").write_text("chg", encoding="utf-8")

    result = prepare_unit(
        UnitSpec(
            task="band",
            unit="nscf",
            workdir=tmp_path / "band-nscf",
            source_workdir=source,
            line_kpoints=[
                {"coords": [0.0, 0.0, 0.0], "label": "G"},
                {"coords": [0.5, 0.0, 0.0], "label": "X"},
            ],
            line_segments=12,
        )
    )

    assert result.unit == "nscf"
    assert result.workspace.inputs_dir.joinpath("OUT.ABACUS", "ABACUS-CHARGE-DENSITY.restart").read_text(encoding="utf-8") == "chg"
    input_text = result.workspace.inputs_dir.joinpath("INPUT").read_text(encoding="utf-8")
    assert "calculation nscf" in input_text
    assert "out_band 1" in input_text
    assert "symmetry 0" in input_text
    manifest = json.loads(result.workspace.root.joinpath("forge-unit.json").read_text(encoding="utf-8"))
    assert manifest["task"] == "band"
    assert manifest["unit"] == "nscf"
    assert manifest["source_workdir"] == str(source)
    assert manifest["prepared"] is True


def test_prepare_unit_reproduces_reference_dos_nscf_controls(tmp_path: Path) -> None:
    source = tmp_path / "dos-scf"
    prepared_source = prepare_unit(
        UnitSpec(
            task="dos",
            unit="scf",
            workdir=source,
            structure=Atoms(symbols=["Ni", "O"], positions=[[0, 0, 0], [1, 1, 1]], cell=[4, 4, 4], pbc=True),
            parameters={"basis_type": "lcao"},
        )
    )
    (prepared_source.workspace.inputs_dir / "OUT.ABACUS").mkdir()
    (prepared_source.workspace.inputs_dir / "OUT.ABACUS" / "ABACUS-CHARGE-DENSITY.restart").write_text("chg", encoding="utf-8")

    result = prepare_unit(
        UnitSpec(
            task="dos",
            unit="nscf",
            workdir=tmp_path / "dos-nscf",
            source_workdir=source,
            parameters={
                "basis_type": "lcao",
                "dos_edelta_ev": 0.01,
                "dos_sigma": 0.07,
                "dos_scale": 0.01,
                "dos_nche": 1000,
            },
        )
    )

    input_text = result.workspace.inputs_dir.joinpath("INPUT").read_text(encoding="utf-8")
    assert "calculation nscf" in input_text
    assert "init_chg file" in input_text
    assert "out_chg -1" in input_text
    assert "out_dos 2" in input_text
    assert "dos_scale 0.01" in input_text
    assert "dos_nche 1000" in input_text


def test_execute_and_collect_unit_are_decoupled_for_abacus(tmp_path: Path) -> None:
    executable = _write_fake_abacus(tmp_path / "fake-abacus")
    prepared = prepare_unit(
        UnitSpec(
            task="cell-relax",
            workdir=tmp_path / "cell-relax",
            structure=Atoms(symbols=["Si"], positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True),
        )
    )

    executed = execute_unit(UnitSpec(task="cell-relax", workdir=prepared.workspace.root, command=[str(executable)]))
    collected = collect_unit(UnitSpec(task="cell-relax", workdir=prepared.workspace.root))

    assert executed.returncode == 0
    assert collected.status == "completed"
    assert collected.metrics["total_energy"] == -3.2
    manifest = json.loads(prepared.workspace.root.joinpath("forge-result.json").read_text(encoding="utf-8"))
    assert manifest["step"] == "collect"
    assert manifest["task"] == "cell-relax"


def test_modify_unit_edits_prepared_workspace_inputs(tmp_path: Path) -> None:
    prepared = prepare_unit(
        UnitSpec(
            task="cell-relax",
            workdir=tmp_path / "cell-relax",
            structure=Atoms(symbols=["Fe", "Fe"], positions=[[0, 0, 0], [1, 1, 1]], cell=[4, 4, 4], pbc=True),
            parameters={"ecutwfc": 80, "smearing_sigma": 0.02},
        )
    )

    result = modify_unit(
        UnitModifySpec(
            task="cell-relax",
            workdir=prepared.workspace.root,
            input_updates={"force_thr": "1e-4"},
            remove_parameters=["smearing_sigma"],
            kpt_mode="mesh",
            mesh=[6, 6, 2],
            shifts=[1, 1, 0],
            magmom_by_element={"Fe": 3.0},
            afm=True,
        )
    )

    assert result.status == "completed"
    assert result.task == "cell-relax"
    assert result.unit == "default"
    assert set(result.modified_files) == {"INPUT", "KPT", "STRU"}
    assert read_input(prepared.workspace.inputs_dir / "INPUT")["force_thr"] == "1e-4"
    assert "smearing_sigma" not in read_input(prepared.workspace.inputs_dir / "INPUT")
    assert read_kpt(prepared.workspace.inputs_dir / "KPT") == {"mode": "mesh", "mesh": [6, 6, 2], "shifts": [1, 1, 0]}
    manifest = json.loads(prepared.workspace.root.joinpath("forge-result.json").read_text(encoding="utf-8"))
    assert manifest["step"] == "modify"
    assert manifest["modified_files"] == ["INPUT", "KPT", "STRU"]


def test_modify_unit_rejects_missing_requested_input_file(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "missing-input").ensure_layout()

    try:
        modify_unit(UnitModifySpec(task="scf", workdir=workspace.root, input_updates={"ecutwfc": 90}))
    except FileNotFoundError as exc:
        assert "INPUT" in str(exc)
    else:
        raise AssertionError("modify_unit should reject requested INPUT edits when INPUT is absent")


def test_collect_unit_postprocesses_abacus_band_outputs(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "band-nscf").ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation nscf\nout_band 1\n")
    workspace.write_text("outputs/stdout.log", "BAND GAP = 1.2\nSCF CONVERGED\n")
    workspace.write_text("outputs/stderr.log", "")
    workspace.write_text("outputs/OUT.ABACUS/BANDS_1.dat", "1 0.0 -1.0 0.8\n2 0.5 -0.6 1.2\n")

    result = collect_unit(UnitSpec(task="band", unit="nscf", workdir=workspace.root))

    assert result.status == "completed"
    assert result.diagnostics["unit_postprocess"]["status"] == "completed"
    assert (workspace.outputs_dir / "band.png").exists()
    assert (workspace.outputs_dir / "band.dat").exists()
    assert (workspace.reports_dir / "metrics_band.json").exists()
    assert result.metrics["band_metrics"]["band_picture"].endswith("band.png")


def test_collect_unit_postprocesses_abacus_dos_outputs(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "dos-nscf").ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation nscf\nout_dos 2\nbasis_type lcao\n")
    workspace.write_text("outputs/stdout.log", "SCF CONVERGED\n")
    workspace.write_text("outputs/stderr.log", "")
    workspace.write_text("outputs/OUT.ABACUS/DOS1_smearing.dat", "-1.0 0.2\n0.0 1.0\n1.0 0.3\n")
    write_sample_dos_family_artifacts(workspace.outputs_dir / "OUT.ABACUS")

    result = collect_unit(UnitSpec(task="dos", unit="nscf", workdir=workspace.root, pdos_mode="species"))

    assert result.status == "completed"
    assert result.diagnostics["unit_postprocess"]["status"] == "completed"
    assert (workspace.outputs_dir / "DOS.dat").exists()
    assert (workspace.outputs_dir / "DOS.png").exists()
    assert (workspace.outputs_dir / "PDOS.dat").exists()
    assert (workspace.outputs_dir / "PDOS.png").exists()
    assert result.metrics["dos_family_metrics"]["artifacts"]["PDOS.png"].endswith("PDOS.png")


def test_collect_unit_normalizes_pyatb_band_pdf_for_collection(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "pyatb-band").ensure_layout()
    workspace.write_text("inputs/Input", "INPUT_PARAMETERS\n{}\n")
    workspace.write_text("inputs/Out/Band_Structure/band_info.dat", "band gap = 1.4\n")
    workspace.write_text("inputs/Out/Band_Structure/band.pdf", "%PDF-1.4\n")

    result = collect_unit(UnitSpec(task="band", unit="pyatb", engine="pyatb", workdir=workspace.root))

    assert result.status == "completed"
    assert result.diagnostics["unit_postprocess"]["status"] == "completed"
    assert (workspace.inputs_dir / "Out" / "Band_Structure" / "band.png").exists()
    assert result.metrics["band_picture"].endswith("band.png")


def test_prepare_unit_requires_source_for_nscf_units(tmp_path: Path) -> None:
    try:
        prepare_unit(UnitSpec(task="dos", unit="nscf", workdir=tmp_path / "dos-nscf"))
    except ValueError as exc:
        assert "requires source_workdir" in str(exc)
    else:
        raise AssertionError("prepare_unit should reject nscf without source_workdir")


def _write_fake_abacus(path: Path) -> Path:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "print('TOTAL ENERGY = -3.2')\n"
        "print('SCF CONVERGED')\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path
