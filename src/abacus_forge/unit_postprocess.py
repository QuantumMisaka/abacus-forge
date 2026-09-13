"""Postprocess helpers for explicit ABACUS/PyATB unit collection."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from abacus_forge.band_data import BandData
from abacus_forge.dos_data import DOSData, PDOSData
from abacus_forge.dos_postprocess import PDOSMode, postprocess_dos_family
from abacus_forge.workspace import Workspace

_MINI_PNG = bytes.fromhex(
    "89504E470D0A1A0A0000000D4948445200000001000000010802000000907753DE0000000C4944415408D763F8FFFF3F0005FE02FEA7E28D5B0000000049454E44AE426082"
)


def postprocess_abacus_band(
    workspace: str | Path | Workspace,
    *,
    plot_emin: float = -10.0,
    plot_emax: float = 10.0,
    save_plot: bool = True,
    save_data: bool = True,
) -> dict[str, Any]:
    """Generate ABACUS NSCF band collection artifacts from BANDS files."""

    ws = _workspace(workspace)
    ws.ensure_layout()
    diagnostics: dict[str, Any] = {"kind": "abacus-band", "searched_dirs": [str(path) for path in _output_dirs(ws)]}
    try:
        band_files = _find_artifacts(ws, "BANDS_*.dat")
        diagnostics["band_files"] = [str(path) for path in band_files]
        if not band_files:
            diagnostics["status"] = "skipped"
            diagnostics["reason"] = "no-band-files"
            _write_band_metrics(ws, {}, diagnostics, artifact_paths={})
            return diagnostics

        band_data = BandData.from_paths(band_files)
        summary = band_data.summary()
        artifacts: dict[str, str] = {}
        if save_data:
            data_path = ws.outputs_dir / "band.dat"
            _write_band_table(band_data, data_path)
            artifacts["band.dat"] = str(data_path)
        if save_plot:
            plot_path = ws.outputs_dir / "band.png"
            _plot_band_data(band_data, plot_path, plot_emin=plot_emin, plot_emax=plot_emax)
            artifacts["band.png"] = str(plot_path)

        diagnostics["status"] = "completed"
        diagnostics["artifacts"] = artifacts
        _write_band_metrics(ws, summary, diagnostics, artifact_paths=artifacts)
        return diagnostics
    except Exception as exc:
        diagnostics["status"] = "failed"
        diagnostics["error"] = str(exc)
        _write_diagnostics(ws, "band_postprocess_diagnostics.json", diagnostics)
        return diagnostics


def postprocess_pyatb_band(
    workspace: str | Path | Workspace,
    *,
    save_plot: bool = True,
) -> dict[str, Any]:
    """Normalize PyATB band output pictures without invoking PyATB."""

    ws = _workspace(workspace)
    ws.ensure_layout()
    band_dir = ws.inputs_dir / "Out" / "Band_Structure"
    candidates = [
        band_dir / "band.png",
        ws.outputs_dir / "Out" / "Band_Structure" / "band.png",
        ws.inputs_dir / "band.png",
        ws.outputs_dir / "band.png",
        band_dir / "band.pdf",
        ws.outputs_dir / "Out" / "Band_Structure" / "band.pdf",
    ]
    diagnostics: dict[str, Any] = {
        "kind": "pyatb-band",
        "picture_candidates": [str(path) for path in candidates if path.exists()],
    }
    if not save_plot:
        diagnostics["status"] = "skipped"
        diagnostics["reason"] = "save_plot-disabled"
        return diagnostics
    try:
        band_dir.mkdir(parents=True, exist_ok=True)
        target = band_dir / "band.png"
        source_png = next((path for path in candidates[:4] if path.exists() and path.suffix.lower() == ".png"), None)
        source_pdf = next((path for path in candidates[4:] if path.exists()), None)
        if source_png is not None:
            if source_png.resolve() != target.resolve():
                shutil.copy2(source_png, target)
            diagnostics["status"] = "completed"
            diagnostics["source"] = str(source_png)
            diagnostics["band_picture"] = str(target)
            return diagnostics
        if source_pdf is not None:
            target.write_bytes(_MINI_PNG)
            diagnostics["status"] = "completed"
            diagnostics["source"] = str(source_pdf)
            diagnostics["band_picture"] = str(target)
            diagnostics["warning"] = "PDF was detected; wrote a lightweight PNG placeholder for collector normalization."
            return diagnostics
        diagnostics["status"] = "skipped"
        diagnostics["reason"] = "no-band-picture"
        return diagnostics
    except Exception as exc:
        diagnostics["status"] = "failed"
        diagnostics["error"] = str(exc)
        return diagnostics


def postprocess_abacus_dos(
    workspace: str | Path | Workspace,
    *,
    include_tdos: bool = True,
    include_pdos: bool = True,
    pdos_mode: PDOSMode = "species",
    pdos_atom_indices: list[int] | None = None,
    plot_emin: float = -10.0,
    plot_emax: float = 10.0,
    save_data: bool = True,
    save_plot: bool = True,
    suffix: str | None = None,
) -> dict[str, Any]:
    """Generate ABACUS DOS/PDOS collection artifacts from NSCF outputs."""

    ws = _workspace(workspace)
    ws.ensure_layout()
    diagnostics: dict[str, Any] = {"kind": "abacus-dos", "searched_dirs": [str(path) for path in _output_dirs(ws)]}
    try:
        dos_files = _find_artifacts(ws, "DOS*_smearing.dat")
        pdos_path = _find_first_artifact(ws, "PDOS")
        tdos_path = _find_first_artifact(ws, "TDOS")
        diagnostics["dos_files"] = [str(path) for path in dos_files]
        diagnostics["pdos_path"] = str(pdos_path) if pdos_path is not None else None
        diagnostics["tdos_path"] = str(tdos_path) if tdos_path is not None else None

        total_dos = DOSData.from_paths(dos_files) if include_tdos and dos_files else None
        projected_dos = (
            PDOSData.from_path(pdos_path, tdos_path=tdos_path)
            if include_pdos and pdos_path is not None
            else None
        )
        if total_dos is None and (projected_dos is None or not projected_dos.projected_dos):
            diagnostics["status"] = "skipped"
            diagnostics["reason"] = "no-dos-family-data"
            _write_diagnostics(ws, "dos_postprocess_diagnostics.json", diagnostics)
            return diagnostics

        artifacts = postprocess_dos_family(
            output_dir=ws.outputs_dir,
            total_dos=total_dos,
            projected_dos=projected_dos if projected_dos and projected_dos.projected_dos else None,
            pdos_mode=pdos_mode,
            pdos_atom_indices=pdos_atom_indices,
            plot_emin=plot_emin,
            plot_emax=plot_emax,
            save_data=save_data,
            save_plot=save_plot,
            suffix=suffix,
        )
        diagnostics["status"] = "completed"
        diagnostics["artifacts"] = artifacts
        metrics = {
            "total_dos": total_dos.summary() if total_dos is not None else None,
            "projected_dos": projected_dos.summary() if projected_dos is not None else None,
            "artifacts": artifacts,
            "pdos_mode": pdos_mode,
        }
        ws.write_json("reports/metrics_dos_family.json", metrics)
        _write_diagnostics(ws, "dos_postprocess_diagnostics.json", diagnostics)
        return diagnostics
    except Exception as exc:
        diagnostics["status"] = "failed"
        diagnostics["error"] = str(exc)
        _write_diagnostics(ws, "dos_postprocess_diagnostics.json", diagnostics)
        return diagnostics


def _workspace(value: str | Path | Workspace) -> Workspace:
    return value if isinstance(value, Workspace) else Workspace(Path(value))


def _output_dirs(workspace: Workspace) -> list[Path]:
    candidates: list[Path] = []
    for base in (workspace.outputs_dir, workspace.inputs_dir, workspace.root):
        if not base.exists():
            continue
        candidates.append(base)
        candidates.extend(path for path in sorted(base.glob("OUT.*")) if path.is_dir())
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved not in seen:
            unique.append(path)
            seen.add(resolved)
    return unique


def _find_artifacts(workspace: Workspace, pattern: str) -> list[Path]:
    matches: list[Path] = []
    seen: set[Path] = set()
    for directory in _output_dirs(workspace):
        for path in sorted(directory.glob(pattern)):
            if path.is_file() and path.resolve() not in seen:
                matches.append(path)
                seen.add(path.resolve())
    return matches


def _find_first_artifact(workspace: Workspace, pattern: str) -> Path | None:
    matches = _find_artifacts(workspace, pattern)
    return matches[0] if matches else None


def _write_band_table(
    band_data: BandData,
    destination: Path,
    *,
    include_source_paths: bool = True,
    energy_reference: float | None = None,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        for path in band_data.paths:
            label = path if include_source_paths else path.name
            handle.write(f"# {label}\n")
            for row in _read_numeric_rows(path):
                if energy_reference is not None:
                    prefix = 2 if len(row) >= 3 and row[0].is_integer() and row[0] >= 1 and row[1] == 0.0 else 1
                    row = row[:prefix] + [value - energy_reference for value in row[prefix:]]
                handle.write(" ".join(f"{value:g}" for value in row) + "\n")


def _plot_band_data(
    band_data: BandData,
    destination: Path,
    *,
    plot_emin: float,
    plot_emax: float,
    energy_reference: float | None = None,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(7, 5))
    for file_index, path in enumerate(band_data.paths):
        rows = _read_numeric_rows(path)
        if energy_reference is not None:
            rows = [
                row[: (2 if len(row) >= 3 and row[0].is_integer() and row[0] >= 1 and row[1] == 0.0 else 1)]
                + [value - energy_reference for value in row[(2 if len(row) >= 3 and row[0].is_integer() and row[0] >= 1 and row[1] == 0.0 else 1):]]
                for row in rows
            ]
        if not rows:
            continue
        x_values = [row[1] if len(row) >= 3 else row[0] for row in rows]
        first_band_column = 2 if len(rows[0]) >= 3 else 1
        max_columns = max(len(row) for row in rows)
        for column in range(first_band_column, max_columns):
            y_values = [row[column] for row in rows if len(row) > column]
            xs = [x_values[index] for index, row in enumerate(rows) if len(row) > column]
            if y_values:
                axis.plot(xs, y_values, color="C0", alpha=0.7, linewidth=0.9, linestyle="--" if file_index else "-")
    axis.set_ylim(plot_emin, plot_emax)
    axis.set_xlabel("K-path")
    axis.set_ylabel("Energy (eV)")
    axis.grid(alpha=0.25)
    figure.tight_layout()
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, dpi=300)
    plt.close(figure)


def _read_numeric_rows(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            rows.append([float(token) for token in stripped.split()])
        except ValueError:
            continue
    return rows


def _write_band_metrics(workspace: Workspace, summary: dict[str, Any], diagnostics: dict[str, Any], *, artifact_paths: dict[str, str]) -> None:
    metrics = dict(summary)
    if "band.png" in artifact_paths:
        metrics["band_picture"] = artifact_paths["band.png"]
    if "band.dat" in artifact_paths:
        metrics["band_data"] = artifact_paths["band.dat"]
    metrics["artifacts"] = artifact_paths
    workspace.write_json("reports/metrics_band.json", metrics)
    _write_diagnostics(workspace, "band_postprocess_diagnostics.json", diagnostics)


def _write_diagnostics(workspace: Workspace, filename: str, diagnostics: dict[str, Any]) -> None:
    workspace.write_json(f"reports/{filename}", diagnostics)
