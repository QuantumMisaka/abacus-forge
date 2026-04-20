"""Workspace model for a single ABACUS run directory."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Workspace:
    """Encapsulate the on-disk layout for one run workspace."""

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)

    @property
    def inputs_dir(self) -> Path:
        return self.root / "inputs"

    @property
    def outputs_dir(self) -> Path:
        return self.root / "outputs"

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"

    @property
    def meta_path(self) -> Path:
        return self.root / "meta.json"

    def ensure_layout(self) -> "Workspace":
        self.inputs_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        return self

    def write_text(self, relative_path: str | Path, content: str) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_json(self, relative_path: str | Path, payload: dict[str, Any]) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def record_metadata(self, payload: dict[str, Any]) -> Path:
        return self.write_json(self.meta_path.relative_to(self.root), payload)
