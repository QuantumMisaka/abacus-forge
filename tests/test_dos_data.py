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


def test_prepare_rejects_independent_pdos_task_and_drifted_dos_parameters(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported task: pdos"):
        prepare(tmp_path / "pdos-case", task="pdos")

    with pytest.raises(ValueError, match="dos_scale"):
        prepare(tmp_path / "dos-case", task="dos", parameters={"dos_scale": 1.2})


def test_prepare_lcao_dos_uses_abacus_out_dos_two(tmp_path: Path) -> None:
    workspace = prepare(tmp_path / "dos-lcao", task="dos", parameters={"basis_type": "lcao"})

    input_text = (workspace.inputs_dir / "INPUT").read_text(encoding="utf-8")
    assert "out_dos 2" in input_text
    assert "out_pdos" not in input_text
