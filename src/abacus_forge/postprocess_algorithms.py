"""Event-free algorithms for explicit ABACUS postprocess inputs.

The functions in this module deliberately do not know about a Forge
workspace.  A caller supplies the exact input files and the output directory
that it has already admitted.  The compatibility wrappers in
``unit_postprocess`` retain the old workspace discovery and diagnostic
behavior.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Literal

import numpy as np

from abacus_forge.band_data import BandData
from abacus_forge.contracts import JSONValue
from abacus_forge.dos_data import DOSData, PDOSData
from abacus_forge.dos_postprocess import PDOSMode


@dataclass(frozen=True, slots=True)
class ExplicitPostprocessResult:
    """Parser facts and generated paths from one explicit algorithm call.

    ``summary`` and ``diagnostics`` are JSON-safe and intentionally contain
    source/output names rather than absolute paths.  ``generated_paths`` is
    kept separate so the service can turn the exact paths into contained
    artifact records without putting ``Path`` values in a typed envelope.
    """

    summary: dict[str, JSONValue]
    diagnostics: dict[str, JSONValue]
    generated_paths: tuple[Path, ...]


class PostprocessAlgorithmError(ValueError):
    """Base class for errors a typed postprocess service can classify."""


class PostprocessPreconditionError(PostprocessAlgorithmError):
    """An explicit input/output precondition was not satisfied."""


class PostprocessParseError(PostprocessAlgorithmError):
    """A supplied parser input could not provide usable numeric data."""


EnergyAxis = Literal["source", "fermi_relative"]


def process_band_files(
    source_paths: Sequence[Path],
    output_dir: Path,
    *,
    plot_emin: float,
    plot_emax: float,
    save_data: bool,
    save_plot: bool,
    energy_axis: EnergyAxis = "source",
    fermi_reference_ev: float | None = None,
) -> ExplicitPostprocessResult:
    paths = _required_source_paths(source_paths, "source_paths")
    _validate_plot_bounds(plot_emin, plot_emax)
    reference = _validate_energy_axis(energy_axis, fermi_reference_ev)

    try:
        band_data = BandData.from_paths(list(paths))
    except Exception as exc:
        raise PostprocessParseError(f"could not parse band files: {exc}") from exc
    if not band_data.rows:
        raise PostprocessParseError("band parser found no numeric rows")

    base = _prepare_output_dir(output_dir)
    generated: list[Path] = []
    if save_data:
        data_path = _contained_output_path(base, "band.dat")
        # Import lazily to reuse the compatibility writer without making the
        # legacy module depend on this explicit algorithm module at import
        # time.  The optional flag keeps legacy source comments unchanged.
        from abacus_forge.unit_postprocess import _write_band_table

        _write_band_table(band_data, data_path, include_source_paths=False, energy_reference=reference)
        generated.append(data_path)
    if save_plot:
        plot_path = _contained_output_path(base, "band.png")
        from abacus_forge.unit_postprocess import _plot_band_data

        try:
            _plot_band_data(band_data, plot_path, plot_emin=plot_emin, plot_emax=plot_emax, energy_reference=reference)
        except Exception as exc:
            raise PostprocessParseError(f"could not render band plot: {exc}") from exc
        generated.append(plot_path)

    summary = _band_summary(band_data)
    summary["energy_axis"] = energy_axis
    summary["fermi_reference_ev"] = reference
    diagnostics: dict[str, JSONValue] = {
        "source_files": [path.name for path in paths],
        "source_count": len(paths),
        "numeric_rows": len(band_data.rows),
        "generated_files": [path.name for path in generated],
        "energy_axis": energy_axis,
        "fermi_reference_ev": reference,
    }
    return ExplicitPostprocessResult(summary=summary, diagnostics=diagnostics, generated_paths=tuple(generated))


def process_dos_files(
    dos_paths: Sequence[Path],
    pdos_path: Path | None,
    tdos_path: Path | None,
    output_dir: Path,
    *,
    include_tdos: bool,
    include_pdos: bool,
    pdos_mode: PDOSMode,
    pdos_atom_indices: Sequence[int],
    plot_emin: float,
    plot_emax: float,
    save_data: bool,
    save_plot: bool,
    suffix: str | None,
    energy_axis: EnergyAxis = "source",
    fermi_reference_ev: float | None = None,
) -> ExplicitPostprocessResult:
    paths = _required_source_paths(dos_paths, "dos_paths")
    pdos = _optional_source_path(pdos_path, "pdos_path")
    tdos = _optional_source_path(tdos_path, "tdos_path")
    _validate_plot_bounds(plot_emin, plot_emax)
    _validate_suffix(suffix)
    reference = _validate_energy_axis(energy_axis, fermi_reference_ev)

    total_dos: DOSData | None = None
    projected_dos: PDOSData | None = None
    missing_families: list[str] = []
    parsed_families: list[str] = []

    if include_tdos:
        try:
            total_dos = _typed_total_dos(paths)
        except Exception as exc:
            raise PostprocessParseError(f"could not parse total DOS files: {exc}") from exc
        if not total_dos.rows:
            raise PostprocessParseError("total DOS parser found no numeric rows")
        parsed_families.append("total_dos")

    if include_pdos:
        if pdos is None:
            # PDOS is optional at the algorithm boundary.  Preserve the
            # successful total-DOS result while reporting the absence as a
            # fact for the service to project into a partial collection.
            missing_families.append("pdos")
        else:
            try:
                projected_dos = PDOSData.from_path(pdos, tdos_path=tdos)
            except Exception as exc:
                raise PostprocessParseError(f"could not parse projected DOS file: {exc}") from exc
            if projected_dos.projected_dos:
                if projected_dos.energy is None or len(projected_dos.energy) == 0:
                    raise PostprocessParseError("projected DOS parser found no numeric energy rows")
                parsed_families.append("pdos")
            else:
                raise PostprocessParseError("projected DOS parser found no numeric rows")

    base = _prepare_output_dir(output_dir)
    expected_names: list[str] = []
    if total_dos is not None:
        if save_data:
            expected_names.append(_dos_output_name("DOS", "dat", suffix))
        if save_plot:
            expected_names.append(_dos_output_name("DOS", "png", suffix))
    if projected_dos is not None and projected_dos.projected_dos:
        if save_data:
            expected_names.append(_dos_output_name("PDOS", "dat", suffix))
        if save_plot:
            expected_names.append(_dos_output_name("PDOS", "png", suffix))
    # Check every target before invoking the writer.  In particular, an
    # existing symlink must not let a normal output filename write elsewhere.
    for name in expected_names:
        _contained_output_path(base, name)
    generated: list[Path] = []
    if total_dos is not None or projected_dos is not None and projected_dos.projected_dos:
        from abacus_forge.dos_postprocess import postprocess_dos_family

        try:
            artifacts = postprocess_dos_family(
                output_dir=base,
                total_dos=total_dos,
                projected_dos=projected_dos if projected_dos and projected_dos.projected_dos else None,
                pdos_mode=pdos_mode,
                pdos_atom_indices=list(pdos_atom_indices),
                plot_emin=plot_emin,
                plot_emax=plot_emax,
                save_data=save_data,
                save_plot=save_plot,
                suffix=suffix,
                energy_reference=reference,
            )
        except OSError:
            # Preserve destination and other output I/O failures for the
            # service layer to classify separately from parser failures.
            raise
        except PostprocessAlgorithmError:
            raise
        except Exception as exc:
            raise PostprocessParseError(f"could not render DOS family: {exc}") from exc
        generated = [Path(path) for path in artifacts.values()]
        for path in generated:
            _assert_contained_output(base, path)

    summary: dict[str, JSONValue] = {
        "total_dos": _dos_summary(total_dos) if total_dos is not None else None,
        "projected_dos": _pdos_summary(projected_dos) if projected_dos is not None and projected_dos.projected_dos else None,
        "pdos_mode": pdos_mode,
        "energy_axis": energy_axis,
        "fermi_reference_ev": reference,
    }
    diagnostics: dict[str, JSONValue] = {
        "source_files": {
            "dos": [path.name for path in paths],
            "pdos": pdos.name if pdos is not None else None,
            "tdos": tdos.name if tdos is not None else None,
        },
        "parsed_families": parsed_families,
        "missing_families": missing_families,
        "generated_files": [path.name for path in generated],
        "energy_axis": energy_axis,
        "fermi_reference_ev": reference,
    }
    return ExplicitPostprocessResult(summary=summary, diagnostics=diagnostics, generated_paths=tuple(generated))


def _required_source_paths(paths: Sequence[Path], field_name: str) -> tuple[Path, ...]:
    if isinstance(paths, (str, bytes)):
        raise PostprocessPreconditionError(f"{field_name} must be a non-empty sequence of Path values")
    try:
        values = tuple(paths)
    except TypeError as exc:
        raise PostprocessPreconditionError(f"{field_name} must be a non-empty sequence of Path values") from exc
    if not values:
        raise PostprocessPreconditionError(f"{field_name} must be a non-empty sequence of Path values")
    checked: list[Path] = []
    for value in values:
        if not isinstance(value, Path):
            raise PostprocessPreconditionError(f"{field_name} must contain Path values")
        if not value.exists() or not value.is_file():
            raise PostprocessPreconditionError(f"{field_name} source is not a regular file: {value.name}")
        checked.append(value)
    return tuple(checked)


def _optional_source_path(value: Path | None, field_name: str) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, Path):
        raise PostprocessPreconditionError(f"{field_name} must be a Path or None")
    if not value.exists() or not value.is_file():
        raise PostprocessPreconditionError(f"{field_name} source is not a regular file: {value.name}")
    return value


def _prepare_output_dir(output_dir: Path) -> Path:
    if not isinstance(output_dir, Path):
        raise PostprocessPreconditionError("output_dir must be a Path")
    if output_dir.is_symlink():
        raise PostprocessPreconditionError("output_dir must not be a symlink")
    # Keep filesystem failures visible to the service layer so it can
    # distinguish output I/O from typed input/output precondition errors.
    output_dir.mkdir(parents=True, exist_ok=True)
    if not output_dir.is_dir():
        raise PostprocessPreconditionError("output_dir must be a directory")
    return output_dir


def _contained_output_path(base: Path, name: str) -> Path:
    path = base / name
    if path.is_symlink():
        raise PostprocessPreconditionError(f"output path is a symlink: {name}")
    _assert_contained_output(base, path)
    return path


def _dos_output_name(stem: str, extension: str, suffix: str | None) -> str:
    return f"{stem}_{suffix}.{extension}" if suffix else f"{stem}.{extension}"


def _assert_contained_output(base: Path, path: Path) -> None:
    try:
        path.resolve().relative_to(base.resolve())
    except (OSError, RuntimeError, ValueError) as exc:
        raise PostprocessPreconditionError(f"generated output escapes output_dir: {path.name}") from exc


def _validate_plot_bounds(plot_emin: float, plot_emax: float) -> None:
    if not isinstance(plot_emin, (int, float)) or isinstance(plot_emin, bool):
        raise PostprocessPreconditionError("plot_emin must be numeric")
    if not isinstance(plot_emax, (int, float)) or isinstance(plot_emax, bool):
        raise PostprocessPreconditionError("plot_emax must be numeric")
    if not (float("-inf") < float(plot_emin) < float(plot_emax) < float("inf")):
        raise PostprocessPreconditionError("plot_emin must be finite and less than plot_emax")


def _validate_energy_axis(energy_axis: str, fermi_reference_ev: float | None) -> float | None:
    if energy_axis not in {"source", "fermi_relative"}:
        raise PostprocessPreconditionError("energy_axis must be 'source' or 'fermi_relative'")
    if energy_axis == "fermi_relative":
        if fermi_reference_ev is None or isinstance(fermi_reference_ev, bool):
            raise PostprocessPreconditionError("fermi_reference_ev is required for fermi_relative energy_axis")
        if not math.isfinite(float(fermi_reference_ev)):
            raise PostprocessPreconditionError("fermi_reference_ev must be finite")
        return float(fermi_reference_ev)
    if fermi_reference_ev is not None:
        raise PostprocessPreconditionError("fermi_reference_ev is only valid for fermi_relative energy_axis")
    return None


def _validate_suffix(suffix: str | None) -> None:
    if suffix is None:
        return
    if not isinstance(suffix, str) or not suffix:
        raise PostprocessPreconditionError("suffix must be a non-empty safe filename component or None")
    if "/" in suffix or "\\" in suffix or any(part in {".", ".."} for part in suffix.split("/")):
        raise PostprocessPreconditionError("suffix must be a non-empty safe filename component or None")


def _band_summary(data: BandData) -> dict[str, JSONValue]:
    summary = dict(data.summary())
    summary["num_bands"] = max(
        len(data.rows[0]) - _band_prefix_columns(data.rows), 0
    ) if data.rows else 0
    summary["band_files"] = [path.name for path in data.paths]
    return _json_safe(summary)


def _band_prefix_columns(rows: Sequence[Sequence[float]]) -> int:
    """Recognize the explicit ABACUS k-index/path-distance prefixes.

    Existing Forge fixtures use one leading path-distance column.  ABACUS
    band rows can instead begin with a one-based k-point index followed by
    path distance (for example ``1 0.0 -1.0 1.0``).  Requiring every row to
    have an integer-like positive index and the first path distance to be zero
    keeps this detector conservative for the legacy one-prefix shape.
    """

    if not rows or any(len(row) < 3 for row in rows):
        return 1
    indices = [row[0] for row in rows]
    if not all(_is_integer_like(value) and value >= 1 for value in indices):
        return 1
    if not math.isclose(indices[0], 1.0, rel_tol=0.0, abs_tol=1e-12):
        return 1
    if not math.isclose(rows[0][1], 0.0, rel_tol=0.0, abs_tol=1e-12):
        return 1
    return 2


def _is_integer_like(value: float) -> bool:
    return math.isfinite(value) and math.isclose(value, round(value), rel_tol=0.0, abs_tol=1e-12)


def _typed_total_dos(paths: Sequence[Path]) -> DOSData:
    """Parse total DOS columns without changing the legacy DOSData loader.

    ABACUS total-DOS rows are ``energy, DOS, cumulative-integral``.  The
    typed boundary retains only the DOS column and treats explicitly supplied
    files as spin channels on one shared energy grid.
    """

    tables = tuple(_read_typed_dos_table(path) for path in paths)
    common_energy, _ = tables[0]
    channels = [values for _, values in tables]
    reference = np.asarray(common_energy, dtype=float)
    for energy, _ in tables[1:]:
        candidate = np.asarray(energy, dtype=float)
        if candidate.shape != reference.shape or not np.allclose(
            candidate, reference, rtol=0.0, atol=1e-12
        ):
            raise PostprocessParseError("total DOS files must use a common energy grid")
    dosdata = np.asarray(channels, dtype=float).T
    rows = [
        [float(energy), *[float(channel[index]) for channel in channels]]
        for index, energy in enumerate(common_energy)
    ]
    return DOSData(
        paths=list(paths),
        rows=rows,
        energy=reference,
        dosdata=dosdata,
    )


def _read_typed_dos_table(path: Path) -> tuple[list[float], list[float]]:
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            values = [float(token) for token in stripped.split()]
        except ValueError:
            continue
        if len(values) >= 2:
            rows.append(values)
    if not rows:
        raise PostprocessParseError("total DOS parser found no numeric rows")
    return [row[0] for row in rows], [row[1] for row in rows]


def _dos_summary(data: DOSData) -> dict[str, JSONValue]:
    summary = dict(data.summary())
    summary["dos_files"] = [path.name for path in data.paths]
    return _json_safe(summary)


def _pdos_summary(data: PDOSData) -> dict[str, JSONValue]:
    summary = dict(data.summary())
    summary["pdos_file"] = data.pdos_path.name if data.pdos_path is not None else None
    summary["tdos_file"] = data.tdos_path.name if data.tdos_path is not None else None
    return _json_safe(summary)


def _json_safe(value: Any) -> dict[str, JSONValue]:
    """Detach parser summaries and normalize non-standard scalar values."""
    if not isinstance(value, Mapping):
        return {"value": _json_value(value)}
    return {str(key): _json_value(item) for key, item in value.items()}


def _json_value(value: Any) -> JSONValue:
    if isinstance(value, Path):
        return value.name
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    # Parser summaries currently contain Python scalars.  Keep this fallback
    # deliberately small so a future NumPy scalar cannot make the typed
    # result fail JSON serialization.
    if hasattr(value, "item"):
        try:
            return _json_value(value.item())
        except (AttributeError, ValueError, TypeError):
            pass
    if hasattr(value, "tolist"):
        try:
            return _json_value(value.tolist())
        except (AttributeError, ValueError, TypeError):
            pass
    return str(value)


__all__ = [
    "ExplicitPostprocessResult",
    "PostprocessAlgorithmError",
    "PostprocessPreconditionError",
    "PostprocessParseError",
    "process_band_files",
    "process_dos_files",
]
