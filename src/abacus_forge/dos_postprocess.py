"""DOS-family plotting and table export helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np

from abacus_forge.dos_data import DOSData, L_MAP, ORBITAL_NAMES, PDOSData

PDOSMode = Literal["species", "species+shell", "species+orbital", "atom", "atoms"]
COLOR_LIST = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
    "#aec7e8",
    "#ffbb78",
    "#98df8a",
    "#ff9896",
]


def postprocess_dos_family(
    *,
    output_dir: str | Path,
    total_dos: DOSData | None,
    projected_dos: PDOSData | None = None,
    pdos_mode: PDOSMode = "species",
    pdos_atom_indices: list[int] | None = None,
    plot_emin: float = -10.0,
    plot_emax: float = 10.0,
    save_data: bool = True,
    save_plot: bool = True,
    suffix: str | None = None,
) -> dict[str, str]:
    """Write requested DOS-family postprocess artifacts."""

    base = Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}
    if total_dos is not None:
        if save_data:
            path = _output_path(base, "DOS", "dat", suffix)
            write_dos_pdos([_require_dos_array(total_dos)], _require_energy(total_dos), ["DOS"], total_dos.efermi is not None, path)
            artifacts[path.name] = str(path)
        if save_plot:
            path = _output_path(base, "DOS", "png", suffix)
            plot_dos_pdos([[_require_dos_array(total_dos)]], [["DOS"]], ["Density of States"], _require_energy(total_dos), plot_emin, plot_emax, total_dos.efermi is not None, path)
            artifacts[path.name] = str(path)
    if projected_dos is not None and projected_dos.projected_dos:
        pdosdatas, labels, titles = build_pdos_groups(projected_dos, mode=pdos_mode, atom_indices=pdos_atom_indices)
        flat_data = [data for group in pdosdatas for data in group]
        flat_labels = [label for group in labels for label in group]
        if save_data:
            path = _output_path(base, "PDOS", "dat", suffix)
            write_dos_pdos(flat_data, _require_pdos_energy(projected_dos), flat_labels, projected_dos.efermi is not None, path)
            artifacts[path.name] = str(path)
        if save_plot:
            path = _output_path(base, "PDOS", "png", suffix)
            plot_dos_pdos(pdosdatas, labels, titles, _require_pdos_energy(projected_dos), plot_emin, plot_emax, projected_dos.efermi is not None, path)
            artifacts[path.name] = str(path)
    return artifacts


def build_pdos_groups(
    pdos_data: PDOSData,
    *,
    mode: PDOSMode,
    atom_indices: list[int] | None = None,
) -> tuple[list[list[np.ndarray]], list[list[str]], list[str]]:
    normalized_mode = "atom" if mode == "atoms" else mode
    if normalized_mode == "species":
        species = pdos_data.get_species()
        return (
            [[pdos_data.get_pdos_by_species(item) for item in species]],
            [species],
            ["Projected density of states by species"],
        )
    if normalized_mode == "species+shell":
        groups: list[list[np.ndarray]] = []
        labels: list[list[str]] = []
        titles: list[str] = []
        for species in pdos_data.get_species():
            shells = pdos_data.get_species_shell(species)
            groups.append([pdos_data.get_pdos_by_species_shell(species, shell) for shell in shells])
            labels.append([f"{species}-{L_MAP[shell]}" for shell in shells])
            titles.append(f"PDOS for {species}")
        return groups, labels, titles
    if normalized_mode == "species+orbital":
        groups = []
        labels = []
        titles = []
        for species in pdos_data.get_species():
            for shell in pdos_data.get_species_shell(species):
                orbitals = pdos_data.get_species_shell_orbital(species, shell)
                groups.append([pdos_data.get_pdos_by_species_orbital(species, shell, orbital) for orbital in orbitals])
                labels.append([f"{species}-{ORBITAL_NAMES.get((shell, orbital), f'm{orbital}')}" for orbital in orbitals])
                titles.append(f"PDOS for {species}-{L_MAP[shell]}")
        return groups, labels, titles
    if normalized_mode == "atom":
        selected_atoms = atom_indices or sorted({orbital["atom_index"] for orbital in pdos_data.projected_dos})[:3]
        groups = []
        labels = []
        titles = []
        for atom_index in selected_atoms:
            species = pdos_data.get_atom_species(atom_index)
            for shell in pdos_data.get_atom_shell(atom_index):
                orbitals = pdos_data.get_atom_shell_orbital(atom_index, shell)
                groups.append([pdos_data.get_pdos_by_atom_orbital(atom_index, shell, orbital) for orbital in orbitals])
                labels.append([f"{species}{atom_index}-{ORBITAL_NAMES.get((shell, orbital), f'm{orbital}')}" for orbital in orbitals])
                titles.append(f"PDOS for {species}{atom_index}-{L_MAP[shell]}")
        return groups, labels, titles
    raise ValueError(f"Unsupported PDOS mode: {mode}")


def plot_dos_pdos(
    pdosdatas: list[list[np.ndarray]],
    labels: list[list[str]],
    titles: list[str],
    energy: np.ndarray,
    energy_min: float,
    energy_max: float,
    shifted: bool,
    filename: str | Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    num_subplots = len(pdosdatas)
    if num_subplots == 0:
        raise ValueError("No DOS data to plot")
    if num_subplots >= 4:
        ncol = max(3, int(np.sqrt(num_subplots))) if num_subplots > 6 else 2
        nrow = int(np.ceil(num_subplots / ncol))
    else:
        nrow = num_subplots
        ncol = 1
    figure, axes = plt.subplots(nrow, ncol, figsize=(8 * ncol, 4 * nrow))
    axes_array = np.asarray([axes]).flatten() if nrow * ncol == 1 else np.asarray(axes).flatten()
    for axis in axes_array[num_subplots:]:
        axis.set_visible(False)
    visible_mask = (energy >= energy_min) & (energy <= energy_max)
    for index, group in enumerate(pdosdatas):
        axis = axes_array[index]
        spin_polarized = False
        y_values: list[np.ndarray] = []
        for data_index, (data, label) in enumerate(zip(group, labels[index])):
            array = _as_2d(data)
            color = COLOR_LIST[data_index % len(COLOR_LIST)]
            if array.shape[1] == 1:
                axis.plot(energy, array[:, 0], label=label, color=color, linewidth=1.0)
                y_values.append(array[visible_mask, 0])
            elif array.shape[1] == 2:
                spin_polarized = True
                axis.plot(energy, array[:, 0], label=f"{label} up", color=color, linewidth=1.0)
                axis.plot(energy, -array[:, 1], label=f"{label} dn", color=color, linestyle="--", linewidth=1.0)
                y_values.extend([array[visible_mask, 0], -array[visible_mask, 1]])
        axis.set_xlim(energy_min, energy_max)
        finite = np.concatenate([values for values in y_values if values.size]) if y_values else np.asarray([0.0])
        ymin = float(np.min(finite))
        ymax = float(np.max(finite))
        margin = (ymax - ymin) * 0.05 if ymax > ymin else 0.1
        axis.set_ylim((ymin - margin, ymax + margin) if spin_polarized else (0, ymax + margin))
        axis.set_xlabel("E-E_F (eV)" if shifted else "Energy (eV)")
        axis.set_ylabel("States")
        axis.set_title(titles[index])
        axis.grid(alpha=0.3)
        axis.legend(loc="best", fontsize=8, ncol=2 if spin_polarized else 1)
        if shifted:
            axis.axvline(x=0, color="k", linestyle=":", alpha=0.5)
    figure.tight_layout()
    figure.savefig(filename, dpi=300)
    plt.close(figure)


def write_dos_pdos(pdosdatas: list[np.ndarray], energy: np.ndarray, labels: list[str], shifted: bool, filename: str | Path) -> None:
    if len(pdosdatas) != len(labels):
        raise ValueError("number of DOS arrays must match labels")
    arrays = [_as_2d(data) for data in pdosdatas]
    min_width = 12
    energy_header = "E-E_F(eV)" if shifted else "Energy(eV)"
    column_headers: list[str] = []
    for array, label in zip(arrays, labels):
        if array.shape[1] == 1:
            column_headers.append(label)
        elif array.shape[1] == 2:
            column_headers.extend([f"{label}_up", f"{label}_dn"])
        else:
            raise ValueError(f"unsupported spin channel count: {array.shape[1]}")
    widths = [max(min_width, len(energy_header))] + [max(min_width, len(header) + 1) for header in column_headers]
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(f"{energy_header:>{widths[0]}s}" + "".join(f"{header:>{width}s}" for header, width in zip(column_headers, widths[1:])) + "\n")
        for row_index, value in enumerate(energy):
            row = f"{value:>{widths[0]}.6f}"
            width_index = 1
            for array in arrays:
                row += f"{array[row_index, 0]:>{widths[width_index]}.6f}"
                width_index += 1
                if array.shape[1] == 2:
                    row += f"{array[row_index, 1]:>{widths[width_index]}.6f}"
                    width_index += 1
            handle.write(row + "\n")


def _output_path(base: Path, stem: str, extension: str, suffix: str | None) -> Path:
    return base / f"{stem}_{suffix}.{extension}" if suffix else base / f"{stem}.{extension}"


def _as_2d(data: np.ndarray) -> np.ndarray:
    array = np.asarray(data, dtype=float)
    return array.reshape((-1, 1)) if array.ndim == 1 else array


def _require_energy(dos_data: DOSData) -> np.ndarray:
    if dos_data.energy is None:
        raise ValueError("DOSData has no energy grid")
    return np.asarray(dos_data.energy, dtype=float)


def _require_dos_array(dos_data: DOSData) -> np.ndarray:
    if dos_data.dosdata is None:
        raise ValueError("DOSData has no DOS values")
    return _as_2d(dos_data.dosdata)


def _require_pdos_energy(pdos_data: PDOSData) -> np.ndarray:
    if pdos_data.energy is None:
        raise ValueError("PDOSData has no energy grid")
    return np.asarray(pdos_data.energy, dtype=float)
