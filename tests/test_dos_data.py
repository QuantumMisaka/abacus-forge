from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from abacus_forge import prepare
from abacus_forge.dos_data import DOSFamilyData, LocalDOSData, PDOSData, write_sample_dos_family_artifacts


def test_pdos_xml_queries_and_summary(tmp_path: Path) -> None:
    write_sample_dos_family_artifacts(tmp_path)
    pdos = PDOSData.from_path(tmp_path / "PDOS", tdos_path=tmp_path / "TDOS")

    assert pdos.summary()["points"] == 3
    assert pdos.summary()["orbitals"] == 4
    assert pdos.get_species() == ["Ni", "O"]
    assert pdos.get_species_shell("Ni") == [0, 1]
    assert pdos.get_atom_species(1) == "Ni"
    assert pdos.get_atom_shell(2) == [0, 1]

    assert np.allclose(pdos.get_pdos_by_species("Ni")[:, 0], [0.3, 0.5, 0.3])
    assert np.allclose(pdos.get_pdos_by_species_shell("O", "p")[:, 0], [0.15, 0.20, 0.15])
    assert np.allclose(pdos.get_pdos_by_atom_orbital(1, "p", 0)[:, 0], [0.2, 0.3, 0.2])


def test_pdos_data_from_job_dir_binds_unique_artifact_and_fermi(tmp_path: Path) -> None:
    root = tmp_path / "job"
    out = root / "OUT.ABACUS"
    out.mkdir(parents=True)
    (out / "PDOS").write_text(
        "<pdos><nspin>1</nspin><energy_values>0 1</energy_values>"
        "<orbital index='1' atom_index='1' species='Si' l='1' m='0' z='1'>"
        "<data>1 2</data></orbital></pdos>"
    )
    (out / "running_scf.log").write_text(" E-fermi : 5.0 eV\n")
    pdos = PDOSData.from_job_dir(root)
    assert pdos.efermi == 5.0
    assert pdos.energy.tolist() == [-5.0, -4.0]


def test_pdos_data_from_job_dir_reads_native_two_column_fermi(tmp_path: Path) -> None:
    root = tmp_path / "job"
    out = root / "OUT.ABACUS"
    out.mkdir(parents=True)
    (out / "PDOS").write_text("<pdos><energy_values>0 1</energy_values></pdos>")
    (out / "running_scf.log").write_text(
        "E_Fermi        -0.1000000000      1.25\n"
        "E_Fermi        -0.2000000000      2.50\n"
    )
    pdos = PDOSData.from_job_dir(root)
    assert pdos.efermi == 2.5


def test_pdos_data_from_job_dir_reads_underscore_single_value_fermi(tmp_path: Path) -> None:
    root = tmp_path / "job"
    out = root / "OUT.ABACUS"
    out.mkdir(parents=True)
    (out / "PDOS").write_text("<pdos><energy_values>0 1</energy_values></pdos>")
    (out / "running_scf.log").write_text("E_Fermi : 3.25 eV\n")
    pdos = PDOSData.from_job_dir(root)
    assert pdos.efermi == 3.25


def test_pdos_data_from_job_dir_rejects_ambiguous_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "job"
    out = root / "OUT.ABACUS"
    out.mkdir(parents=True)
    content = "<pdos><nspin>1</nspin><energy_values>0 1</energy_values></pdos>"
    (out / "PDOS").write_text(content)
    (out / "PDOS.xml").write_text(content)
    (out / "running_scf.log").write_text(" E-fermi : 5.0 eV\n")
    with pytest.raises(ValueError, match="exactly one PDOS"):
        PDOSData.from_job_dir(root)


def test_pdos_data_from_job_dir_binds_log_to_pdos_output(tmp_path: Path) -> None:
    root = tmp_path / "job"
    out = root / "OUT.ABACUS"
    out.mkdir(parents=True)
    (out / "PDOS").write_text("<pdos><energy_values>0 1</energy_values></pdos>")
    (root / "OUT.other").mkdir()
    (root / "OUT.other" / "running_scf.log").write_text("E-fermi : 99 eV\n")
    with pytest.raises(ValueError, match="Fermi"):
        PDOSData.from_job_dir(root)


def test_pdos_data_from_job_dir_rejects_conflicting_fermi_values(tmp_path: Path) -> None:
    root = tmp_path / "job"
    out = root / "OUT.ABACUS"
    out.mkdir(parents=True)
    (out / "PDOS").write_text("<pdos><energy_values>0 1</energy_values></pdos>")
    (out / "running_scf.log").write_text("E-fermi : 1 eV\nE-fermi : 2 eV\n")
    (out / "running_nscf.log").write_text("E-fermi : 3 eV\n")
    with pytest.raises(ValueError, match="conflicting Fermi"):
        PDOSData.from_job_dir(root)


def test_pdos_data_from_job_dir_rejects_malformed_xml(tmp_path: Path) -> None:
    root = tmp_path / "job"
    out = root / "OUT.ABACUS"
    out.mkdir(parents=True)
    (out / "PDOS").write_text("<pdos>")
    (out / "running_scf.log").write_text("E-fermi : 1 eV\n")
    with pytest.raises(RuntimeError, match="malformed"):
        PDOSData.from_job_dir(root)


def test_sum_pdos_data_supports_spin_polarized_arrays() -> None:
    selected = [
        {"data": np.asarray([[1.0, 0.5], [2.0, 1.5]])},
        {"data": np.asarray([[0.25, 0.5], [0.75, 1.0]])},
    ]

    assert np.allclose(PDOSData.sum_pdos_data(selected), [[1.25, 1.0], [2.75, 2.5]])


def test_dos_family_summary_includes_reserved_ldos(tmp_path: Path) -> None:
    write_sample_dos_family_artifacts(tmp_path)
    family = DOSFamilyData(
        projected_dos=PDOSData.from_path(tmp_path / "PDOS"),
        local_dos=LocalDOSData(),
        metadata={"efermi": 3.2},
    )

    summary = family.summary()
    assert summary["projected_dos"]["species"] == ["Ni", "O"]
    assert summary["local_dos"]["implemented"] is False
    assert summary["metadata"]["efermi"] == 3.2


def test_prepare_rejects_independent_pdos_task_and_preserves_abacus_dos_parameters(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported task: pdos"):
        prepare(tmp_path / "pdos-case", task="pdos")

    workspace = prepare(tmp_path / "dos-case", task="dos", parameters={"dos_scale": 0.01, "dos_nche": 1000})
    input_text = (workspace.inputs_dir / "INPUT").read_text(encoding="utf-8")
    assert "dos_scale 0.01" in input_text
    assert "dos_nche 1000" in input_text


def test_prepare_lcao_dos_uses_abacus_out_dos_two(tmp_path: Path) -> None:
    workspace = prepare(tmp_path / "dos-lcao", task="dos", parameters={"basis_type": "lcao"})

    input_text = (workspace.inputs_dir / "INPUT").read_text(encoding="utf-8")
    assert "out_dos 2" in input_text
    assert "out_pdos" not in input_text
