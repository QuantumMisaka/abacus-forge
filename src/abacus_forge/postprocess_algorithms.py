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
from typing import Any

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


def process_band_files(
    source_paths: Sequence[Path],
    output_dir: Path,
    *,
    plot_emin: float,
    plot_emax: float,
    save_data: bool,
    save_plot: bool,
) -> ExplicitPostprocessResult:
    paths = _required_source_paths(source_paths, "source_paths")
    _validate_plot_bounds(plot_emin, plot_emax)

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

        _write_band_table(band_data, data_path, include_source_paths=False)
        generated.append(data_path)
    if save_plot:
        plot_path = _contained_output_path(base, "band.png")
        from abacus_forge.unit_postprocess import _plot_band_data

        try:
            _plot_band_data(band_data, plot_path, plot_emin=plot_emin, plot_emax=plot_emax)
        except Exception as exc:
            raise PostprocessParseError(f"could not render band plot: {exc}") from exc
        generated.append(plot_path)

    summary = _band_summary(band_data)
    diagnostics: dict[str, JSONValue] = {
        "source_files": [path.name for path in paths],
        "source_count": len(paths),
        "numeric_rows": len(band_data.rows),
        "generated_files": [path.name for path in generated],
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
) -> ExplicitPostprocessResult:
    paths = _required_source_paths(dos_paths, "dos_paths")
    pdos = _optional_source_path(pdos_path, "pdos_path")
    tdos = _optional_source_path(tdos_path, "tdos_path")
    _validate_plot_bounds(plot_emin, plot_emax)
    _validate_suffix(suffix)

    total_dos: DOSData | None = None
    projected_dos: PDOSData | None = None
    missing_families: list[str] = []
    parsed_families: list[str] = []

    if include_tdos:
        try:
            total_dos = DOSData.from_paths(list(paths))
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
            )
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
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PostprocessPreconditionError(f"output_dir is not writable: {output_dir}") from exc
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


def _validate_suffix(suffix: str | None) -> None:
    if suffix is None:
        return
    if not isinstance(suffix, str) or not suffix:
        raise PostprocessPreconditionError("suffix must be a non-empty safe filename component or None")
    if "/" in suffix or "\\" in suffix or any(part in {".", ".."} for part in suffix.split("/")):
        raise PostprocessPreconditionError("suffix must be a non-empty safe filename component or None")


def _band_summary(data: BandData) -> dict[str, JSONValue]:
    summary = dict(data.summary())
    summary["band_files"] = [path.name for path in data.paths]
    return _json_safe(summary)


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
