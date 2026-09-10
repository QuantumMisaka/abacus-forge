"""Read-only source resolution and no-replace JSON publication for typed export.

This module deliberately keeps the export I/O boundary small.  Source
artifacts are historical records in an immutable operation event: resolving a
source validates the recorded path, but never re-reads or re-stat's the file
currently at that path.  The destination writer is separate and publishes a
new document without replacing a path which appeared concurrently.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping

from abacus_forge.contracts import (
    ArtifactRecord,
    ArtifactRef,
    OperationOutcome,
    canonical_relative_path,
)
from abacus_forge.errors import (
    ForgePathError,
    ForgePersistenceError,
    ForgePreconditionError,
    ForgeRequestError,
)
from abacus_forge.export_contracts import ExportDocument
from abacus_forge.workspace import Workspace


@dataclass(frozen=True, slots=True)
class ResolvedExportSource:
    """The immutable source facts selected by one export request."""

    operation_id: str
    artifact_refs: tuple[ArtifactRef, ...]
    outcome: OperationOutcome
    event_path_rel: str
    artifacts: tuple[ArtifactRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class WrittenExportDocument:
    """Facts about the newly published export document."""

    path: Path
    path_rel: str
    sha256: str
    size_bytes: int


def _normalize_refs(refs: object) -> tuple[ArtifactRef, ...]:
    if isinstance(refs, (str, bytes, Mapping)):
        raise ForgePreconditionError("source artifact references must be an array")
    try:
        values = tuple(refs)  # type: ignore[arg-type]
    except TypeError as error:
        raise ForgePreconditionError("source artifact references must be an array") from error
    if not values or not all(isinstance(ref, ArtifactRef) for ref in values):
        raise ForgePreconditionError("source artifact references are invalid")
    identities = {(ref.operation_id, ref.artifact_id) for ref in values}
    if len(identities) != len(values):
        raise ForgePreconditionError("source artifact references must not contain duplicates")
    operation_ids = {ref.operation_id for ref in values}
    if len(operation_ids) != 1:
        raise ForgePreconditionError("source artifact references must identify one operation")
    return values


def _historical_path_is_contained(workspace: Workspace, path_rel: object) -> str:
    """Validate a recorded artifact path without touching its current target."""

    if not isinstance(path_rel, str):
        raise ForgePreconditionError("source artifact path is invalid")
    try:
        canonical = canonical_relative_path(path_rel)
    except ValueError as error:
        raise ForgePreconditionError("source artifact path is not canonical") from error
    if canonical == ".":
        raise ForgePreconditionError("source artifact path must not be the workspace root")

    # ``canonical_relative_path`` rules out absolute paths and ``..``.  Keep
    # this containment check lexical: resolving the current source path would
    # turn a historical fact lookup into an implicit file read/symlink check.
    candidate = workspace.root / Path(canonical)
    try:
        candidate.relative_to(workspace.root)
    except ValueError as error:
        raise ForgePreconditionError("source artifact path escapes workspace") from error
    return canonical


def _manifest(workspace: Workspace) -> Mapping[str, object]:
    try:
        manifest_path = workspace.ensure_manifest()
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (ForgePersistenceError, OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ForgePreconditionError("source workspace manifest is unavailable") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise ForgePreconditionError("source workspace manifest is malformed")
    return payload


def resolve_export_source(
    workspace: Workspace,
    refs: object,
) -> ResolvedExportSource:
    """Resolve exactly one source outcome from the workspace event index."""

    normalized_refs = _normalize_refs(refs)
    source_operation_id = normalized_refs[0].operation_id
    manifest = _manifest(workspace)
    matches = [
        item
        for item in manifest["events"]
        if isinstance(item, dict) and item.get("id") == source_operation_id
    ]
    if len(matches) != 1:
        raise ForgePreconditionError("source operation event is missing or ambiguous")
    entry = matches[0]
    path_rel = entry.get("path_rel")
    operation = entry.get("operation")
    if not isinstance(operation, str) or not operation:
        raise ForgePreconditionError("source operation event is malformed")
    if not isinstance(path_rel, str):
        raise ForgePreconditionError("source operation event path is malformed")
    try:
        canonical_event_path = canonical_relative_path(path_rel)
    except ValueError as error:
        raise ForgePathError("source operation event path must be canonical") from error
    if canonical_event_path == ".":
        raise ForgePathError("source operation event path must name a file")
    try:
        event_path = workspace.resolve_relative(canonical_event_path)
    except ForgePathError:
        raise
    try:
        event_payload = json.loads(event_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ForgePreconditionError("source operation event is unavailable") from error
    if not isinstance(event_payload, dict):
        raise ForgePreconditionError("source operation event is malformed")
    if (
        event_payload.get("id") != source_operation_id
        or event_payload.get("operation") != operation
        or not isinstance(event_payload.get("payload"), dict)
    ):
        raise ForgePreconditionError("source operation event identity is inconsistent")
    try:
        outcome = OperationOutcome.from_dict(event_payload["payload"])
    except (TypeError, ValueError, KeyError, AttributeError) as error:
        raise ForgePreconditionError("source operation outcome is malformed") from error
    if outcome.operation_id != source_operation_id or outcome.envelope.operation != operation:
        raise ForgePreconditionError("source operation outcome identity is inconsistent")

    artifacts_by_id: dict[str, ArtifactRecord] = {}
    for artifact in outcome.envelope.artifacts:
        _historical_path_is_contained(workspace, artifact.path_rel)
        if artifact.id in artifacts_by_id:
            raise ForgePreconditionError("source operation contains duplicate artifact ids")
        artifacts_by_id[artifact.id] = artifact
    selected: list[ArtifactRecord] = []
    for ref in normalized_refs:
        artifact = artifacts_by_id.get(ref.artifact_id)
        if artifact is None:
            raise ForgePreconditionError("source artifact reference is not in the outcome")
        selected.append(artifact)
    return ResolvedExportSource(
        operation_id=source_operation_id,
        artifact_refs=normalized_refs,
        outcome=outcome,
        event_path_rel=canonical_event_path,
        artifacts=tuple(selected),
    )


_RESERVED_FILES = frozenset(
    {
        "reports/forge-workspace.json",
        "reports/.forge-workspace.lock",
        "reports/.forge-operation.lock",
        "forge-unit.json",
        "forge-result.json",
    }
)
_RESERVED_DIRECTORIES = ("reports/events", "reports/claims")


def _destination(workspace: Workspace, destination_path_rel: object) -> tuple[str, Path]:
    if not isinstance(destination_path_rel, str):
        raise ForgePathError("destination path must be canonical")
    try:
        canonical = canonical_relative_path(destination_path_rel)
    except ValueError as error:
        raise ForgePathError("destination path must be canonical") from error
    if canonical == ".":
        raise ForgePathError("destination path must name a file")
    if canonical in _RESERVED_FILES or any(
        canonical == directory or canonical.startswith(directory + "/")
        for directory in _RESERVED_DIRECTORIES
    ):
        raise ForgePathError("destination path is reserved for Forge audit")
    try:
        path = workspace.resolve_relative(canonical)
    except ForgePathError:
        raise
    return canonical, path


def _overlaps_source_artifact(document: ExportDocument, destination_path_rel: str) -> bool:
    """Return whether the destination is one of the recorded source paths."""

    try:
        source_payload = document.to_dict()["source_outcome"]
        outcome = OperationOutcome.from_dict(source_payload)  # type: ignore[arg-type]
    except (KeyError, TypeError, ValueError) as error:
        # ExportDocument validates this invariant at construction time.  Keep
        # the writer defensive if a future implementation changes that type.
        raise ForgeRequestError("export document has an invalid source outcome") from error
    return any(
        artifact.path_rel == destination_path_rel
        for artifact in outcome.envelope.artifacts
    )


def _directory_flags() -> int:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    return flags


def _open_destination_directory(workspace: Workspace, path_rel: str) -> int:
    """Open the destination parent as a no-follow directory FD.

    Walking each component relative to the previously opened directory keeps
    the later temporary-file creation and hard-link publication anchored to
    the workspace even if a pathname is swapped concurrently.
    """

    try:
        workspace.root.mkdir(parents=True, exist_ok=True)
        current_fd = os.open(workspace.root, _directory_flags())
    except OSError as error:
        raise ForgePersistenceError("unable to open export workspace directory") from error

    parent = PurePosixPath(path_rel).parent
    components = () if str(parent) == "." else parent.parts
    try:
        for component in components:
            try:
                os.mkdir(component, dir_fd=current_fd)
            except FileExistsError:
                pass
            try:
                next_fd = os.open(component, _directory_flags(), dir_fd=current_fd)
            except OSError as error:
                raise ForgePathError("export destination parent is not a contained directory") from error
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except Exception:
        try:
            os.close(current_fd)
        except OSError:
            pass
        raise


def _new_temporary_file(directory_fd: int, target_name: str) -> tuple[str, int]:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    for _ in range(100):
        name = f".{target_name}.{uuid.uuid4().hex}.tmp"
        try:
            fd = os.open(name, flags, 0o600, dir_fd=directory_fd)
            return name, fd
        except FileExistsError:
            continue
        except OSError as error:
            raise ForgePersistenceError("unable to create export temporary file") from error
    raise ForgePersistenceError("unable to allocate export temporary file")


def _unlink_if_owned(directory_fd: int, name: str, published_stat: os.stat_result | None) -> None:
    """Best-effort rollback which never intentionally removes a raced inode."""

    if published_stat is None:
        return
    try:
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != (published_stat.st_dev, published_stat.st_ino):
            return
        os.unlink(name, dir_fd=directory_fd)
    except (FileNotFoundError, OSError):
        return


def write_export_document(
    workspace: Workspace,
    destination_path_rel: object,
    document: object,
    pretty: object,
) -> WrittenExportDocument:
    """Atomically publish one contained export document without replacement."""

    if not isinstance(document, ExportDocument):
        raise ForgeRequestError("document must be an ExportDocument")
    if not isinstance(pretty, bool):
        raise ForgeRequestError("pretty must be a boolean")
    path_rel, target = _destination(workspace, destination_path_rel)
    if _overlaps_source_artifact(document, path_rel):
        raise ForgePathError("destination overlaps a source artifact")
    try:
        if target.exists():
            raise ForgeRequestError("destination already exists")
    except ForgeRequestError:
        raise
    except OSError as error:
        raise ForgePersistenceError("unable to inspect export destination") from error

    try:
        payload = json.dumps(
            document.to_dict(),
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ForgeRequestError("export document is not JSON serializable") from error

    directory_fd: int | None = None
    temporary_name: str | None = None
    temporary_fd: int | None = None
    published = False
    published_stat: os.stat_result | None = None
    target_name = PurePosixPath(path_rel).name
    try:
        directory_fd = _open_destination_directory(workspace, path_rel)
        # A no-follow directory walk above is the final containment check.  A
        # concurrent pathname replacement cannot redirect the FD-relative
        # operations below.
        temporary_name, temporary_fd = _new_temporary_file(directory_fd, target_name)
        with os.fdopen(temporary_fd, "wb") as temporary:
            temporary_fd = None
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_stat = os.fstat(temporary.fileno())
        if temporary_stat.st_size != len(payload):
            raise ForgePersistenceError("export temporary file size changed during write")
        try:
            os.link(
                temporary_name,
                target_name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileExistsError as error:
            raise ForgeRequestError("destination already exists") from error
        except OSError as error:
            raise ForgePersistenceError("unable to publish export document") from error
        published = True
        # A hard link shares the temporary inode.  Keep that identity for
        # rollback, so an intervening unlink/recreate by another process is
        # never mistaken for our output.
        published_stat = temporary_stat
        try:
            linked_stat = os.stat(target_name, dir_fd=directory_fd, follow_symlinks=False)
        except OSError as error:
            raise ForgePersistenceError("unable to inspect published export document") from error
        if (linked_stat.st_dev, linked_stat.st_ino) != (temporary_stat.st_dev, temporary_stat.st_ino):
            raise ForgePersistenceError("published export document changed during publication")
        try:
            os.fsync(directory_fd)
        except OSError as error:
            raise ForgePersistenceError("unable to persist export directory entry") from error
        try:
            os.unlink(temporary_name, dir_fd=directory_fd)
        except OSError as error:
            raise ForgePersistenceError("unable to finalize export temporary file") from error
        return WrittenExportDocument(
            path=target,
            path_rel=path_rel,
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=temporary_stat.st_size,
        )
    except ForgeRequestError:
        raise
    except ForgePersistenceError:
        if published:
            _unlink_if_owned(directory_fd, target_name, published_stat)  # type: ignore[arg-type]
        raise
    except OSError as error:
        if published:
            _unlink_if_owned(directory_fd, target_name, published_stat)  # type: ignore[arg-type]
        raise ForgePersistenceError("unable to write export document") from error
    finally:
        if temporary_fd is not None:
            try:
                os.close(temporary_fd)
            except OSError:
                pass
        if directory_fd is not None:
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name, dir_fd=directory_fd)
                except FileNotFoundError:
                    pass
                except OSError:
                    pass
            try:
                os.close(directory_fd)
            except OSError:
                pass


__all__ = [
    "ResolvedExportSource",
    "WrittenExportDocument",
    "resolve_export_source",
    "write_export_document",
]
