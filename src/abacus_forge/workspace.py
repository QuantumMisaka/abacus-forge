"""Workspace model for a single ABACUS run directory."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

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
        raw = os.fspath(relative_path)
        if not isinstance(raw, str) or raw == ".":
            raise ValueError("path must be a canonical relative path under the workspace root")
        # Validate the spelling before Path.resolve() can normalize it.
        try:
            canonical_relative_path(raw)
        except ValueError as error:
            raise ValueError("path must remain under the workspace root and be canonical") from error
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
                # Keep the historical write_json byte representation exactly:
                # json.dumps(..., indent=2, sort_keys=True) has no newline.
                temporary.write(serialized)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, path)
            Workspace._fsync_directory(path.parent)
            temporary_path = None
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except FileNotFoundError:
                    pass

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        """Persist directory-entry changes on supported Unix filesystems."""
        try:
            descriptor = os.open(directory, os.O_RDONLY)
        except OSError:
            return
        try:
            try:
                os.fsync(descriptor)
            except OSError:
                # Directory fsync improves crash durability where supported;
                # atomic replacement remains the process-failure guarantee.
                pass
        finally:
            os.close(descriptor)

    @contextmanager
    def _manifest_lock(self) -> Iterator[None]:
        """Serialize manifest read-modify-write operations across processes."""
        import fcntl

        self.reports_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.resolve_relative(Path("reports") / ".forge-workspace.lock")
        with lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

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
        with self._manifest_lock():
            return self._ensure_manifest_unlocked()

    def _ensure_manifest_unlocked(self) -> Path:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        path = self.resolve_relative(Path("reports") / "forge-workspace.json")
        if not path.exists():
            self._write_json_atomic(
                path,
                {"schema_version": WORKSPACE_SCHEMA_VERSION, "workspace_rel": ".", "events": []},
            )
        self._reconcile_events_unlocked(path)
        return path

    def _reconcile_events_unlocked(self, manifest_path: Path) -> None:
        """Index valid immutable event files that are not yet discoverable."""
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("workspace manifest is not valid JSON") from error
        if not isinstance(manifest, dict) or not isinstance(manifest.get("events"), list):
            raise ValueError("workspace manifest has invalid events")
        indexed = {item.get("id") for item in manifest["events"] if isinstance(item, dict)}
        additions = []
        events_dir = self.resolve_relative(Path("reports") / "events")
        if events_dir.exists():
            for event_path in sorted(events_dir.glob("*.json"), key=lambda item: item.name):
                try:
                    event = json.loads(event_path.read_text(encoding="utf-8"))
                    event_id = event["id"]
                    operation = event["operation"]
                    if not isinstance(event, dict) or not isinstance(event_id, str) or not isinstance(operation, str) or not operation or not isinstance(event.get("payload"), dict):
                        continue
                    if event_id in indexed:
                        continue
                    rel = canonical_relative_path(event_path.relative_to(self.root.resolve()).as_posix())
                    additions.append({"id": event_id, "operation": operation, "path_rel": rel})
                    indexed.add(event_id)
                except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                    continue
        if additions:
            manifest["events"].extend(additions)
            self._write_json_atomic(manifest_path, manifest)

    def append_operation_event(self, operation: str, payload: Mapping[str, JSONValue]) -> Path:
        """Atomically write an operation event and append its manifest reference."""
        if not isinstance(operation, str) or not operation or "/" in operation or "\\" in operation:
            raise ValueError("operation must be a non-empty path-safe string")
        with self._manifest_lock():
            manifest_path = self._ensure_manifest_unlocked()
            events_dir = self.resolve_relative(Path("reports") / "events")
            events_dir.mkdir(parents=True, exist_ok=True)

            event_id = uuid.uuid4().hex
            event_path = events_dir / f"{event_id}-{operation}.json"
            while event_path.exists():
                event_id = uuid.uuid4().hex
                event_path = events_dir / f"{event_id}-{operation}.json"
            self._write_json_atomic(event_path, {"id": event_id, "operation": operation, "payload": payload})

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict) or not isinstance(manifest.get("events"), list):
                raise ValueError("workspace manifest has invalid events")
            event_rel = canonical_relative_path(event_path.relative_to(self.root.resolve()).as_posix())
            manifest["events"].append({"id": event_id, "operation": operation, "path_rel": event_rel})
            # Event file is authoritative if this replacement fails; the next
            # locked workspace access reconciles it into the index.
            self._write_json_atomic(manifest_path, manifest)
        return event_path

    def append_v1_operation_event(self, operation_id: str, operation: str, payload: Mapping[str, JSONValue]) -> Path:
        """Append one v1 event whose identity is supplied by its typed request."""
        if not isinstance(operation_id, str):
            raise ValueError("operation_id must be a lowercase UUIDv4")
        try:
            parsed_id = uuid.UUID(operation_id)
        except ValueError as error:
            raise ValueError("operation_id must be a lowercase UUIDv4") from error
        if parsed_id.version != 4 or str(parsed_id) != operation_id:
            raise ValueError("operation_id must be a lowercase UUIDv4")
        if not isinstance(operation, str) or not operation or "/" in operation or "\\" in operation:
            raise ValueError("operation must be a non-empty path-safe string")

        with self._manifest_lock():
            manifest_path = self._ensure_manifest_unlocked()
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict) or not isinstance(manifest.get("events"), list):
                raise ValueError("workspace manifest has invalid events")
            if any(isinstance(event, dict) and event.get("id") == operation_id for event in manifest["events"]):
                raise ValueError("operation_id already exists in workspace manifest")

            events_dir = self.resolve_relative(Path("reports") / "events")
            events_dir.mkdir(parents=True, exist_ok=True)
            event_path = events_dir / f"{operation_id}-{operation}.json"
            if event_path.exists():
                raise ValueError("operation_id already exists in workspace events")
            self._write_json_atomic(event_path, {"id": operation_id, "operation": operation, "payload": payload})
            event_rel = canonical_relative_path(event_path.relative_to(self.root.resolve()).as_posix())
            manifest["events"].append({"id": operation_id, "operation": operation, "path_rel": event_rel})
            self._write_json_atomic(manifest_path, manifest)
        return event_path

    def record_metadata(self, payload: dict[str, Any]) -> Path:
        return self.write_json(self.meta_path.relative_to(self.root), payload)
