from __future__ import annotations

import os
import stat
from pathlib import Path

from ase import Atoms

from abacus_forge.api import prepare
from abacus_forge.pyatb import collect_pyatb, prepare_pyatb_band
from abacus_forge.tasks import run_band_sequence
from abacus_forge.workspace import Workspace


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


def test_run_band_sequence_with_pyatb_backend(tmp_path: Path) -> None:
    abacus = _write_fake_abacus_with_matrix(tmp_path / "fake-abacus")
    pyatb = _write_fake_pyatb(tmp_path / "fake-pyatb")
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
    abacus = _write_fake_abacus_with_matrix(tmp_path / "fake-abacus")
    pyatb = _write_fake_pyatb(tmp_path / "fake-pyatb")
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


def _write_fake_abacus_with_matrix(path: Path) -> Path:
    body = [
        "#!/usr/bin/env python3",
        "from pathlib import Path",
        "workspace = Path.cwd().parent",
        "out = workspace / 'inputs' / 'OUT.ABACUS'",
        "out.mkdir(parents=True, exist_ok=True)",
        "(out / 'data-HR-sparse_SPIN0.csr').write_text('hr', encoding='utf-8')",
        "(out / 'data-SR-sparse_SPIN0.csr').write_text('sr', encoding='utf-8')",
        "(out / 'data-rR-sparse.csr').write_text('rr', encoding='utf-8')",
        "print('TOTAL ENERGY = -9.2')",
        "print('FERMI ENERGY = 3.2')",
        "print('SCF CONVERGED')",
    ]
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def _write_fake_pyatb(path: Path) -> Path:
    body = [
        "#!/usr/bin/env python3",
        "from pathlib import Path",
        "out = Path.cwd() / 'Out' / 'Band_Structure'",
        "out.mkdir(parents=True, exist_ok=True)",
        "(out / 'band_info.dat').write_text('Band gap is 2.5\\n', encoding='utf-8')",
        "(out / 'band.png').write_text('fake image', encoding='utf-8')",
        "print('pyatb done')",
    ]
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path
