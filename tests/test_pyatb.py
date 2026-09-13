from __future__ import annotations

import os
from pathlib import Path

from ase import Atoms
import pytest

from abacus_forge.api import prepare
from abacus_forge.pyatb import collect_pyatb, prepare_pyatb_band
from abacus_forge.pyatb_manifest import classify_pyatb_output
from abacus_forge.tasks import run_band_sequence
from abacus_forge.workspace import Workspace
from tests.support.fake_executables import write_fake_abacus_with_matrix, write_fake_pyatb


def test_prepare_pyatb_band_writes_input_from_scf_outputs(tmp_path: Path) -> None:
    scf = prepare(
        tmp_path / "scf",
        task="scf",
        structure=Atoms(symbols=["Si"], positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True),
        parameters={"basis_type": "lcao", "suffix": "ABACUS", "nspin": 1},
    )
    scf.write_text("outputs/stdout.log", "FERMI ENERGY = 3.2\nSCF CONVERGED\n")
    scf.write_text("inputs/OUT.ABACUS/data-HR-sparse_SPIN0.csr", "hr")
    scf.write_text("inputs/OUT.ABACUS/data-SR-sparse_SPIN0.csr", "sr")
    scf.write_text("inputs/OUT.ABACUS/data-rR-sparse.csr", "rr")

    pyatb = prepare_pyatb_band(
        tmp_path / "pyatb",
        scf_workspace=scf,
        line_segments=16,
        line_kpoints=[
            {"coords": [0.0, 0.0, 0.0], "label": "G"},
            {"coords": [0.5, 0.0, 0.0], "label": "X"},
        ],
    )

    text = (pyatb.inputs_dir / "Input").read_text(encoding="utf-8")
    assert "package  ABACUS" in text
    assert "fermi_energy  3.2" in text
    assert "HR_route  OUT.ABACUS/data-HR-sparse_SPIN0.csr" in text
    assert "kpoint_label  G, X" in text
    assert "0.0 0.0 0.0 16" in text


