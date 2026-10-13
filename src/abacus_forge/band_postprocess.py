"""Shared ABACUS band table and plot output for explicit and unit callers."""

from __future__ import annotations

import math
from pathlib import Path

from abacus_forge.band_data import BandData


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
            rows = _read_numeric_rows(path)
            prefix = _band_energy_prefix(rows)
            for row in rows:
                if energy_reference is not None:
                    row = row[:prefix] + [value - energy_reference for value in row[prefix:]]
                # Keep enough significant digits for a downstream parity
                # comparison; the default ``g`` precision silently rounded
                # ABACUS's eight-decimal band tables to six significant digits.
                handle.write(" ".join(f"{value:.12g}" for value in row) + "\n")


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
            prefix = _band_energy_prefix(rows)
            rows = [
                row[:prefix] + [value - energy_reference for value in row[prefix:]]
                for row in rows
            ]
        if not rows:
            continue
        prefix = _band_energy_prefix(rows)
        x_column = prefix - 1
        x_values = [row[x_column] for row in rows]
        first_band_column = prefix
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


def _band_energy_prefix(rows: list[list[float]]) -> int:
    """Return the non-energy prefix count for an entire ABACUS band table.

    Tables use either one path-distance prefix or a one-based k-point index
    followed by path distance.  Looking at a single row would misclassify
    later k-points because only the first path distance is zero.
    """

    if not rows or any(len(row) < 3 for row in rows):
        return 1
    indices = [row[0] for row in rows]
    if not all(
        math.isfinite(value)
        and value >= 1
        and math.isclose(value, round(value), rel_tol=0.0, abs_tol=1e-12)
        for value in indices
    ):
        return 1
    if not math.isclose(indices[0], 1.0, rel_tol=0.0, abs_tol=1e-12):
        return 1
    if not math.isclose(rows[0][1], 0.0, rel_tol=0.0, abs_tol=1e-12):
        return 1
    return 2
