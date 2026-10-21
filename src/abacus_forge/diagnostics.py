"""Side-effect-free diagnostics for a pip-installed Forge environment."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import re
import shutil
import sys
from importlib import metadata
from pathlib import Path
from typing import Sequence

from abacus_forge import __version__

SCHEMA_VERSION = "forge.environment/v1"
_FALLBACK_DEPENDENCIES = ("ase", "dpdata", "matplotlib", "numpy", "pymatgen")


def _core_dependencies(distribution: metadata.Distribution | None) -> tuple[str, ...]:
    """Use installed wheel metadata; fall back to the release's base set."""
    if distribution is None:
        return _FALLBACK_DEPENDENCIES
    names: list[str] = []
    for requirement in distribution.requires or ():
        # Optional extras carry an ``extra == ...`` marker.  Parsing the base
        # distribution names needs no packaging or other third-party import.
        if re.search(r"\bextra\s*==", requirement):
            continue
        match = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement)
        if match:
            names.append(match.group(1))
    return tuple(dict.fromkeys(names)) or _FALLBACK_DEPENDENCIES


def _dependency(name: str) -> dict[str, str | None]:
    try:
        version = metadata.version(name)
    except metadata.PackageNotFoundError:
        return {"name": name, "status": "missing", "version": None,
                "path": None, "suggestion": f"Install the missing core dependency: python -m pip install {name}"}
    try:
        distribution = metadata.distribution(name)
        path = str(Path(distribution.locate_file("")).resolve())
    except (metadata.PackageNotFoundError, OSError, ValueError):
        path = None
    try:
        discoverable = importlib.util.find_spec(name.replace("-", "_")) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        discoverable = False
    if not discoverable:
        return {"name": name, "status": "missing", "version": version,
                "path": path, "suggestion": f"The {name} distribution is installed but its Python module is not discoverable; reinstall it."}
    return {"name": name, "status": "present", "version": version,
            "path": path, "suggestion": None}


def _executable(value: str) -> dict[str, str | None]:
    found = shutil.which(value)
    path = str(Path(found).resolve()) if found else None
    return {"requested": value, "status": "present" if found else "missing",
            "path": path,
            "suggestion": None if found else "Provide an executable file or a command available on PATH; doctor never runs it."}


def _asset(value: str) -> dict[str, str | None]:
    try:
        candidate = Path(value).expanduser().resolve()
        present = candidate.is_file() and os.access(candidate, os.R_OK)
        path = str(candidate)
    except (OSError, ValueError):
        present, path = False, None
    return {"requested": value, "status": "present" if present else "missing",
            "path": path,
            "suggestion": None if present else "Provide a readable file path for this asset."}


def environment_report(*, executable: str | None = None, assets: Sequence[str] = ()) -> dict:
    """Inspect metadata and explicit paths without importing engines or writing files."""
    try:
        distribution = metadata.distribution("abacus-forge")
        installed = {"name": "abacus-forge", "status": "present", "version": distribution.version,
                     "path": str(Path(distribution.locate_file("")).resolve()), "suggestion": None}
    except metadata.PackageNotFoundError:
        distribution = None
        installed = {"name": "abacus-forge", "status": "missing", "version": None,
                     "path": None, "suggestion": "Install abacus-forge into this Python environment."}
    dependencies = [_dependency(name) for name in _core_dependencies(distribution)]
    executables = [_executable(executable)] if executable is not None else []
    asset_checks = [_asset(value) for value in assets]
    missing = any(item["status"] == "missing" for item in [installed, *dependencies, *executables, *asset_checks])
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "missing" if missing else "ready",
        "python": {"version": platform.python_version(), "executable": sys.executable},
        "distribution": installed,
        "dependencies": dependencies,
        "executables": executables,
        "assets": asset_checks,
        "limits": (
            "Discovery and file access only; no program is started. A discoverable executable "
            "does not prove runtime or ABI compatibility, and readable assets do not prove scientific correctness."
        ),
    }


def _human_report(report: dict) -> str:
    lines = [f"Forge environment: {report['status']}",
             f"Python: {report['python']['version']} ({report['python']['executable']})",
             f"Forge: {report['distribution']['status']} ({report['distribution']['version'] or 'unknown'})"]
    for item in report["dependencies"]:
        lines.append(f"Dependency {item['name']}: {item['status']} ({item['version'] or 'unknown'})")
    for item in report["executables"]:
        lines.append(f"Executable {item['requested']}: {item['status']} ({item['path'] or 'not found'})")
    for item in report["assets"]:
        lines.append(f"Asset {item['requested']}: {item['status']} ({item['path'] or 'not found'})")
    if not report["executables"]:
        lines.append("No external engine is required for the default check.")
    for item in [report["distribution"], *report["dependencies"], *report["executables"], *report["assets"]]:
        if item["suggestion"]:
            lines.append(f"Suggestion: {item['suggestion']}")
    lines.append(report["limits"])
    return "\n".join(lines) + "\n"


def run_doctor(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="abacus-forge doctor", description="Inspect this Forge environment without running an engine")
    parser.add_argument("--json", action="store_true", dest="as_json", help="emit forge.environment/v1 JSON")
    parser.add_argument("--executable", metavar="PATH_OR_NAME", help="require this executable path or PATH command")
    parser.add_argument("--asset", action="append", default=[], metavar="PATH", help="require a readable file; repeatable")
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as error:
        return int(error.code)
    if args.executable == "" or any(value == "" for value in args.asset):
        parser.print_usage(sys.stderr)
        print("abacus-forge doctor: error: explicit paths must not be empty", file=sys.stderr)
        return 2
    report = environment_report(executable=args.executable, assets=args.asset)
    print(json.dumps(report, sort_keys=True, allow_nan=False) if args.as_json else _human_report(report), end="\n" if args.as_json else "")
    return 3 if report["status"] == "missing" else 0


def run_version(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="abacus-forge")
    parser.add_argument("--version", action="store_true")
    try:
        parser.parse_args(list(argv))
    except SystemExit as error:
        return int(error.code)
    try:
        version = metadata.version("abacus-forge")
    except metadata.PackageNotFoundError:
        version = __version__
    print(f"abacus-forge {version}")
    return 0
