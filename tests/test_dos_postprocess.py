from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from abacus_forge.dos_data import DOSData, PDOSData, write_sample_dos_family_artifacts
from abacus_forge.dos_postprocess import build_pdos_groups, postprocess_dos_family, write_dos_pdos


def test_build_pdos_groups_supports_all_modes(tmp_path: Path) -> None:
    write_sample_dos_family_artifacts(tmp_path)
    pdos = PDOSData.from_path(tmp_path / "PDOS")

    for mode in ["species", "species+shell", "species+orbital", "atom"]:
        groups, labels, titles = build_pdos_groups(pdos, mode=mode, atom_indices=[1])
        assert groups
        assert labels
        assert titles


def test_write_dos_pdos_uses_spin_suffixes(tmp_path: Path) -> None:
    output = tmp_path / "spin.dat"
    write_dos_pdos(
        [np.asarray([[1.0, 0.5], [2.0, 1.5]])],
        np.asarray([-1.0, 0.0]),
        ["Fe-d"],
        True,
        output,
    )

    text = output.read_text(encoding="utf-8")
    assert "E-E_F(eV)" in text
    assert "Fe-d_up" in text
    assert "Fe-d_dn" in text
    assert "1.500000" in text


def test_postprocess_dos_family_writes_suffix_outputs(tmp_path: Path) -> None:
    write_sample_dos_family_artifacts(tmp_path / "raw")
    total = DOSData.from_arrays([-1.0, 0.0, 1.0], [[0.1], [1.0], [0.2]])
    pdos = PDOSData.from_path(tmp_path / "raw" / "PDOS")

    artifacts = postprocess_dos_family(
        output_dir=tmp_path / "post",
        total_dos=total,
        projected_dos=pdos,
        pdos_mode="species+shell",
        plot_emin=-0.5,
        plot_emax=0.5,
        suffix="species",
    )

    assert "DOS_species.dat" in artifacts
    assert "DOS_species.png" in artifacts
    assert "PDOS_species.dat" in artifacts
    assert "PDOS_species.png" in artifacts
    assert (tmp_path / "post" / "PDOS_species.dat").read_text(encoding="utf-8").splitlines()[0].strip().startswith("Energy")


def test_postprocess_dos_family_empty_suffix_preserves_standard_names(tmp_path: Path) -> None:
    write_sample_dos_family_artifacts(tmp_path / "raw")
    total = DOSData.from_arrays([-1.0, 0.0, 1.0], [[0.1], [1.0], [0.2]])
    pdos = PDOSData.from_path(tmp_path / "raw" / "PDOS")

    artifacts = postprocess_dos_family(
        output_dir=tmp_path / "post",
        total_dos=total,
        projected_dos=pdos,
        save_plot=False,
        suffix="",
    )

    assert artifacts == {
        "DOS.dat": str(tmp_path / "post" / "DOS.dat"),
        "PDOS.dat": str(tmp_path / "post" / "PDOS.dat"),
    }


@pytest.mark.parametrize("suffix", ["../escape", "..\\escape", ".", ".."])
def test_postprocess_dos_family_rejects_unsafe_suffix_without_writing_outside_output(tmp_path: Path, suffix: str) -> None:
    total = DOSData.from_arrays([-1.0, 0.0, 1.0], [[0.1], [1.0], [0.2]])
    output = tmp_path / "post"

    with pytest.raises(ValueError, match="suffix"):
        postprocess_dos_family(
            output_dir=output,
            total_dos=total,
            save_data=True,
            save_plot=False,
            suffix=suffix,
        )

    assert not (tmp_path / "escape.dat").exists()
    assert not (tmp_path / "DOS_..dat").exists()
