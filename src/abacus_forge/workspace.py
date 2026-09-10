"""Workspace model for a single ABACUS run directory."""

from __future__ import annotations

import json
import math
import os
import re
import secrets
import stat
import tempfile
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Iterator, Mapping

from .contracts import JSONValue, WORKSPACE_SCHEMA_VERSION, canonical_relative_path
from .errors import ForgePathError, ForgePersistenceError, ForgeSchemaError, OperationConflictError


_V1_OPERATION_PATTERN = re.compile(r"[a-z][a-z0-9_]*\Z")


def _validate_v1_json_value(value: object, *, active: set[int]) -> JSONValue:
    """Validate and normalize a JSON value for a v1 event payload."""
    if value is None or isinstance(value, (bool, int, str)):
        return value  # type: ignore[return-value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("payload must contain only finite JSON values")
        return value

    value_id = id(value)
    if isinstance(value, Mapping):
        if value_id in active:
            raise ValueError("payload must not contain circular references")
        active.add(value_id)
        try:
            normalized: dict[str, JSONValue] = {}
            try:
                items = value.items()
                for key, item in items:
                    if not isinstance(key, str):
                        raise ValueError("payload object keys must be strings")
                    normalized[key] = _validate_v1_json_value(item, active=active)
            except ValueError:
                raise
            except (TypeError, AttributeError, RuntimeError) as error:
                raise ValueError("payload must contain only JSON values") from error
            return normalized
        finally:
            active.remove(value_id)

    if isinstance(value, list):
        if value_id in active:
            raise ValueError("payload must not contain circular references")
        active.add(value_id)
        try:
            try:
                return [_validate_v1_json_value(item, active=active) for item in value]
            except ValueError:
                raise
            except (TypeError, RuntimeError) as error:
                raise ValueError("payload must contain only JSON values") from error
        finally:
            active.remove(value_id)

    raise ValueError("payload must contain only JSON values")


def _validate_v1_payload(payload: object) -> dict[str, JSONValue]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping of JSON values")
    normalized = _validate_v1_json_value(payload, active=set())
    # The Mapping check above and helper guarantee this cast at runtime.
    return normalized  # type: ignore[return-value]


