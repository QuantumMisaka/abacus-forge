from __future__ import annotations

import json
from pathlib import Path

import pytest

from abacus_forge.band_data import write_sample_band_artifacts
from abacus_forge.dos_data import write_sample_dos_family_artifacts
from abacus_forge.postprocess_algorithms import (
    ExplicitPostprocessResult,
    PostprocessPreconditionError,
    PostprocessParseError,
    process_band_files,
    process_dos_files,
)


def _json_text(value: object) -> str:
    return json.dumps(value, sort_keys=True)


def test_process_band_files_uses_explicit_order_and_contained_outputs(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    write_sample_band_artifacts(sources, include_plot=False)
    extra = sources / "BANDS_3.dat"
    extra.write_text("this file must not be discovered\n", encoding="utf-8")
    output = tmp_path / "outputs" / "band"

    result = process_band_files(
        [sources / "BANDS_2.dat", sources / "BANDS_1.dat"],
        output,
        plot_emin=-2.0,
        plot_emax=2.0,
        save_data=True,
        save_plot=True,
    )

    assert isinstance(result, ExplicitPostprocessResult)
    assert result.summary["band_files"] == ["BANDS_2.dat", "BANDS_1.dat"]
    assert type(result.summary["num_points"]) is int
    assert type(result.summary["num_kpoints"]) is int
    assert type(result.summary["num_bands"]) is int
    assert type(result.summary["num_columns"]) is int
    assert "BANDS_3.dat" not in result.summary["band_files"]
    assert result.generated_paths == (output / "band.dat", output / "band.png")
    assert all(path.parent == output for path in result.generated_paths)
    data = (output / "band.dat").read_text(encoding="utf-8")
    assert data.index("# BANDS_2.dat") < data.index("# BANDS_1.dat")
    assert str(tmp_path) not in data
    assert str(tmp_path) not in _json_text(result.summary)
    assert str(tmp_path) not in _json_text(result.diagnostics)
    assert json.dumps(result.summary, allow_nan=False)
    assert json.dumps(result.diagnostics, allow_nan=False)


def test_process_band_files_counts_energy_columns_after_abacus_prefixes(tmp_path: Path) -> None:
    source = tmp_path / "BANDS_abacus.dat"
    source.write_text("1 0.0 -1.0 1.0\n2 0.5 -0.8 1.2\n", encoding="utf-8")

    result = process_band_files(
        [source],
        tmp_path / "output",
        plot_emin=-2.0,
        plot_emax=2.0,
        save_data=False,
        save_plot=False,
    )

    assert result.summary["num_columns"] == 4
    assert result.summary["num_bands"] == 2


def test_process_band_files_explicitly_shifts_energy_columns_and_records_axis(tmp_path: Path) -> None:
    source = tmp_path / "BANDS.dat"
    source.write_text("1 0.0 -1.0 1.0\n2 0.5 -0.8 1.2\n", encoding="utf-8")

    result = process_band_files(
        [source], tmp_path / "output", plot_emin=-3.0, plot_emax=3.0,
        save_data=True, save_plot=False, energy_axis="fermi_relative", fermi_reference_ev=0.5,
    )

    assert result.diagnostics["energy_axis"] == "fermi_relative"
    assert result.diagnostics["fermi_reference_ev"] == 0.5
    rows = [
        line.split()
        for line in (tmp_path / "output/band.dat").read_text().splitlines()
        if line and not line.startswith("#")
    ]
    assert rows[0][:2] == ["1", "0"]
    assert rows[0][2] == "-1.5"
    assert rows[1][:2] == ["2", "0.5"]
    assert rows[1][2] == "-1.3"


def test_process_band_files_raises_typed_parse_error_without_numeric_rows(tmp_path: Path) -> None:
    source = tmp_path / "BANDS_bad.dat"
    source.write_text("# no numeric rows\nnot a table\n", encoding="utf-8")

    with pytest.raises(PostprocessParseError, match="numeric rows"):
        process_band_files(
            [source],
            tmp_path / "output",
            plot_emin=-1.0,
            plot_emax=1.0,
            save_data=True,
            save_plot=False,
        )


def test_process_band_files_rejects_output_symlink_before_writing(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    write_sample_band_artifacts(sources, include_plot=False)
    output = tmp_path / "output"
    output.mkdir()
    outside = tmp_path / "outside.dat"
    (output / "band.dat").symlink_to(outside)

    with pytest.raises(PostprocessPreconditionError, match="symlink"):
        process_band_files(
            [sources / "BANDS_1.dat"],
            output,
            plot_emin=-1.0,
            plot_emax=1.0,
            save_data=True,
            save_plot=False,
        )

    assert not outside.exists()


def test_process_dos_files_raises_typed_parse_error_without_numeric_rows(tmp_path: Path) -> None:
    source = tmp_path / "DOS_bad_smearing.dat"
    source.write_text("# no numeric rows\nnot a table\n", encoding="utf-8")

    with pytest.raises(PostprocessParseError, match="numeric rows"):
        process_dos_files(
            [source],
            None,
            None,
            tmp_path / "output",
            include_tdos=True,
            include_pdos=False,
            pdos_mode="species",
            pdos_atom_indices=(),
            plot_emin=-1.0,
            plot_emax=1.0,
            save_data=True,
            save_plot=False,
            suffix=None,
        )


def test_process_dos_files_explicitly_shifts_energy_and_records_axis(tmp_path: Path) -> None:
    source = tmp_path / "DOS1_smearing.dat"
    source.write_text("0.0 1.0\n1.0 2.0\n", encoding="utf-8")
    result = process_dos_files(
        [source], None, None, tmp_path / "output", include_tdos=True, include_pdos=False,
        pdos_mode="species", pdos_atom_indices=(), plot_emin=-2.0, plot_emax=2.0,
        save_data=True, save_plot=False, suffix=None,
        energy_axis="fermi_relative", fermi_reference_ev=0.5,
    )
    assert result.diagnostics["energy_axis"] == "fermi_relative"
    assert result.diagnostics["fermi_reference_ev"] == 0.5
    assert "-0.500000" in (tmp_path / "output/DOS.dat").read_text()


def test_process_dos_files_uses_explicit_order_and_reports_missing_optional_family(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    write_sample_dos_family_artifacts(sources)
    output = tmp_path / "outputs" / "dos"

    result = process_dos_files(
        [sources / "DOS2_smearing.dat", sources / "DOS1_smearing.dat"],
        None,
        sources / "TDOS",
        output,
        include_tdos=True,
        include_pdos=True,
        pdos_mode="species",
        pdos_atom_indices=(),
        plot_emin=-2.0,
        plot_emax=2.0,
        save_data=True,
        save_plot=True,
        suffix="selected",
    )

    assert result.summary["total_dos"]["dos_files"] == ["DOS2_smearing.dat", "DOS1_smearing.dat"]
    assert type(result.summary["total_dos"]["points"]) is int
    assert type(result.summary["total_dos"]["energy_min"]) is float
    assert type(result.summary["total_dos"]["spin_channels"]) is int
    assert result.summary["projected_dos"] is None
    assert result.diagnostics["missing_families"] == ["pdos"]
    assert result.generated_paths == (
        output / "DOS_selected.dat",
        output / "DOS_selected.png",
    )
    assert all(path.parent == output for path in result.generated_paths)
    assert str(tmp_path) not in _json_text(result.summary)
    assert str(tmp_path) not in _json_text(result.diagnostics)
    assert json.dumps(result.summary, allow_nan=False)
    assert json.dumps(result.diagnostics, allow_nan=False)


def test_process_dos_files_uses_dos_column_from_three_column_abacus_table(tmp_path: Path) -> None:
    source = tmp_path / "DOS1_smearing.dat"
    source.write_text(
        "# Energy DOS cumulative_integral\n-1.0 0.1 0.1\n0.0 1.0 1.1\n1.0 0.2 1.3\n",
        encoding="utf-8",
    )

    result = process_dos_files(
        [source],
        None,
        None,
        tmp_path / "output",
        include_tdos=True,
        include_pdos=False,
        pdos_mode="species",
        pdos_atom_indices=(),
        plot_emin=-2.0,
        plot_emax=2.0,
        save_data=True,
        save_plot=False,
        suffix=None,
    )

    assert result.summary["total_dos"]["points"] == 3
    assert result.summary["total_dos"]["spin_channels"] == 1
    rows = [
        [float(value) for value in line.split()]
        for line in (tmp_path / "output" / "DOS.dat").read_text(encoding="utf-8").splitlines()[1:]
        if line.strip()
    ]
    assert rows == [[-1.0, 0.1], [0.0, 1.0], [1.0, 0.2]]


def test_process_dos_files_combines_explicit_spin_files_horizontally(tmp_path: Path) -> None:
    spin_up = tmp_path / "DOS1_smearing.dat"
    spin_down = tmp_path / "DOS2_smearing.dat"
    spin_up.write_text("-1.0 0.1 0.1\n0.0 1.0 1.1\n1.0 0.2 1.3\n", encoding="utf-8")
    spin_down.write_text("-1.0 0.3 0.3\n0.0 0.8 1.1\n1.0 0.4 1.5\n", encoding="utf-8")

    result = process_dos_files(
        [spin_up, spin_down],
        None,
        None,
        tmp_path / "output",
        include_tdos=True,
        include_pdos=False,
        pdos_mode="species",
        pdos_atom_indices=(),
        plot_emin=-2.0,
        plot_emax=2.0,
        save_data=True,
        save_plot=False,
        suffix=None,
    )

    assert result.summary["total_dos"]["points"] == 3
    assert result.summary["total_dos"]["spin_channels"] == 2
    rows = [
        [float(value) for value in line.split()]
        for line in (tmp_path / "output" / "DOS.dat").read_text(encoding="utf-8").splitlines()[1:]
        if line.strip()
    ]
    assert rows == [[-1.0, 0.1, 0.3], [0.0, 1.0, 0.8], [1.0, 0.2, 0.4]]


def test_process_dos_files_generates_stable_data_and_plot_paths(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    write_sample_dos_family_artifacts(sources)
    first = process_dos_files(
        [sources / "DOS1_smearing.dat"],
        sources / "PDOS",
        sources / "TDOS",
        tmp_path / "first",
        include_tdos=True,
        include_pdos=True,
        pdos_mode="species+shell",
        pdos_atom_indices=(),
        plot_emin=-2.0,
        plot_emax=2.0,
        save_data=True,
        save_plot=True,
        suffix="stable",
    )
    second = process_dos_files(
        [sources / "DOS1_smearing.dat"],
        sources / "PDOS",
        sources / "TDOS",
        tmp_path / "second",
        include_tdos=True,
        include_pdos=True,
        pdos_mode="species+shell",
        pdos_atom_indices=(),
        plot_emin=-2.0,
        plot_emax=2.0,
        save_data=True,
        save_plot=True,
        suffix="stable",
    )

    assert first.generated_paths == (
        tmp_path / "first" / "DOS_stable.dat",
        tmp_path / "first" / "DOS_stable.png",
        tmp_path / "first" / "PDOS_stable.dat",
        tmp_path / "first" / "PDOS_stable.png",
    )
    assert second.generated_paths == (
        tmp_path / "second" / "DOS_stable.dat",
        tmp_path / "second" / "DOS_stable.png",
        tmp_path / "second" / "PDOS_stable.dat",
        tmp_path / "second" / "PDOS_stable.png",
    )
    assert (first.generated_paths[0]).read_bytes() == second.generated_paths[0].read_bytes()
    assert (first.generated_paths[1]).read_bytes() == second.generated_paths[1].read_bytes()
    assert (first.generated_paths[2]).read_bytes() == second.generated_paths[2].read_bytes()
    assert (first.generated_paths[3]).read_bytes() == second.generated_paths[3].read_bytes()


def test_process_dos_files_preserves_writer_io_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sources = tmp_path / "sources"
    write_sample_dos_family_artifacts(sources)

    def fail_writer(**kwargs: object) -> dict[str, str]:
        raise PermissionError("destination is not writable")

    monkeypatch.setattr("abacus_forge.dos_postprocess.postprocess_dos_family", fail_writer)

    with pytest.raises(PermissionError, match="destination is not writable"):
        process_dos_files(
            [sources / "DOS1_smearing.dat"],
            None,
            None,
            tmp_path / "output",
            include_tdos=True,
            include_pdos=False,
            pdos_mode="species",
            pdos_atom_indices=(),
            plot_emin=-1.0,
            plot_emax=1.0,
            save_data=True,
            save_plot=False,
            suffix=None,
        )


def test_process_band_files_preserves_output_mkdir_errors(tmp_path: Path) -> None:
    sources = tmp_path / "sources"
    write_sample_band_artifacts(sources, include_plot=False)
    output = tmp_path / "output"
    output.write_text("a regular file cannot be used as an output directory\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        process_band_files(
            [sources / "BANDS_1.dat"],
            output,
            plot_emin=-1.0,
            plot_emax=1.0,
            save_data=True,
            save_plot=False,
        )
