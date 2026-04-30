"""Lightweight input and structure modification primitives for Forge."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import numpy as np
from ase import Atoms

from abacus_forge.input_io import read_input, read_kpt, write_input, write_kpt
from abacus_forge.perturbation import perturb_structure
from abacus_forge.structure import AbacusStructure


def modify_input(
    source: str | Path | Mapping[str, Any],
    *,
    updates: Mapping[str, Any] | None = None,
    remove_keys: Iterable[str] | None = None,
    destination: str | Path | None = None,
    header: str = "INPUT_PARAMETERS",
) -> dict[str, str]:
    """Load, update, optionally write, and return an ABACUS ``INPUT`` mapping."""
    params = _load_input_parameters(source)
    for key, value in (updates or {}).items():
        params[str(key)] = str(value)
    for key in remove_keys or ():
        params.pop(str(key), None)
    if destination is not None:
        write_input(destination, params, header=header)
    return params


def modify_stru(
    structure: str | Path | AbacusStructure | Atoms | Any,
    *,
    displacements: list[list[float]] | np.ndarray | None = None,
    swap_axes: tuple[int, int] | None = None,
    supercell: tuple[int, int, int] | list[int] | None = None,
    ensure_pbc: bool = False,
    vacuum: float = 10.0,
    standardization: str | None = None,
    magmoms: Iterable[float] | None = None,
    magmom_by_element: Mapping[str, float] | None = None,
    afm: bool = False,
    afm_elements: Iterable[str] | None = None,
    move_flags: Iterable[Iterable[int]] | None = None,
    destination: str | Path | None = None,
    pp_map: dict[str, str] | None = None,
    orb_map: dict[str, str] | None = None,
) -> AbacusStructure:
    """Apply lightweight structure edits and optionally write a normalized ``STRU`` file."""
    payload = AbacusStructure.from_input(structure)
    if ensure_pbc:
        payload = payload.ensure_3d_pbc(vacuum=vacuum)
    if standardization == "conventional":
        payload = payload.primitive_to_conventional()
    elif standardization == "primitive":
        payload = payload.conventional_to_primitive()
    if swap_axes is not None:
        payload = payload.swap_axes(*swap_axes)
    if supercell is not None:
        payload = payload.make_supercell(supercell)
    if displacements is not None:
        payload = perturb_structure(payload, displacements=displacements)

    atoms = payload.atoms.copy()
    magnetic_moments = _resolve_collinear_magmoms(
        atoms,
        magmoms=magmoms,
        magmom_by_element=magmom_by_element,
        afm=afm,
        afm_elements=afm_elements,
    )
    if magnetic_moments is not None:
        atoms.set_initial_magnetic_moments(magnetic_moments)
    if move_flags is not None:
        flags = np.asarray(list(move_flags), dtype=int)
        if flags.shape != (len(atoms), 3):
            raise ValueError(f"move_flags must have shape ({len(atoms)}, 3), got {flags.shape}")
        atoms.info["abacus_move_flags"] = flags.tolist()

    modified = AbacusStructure(atoms, source_format=payload.source_format)
    if destination is not None:
        Path(destination).write_text(modified.to_stru(pp_map=pp_map, orb_map=orb_map), encoding="utf-8")
    return modified


def modify_kpt(
    source: str | Path | Mapping[str, Any],
    *,
    mode: str | None = None,
    mesh: Iterable[int] | None = None,
    shifts: Iterable[int] | None = None,
    points: Iterable[Mapping[str, Any]] | None = None,
    segments: int | None = None,
    destination: str | Path | None = None,
) -> dict[str, Any]:
    """Load, normalize, optionally write, and return a structured ABACUS ``KPT`` payload."""
    payload = _load_kpt_payload(source)
    if mode is not None:
        payload["mode"] = mode
    if mesh is not None:
        payload["mesh"] = [int(value) for value in mesh]
    if shifts is not None:
        payload["shifts"] = [int(value) for value in shifts]
    if points is not None:
        payload["points"] = [
            {
                "coords": [float(value) for value in point["coords"]],
                "label": point.get("label"),
            }
            for point in points
        ]
    if segments is not None:
        payload["segments"] = int(segments)

    normalized = _normalize_kpt_payload(payload)
    if destination is not None:
        write_kpt(destination, normalized)
    return normalized


def _load_input_parameters(source: str | Path | Mapping[str, Any]) -> dict[str, str]:
    """Normalize a file path or mapping into stringified ``INPUT`` parameters."""
    if isinstance(source, Mapping):
        return {str(key): str(value) for key, value in source.items()}
    return read_input(source)


def _load_kpt_payload(source: str | Path | Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a file path or mapping into a structured ``KPT`` payload."""
    if isinstance(source, Mapping):
        return dict(source)
    return read_kpt(source)