@dataclass(slots=True)
class Workspace:
    """Encapsulate the on-disk layout for one run workspace."""

    root: Path
    _operation_locks: ClassVar[dict[str, threading.Lock]] = {}
    _operation_locks_guard: ClassVar[threading.Lock] = threading.Lock()

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
            raise ForgePathError("path must remain under the workspace root") from error
        return candidate

    def _resolve_owned_path(self, relative_path: str | Path) -> Path:
        raw = os.fspath(relative_path)
        if not isinstance(raw, str) or raw == ".":
            raise ForgePathError("path must be a canonical relative path under the workspace root")
        # Validate the spelling before Path.resolve() can normalize it.
        try:
            canonical_relative_path(raw)
        except ValueError as error:
            raise ForgePathError("path must remain under the workspace root and be canonical") from error
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

    @staticmethod
    def _release_lock(fd: int, message: str) -> None:
        """Release an audit lock, typing only release-time filesystem errors."""
        import fcntl

        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError as error:
            raise ForgePersistenceError(message) from error

    @contextmanager
    def _manifest_lock(self) -> Iterator[None]:
        """Serialize manifest read-modify-write operations across processes."""
        import fcntl

        try:
            self.reports_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise ForgePersistenceError("unable to create reports directory") from error
        lock_path = self.resolve_relative(Path("reports") / ".forge-workspace.lock")
        try:
            lock = lock_path.open("a+", encoding="utf-8")
        except OSError as error:
            raise ForgePersistenceError("unable to acquire workspace manifest lock") from error
        with lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            except OSError as error:
                raise ForgePersistenceError("unable to acquire workspace manifest lock") from error
            try:
                yield
            finally:
                self._release_lock(lock.fileno(), "unable to release workspace manifest lock")

    @contextmanager
    def _operation_lock(self) -> Iterator[None]:
        """Serialize all operations mutating or auditing this workspace.

        ``flock`` protects separate Forge processes; the keyed threading lock
        closes the same-process/thread gap in which ``flock`` is not a useful
        mutual exclusion primitive.
        """
        try:
            self.reports_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise ForgePersistenceError("unable to create reports directory") from error
        key = str(self.root.resolve())
        with self._operation_locks_guard:
            lock = self._operation_locks.setdefault(key, threading.Lock())
        with lock:
            lock_path = self.resolve_relative(Path("reports") / ".forge-operation.lock")
            try:
                operation_lock = lock_path.open("a+", encoding="utf-8")
            except OSError as error:
                raise ForgePersistenceError("unable to acquire operation lock") from error
            with operation_lock:
                import fcntl

                try:
                    fcntl.flock(operation_lock.fileno(), fcntl.LOCK_EX)
                except OSError as error:
                    raise ForgePersistenceError("unable to acquire operation lock") from error
                try:
                    yield
                finally:
                    self._release_lock(operation_lock.fileno(), "unable to release operation lock")

    @contextmanager
    def operation_guard(self, operation_id: str, operation: str) -> Iterator[str]:
        """Admit one operation and hold the workspace lock to its commit.

        The returned opaque token is required by
        :meth:`append_claimed_v1_operation_event`.  Admission files are
        durable tombstones: they are removed only by a successful event and
        manifest commit owned by this token.
        """
        self._validate_v1_identity(operation_id, operation)
        with self._operation_lock():
            owner_token = self._admit_v1_operation(operation_id, operation)
            yield owner_token

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
        try:
            self.reports_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise ForgePersistenceError("unable to create reports directory") from error
        path = self.resolve_relative(Path("reports") / "forge-workspace.json")
        if not path.exists():
            try:
                self._write_json_atomic(
                    path,
                    {"schema_version": WORKSPACE_SCHEMA_VERSION, "workspace_rel": ".", "events": []},
                )
            except OSError as error:
                raise ForgePersistenceError("unable to persist workspace manifest") from error
        self._reconcile_events_unlocked(path)
        return path

    @staticmethod
    def _reconciliation_directory_flags() -> int:
        flags = os.O_RDONLY
        flags |= getattr(os, "O_DIRECTORY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        return flags

    def _open_events_directory_unlocked(self) -> int | None:
        """Open reports/events as a no-follow directory relative to root.

        The returned descriptor anchors all later event enumeration and file
        reads.  If the directory is absent or unsafe, reconciliation simply
        has no event files to index, matching the best-effort nature of the
        historical glob-based reconciliation.
        """

        flags = self._reconciliation_directory_flags()
        root_fd: int | None = None
        reports_fd: int | None = None
        events_fd: int | None = None
        try:
            root_fd = os.open(self.root, flags)
            reports_fd = os.open("reports", flags, dir_fd=root_fd)
            events_fd = os.open("events", flags, dir_fd=reports_fd)
            result = events_fd
            events_fd = None
            return result
        except OSError:
            return None
        finally:
            for descriptor in (events_fd, reports_fd, root_fd):
                if descriptor is not None:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass

    @staticmethod
    def _read_reconciliation_event(events_fd: int, name: str) -> object:
        """Read one regular event file without following its leaf symlink."""

        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor: int | None = None
        try:
            descriptor = os.open(name, flags, dir_fd=events_fd)
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                return None
            with os.fdopen(descriptor, "r", encoding="utf-8") as event_file:
                descriptor = None
                return json.load(event_file)
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass

    def _reconcile_events_unlocked(self, manifest_path: Path) -> None:
        """Index valid immutable event files that are not yet discoverable."""
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ForgePersistenceError("workspace manifest is not valid JSON") from error
        if not isinstance(manifest, dict) or not isinstance(manifest.get("events"), list):
            raise ForgePersistenceError("workspace manifest has invalid events")
        indexed = {item.get("id") for item in manifest["events"] if isinstance(item, dict)}
        additions = []
        events_fd = self._open_events_directory_unlocked()
        if events_fd is not None:
            try:
                try:
                    with os.scandir(events_fd) as entries:
                        names = sorted(
                            entry.name for entry in entries if entry.name.endswith(".json")
                        )
                except OSError:
                    names = []
                for name in names:
                    try:
                        event = self._read_reconciliation_event(events_fd, name)
                        if not isinstance(event, dict):
                            continue
                        event_id = event.get("id")
                        operation = event.get("operation")
                        if (
                            not isinstance(event_id, str)
                            or not isinstance(operation, str)
                            or not operation
                            or not isinstance(event.get("payload"), dict)
                        ):
                            continue
                        if event_id in indexed:
                            continue
                        rel = canonical_relative_path(f"reports/events/{name}")
                        additions.append({"id": event_id, "operation": operation, "path_rel": rel})
                        indexed.add(event_id)
                    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                        continue
            finally:
                try:
                    os.close(events_fd)
                except OSError:
                    pass
        if additions:
            manifest["events"].extend(additions)
            try:
                self._write_json_atomic(manifest_path, manifest)
            except OSError as error:
                raise ForgePersistenceError("unable to reconcile workspace manifest") from error

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
        return self._append_v1_operation_event(operation_id, operation, payload, claim_token=None)

    @contextmanager
    def claim_v1_operation(self, operation_id: str, operation: str) -> Iterator[str]:
        """Compatibility name for the full operation guard."""
        with self.operation_guard(operation_id, operation) as owner_token:
            yield owner_token

    @staticmethod
    def _validate_v1_identity(operation_id: str, operation: str) -> None:
        if not isinstance(operation_id, str):
            raise ForgeSchemaError("operation_id must be a lowercase UUIDv4")
        try:
            parsed_id = uuid.UUID(operation_id)
        except (AttributeError, ValueError) as error:
            raise ForgeSchemaError("operation_id must be a lowercase UUIDv4") from error
        if parsed_id.version != 4 or str(parsed_id) != operation_id:
            raise ForgeSchemaError("operation_id must be a lowercase UUIDv4")
        if not isinstance(operation, str) or _V1_OPERATION_PATTERN.fullmatch(operation) is None:
            raise ForgeSchemaError("operation must match [a-z][a-z0-9_]*")

    def _admit_v1_operation(self, operation_id: str, operation: str) -> str:
        with self._manifest_lock():
            claims_dir = self.resolve_relative(Path("reports") / "claims")
            claim_path = claims_dir / f"{operation_id}.json"
            event_path = self.resolve_relative(Path("reports") / "events" / f"{operation_id}-{operation}.json")
            # Check durable identity markers before any manifest reconciliation.
            # A stale claim or an event left by a crash is never silently
            # reclaimed, even if the manifest itself also needs repair.
            if claim_path.exists() or event_path.exists():
                raise OperationConflictError("operation_id is already admitted")
            manifest_path = self._ensure_manifest_unlocked()
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise ForgePersistenceError("workspace manifest is not readable") from error
            if not isinstance(manifest, dict) or not isinstance(manifest.get("events"), list):
                raise ForgePersistenceError("workspace manifest has invalid events")
            if any(isinstance(event, dict) and event.get("id") == operation_id for event in manifest["events"]):
                raise OperationConflictError("operation_id already exists in workspace manifest")

            try:
                claims_dir.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                raise ForgePersistenceError("unable to create operation claims directory") from error
            owner_token = secrets.token_urlsafe(32)
            try:
                with claim_path.open("x", encoding="utf-8") as claim:
                    json.dump(
                        {"operation_id": operation_id, "operation": operation, "owner_token": owner_token},
                        claim,
                        sort_keys=True,
                    )
                    claim.flush()
                    os.fsync(claim.fileno())
                self._fsync_directory(claims_dir)
            except FileExistsError as error:
                raise OperationConflictError("operation_id is already admitted") from error
            except OSError as error:
                raise ForgePersistenceError("unable to persist operation admission") from error
            return owner_token

    def append_claimed_v1_operation_event(
        self,
        operation_id: str,
        operation: str,
        payload: Mapping[str, JSONValue],
        *,
        owner_token: str,
    ) -> Path:
        """Durably commit an admitted event and then remove its admission."""
        return self._append_v1_operation_event(operation_id, operation, payload, claim_token=owner_token)

    def _append_v1_operation_event(self, operation_id: str, operation: str, payload: Mapping[str, JSONValue], *, claim_token: str | None) -> Path:
        self._validate_v1_identity(operation_id, operation)
        normalized_payload = _validate_v1_payload(payload)

        with self._manifest_lock():
            try:
                manifest_path = self._ensure_manifest_unlocked()
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, ForgePersistenceError) as error:
                raise ForgePersistenceError("unable to read workspace manifest") from error
            if not isinstance(manifest, dict) or not isinstance(manifest.get("events"), list):
                raise ForgePersistenceError("workspace manifest has invalid events")
            if any(isinstance(event, dict) and event.get("id") == operation_id for event in manifest["events"]):
                raise OperationConflictError("operation_id already exists in workspace manifest")
            claim_path = self.resolve_relative(Path("reports") / "claims" / f"{operation_id}.json")
            if claim_token is None:
                if claim_path.exists():
                    raise OperationConflictError("operation_id is already admitted")
            else:
                try:
                    claim = json.loads(claim_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as error:
                    raise ForgePersistenceError("operation admission is not readable") from error
                if (
                    not isinstance(claim, dict)
                    or claim.get("operation_id") != operation_id
                    or claim.get("operation") != operation
                    or claim.get("owner_token") != claim_token
                ):
                    raise OperationConflictError("operation admission owner mismatch")

            events_dir = self.resolve_relative(Path("reports") / "events")
            try:
                events_dir.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                raise ForgePersistenceError("unable to create operation events directory") from error
            event_path = events_dir / f"{operation_id}-{operation}.json"
            if event_path.exists():
                raise OperationConflictError("operation_id already exists in workspace events")
            try:
                self._write_json_atomic(
                    event_path, {"id": operation_id, "operation": operation, "payload": normalized_payload}
                )
            except OSError as error:
                raise ForgePersistenceError("unable to persist operation event") from error
            event_rel = canonical_relative_path(event_path.relative_to(self.root.resolve()).as_posix())
            manifest["events"].append({"id": operation_id, "operation": operation, "path_rel": event_rel})
            try:
                self._write_json_atomic(manifest_path, manifest)
            except OSError as error:
                # Leave both the immutable event and the admission tombstone:
                # the event can be reconciled, while the ID cannot be replayed.
                raise ForgePersistenceError("unable to persist workspace manifest") from error
            if claim_token is not None:
                try:
                    claim_path.unlink()
                    self._fsync_directory(claim_path.parent)
                except OSError as error:
                    raise ForgePersistenceError("unable to finalize operation admission") from error
        return event_path

    def record_metadata(self, payload: dict[str, Any]) -> Path:
        return self.write_json(self.meta_path.relative_to(self.root), payload)
