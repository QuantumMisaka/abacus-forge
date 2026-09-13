"""Capability-independent helpers for typed operation boundaries."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TypeVar

from abacus_forge.contracts import (
    ArtifactRecord, ArtifactRef, ForgeErrorEnvelope, ForgeResultEnvelope,
    Observation, OperationOutcome,
)
from abacus_forge.errors import (
    ForgeInternalError, ForgePathError, ForgePersistenceError,
    ForgePreconditionError, ForgeRequestError, ForgeSchemaError,
    normalize_error_message, OperationConflictError,
)
from abacus_forge.workspace import Workspace

RequestT = TypeVar("RequestT")


class ServiceContext:
    """Capability-independent path, error and durable outcome support."""

    def __init__(
        self,
        *,
        workspace_root: str | Path = ".",
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()

    def workspace(self, workspace_rel: str) -> Workspace:
        candidate = (self.workspace_root / workspace_rel).resolve()
        try:
            candidate.relative_to(self.workspace_root)
        except ValueError as error:
            raise ForgePathError("workspace_rel must remain under workspace_root") from error
        return Workspace(candidate)

    @staticmethod
    def workspace_path(workspace: Workspace, path_rel: str, field_name: str) -> Path:
        candidate = (workspace.root / path_rel).resolve()
        try:
            candidate.relative_to(workspace.root)
        except ValueError as error:
            raise ForgePathError(f"{field_name} must remain under workspace_rel") from error
        return candidate

    @staticmethod
    def require_file(candidate: Path, path_rel: str, field_name: str) -> Path:
        if not candidate.is_file():
            raise ForgePreconditionError(f"{field_name} file not found: {path_rel}")
        return candidate

    def persist(
        self,
        workspace: Workspace,
        request: RequestT,
        envelope: ForgeResultEnvelope,
        *,
        owner_token: str,
        extra_observations: tuple[Observation, ...] = (),
    ) -> OperationOutcome:
        # Artifact references are operation-scoped and are injected once, at
        # the boundary where the serializable outcome is assembled.
        envelope = _with_artifact_refs(envelope, request.operation_id)  # type: ignore[attr-defined]
        outcome = OperationOutcome(
            operation_id=request.operation_id,  # type: ignore[attr-defined]
            envelope=envelope,
            observations=tuple(
                {
                    observation.name: observation
                    for observation in (*_observations(envelope), *extra_observations)
                }.values()
            ),
        )
        workspace.append_claimed_v1_operation_event(
            request.operation_id, envelope.operation, outcome.to_dict(), owner_token=owner_token  # type: ignore[attr-defined]
        )
        return outcome

    @staticmethod
    def error(error_class: str, message: str, request: object) -> ForgeErrorEnvelope:
        operation_id = getattr(request, "operation_id", None)
        workspace_rel = getattr(request, "workspace_rel", None)
        if not isinstance(operation_id, str):
            operation_id = None
        if not isinstance(workspace_rel, str):
            workspace_rel = None
        return ForgeErrorEnvelope(
            error_class=error_class,
            message=normalize_error_message(error_class, message),
            affected_fields=("request",),
            operation_id=operation_id,
            workspace_rel=workspace_rel,
        )

    def error_from_exception(self, error: Exception, request: object) -> ForgeErrorEnvelope:
        if isinstance(error, OperationConflictError):
            error_class = "operation.conflict"
        elif isinstance(error, ForgeSchemaError):
            error_class = "request.schema"
        elif isinstance(error, ForgePathError):
            error_class = "request.path"
        elif isinstance(error, ForgePersistenceError):
            error_class = "persistence.failure"
        elif isinstance(error, ForgePreconditionError):
            error_class = "precondition.missing"
        elif isinstance(error, ForgeInternalError):
            error_class = "internal.failure"
        elif isinstance(error, ForgeRequestError):
            error_class = "request.invalid"
        else:
            error_class = "internal.failure"
        affected = {
            "operation.conflict": ("operation_id",),
            "request.path": ("workspace_rel",),
            "persistence.failure": ("workspace_rel",),
            "precondition.missing": ("request",),
        }.get(error_class, ("request",))
        configured_fields = getattr(error, "affected_fields", None)
        if isinstance(configured_fields, tuple) and all(isinstance(item, str) for item in configured_fields):
            affected = configured_fields
        result = self.error(error_class, str(error), request)
        return ForgeErrorEnvelope(
            error_class=result.error_class,
            message=result.message,
            affected_fields=affected,
            operation_id=result.operation_id,
            workspace_rel=result.workspace_rel,
        )


def _with_workspace(envelope: ForgeResultEnvelope, workspace_rel: str) -> ForgeResultEnvelope:
    diagnostics = dict(envelope.to_dict()["diagnostics"])  # type: ignore[arg-type]
    return ForgeResultEnvelope(
        operation=envelope.operation,
        workspace_rel=workspace_rel,
        status=envelope.status,
        artifacts=envelope.artifacts,
        metrics=envelope.metrics,
        checks=envelope.checks,
        warnings=envelope.warnings,
        diagnostics=diagnostics,
    )


def _observations(envelope: ForgeResultEnvelope) -> tuple[Observation, ...]:
    """Expose engine/parser facts without deriving scientific conclusions."""
    observations: list[Observation] = []
    seen: set[str] = set()

    def add(observation: Observation) -> None:
        if observation.name not in seen:
            seen.add(observation.name)
            observations.append(observation)

    for metric in envelope.metrics:
        source = "runtime" if metric.kind == "runtime" or metric.name in {"returncode", "omp_threads"} else "parser"
        add(Observation(name=metric.name, value=metric.value, source=source))
    for check in envelope.checks:
        add(Observation(name=check.name, value=check.status, source="parser"))
    diagnostics = envelope.to_dict()["diagnostics"]
    if isinstance(diagnostics, dict):
        for name in ("failure_class", "dry_run", "normal_end", "converged", "termination"):
            if name in diagnostics:
                source = "log" if name == "normal_end" else (
                    "runtime" if name in {"failure_class", "dry_run", "termination"} else "parser"
                )
                add(Observation(name=name, value=diagnostics[name], source=source))
    return tuple(observations)


def _manifest_artifact(workspace: Workspace) -> tuple[ArtifactRecord, ...]:
    path = workspace.root / "forge-unit.json"
    if not path.is_file():
        return ()
    return (
        ArtifactRecord(
            id="provenance_manifest",
            path_rel="forge-unit.json",
            role="provenance_manifest",
            stage="prepare",
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            size_bytes=path.stat().st_size,
        ),
    )


def _prepare_artifacts(workspace: Workspace) -> tuple[ArtifactRecord, ...]:
    records = list(_manifest_artifact(workspace))
    used_ids = {record.id for record in records}
    if workspace.inputs_dir.is_dir():
        files = _contained_files(workspace, workspace.inputs_dir)
        base_ids = [
            f"input-{path.relative_to(workspace.inputs_dir).as_posix().replace('/', '-').lower()}"
            for path, _ in files
        ]
        base_counts = {base_id: base_ids.count(base_id) for base_id in set(base_ids)}
        for (path, resolved), base_id in zip(files, base_ids, strict=True):
            relative = path.relative_to(workspace.root.resolve()).as_posix()
            artifact_id = base_id
            if base_counts[base_id] > 1:
                digest = hashlib.sha256(relative.encode("utf-8")).hexdigest()
                suffix_length = 12
                attempt = 0
                while True:
                    suffix = digest[:suffix_length]
                    if attempt:
                        suffix = f"{suffix}-{attempt}"
                    artifact_id = f"{base_id}-{suffix}"
                    if artifact_id not in used_ids:
                        break
                    attempt += 1
            elif artifact_id in used_ids:
                digest = hashlib.sha256(relative.encode("utf-8")).hexdigest()
                artifact_id = f"{base_id}-{digest[:12]}"
                attempt = 0
                while artifact_id in used_ids:
                    attempt += 1
                    artifact_id = f"{base_id}-{digest[:12]}-{attempt}"
            records.append(ArtifactRecord(
                id=artifact_id,
                path_rel=relative, role="input", stage="prepare",
                sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(), size_bytes=resolved.stat().st_size,
            ))
            used_ids.add(artifact_id)
    return tuple(records)


def _input_snapshot(workspace: Workspace) -> dict[str, object]:
    snapshot: dict[str, object] = {}
    if workspace.inputs_dir.is_dir():
        for path, resolved in _contained_files(workspace, workspace.inputs_dir):
            rel = path.relative_to(workspace.inputs_dir).as_posix()
            snapshot[rel] = {
                "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
                "size_bytes": resolved.stat().st_size,
            }
    return snapshot


def _contained_files(workspace: Workspace, directory: Path) -> tuple[tuple[Path, Path], ...]:
    """Return files whose resolved targets remain inside the workspace."""
    root = workspace.root.resolve()
    contained: list[tuple[Path, Path]] = []
    for path in sorted(directory.rglob("*")):
        try:
            resolved = path.resolve()
            resolved.relative_to(root)
        except (OSError, RuntimeError, ValueError) as error:
            raise ForgePathError(f"artifact path escapes workspace: {path}") from error
        if resolved.is_file():
            contained.append((path, resolved))
    return tuple(contained)


def _with_artifact_refs(envelope: ForgeResultEnvelope, operation_id: str) -> ForgeResultEnvelope:
    diagnostics = dict(envelope.to_dict()["diagnostics"])  # type: ignore[arg-type]
    diagnostics["artifact_refs"] = [ArtifactRef(operation_id, artifact.id).to_dict() for artifact in envelope.artifacts]
    return ForgeResultEnvelope(
        operation=envelope.operation, workspace_rel=envelope.workspace_rel, status=envelope.status,
        artifacts=envelope.artifacts, metrics=envelope.metrics, checks=envelope.checks,
        warnings=envelope.warnings, diagnostics=diagnostics,
    )
