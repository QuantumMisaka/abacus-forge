"""Event-free preparation of canonical ABACUS workspace inputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from ase import Atoms

from abacus_forge.assets import (
    AssetMaterialization,
    collect_assets,
    materialize_assets,
    stage_assets,
)
from abacus_forge.errors import ForgeRequestError
from abacus_forge.input_io import write_input, write_kpt_line_mode, write_kpt_mesh
from abacus_forge.prepare_profiles import build_task_parameters
from abacus_forge.structure import AbacusStructure
from abacus_forge.structure_recognition import detect_structure_format
from abacus_forge.validation import validate_inputs
from abacus_forge.workspace import Workspace


def prepare(
    workspace: str | Path | Workspace,
    *,
    structure: str | Path | AbacusStructure | Atoms | Any | None = None,
    structure_format: str | None = None,
    task: str | None = None,
    parameters: dict[str, Any] | None = None,
    input_overrides: dict[str, Any] | None = None,
    remove_parameters: Iterable[str] | None = None,
    kpoints: Iterable[int] | None = None,
    kpt_mode: str = "mesh",
    line_kpoints: Iterable[tuple[Iterable[float], str | None]] | None = None,
    metadata: dict[str, Any] | None = None,
    pseudo_path: str | Path | None = None,
    orbital_path: str | Path | None = None,
    asset_mode: str = "link",
    ensure_pbc: bool = False,
    structure_standardization: str | None = None,
    magmom_by_element: dict[str, float] | None = None,
) -> Workspace:
    """Create a prepared workspace with canonical ABACUS inputs."""

    ws = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace))
    ws.ensure_layout()

    structure_payload = None
    structure_info: dict[str, Any] | None = None
    if structure is not None:
        try:
            structure_payload = AbacusStructure.from_input(structure, structure_format=structure_format)
        except Exception:
            structure_payload = None
            if _is_recognized_stru_source(structure, structure_format):
                raise
            if not _write_structure_fallback(ws, structure):
                raise
        if structure_payload is not None:
            if ensure_pbc:
                structure_payload = structure_payload.ensure_3d_pbc()
            if structure_standardization == "conventional":
                structure_payload = structure_payload.primitive_to_conventional()
            elif structure_standardization == "primitive":
                structure_payload = structure_payload.conventional_to_primitive()
            elif structure_standardization == "swap-layer-to-c":
                meta = structure_payload.metadata()
                if meta.structure_class == "layer" and meta.layer_info and meta.layer_info["long_axis"] != 2:
                    structure_payload = structure_payload.swap_axes(meta.layer_info["long_axis"], 2)
                elif meta.structure_class == "string" and meta.string_info and meta.string_info["extension_axis"] != 2:
                    structure_payload = structure_payload.swap_axes(meta.string_info["extension_axis"], 2)
            if magmom_by_element:
                atoms = structure_payload.atoms.copy()
                initial_magmoms = [
                    float(magmom_by_element.get(symbol, 0.0))
                    for symbol in atoms.get_chemical_symbols()
                ]
                atoms.set_initial_magnetic_moments(initial_magmoms)
                structure_payload = AbacusStructure(atoms, source_format=structure_payload.source_format)
            pseudo_map = collect_assets(pseudo_path, family="pseudo")
            orbital_map = collect_assets(orbital_path, family="orbital")
            ws.write_text("inputs/STRU", structure_payload.to_stru(pp_map=_basename_map(pseudo_map), orb_map=_basename_map(orbital_map)))
            stage_assets(ws.inputs_dir, pseudo_map=pseudo_map, orbital_map=orbital_map, mode=asset_mode)
            structure_info = structure_payload.metadata().to_dict()

    params = build_task_parameters(task, metadata=structure_payload.metadata() if structure_payload is not None else None, parameters=parameters)
    if input_overrides:
        params.update(input_overrides)
    for key in remove_parameters or ():
        params.pop(str(key), None)
    write_input(ws.inputs_dir / "INPUT", params)

    mesh = list(kpoints or [1, 1, 1])
    if kpt_mode == "line" and line_kpoints:
        write_kpt_line_mode(ws.inputs_dir / "KPT", list(line_kpoints))
    else:
        write_kpt_mesh(ws.inputs_dir / "KPT", mesh)

    ws.record_metadata(
        {
            "kind": "abacus-forge.workspace",
            "task": task or "scf",
            "structure": str(Path(structure)) if isinstance(structure, (str, Path)) else None,
            "structure_format": structure_payload.source_format if structure_payload is not None else structure_format,
            "structure_metadata": structure_info,
            "parameters": params,
            "kpoints": mesh,
            "metadata": metadata or {},
            "validation": validate_inputs(ws.inputs_dir),
        }
    )
    return ws


def prepare_with_assets(
    workspace: str | Path | Workspace,
    *,
    structure: str | Path | AbacusStructure | Atoms | Any | None = None,
    structure_format: str | None = None,
    task: str | None = None,
    parameters: dict[str, Any] | None = None,
    input_overrides: dict[str, Any] | None = None,
    remove_parameters: Iterable[str] | None = None,
    kpoints: Iterable[int] | None = None,
    kpt_mode: str = "mesh",
    line_kpoints: Iterable[tuple[Iterable[float], str | None]] | None = None,
    metadata: dict[str, Any] | None = None,
    pseudo_sources: Mapping[str, str] | None = None,
    orbital_sources: Mapping[str, str] | None = None,
    asset_mode: str = "copy",
    ensure_pbc: bool = False,
    structure_standardization: str | None = None,
    magmom_by_element: dict[str, float] | None = None,
) -> tuple[Workspace, tuple[AssetMaterialization, ...]]:
    """Prepare typed inputs with explicit, provenance-carrying assets.

    This entry point deliberately does not call :func:`prepare`: typed
    requests must never fall back to directory scanning or filename-based
    asset inference.  The legacy function above retains its historical
    arguments, defaults, and directory-based behavior.
    """

    if not isinstance(asset_mode, str) or asset_mode not in {"copy", "link"}:
        raise ForgeRequestError(f"unsupported asset mode: {asset_mode}")
    pseudo_map = dict(pseudo_sources or {})
    orbital_map = dict(orbital_sources or {})
    explicit_assets = bool(pseudo_map or orbital_map)

    ws = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace))
    ws.ensure_layout()

    structure_payload = None
    structure_info: dict[str, Any] | None = None
    materialization: tuple[AssetMaterialization, ...] = ()
    if structure is not None:
        try:
            structure_payload = AbacusStructure.from_input(structure, structure_format=structure_format)
        except (OSError, ValueError):
            structure_payload = None
            if _is_recognized_stru_source(structure, structure_format):
                raise
            if explicit_assets:
                raise ForgeRequestError("explicit asset maps require a parsed structure")
            if not _write_structure_fallback(ws, structure):
                raise
        if structure_payload is not None:
            if ensure_pbc:
                structure_payload = structure_payload.ensure_3d_pbc()
            if structure_standardization == "conventional":
                structure_payload = structure_payload.primitive_to_conventional()
            elif structure_standardization == "primitive":
                structure_payload = structure_payload.conventional_to_primitive()
            elif structure_standardization == "swap-layer-to-c":
                meta = structure_payload.metadata()
                if meta.structure_class == "layer" and meta.layer_info and meta.layer_info["long_axis"] != 2:
                    structure_payload = structure_payload.swap_axes(meta.layer_info["long_axis"], 2)
                elif meta.structure_class == "string" and meta.string_info and meta.string_info["extension_axis"] != 2:
                    structure_payload = structure_payload.swap_axes(meta.string_info["extension_axis"], 2)
            if magmom_by_element:
                atoms = structure_payload.atoms.copy()
                initial_magmoms = [
                    float(magmom_by_element.get(symbol, 0.0))
                    for symbol in atoms.get_chemical_symbols()
                ]
                atoms.set_initial_magnetic_moments(initial_magmoms)
                structure_payload = AbacusStructure(atoms, source_format=structure_payload.source_format)

            final_species = set(structure_payload.atoms.get_chemical_symbols())
            unknown_species = (set(pseudo_map) | set(orbital_map)) - final_species
            if unknown_species:
                unknown = ", ".join(sorted(unknown_species))
                raise ForgeRequestError(f"asset map contains unknown structure species: {unknown}")

            # Render once before materialization.  In particular, this checks
            # that a partial orbital map can still produce a complete final
            # STRU from source metadata before any asset is written.
            final_stru = structure_payload.to_stru(
                pp_map={species: Path(source).name for species, source in pseudo_map.items()},
                orb_map={species: Path(source).name for species, source in orbital_map.items()},
            )
            if explicit_assets:
                materialization = materialize_assets(
                    ws.inputs_dir,
                    ws.root,
                    pseudo_sources=pseudo_map,
                    orbital_sources=orbital_map,
                    mode=asset_mode,
                )
            ws.write_text("inputs/STRU", final_stru)
            structure_info = structure_payload.metadata().to_dict()
        elif explicit_assets:
            raise ForgeRequestError("explicit asset maps require a parsed structure")

    params = build_task_parameters(
        task,
        metadata=structure_payload.metadata() if structure_payload is not None else None,
        parameters=parameters,
    )
    if input_overrides:
        params.update(input_overrides)
    for key in remove_parameters or ():
        params.pop(str(key), None)
    write_input(ws.inputs_dir / "INPUT", params)

    mesh = list(kpoints or [1, 1, 1])
    if kpt_mode == "line" and line_kpoints:
        write_kpt_line_mode(ws.inputs_dir / "KPT", list(line_kpoints))
    else:
        write_kpt_mesh(ws.inputs_dir / "KPT", mesh)

    ws.record_metadata(
        {
            "kind": "abacus-forge.workspace",
            "task": task or "scf",
            "structure": str(Path(structure)) if isinstance(structure, (str, Path)) else None,
            "structure_format": structure_payload.source_format if structure_payload is not None else structure_format,
            "structure_metadata": structure_info,
            "parameters": params,
            "kpoints": mesh,
            "metadata": metadata or {},
            "validation": validate_inputs(ws.inputs_dir),
        }
    )
    return ws, materialization


def _basename_map(mapping: dict[str, Path]) -> dict[str, str]:
    return {element: path.name for element, path in mapping.items()}


def _write_structure_fallback(workspace: Workspace, structure: Any) -> bool:
    if isinstance(structure, Path):
        if structure.exists() and structure.is_file():
            workspace.write_text("inputs/STRU", structure.read_text(encoding="utf-8", errors="ignore"))
            return True
        return False
    if isinstance(structure, str):
        path = _existing_path(structure)
        if path is not None:
            workspace.write_text("inputs/STRU", path.read_text(encoding="utf-8", errors="ignore"))
            return True
        if _looks_like_stru_text(structure):
            workspace.write_text("inputs/STRU", structure if structure.endswith("\n") else structure + "\n")
            return True
    return False


def _is_recognized_stru_source(structure: Any, structure_format: str | None) -> bool:
    if structure_format is not None and structure_format.lower() == "stru":
        return True
    if isinstance(structure, Path):
        try:
            return detect_structure_format(structure) == "stru"
        except OSError:
            return False
    if isinstance(structure, str):
        if _looks_like_stru_text(structure):
            return True
        path = _existing_path(structure)
        if path is not None:
            return detect_structure_format(path) == "stru"
    return False


def _existing_path(value: str) -> Path | None:
    try:
        candidate = Path(value)
    except OSError:
        return None
    try:
        if candidate.exists() and candidate.is_file():
            return candidate
    except OSError:
        return None
    return None


def _looks_like_stru_text(payload: str) -> bool:
    markers = ("ATOMIC_SPECIES", "ATOMIC_POSITIONS", "LATTICE_VECTORS")
    return sum(marker in payload for marker in markers) >= 2
