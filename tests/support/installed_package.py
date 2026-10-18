"""Prove that tests import a wheel-installed package instead of source.

``ABACUS_FORGE_INSTALLED_PACKAGE_ONLY=1`` exists to validate a built wheel, so
the guard must reject any installation mode that executes source: editable
installs (PEP 660 ``direct_url.json`` or legacy ``setup.py develop`` egg-links)
and imports that resolve outside the installed distribution.  A wheel installed
into a virtual environment inside the repository is legitimate; the check
therefore compares against the distribution's own file list rather than the
repository root.
"""

from __future__ import annotations

import json
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

DISTRIBUTION_NAME = "abacus-forge"


class NotWheelInstalledError(RuntimeError):
    """The imported distribution is not a wheel install of abacus-forge."""


def _direct_url(dist: Any) -> dict[str, Any] | None:
    try:
        raw = dist.read_text("direct_url.json")
    except (OSError, ValueError):
        return None
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def egg_link_targets() -> dict[Path, Path]:
    """Map every legacy ``*.egg-link`` on ``sys.path`` to its target directory."""

    targets: dict[Path, Path] = {}
    for entry in sys.path:
        if not entry:
            continue
        directory = Path(entry)
        if not directory.is_dir():
            continue
        try:
            links = sorted(directory.glob("*.egg-link"))
        except OSError:
            continue
        for link in links:
            try:
                lines = link.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            first = lines[0].strip() if lines else ""
            if not first:
                continue
            target = Path(first).expanduser()
            if not target.is_absolute():
                target = link.parent / target
            targets[link.resolve()] = target.resolve()
    return targets


def non_wheel_reason(dist: Any) -> str | None:
    """Return why ``dist`` is not a wheel install, or ``None`` for a wheel."""

    path = getattr(dist, "_path", None)
    metadata_dir = Path(path) if path is not None else None
    if metadata_dir is not None and metadata_dir.name.endswith(".egg-link"):
        return f"legacy egg-link metadata {metadata_dir}"

    direct_url = _direct_url(dist)
    if direct_url and direct_url.get("dir_info", {}).get("editable"):
        return f"PEP 660 editable direct_url for {DISTRIBUTION_NAME}"

    if metadata_dir is not None and metadata_dir.name.endswith(".egg-info"):
        project_root = metadata_dir.parent.resolve()
        for link, target in egg_link_targets().items():
            if target == project_root:
                return f"legacy egg-link {link} points at {target}"
        return (
            f"source-tree egg-info {metadata_dir} without a wheel RECORD; "
            "run a wheel install instead of setup.py develop"
        )
    return None


def is_editable_install(dist: Any) -> bool:
    """Return True for every editable/develop installation mode."""

    return non_wheel_reason(dist) is not None


def installed_python_files(dist: Any) -> set[Path]:
    files = dist.files
    if not files:
        return set()
    return {
        Path(dist.locate_file(item)).resolve()
        for item in files
        if str(item).endswith(".py")
    }


def validate_wheel_install(module: Any, dist: Any | None = None) -> None:
    """Fail unless ``module`` comes from a wheel-installed distribution."""

    try:
        distribution = dist if dist is not None else metadata.distribution(DISTRIBUTION_NAME)
    except metadata.PackageNotFoundError as error:
        raise NotWheelInstalledError(
            f"{DISTRIBUTION_NAME} distribution metadata was not found; install the built wheel"
        ) from error

    reason = non_wheel_reason(distribution)
    if reason is not None:
        raise NotWheelInstalledError(
            f"{DISTRIBUTION_NAME} is not a wheel install ({reason})"
        )

    installed = installed_python_files(distribution)
    if not installed:
        raise NotWheelInstalledError(
            f"{DISTRIBUTION_NAME} exposes no installed Python files; "
            "the installation artifact cannot be verified"
        )
    resolved = Path(module.__file__).resolve()
    if resolved not in installed:
        raise NotWheelInstalledError(
            f"imported {DISTRIBUTION_NAME} from {resolved}, which is not one of the "
            f"{len(installed)} files recorded by the installed distribution"
        )
