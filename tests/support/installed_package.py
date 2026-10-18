"""Prove that tests import a wheel-installed package instead of source.

``ABACUS_FORGE_INSTALLED_PACKAGE_ONLY=1`` exists to validate a built wheel, so
the guard must reject any installation mode that executes source: editable
installs (PEP 660 ``direct_url.json`` or legacy ``.egg-link``) and imports that
resolve outside the installed distribution.  A wheel installed into a virtual
environment inside the repository is legitimate; the check therefore compares
against the distribution's own file list rather than the repository root.
"""

from __future__ import annotations

import json
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


def is_editable_install(dist: Any) -> bool:
    """Return True for editable installs, including legacy egg-link records."""

    path = getattr(dist, "_path", None)
    if path is not None and str(path).endswith(".egg-link"):
        return True
    direct_url = _direct_url(dist)
    return bool(direct_url and direct_url.get("dir_info", {}).get("editable"))


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

    distribution = dist if dist is not None else metadata.distribution(DISTRIBUTION_NAME)
    if is_editable_install(distribution):
        raise NotWheelInstalledError(
            f"{DISTRIBUTION_NAME} is installed in editable mode; "
            "install the built wheel instead of the source checkout"
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
