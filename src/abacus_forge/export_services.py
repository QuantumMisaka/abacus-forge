"""Typed, facts-only service for exporting one recorded Forge outcome."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol, runtime_checkable

from abacus_forge.contracts import (
    ArtifactRecord,
    ForgeErrorEnvelope,
    ForgeResultEnvelope,
    OperationOutcome,
    OperationStatus,
)
from abacus_forge.errors import (
    ForgePathError,
    ForgePersistenceError,
    ForgeRequestError,
    OperationConflictError,
)
from abacus_forge.export_contracts import ExportDocument, ExportRequest
from abacus_forge.export_io import (
    _destination,
    _paths_overlap,
    resolve_export_source,
    write_export_document,
)
from abacus_forge.service_support import ServiceContext
from abacus_forge.workspace import Workspace


ServiceResult = OperationOutcome | ForgeErrorEnvelope


@runtime_checkable
class ExportServiceProtocol(Protocol):
    """Narrow protocol for one explicit typed export operation."""

    def export(self, request: ExportRequest) -> ServiceResult: ...


class ExportService:
    """Serialize one explicitly referenced historical operation outcome."""

    def __init__(self, context: ServiceContext) -> None:
        self._context = context

    def export(self, request: ExportRequest) -> ServiceResult:
        if not isinstance(request, ExportRequest):
            return self._context.error("request.invalid", "expected ExportRequest", request)
        try:
            workspace = self._context.workspace(request.workspace_rel)
            # Path and reserved-audit validation is side-effect free and must
            # happen before admission.  Destination existence is also checked
            # here for the common case; the writer repeats it after admission
            # to close the race with a concurrently-created target.
            _, destination = _destination(workspace, request.destination_path_rel)
            if _operation_marker_exists(workspace, request.operation_id):
                raise OperationConflictError("operation_id is already admitted")
            try:
                if destination.exists():
                    raise ForgeRequestError("destination already exists")
            except ForgeRequestError:
                raise
            except OSError as error:
                raise ForgePersistenceError("unable to inspect export destination") from error

            with workspace.operation_guard(request.operation_id, request.operation) as owner_token:
                resolved = resolve_export_source(workspace, request.source_artifact_refs)
                document = ExportDocument(
                    schema_version="forge.export/v1",
                    source_operation_id=resolved.operation_id,
                    source_artifact_refs=resolved.artifact_refs,
                    source_outcome=resolved.outcome.to_dict(),
                )
                # A destination which aliases any historical source artifact
                # is a request conflict, not a path/schema error.  The claim
                # remains as an admission tombstone under existing rules.
                if any(
                    _paths_overlap(artifact.path_rel, request.destination_path_rel)
                    for artifact in resolved.outcome.envelope.artifacts
                ):
                    raise ForgeRequestError("destination overlaps a source artifact")
                written = write_export_document(
                    workspace,
                    request.destination_path_rel,
                    document,
                    request.pretty,
                )
                artifact_id = _export_artifact_id(
                    request.destination_path_rel,
                    resolved.outcome,
                )
                artifact = ArtifactRecord(
                    id=artifact_id,
                    path_rel=written.path_rel,
                    role="output",
                    stage="export",
                    media_type="application/json",
                    sha256=written.sha256,
                    size_bytes=written.size_bytes,
                )
                envelope = ForgeResultEnvelope(
                    operation="export",
                    workspace_rel=request.workspace_rel,
                    status=OperationStatus(
                        execution="completed",
                        scientific="unassessed",
                        collection="complete",
                    ),
                    artifacts=(artifact,),
                    diagnostics={
                        "source_artifact_refs": [
                            ref.to_dict() for ref in resolved.artifact_refs
                        ],
                        "source_operation_id": resolved.operation_id,
                        "destination_path_rel": written.path_rel,
                        "format": request.format,
                        "overwrite_policy": request.overwrite_policy,
                    },
                )
                return self._context.persist(
                    workspace,
                    request,
                    envelope,
                    owner_token=owner_token,
                )
        except Exception as error:
            return self._context.error_from_exception(error, request)


def _export_artifact_id(destination_path_rel: str, source_outcome: OperationOutcome) -> str:
    """Choose a deterministic output id which does not shadow source ids."""

    used = {artifact.id for artifact in source_outcome.envelope.artifacts}
    candidate = "export-document"
    if candidate not in used:
        return candidate
    suffix = hashlib.sha256(destination_path_rel.encode("utf-8")).hexdigest()[:12]
    candidate = f"export-document-{suffix}"
    attempt = 0
    while candidate in used:
        attempt += 1
        candidate = f"export-document-{suffix}-{attempt}"
    return candidate


def _operation_marker_exists(workspace: Workspace, operation_id: str) -> bool:
    """Detect the durable typed-operation markers before destination checks.

    This preserves the stable ``operation.conflict`` class when a replay uses
    the same operation ID as an already committed export, even if its old
    destination also exists.  It is only a read-only preflight; the operation
    guard remains the authority for admission and race handling.
    """

    root = workspace.root
    return any(
        path.exists()
        for path in (
            root / "reports" / "claims" / f"{operation_id}.json",
            root / "reports" / "events" / f"{operation_id}-export.json",
        )
    )


class ExportServiceSet:
    """Typed export services sharing one :class:`ServiceContext`."""

    def __init__(
        self,
        *,
        workspace_root: str | Path = ".",
        context: ServiceContext | None = None,
    ) -> None:
        shared_context = context if context is not None else ServiceContext(workspace_root=workspace_root)
        self._context = shared_context
        self.export: ExportServiceProtocol = ExportService(shared_context)

    @classmethod
    def default(cls, workspace_root: str | Path = ".") -> "ExportServiceSet":
        return cls(workspace_root=workspace_root)


__all__ = ["ExportService", "ExportServiceProtocol", "ExportServiceSet"]
