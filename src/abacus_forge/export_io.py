"""I/O primitives for the explicit, typed export operation.

The resolver deliberately works from Forge's immutable operation history.  It
does not inspect the current contents of an artifact referenced by that
history: an export is a serialization of a recorded outcome, not a re-run of
the operation that produced it.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping

from .contracts import (
    ArtifactRecord,
    ArtifactRef,
    OperationOutcome,
    JSONValue,
    canonical_relative_path,
)
from .errors import ForgePathError, ForgePersistenceError, ForgePreconditionError, ForgeRequestError
from .export_contracts import ExportDocument
from .workspace import Workspace


@dataclass(frozen=True, slots=True)
class ResolvedExportSource:
    """The historical source outcome selected by an export request."""

    operation_id: str
    artifact_refs: tuple[ArtifactRef, ...]
    outcome: OperationOutcome
    event_path_rel: str


@dataclass(frozen=True, slots=True)
class WrittenExportDocument:
    """The durable destination and its content identity."""

    path: Path
    path_rel: str
    sha256: str
    size_bytes: int


def _validate_refs(refs: object) -> tuple[ArtifactRef, ...]:
    if isinstance(refs, (str, bytes, Mapping)):
        raise ForgePreconditionError("source artifact references must be a non-empty sequence")
    try:
        values = tuple(refs)  # type: ignore[arg-type]
    except TypeError as error:
        raise ForgePreconditionError("source artifact references must be a non-empty sequence") from error
    if not values or not all(isinstance(ref, ArtifactRef) for ref in values):
        raise ForgePreconditionError("source artifact references must contain ArtifactRef values")
    identities = {(ref.operation_id, ref.artifact_id) for ref in values}
    if len(identities) != len(values):
        raise ForgePreconditionError("source artifact references must not contain duplicates")
    operation_ids = {ref.operation_id for ref in values}
    if len(operation_ids) != 1:
        raise ForgePreconditionError("source artifact references must identify one operation")
    return values


def _path_in_workspace(workspace: Workspace, value: object, *, what: str) -> tuple[str, Path]:
    if not isinstance(value, str):
        raise ForgePathError(f"{what} must be a canonical workspace-relative path")
    try:
        canonical = canonical_relative_path(value)
    except ValueError as error:
        raise ForgePathError(f"{what} must be a canonical workspace-relative path") from error
    try:
        path = workspace.resolve_relative(canonical)
    except ForgePathError:
        raise
    except (OSError, RuntimeError) as error:
        raise ForgePathError(f"{what} must remain contained by the workspace") from error
    return canonical, path


def _read_json(path: Path, *, what: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ForgePreconditionError(f"{what} is missing or invalid") from error


def resolve_export_source(workspace: Workspace, refs: object) -> ResolvedExportSource:
    """Resolve refs against the exact immutable event named by the manifest.

    Historical artifact paths are validated for spelling and workspace
    containment only.  In particular, this function never reads, stats, or
    hashes the current artifact files.
    """

    values = _validate_refs(refs)
    operation_id = values[0].operation_id

    try:
        manifest_path = workspace.ensure_manifest()
    except ForgePersistenceError as error:
        raise ForgePreconditionError("workspace manifest is missing or invalid") from error
    manifest_object = _read_json(manifest_path, what="workspace manifest")
    if not isinstance(manifest_object, dict) or not isinstance(manifest_object.get("events"), list):
        raise ForgePreconditionError("workspace manifest is missing or invalid")

    matching = [
        entry
        for entry in manifest_object["events"]
        if isinstance(entry, dict) and entry.get("id") == operation_id
    ]
    if len(matching) != 1:
        raise ForgePreconditionError("source operation is not uniquely indexed in workspace history")
    entry = matching[0]
    if entry.get("operation") != "collect" and not isinstance(entry.get("operation"), str):
        raise ForgePreconditionError("source event has invalid operation metadata")
    event_path_rel, event_path = _path_in_workspace(workspace, entry.get("path_rel"), what="source event path")
    event_object = _read_json(event_path, what="source event")
    if not isinstance(event_object, dict):
        raise ForgePreconditionError("source event is missing or invalid")
    if event_object.get("id") != operation_id or not isinstance(event_object.get("operation"), str):
        raise ForgePreconditionError("source event identity is inconsistent")
    if event_object.get("operation") != entry.get("operation"):
        raise ForgePreconditionError("source event operation is inconsistent")
    payload = event_object.get("payload")
    if not isinstance(payload, dict):
        raise ForgePreconditionError("source event payload is missing or invalid")
    try:
        outcome = OperationOutcome.from_dict(payload)
    except (TypeError, ValueError, KeyError) as error:
        raise ForgePreconditionError("source event payload is not a valid operation outcome") from error
    if outcome.operation_id != operation_id:
        raise ForgePreconditionError("source outcome identity is inconsistent")

    records = {artifact.id: artifact for artifact in outcome.envelope.artifacts}
    if any(ref.artifact_id not in records for ref in values):
        raise ForgePreconditionError("source artifact reference is absent from the recorded outcome")
    for artifact in records.values():
        _path_in_workspace(workspace, artifact.path_rel, what="recorded artifact path")

    return ResolvedExportSource(
        operation_id=operation_id,
        artifact_refs=values,
        outcome=outcome,
        event_path_rel=event_path_rel,
    )


def _reserved_destination(path_rel: str, document: ExportDocument) -> bool:
    components = PurePosixPath(path_rel).parts
    # reports/ contains the manifest, immutable events, claims and locks.  It
    # is an audit namespace, not an export destination namespace.
    if components and components[0] == "reports":
        return True
    if PurePosixPath(path_rel).name in {"forge-unit.json", "forge-result.json"}:
        return True
    # ``ExportDocument`` retains its validated outcome immutably (using
    # mapping proxies).  Round-trip through its public serializer before
    # reconstructing the outcome so this check remains representation-safe.
    source_payload = document.to_dict()["source_outcome"]
    source_paths = {
        artifact.path_rel
        for artifact in OperationOutcome.from_dict(source_payload).envelope.artifacts  # type: ignore[arg-type]
    }
    return path_rel in source_paths


def write_export_document(
    workspace: Workspace,
    destination_path_rel: str,
    document: ExportDocument,
    pretty: bool,
) -> WrittenExportDocument:
    """Write one typed export document with atomic no-replace publication."""

    if not isinstance(document, ExportDocument):
        raise ForgeRequestError("export document must be an ExportDocument")
    if not isinstance(pretty, bool):
        raise ForgeRequestError("pretty must be a boolean")
    path_rel, target = _path_in_workspace(workspace, destination_path_rel, what="export destination")
    if path_rel == "." or _reserved_destination(path_rel, document):
        raise ForgePathError("export destination is reserved or overlaps a source artifact")

    try:
        if target.exists():
            raise ForgeRequestError("export destination already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        # Re-check after creating the parent: a concurrent replacement of a
        # parent directory must not cause a write through a symlink escape.
        _, checked_target = _path_in_workspace(workspace, path_rel, what="export destination")
        if checked_target != target:
            raise ForgePathError("export destination changed during preparation")
        serialized = json.dumps(
            document.to_dict(),
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
        ).encode("utf-8")
    except ForgeRequestError:
        raise
    except (OSError, TypeError, ValueError) as error:
        raise ForgePersistenceError("unable to prepare export document") from error

    temporary_path: Path | None = None
    published = False
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(serialized)
            temporary.flush()
            os.fsync(temporary.fileno())
        try:
            os.link(temporary_path, target)
            published = True
        except FileExistsError as error:
            raise ForgeRequestError("export destination already exists") from error
        except OSError as error:
            raise ForgePersistenceError("unable to publish export document") from error
        Workspace._fsync_directory(target.parent)
        try:
            size_bytes = target.stat().st_size
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
        except OSError as error:
            raise ForgePersistenceError("unable to inspect published export document") from error
        return WrittenExportDocument(path=target, path_rel=path_rel, sha256=digest, size_bytes=size_bytes)
    except ForgeRequestError:
        raise
    except ForgePersistenceError:
        if published:
            try:
                target.unlink()
            except OSError:
                pass
        raise
    except OSError as error:
        if published:
            try:
                target.unlink()
            except OSError:
                pass
        raise ForgePersistenceError("unable to write export document") from error
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                # The temporary link is an implementation detail; a failed
                # cleanup is reported only if no more specific failure exists.
                pass


__all__ = [
    "ResolvedExportSource",
    "WrittenExportDocument",
    "resolve_export_source",
    "write_export_document",
]
