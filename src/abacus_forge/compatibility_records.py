"""Small shared serializers for existing unversioned compatibility files."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


def unit_manifest(
    *, task: str, unit: str = "default", engine: str = "abacus",
    prepared: bool = True, source_workdir: Path | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": "abacus-forge.unit",
        "task": task,
        "unit": unit,
        "engine": engine,
        "prepared": prepared,
        "source_workdir": str(source_workdir) if source_workdir is not None else None,
        "metadata": dict(metadata or {}),
    }


def modification_record(
    *, workspace: Path, task: str, modified_files: list[str],
    changes: Mapping[str, Any], unit: str = "default", engine: str = "abacus",
    status: str = "completed",
) -> dict[str, Any]:
    return {
        "workspace": str(workspace),
        "task": task,
        "unit": unit,
        "engine": engine,
        "status": status,
        "modified_files": modified_files,
        "changes": dict(changes),
    }