def _resolve_collinear_magmoms(
    atoms: Atoms,
    *,
    magmoms: Iterable[float] | None,
    magmom_by_element: Mapping[str, float] | None,
    afm: bool,
    afm_elements: Iterable[str] | None,
) -> np.ndarray | None:
    """Resolve site magnetic moments from explicit values, element defaults, and AFM rules."""
    if not any((magmoms is not None, magmom_by_element, afm)):
        return None

    if atoms.has("initial_magmoms"):
        resolved = np.asarray(atoms.get_initial_magnetic_moments(), dtype=float)
    else:
        resolved = np.zeros(len(atoms), dtype=float)

    if magmom_by_element:
        for idx, symbol in enumerate(atoms.get_chemical_symbols()):
            if symbol in magmom_by_element:
                resolved[idx] = float(magmom_by_element[symbol])

    if afm:
        selected = set(afm_elements or ())
        if not selected:
            selected = {
                symbol
                for symbol, magnitude in (magmom_by_element or {}).items()
                if float(magnitude) != 0.0
            }
        if not selected:
            selected = {
                symbol
                for symbol, magnitude in zip(atoms.get_chemical_symbols(), resolved, strict=False)
                if float(magnitude) != 0.0
            }
        counters: dict[str, int] = {}
        for idx, symbol in enumerate(atoms.get_chemical_symbols()):
            if symbol not in selected:
                continue
            order = counters.get(symbol, 0)
            magnitude = abs(float(resolved[idx]))
            resolved[idx] = magnitude if order % 2 == 0 else -magnitude
            counters[symbol] = order + 1

    if magmoms is not None:
        explicit = np.asarray(list(magmoms), dtype=float)
        if explicit.shape != (len(atoms),):
            raise ValueError(f"magmoms must have shape ({len(atoms)},), got {explicit.shape}")
        resolved = explicit

    return resolved


def _normalize_kpt_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize mesh- or line-mode ``KPT`` payloads."""
    mode = str(payload.get("mode", "")).lower()
    if mode == "mesh":
        mesh = [int(value) for value in payload.get("mesh", [])]
        shifts = [int(value) for value in payload.get("shifts", [0, 0, 0])]
        if len(mesh) != 3 or len(shifts) != 3:
            raise ValueError("mesh-mode KPT requires 3 mesh values and 3 shift values")
        return {"mode": "mesh", "mesh": mesh, "shifts": shifts}
    if mode == "line":
        points = []
        for point in payload.get("points", []):
            coords = [float(value) for value in point["coords"]]
            if len(coords) != 3:
                raise ValueError("line-mode KPT point requires 3 coordinates")
            points.append({"coords": coords, "label": point.get("label")})
        if not points:
            raise ValueError("line-mode KPT requires at least one point")
        return {
            "mode": "line",
            "segments": int(payload.get("segments", 20)),
            "points": points,
        }
    raise ValueError(f"Unsupported KPT payload mode: {payload.get('mode')!r}")
