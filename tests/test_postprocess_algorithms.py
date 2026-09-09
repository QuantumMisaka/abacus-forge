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