def test_prepare_pyatb_band_links_outputs_from_relative_workspaces(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    scf = prepare(
        Path("scf"),
        task="scf",
        structure=Atoms(symbols=["Si"], positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True),
        parameters={"basis_type": "lcao", "suffix": "ABACUS", "nspin": 1},
    )
    scf.write_text("outputs/stdout.log", "FERMI ENERGY = 3.2\nSCF CONVERGED\n")
    scf.write_text("inputs/OUT.ABACUS/data-HR-sparse_SPIN0.csr", "hr")
    scf.write_text("inputs/OUT.ABACUS/data-SR-sparse_SPIN0.csr", "sr")
    scf.write_text("inputs/OUT.ABACUS/data-rR-sparse.csr", "rr")

    pyatb = prepare_pyatb_band(
        Path("pyatb"),
        scf_workspace=Path("scf"),
        line_kpoints=[
            {"coords": [0.0, 0.0, 0.0], "label": "G"},
            {"coords": [0.5, 0.0, 0.0], "label": "X"},
        ],
    )

    out_dir = pyatb.inputs_dir / "OUT.ABACUS"
    assert out_dir.is_symlink()
    assert Path(os.readlink(out_dir)).is_absolute()
    assert (out_dir / "data-HR-sparse_SPIN0.csr").read_text(encoding="utf-8") == "hr"


def test_collect_pyatb_reads_band_info_and_artifacts(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "pyatb-case").ensure_layout()
    workspace.write_text("inputs/Input", "INPUT_PARAMETERS\n{}\n")
    workspace.write_text("inputs/Out/Band_Structure/band_info.dat", "Band gap is 1.42\n")
    workspace.write_text("inputs/Out/Band_Structure/band.png", "fake")
    workspace.write_text("outputs/stderr.log", "")

    result = collect_pyatb(workspace)

    assert result.status == "completed"
    assert result.metrics["band_gap"] == 1.42
    assert result.metrics["band_picture"].endswith("band.png")
    assert "inputs/Out/Band_Structure/band_info.dat" in result.artifacts


def test_prepare_pyatb_band_reuses_spin0_overlap_for_spin_polarized_abacus(tmp_path: Path) -> None:
    scf = prepare(
        tmp_path / "scf-spin",
        task="scf",
        structure=Atoms(symbols=["Ni"], positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True),
        parameters={"basis_type": "lcao", "suffix": "ABACUS", "nspin": 2},
    )
    scf.write_text("outputs/stdout.log", "FERMI ENERGY = 7.7\nSCF CONVERGED\n")
    scf.write_text("inputs/OUT.ABACUS/data-HR-sparse_SPIN0.csr", "hr0")
    scf.write_text("inputs/OUT.ABACUS/data-HR-sparse_SPIN1.csr", "hr1")
    scf.write_text("inputs/OUT.ABACUS/data-SR-sparse_SPIN0.csr", "sr")
    scf.write_text("inputs/OUT.ABACUS/data-rR-sparse.csr", "rr")

    pyatb = prepare_pyatb_band(
        tmp_path / "pyatb-spin",
        scf_workspace=scf,
        line_kpoints=[
            {"coords": [0.0, 0.0, 0.0], "label": "G"},
            {"coords": [0.5, 0.0, 0.0], "label": "X"},
        ],
    )

    text = (pyatb.inputs_dir / "Input").read_text(encoding="utf-8")
    assert "HR_route  OUT.ABACUS/data-HR-sparse_SPIN0.csr OUT.ABACUS/data-HR-sparse_SPIN1.csr" in text
    assert "SR_route  OUT.ABACUS/data-SR-sparse_SPIN0.csr OUT.ABACUS/data-SR-sparse_SPIN0.csr" in text


@pytest.mark.parametrize("nspin", (1, 4))
def test_prepare_pyatb_band_accepts_new_shared_matrix_names(tmp_path: Path, nspin: int) -> None:
    scf = prepare(
        tmp_path / f"scf-{nspin}", task="scf",
        structure=Atoms(symbols=["Si"], positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True),
        parameters={"basis_type": "lcao", "suffix": "ABACUS", "nspin": nspin},
    )
    scf.write_text("outputs/stdout.log", "FERMI ENERGY = 3.2\nSCF CONVERGED\n")
    for name in ("hrs1_nao.csr", "sr_nao.csr", "rr.csr"):
        scf.write_text(f"inputs/OUT.ABACUS/{name}", name)

    pyatb = prepare_pyatb_band(
        tmp_path / f"pyatb-{nspin}", scf_workspace=scf,
        line_kpoints=[{"coords": [0.0, 0.0, 0.0], "label": "G"}],
    )
    text = (pyatb.inputs_dir / "Input").read_text(encoding="utf-8")
    assert "HR_route  OUT.ABACUS/hrs1_nao.csr" in text
    assert "SR_route  OUT.ABACUS/sr_nao.csr" in text
    assert "rR_route  OUT.ABACUS/rr.csr" in text


def test_prepare_pyatb_band_accepts_new_spin_pair_names(tmp_path: Path) -> None:
    scf = prepare(
        tmp_path / "scf-spin-new", task="scf",
        structure=Atoms(symbols=["Ni"], positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True),
        parameters={"basis_type": "lcao", "suffix": "ABACUS", "nspin": 2},
    )
    scf.write_text("outputs/stdout.log", "FERMI ENERGY = 7.7\nSCF CONVERGED\n")
    for name in ("hrs1_nao.csr", "hrs2_nao.csr", "sr_nao.csr", "rr.csr"):
        scf.write_text(f"inputs/OUT.ABACUS/{name}", name)
    pyatb = prepare_pyatb_band(
        tmp_path / "pyatb-spin-new", scf_workspace=scf,
        line_kpoints=[{"coords": [0.0, 0.0, 0.0], "label": "G"}],
    )
    text = (pyatb.inputs_dir / "Input").read_text(encoding="utf-8")
    assert "HR_route  OUT.ABACUS/hrs1_nao.csr OUT.ABACUS/hrs2_nao.csr" in text
    assert "SR_route  OUT.ABACUS/sr_nao.csr" in text


def test_prepare_pyatb_band_omits_missing_rr_route(tmp_path: Path) -> None:
    scf = prepare(
        tmp_path / "scf-no-rr", task="scf",
        structure=Atoms(symbols=["Si"], positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True),
        parameters={"basis_type": "lcao", "suffix": "ABACUS", "nspin": 1},
    )
    scf.write_text("outputs/stdout.log", "FERMI ENERGY = 3.2\nSCF CONVERGED\n")
    scf.write_text("inputs/OUT.ABACUS/hrs1_nao.csr", "hr")
    scf.write_text("inputs/OUT.ABACUS/sr_nao.csr", "sr")
    pyatb = prepare_pyatb_band(
        tmp_path / "pyatb-no-rr", scf_workspace=scf,
        line_kpoints=[{"coords": [0.0, 0.0, 0.0], "label": "G"}],
    )
    text = (pyatb.inputs_dir / "Input").read_text(encoding="utf-8")
    assert "rR_route" not in text


def test_prepare_pyatb_band_requires_paired_spin_hr_channels(tmp_path: Path) -> None:
    scf = prepare(
        tmp_path / "scf-spin-incomplete", task="scf",
        structure=Atoms(symbols=["Ni"], positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True),
        parameters={"basis_type": "lcao", "suffix": "ABACUS", "nspin": 2},
    )
    scf.write_text("outputs/stdout.log", "FERMI ENERGY = 7.7\nSCF CONVERGED\n")
    scf.write_text("inputs/OUT.ABACUS/hrs1_nao.csr", "hr1")
    scf.write_text("inputs/OUT.ABACUS/sr_nao.csr", "sr")
    with pytest.raises(FileNotFoundError):
        prepare_pyatb_band(
            tmp_path / "pyatb-spin-incomplete", scf_workspace=scf,
            line_kpoints=[{"coords": [0.0, 0.0, 0.0], "label": "G"}],
        )


@pytest.mark.parametrize(
    ("name", "kind"),
    (("hrs1_nao.csr", "matrix_hr"), ("hrs2_nao.csr", "matrix_hr"),
     ("sr_nao.csr", "matrix_sr"), ("rr.csr", "matrix_rr")),
)
def test_manifest_classifies_new_pyatb_matrix_names(name: str, kind: str) -> None:
    assert classify_pyatb_output(f"OUT.ABACUS/{name}")[0] == kind


def test_run_band_sequence_with_pyatb_backend(tmp_path: Path) -> None:
    abacus = write_fake_abacus_with_matrix(tmp_path / "fake-abacus")
    pyatb = write_fake_pyatb(tmp_path / "fake-pyatb")
    structure = Atoms(symbols=["Si"], positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True)

    result = run_band_sequence(
        tmp_path / "band-pyatb",
        structure=structure,
        parameters={"basis_type": "lcao", "suffix": "ABACUS", "nspin": 1},
        executable=str(abacus),
        pyatb_executable=str(pyatb),
        backend="pyatb",
        line_segments=8,
        line_kpoints=[
            {"coords": [0.0, 0.0, 0.0], "label": "G"},
            {"coords": [0.5, 0.0, 0.0], "label": "X"},
        ],
    )

    assert result.status == "completed"
    assert result.summary["backend"] == "pyatb"
    assert [item["task"] for item in result.subtasks] == ["scf", "pyatb-band"]
    assert result.summary["band_metrics"]["band_gap"] == 2.5
    assert "pyatb/inputs/Out/Band_Structure/band_info.dat" in result.artifacts


def test_run_band_sequence_auto_uses_pyatb_for_lcao(tmp_path: Path) -> None:
    abacus = write_fake_abacus_with_matrix(tmp_path / "fake-abacus")
    pyatb = write_fake_pyatb(tmp_path / "fake-pyatb")
    result = run_band_sequence(
        tmp_path / "band-auto",
        structure=Atoms(symbols=["Si"], positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True),
        parameters={"basis_type": "lcao"},
        executable=str(abacus),
        pyatb_executable=str(pyatb),
        backend="auto",
        line_kpoints=[
            {"coords": [0.0, 0.0, 0.0], "label": "G"},
            {"coords": [0.5, 0.0, 0.0], "label": "X"},
        ],
    )

    assert result.summary["backend"] == "pyatb"
