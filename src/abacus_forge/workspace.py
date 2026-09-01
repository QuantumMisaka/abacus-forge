"""Workspace model for a single ABACUS run directory."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .contracts import JSONValue, WORKSPACE_SCHEMA_VERSION, canonical_relative_path


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

    def resolve_relative(self, relative_path: str | Path) -> Path:
        """Resolve a path and ensure it remains within this workspace."""
        root = self.root.resolve()
        candidate = (root / Path(relative_path)).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise ValueError("path must remain under the workspace root") from error
        return candidate

    def _resolve_owned_path(self, relative_path: str | Path) -> Path:
        return self.resolve_relative(relative_path)

    @staticmethod
    def _write_json_atomic(path: Path, payload: Mapping[str, JSONValue]) -> None:
        serialized = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(serialized)
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except FileNotFoundError:
                    pass

    def write_text(self, relative_path: str | Path, content: str) -> Path:
        path = self._resolve_owned_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_json(self, relative_path: str | Path, payload: Mapping[str, JSONValue]) -> Path:
        path = self._resolve_owned_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json_atomic(path, payload)
        return path

    def ensure_manifest(self) -> Path:
        """Create reports/forge-workspace.json once and return it."""
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        path = self.resolve_relative(Path("reports") / "forge-workspace.json")
        if not path.exists():
            self._write_json_atomic(
                path,
                {"schema_version": WORKSPACE_SCHEMA_VERSION, "workspace_rel": ".", "events": []},
            )
        return path

    def append_operation_event(self, operation: str, payload: Mapping[str, JSONValue]) -> Path:
        """Atomically write an operation event and append its manifest reference."""
        if not isinstance(operation, str) or not operation or "/" in operation or "\\" in operation:
            raise ValueError("operation must be a non-empty path-safe string")
        manifest_path = self.ensure_manifest()
        events_dir = self.resolve_relative(Path("reports") / "events")
        events_dir.mkdir(parents=True, exist_ok=True)

        event_id = uuid.uuid4().hex
        event_path = events_dir / f"{event_id}-{operation}.json"
        while event_path.exists():
            event_id = uuid.uuid4().hex
            event_path = events_dir / f"{event_id}-{operation}.json"
        self._write_json_atomic(event_path, {"id": event_id, "operation": operation, "payload": payload})

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict) or not isinstance(manifest.get("events"), list):
                raise ValueError("workspace manifest has invalid events")
            event_rel = canonical_relative_path(event_path.relative_to(self.root.resolve()).as_posix())
            manifest["events"].append({"id": event_id, "operation": operation, "path_rel": event_rel})
            self._write_json_atomic(manifest_path, manifest)
        except Exception:
            # The event itself remains immutable and can be recovered if the
            # manifest cannot be updated.
            raise
        return event_path

    def record_metadata(self, payload: dict[str, Any]) -> Path:
        return self.write_json(self.meta_path.relative_to(self.root), payload)
