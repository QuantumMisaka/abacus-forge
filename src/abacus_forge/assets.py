"""Pseudopotential and orbital asset helpers."""

from __future__ import annotations

import os
import shutil
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path

from .errors import ForgePathError, ForgePreconditionError, ForgeRequestError


_PSEUDO_SUFFIXES = {".upf"}
_TYPED_PSEUDO_SUFFIXES = {".upf", ".vp"}
_ORBITAL_SUFFIXES = {".orb"}


@dataclass(frozen=True)
class AssetMaterialization:
    """A materialized asset and its content-addressed provenance."""

    family: str
    species: str
    source: str
    destination: str
    mode: str
    source_sha256: str
    destination_sha256: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    def as_dict(self) -> dict[str, str]:
        return self.to_dict()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def materialize_assets(
    target_inputs: str | Path,
    workspace_root: str | Path,
    pseudo_sources: dict[str, str | Path] | None = None,
    orbital_sources: dict[str, str | Path] | None = None,
    mode: str = "copy",
) -> tuple[AssetMaterialization, ...]:
    """Validate and materialize explicitly supplied pseudo/orbital assets."""
    if not isinstance(mode, str) or mode not in {"copy", "link"}:
        raise ForgeRequestError(f"unsupported asset mode: {mode}")
    root = Path(workspace_root).resolve()
    target = Path(target_inputs)
    if not target.is_absolute():
        target = root / target
    target = target.resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ForgePathError("target_inputs must remain under workspace root") from None
    if target.exists() and not target.is_dir():
        raise ForgeRequestError("target_inputs must be a directory")
    entries: list[tuple[str, str, Path]] = []
    for family, supplied in (("pseudo", pseudo_sources), ("orbital", orbital_sources)):
        mapping = {} if supplied is None else supplied
        if not hasattr(mapping, "items"):
            raise ForgeRequestError("asset sources must be mappings")
        for species, raw_source in mapping.items():
            if not isinstance(raw_source, (str, Path)) or not str(raw_source):
                raise ForgeRequestError("asset source must be a non-empty path")
            source = Path(raw_source)
            was_absolute = source.is_absolute()
            candidate = source if was_absolute else root / source
            if candidate.is_symlink():
                raise ForgePreconditionError(f"asset source is not a regular file: {raw_source}")
            source = candidate.resolve()
            if not was_absolute:
                try:
                    source.relative_to(root)
                except ValueError:
                    raise ForgePathError("relative asset source must remain under workspace root") from None
            if not source.exists() or not source.is_file() or source.is_symlink():
                raise ForgePreconditionError(f"asset source is not a regular file: {raw_source}")
            allowed = _TYPED_PSEUDO_SUFFIXES if family == "pseudo" else _ORBITAL_SUFFIXES
            if source.suffix.lower() not in allowed:
                raise ForgeRequestError(f"invalid {family} asset suffix: {source.name}")
            basename = source.name
            if basename in {"", ".", ".."} or Path(basename).name != basename:
                raise ForgeRequestError(f"unsafe asset basename: {basename}")
            entries.append((family, str(species), source))

    destinations: dict[str, tuple[Path, Path]] = {}
    records: list[tuple[str, str, Path, Path, str]] = []
    for family, species, source in entries:
        destination = target / source.name
        key = str(destination)
        prior = destinations.get(key)
        if prior is not None and prior[1] != source:
            raise ForgeRequestError(f"duplicate asset basename from distinct sources: {source.name}")
        destinations[key] = (destination, source)
        if mode == "link":
            try:
                source.relative_to(root)
            except ValueError:
                raise ForgeRequestError("external assets cannot be linked") from None
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() and mode == "link":
                existing_source = (destination.parent / destination.readlink()).resolve()
                if existing_source != source:
                    raise ForgeRequestError(f"conflicting existing destination: {destination}")
            elif mode == "link" or not destination.is_file() or destination.is_symlink() or _sha256(destination) != _sha256(source):
                raise ForgeRequestError(f"conflicting existing destination: {destination}")
        records.append((family, species, source, destination, mode))

    target.mkdir(parents=True, exist_ok=True)
    output: list[AssetMaterialization] = []
    written: set[Path] = set()
    for family, species, source, destination, selected_mode in records:
        if destination not in written and not (destination.exists() or destination.is_symlink()):
            if selected_mode == "copy":
                shutil.copy2(source, destination)
            else:
                os.symlink(os.path.relpath(source, destination.parent), destination)
            written.add(destination)
        try:
            source_ref = str(source.relative_to(root))
        except ValueError:
            source_ref = str(source)
        output.append(AssetMaterialization(
            family, species, source_ref, str(destination.relative_to(root)), selected_mode,
            _sha256(source), _sha256(destination)))
    return tuple(output)


def collect_assets(directory: str | Path | None, *, family: str | None = None) -> dict[str, Path]:
    if directory is None:
        return {}
    base = Path(directory)
    if not base.is_dir():
        return {}
    mapping: dict[str, Path] = {}
    for entry in sorted(base.iterdir()):
        if not entry.is_file():
            continue
        if not _matches_family(entry, family=family):
            continue
        element = _infer_element(entry.name)
        if element and element not in mapping:
            mapping[element] = entry
    return mapping


def _matches_family(path: Path, *, family: str | None) -> bool:
    if family is None:
        return path.suffix.lower() in _PSEUDO_SUFFIXES | _ORBITAL_SUFFIXES
    if family == "pseudo":
        return path.suffix.lower() in _PSEUDO_SUFFIXES
    if family == "orbital":
        return path.suffix.lower() in _ORBITAL_SUFFIXES
    raise ValueError(f"unsupported asset family: {family}")


def stage_assets(
    target_dir: str | Path,
    *,
    pseudo_map: dict[str, Path] | None = None,
    orbital_map: dict[str, Path] | None = None,
    mode: str = "link",
) -> dict[str, list[str]]:
    target = Path(target_dir)
    staged = {"pseudo_files": [], "orbital_files": []}
    for key, mapping in (("pseudo_files", pseudo_map or {}), ("orbital_files", orbital_map or {})):
        for source in mapping.values():
            destination = target / source.name
            if destination.exists() or destination.is_symlink():
                destination.unlink()
            if mode == "copy":
                shutil.copy2(source, destination)
            else:
                os.symlink(source.resolve(), destination)
            staged[key].append(str(destination))
    return staged


def _infer_element(filename: str) -> str | None:
    name = Path(filename).stem
    if not name:
        return None
    if len(name) == 1:
        return name.capitalize()
    candidate = name[:2]
    if candidate[1].islower():
        return candidate[0].upper() + candidate[1]
    return candidate[0].upper()
