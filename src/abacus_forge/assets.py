"""Pseudopotential and orbital asset helpers."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def collect_assets(directory: str | Path | None) -> dict[str, Path]:
    if directory is None:
        return {}
    base = Path(directory)
    if not base.is_dir():
        return {}
    mapping: dict[str, Path] = {}
    for entry in sorted(base.iterdir()):
        if not entry.is_file():
            continue
        element = _infer_element(entry.name)
        if element and element not in mapping:
            mapping[element] = entry
    return mapping


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
