"""Structured results for run and collect primitives."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RunResult:
    """Outcome of one runner invocation."""

    workspace: Path
    command: list[str]
    returncode: int
    status: str
    stdout_path: Path
    stderr_path: Path
    omp_threads: int
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {
            **payload,
            "workspace": str(self.workspace),
            "stdout_path": str(self.stdout_path),
            "stderr_path": str(self.stderr_path),
        }


@dataclass(slots=True)
class CollectionResult:
    """Parsed metrics and file index from one workspace."""

    workspace: Path
    status: str
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    inputs_snapshot: dict[str, Any] = field(default_factory=dict)
    structure_snapshot: dict[str, Any] | None = None
    final_structure_snapshot: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace": str(self.workspace),
            "status": self.status,
            "metrics": self.metrics,
            "artifacts": self.artifacts,
            "diagnostics": self.diagnostics,
            "inputs_snapshot": self.inputs_snapshot,
            "structure_snapshot": self.structure_snapshot,
            "final_structure_snapshot": self.final_structure_snapshot,
        }
