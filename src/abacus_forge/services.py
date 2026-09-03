"""Typed, policy-aware SCF services over the legacy Forge primitives."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TypeVar

from abacus_forge.api import UnitModifySpec, UnitSpec, collect, modify_unit, prepare_unit, execute, suppress_legacy_events
from abacus_forge.contracts import (
    ArtifactRecord, ArtifactRef,
    CheckRecord,
    ForgeErrorEnvelope,
    ForgeResultEnvelope,
    OperationStatus,
    ScfCollectRequest,
    ScfExecuteRequest,
    ScfModifyRequest,
    ScfPrepareRequest,
)
from abacus_forge.policies import evaluate_abacus_scf_v1
from abacus_forge.result import CollectionResult
from abacus_forge.runner import LocalRunner
from abacus_forge.errors import (
    ForgeInternalError,
    ForgePolicyError,
    ForgePathError,
    ForgePersistenceError,
    ForgePreconditionError,
    ForgeSchemaError,
    OperationConflictError,
)
from abacus_forge.workspace import Workspace


RequestT = TypeVar("RequestT")


class ForgeServices:
    """Narrow typed SCF facade that preserves the existing primitive API.

    ``workspace_rel`` is resolved below ``workspace_root``.  The typed
    request deliberately has no broad UnitSpec payload yet; the first SCF
    vertical slice therefore uses the legacy SCF defaults and lets later
    contract work add operation-specific inputs.
    """

    def __init__(self, *, workspace_root: str | Path = ".", runner: LocalRunner | None = None) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.runner = runner or LocalRunner()
        self._execution: dict[Path, str] = {}

    @classmethod
    def default(
        cls, *, workspace_root: str | Path = ".", runner: LocalRunner | None = None
    ) -> "ForgeServices":
        return cls(workspace_root=workspace_root, runner=runner)

    def prepare_scf(self, request: ScfPrepareRequest) -> ForgeResultEnvelope | ForgeErrorEnvelope:
        if not isinstance(request, ScfPrepareRequest):
            return self._error("request.type", "expected ScfPrepareRequest", request)
        try:
            self._validate_policy(request.policy_id, allow_none=True)
            workspace = self._workspace(request.workspace_rel)
            structure_path = self._workspace_file(workspace, request.structure_path_rel, "structure_path_rel")
            with workspace.operation_guard(request.operation_id, request.operation) as owner_token:
                with suppress_legacy_events():
                    result = prepare_unit(
                        UnitSpec(
                            task="scf", workdir=workspace.root, structure=structure_path,
                            structure_format=request.structure_format, parameters=dict(request.parameters),
                        )
                    )
                envelope = ForgeResultEnvelope(
                    operation="prepare", workspace_rel=request.workspace_rel,
                    status=OperationStatus(execution="not_run", scientific="unassessed", collection="not_collected"),
                    artifacts=_prepare_artifacts(workspace),
                    diagnostics={"policy_id": request.policy_id, "task": result.task, "unit": result.unit,
                                 "prepare_manifest": "forge-unit.json"},
                )
                return self._persist(workspace, request, envelope, owner_token=owner_token)
        except Exception as error:
            return self._error_from_exception(error, request)

    def modify_scf(self, request: ScfModifyRequest) -> ForgeResultEnvelope | ForgeErrorEnvelope:
        if not isinstance(request, ScfModifyRequest):
            return self._error("request.type", "expected ScfModifyRequest", request)
        try:
            self._validate_policy(request.policy_id, allow_none=True)
            workspace = self._workspace(request.workspace_rel)
            with workspace.operation_guard(request.operation_id, request.operation) as owner_token:
                before = _input_snapshot(workspace)
                with suppress_legacy_events():
                    result = modify_unit(UnitModifySpec(
                        task="scf", workdir=workspace.root,
                        input_updates=dict(request.input_updates), remove_parameters=request.remove_parameters,
                    ))
                after = _input_snapshot(workspace)
                artifacts = tuple(
                    ArtifactRecord(id=f"artifact-{name.lower()}", path_rel=f"inputs/{name}", role="input", stage="modify")
                    for name in result.modified_files if (workspace.inputs_dir / name).is_file()
                )
                envelope = ForgeResultEnvelope(
                    operation="modify", workspace_rel=request.workspace_rel,
                    status=OperationStatus(execution="not_run", scientific="unassessed", collection="not_collected"),
                    artifacts=artifacts,
                    diagnostics={"policy_id": request.policy_id, "task": result.task, "unit": result.unit,
                                 "modified_files": result.modified_files, "changes": result.changes,
                                 "input_snapshot_before": before, "input_snapshot_after": after},
                )
                return self._persist(workspace, request, envelope, owner_token=owner_token)
        except Exception as error:
            return self._error_from_exception(error, request)

    def execute_scf(self, request: ScfExecuteRequest) -> ForgeResultEnvelope | ForgeErrorEnvelope:
        if not isinstance(request, ScfExecuteRequest):
            return self._error("request.type", "expected ScfExecuteRequest", request)
        try:
            self._validate_policy(request.policy_id, allow_none=True)
            workspace = self._workspace(request.workspace_rel)
            with workspace.operation_guard(request.operation_id, request.operation) as owner_token:
                if request.dry_run:
                    # Dry-run is an explicit typed-service fact.  Do not inspect
                    # existing logs or invoke the runner.
                    workspace.ensure_layout()
                    workspace.write_json(
                        "forge-result.json",
                        {"step": "execute", "task": "scf", "unit": "default", "engine": "abacus",
                         "status": "skipped", "returncode": None, "command": [], "dry_run": True},
                    )
                    envelope = ForgeResultEnvelope(
                        operation="execute", workspace_rel=request.workspace_rel,
                        status=OperationStatus(execution="skipped", scientific="unassessed", collection="not_collected"),
                        diagnostics={"policy_id": request.policy_id, "dry_run": True},
                    )
                else:
                    # Typed services intentionally bypass the legacy log-based
                    # skip policy and use only this invocation's result.
                    result = self.runner.run(workspace)
                    workspace.write_json(
                        "forge-result.json",
                        {"step": "execute", "task": "scf", "unit": "default", "engine": "abacus",
                         "status": result.status, "returncode": result.returncode, "command": result.command},
                    )
                    envelope = _with_workspace(result.to_envelope(), request.workspace_rel, policy_id=request.policy_id,
                                               operation_id=request.operation_id)
                return self._persist(workspace, request, envelope, owner_token=owner_token)
        except Exception as error:
            return self._error_from_exception(error, request)

    def collect_scf(self, request: ScfCollectRequest) -> ForgeResultEnvelope | ForgeErrorEnvelope:
        if not isinstance(request, ScfCollectRequest):
            return self._error("request.type", "expected ScfCollectRequest", request)
        try:
            if request.policy_id != "abacus.scf/v1":
                raise ValueError("unsupported policy_id; expected 'abacus.scf/v1'")
            self._validate_policy(request.policy_id, allow_none=False)
            workspace = self._workspace(request.workspace_rel)
            with workspace.operation_guard(request.operation_id, request.operation) as owner_token:
                result = collect(workspace)
                envelope = self._policy_envelope(workspace, request, result)
                return self._persist(workspace, request, envelope, owner_token=owner_token)
        except Exception as error:
            return self._error_from_exception(error, request)

    def _policy_envelope(
        self, workspace: Workspace, request: ScfCollectRequest, result: CollectionResult
    ) -> ForgeResultEnvelope:
        base = result.to_envelope()
        execution = "not_run"
        log_sources = result.diagnostics.get("log_sources", 0)
        normal_end = CheckRecord(
            name="normal_end",
            status="passed" if result.metrics.get("normal_end") is True else ("warning" if log_sources else "unavailable"),
        )
        negative = result.diagnostics.get("matched_nonconverged_markers", [])
        convergence = CheckRecord(
            name="scf_convergence",
            status="failed" if negative else ("passed" if result.metrics.get("converged") is True else ("warning" if log_sources else "unavailable")),
        )
        parser_complete = CheckRecord(
            name="parser_complete",
            status="passed" if base.status.collection == "complete" else ("warning" if base.status.collection == "partial" else "unavailable"),
        )
        required_artifacts = any(
            artifact.path_rel.startswith("outputs/") for artifact in base.artifacts
        )
        status, checks = evaluate_abacus_scf_v1(
            execution=execution,
            collection=base.status.collection,
            normal_end=normal_end,
            convergence=convergence,
            parser_complete=parser_complete,
            required_artifacts_present=required_artifacts,
        )
        diagnostics = dict(base.to_dict()["diagnostics"])  # type: ignore[arg-type]
        diagnostics["policy_id"] = request.policy_id
        return ForgeResultEnvelope(
            operation="collect",
            workspace_rel=request.workspace_rel,
            status=status,
            artifacts=base.artifacts,
            metrics=base.metrics,
            checks=checks,
            warnings=base.warnings,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _validate_policy(policy_id: str, *, allow_none: bool) -> None:
        allowed = {"abacus.scf/v1"} | ({"none"} if allow_none else set())
        if policy_id not in allowed:
            raise ForgePolicyError("unsupported policy_id; expected one of: " + ", ".join(sorted(allowed)))

    def _workspace(self, workspace_rel: str) -> Workspace:
        candidate = (self.workspace_root / workspace_rel).resolve()
        try:
            candidate.relative_to(self.workspace_root)
        except ValueError as error:
            raise ForgePathError("workspace_rel must remain under workspace_root") from error
        return Workspace(candidate)

    @staticmethod
    def _workspace_file(workspace: Workspace, path_rel: str, field_name: str) -> Path:
        candidate = (workspace.root / path_rel).resolve()
        try:
            candidate.relative_to(workspace.root)
        except ValueError as error:
            raise ForgePathError(f"{field_name} must remain under workspace_rel") from error
        if not candidate.is_file():
            raise ForgePreconditionError(f"{field_name} file not found: {path_rel}")
        return candidate

    def _persist(self, workspace: Workspace, request: RequestT, envelope: ForgeResultEnvelope, *, owner_token: str) -> ForgeResultEnvelope:
        envelope = _with_artifact_refs(envelope, request.operation_id)  # type: ignore[attr-defined]
        workspace.append_claimed_v1_operation_event(
            request.operation_id, envelope.operation, envelope.to_dict(), owner_token=owner_token  # type: ignore[attr-defined]
        )
        return envelope

    @staticmethod
    def _error(error_class: str, message: str, request: object) -> ForgeErrorEnvelope:
        operation_id = getattr(request, "operation_id", None)
        workspace_rel = getattr(request, "workspace_rel", None)
        if not isinstance(operation_id, str):
            operation_id = None
        if not isinstance(workspace_rel, str):
            workspace_rel = None
        return ForgeErrorEnvelope(
            error_class=error_class,
            message=message,
            affected_fields=("request",),
            operation_id=operation_id,
            workspace_rel=workspace_rel,
        )

    def _error_from_exception(self, error: Exception, request: object) -> ForgeErrorEnvelope:
        if isinstance(error, OperationConflictError):
            error_class = "operation.conflict"
        elif isinstance(error, ForgePolicyError):
            error_class = "request.policy"
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
        elif isinstance(error, FileNotFoundError):
            error_class = "precondition.missing"
        elif isinstance(error, OSError):
            error_class = "persistence.failure"
        elif isinstance(error, (TypeError, ValueError)):
            error_class = "request.invalid"
        else:
            error_class = "internal.failure"
        affected = {
            "operation.conflict": ("operation_id",),
            "request.policy": ("policy_id",),
            "request.path": ("workspace_rel",),
            "persistence.failure": ("workspace_rel",),
            "precondition.missing": ("request",),
        }.get(error_class, ("request",))
        result = self._error(error_class, str(error), request)
        return ForgeErrorEnvelope(
            error_class=result.error_class,
            message=result.message,
            affected_fields=affected,
            operation_id=result.operation_id,
            workspace_rel=result.workspace_rel,
        )


def _with_workspace(envelope: ForgeResultEnvelope, workspace_rel: str, *, policy_id: str, operation_id: str | None = None) -> ForgeResultEnvelope:
    diagnostics = dict(envelope.to_dict()["diagnostics"])  # type: ignore[arg-type]
    diagnostics["policy_id"] = policy_id
    if operation_id is not None:
        diagnostics["artifact_refs"] = [ArtifactRef(operation_id, artifact.id).to_dict() for artifact in envelope.artifacts]
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
    if workspace.inputs_dir.is_dir():
        for path in sorted(item for item in workspace.inputs_dir.rglob("*") if item.is_file()):
            relative = path.relative_to(workspace.root).as_posix()
            records.append(ArtifactRecord(
                id=f"input-{path.relative_to(workspace.inputs_dir).as_posix().replace('/', '-').lower()}",
                path_rel=relative, role="input", stage="prepare",
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(), size_bytes=path.stat().st_size,
            ))
    return tuple(records)


def _input_snapshot(workspace: Workspace) -> dict[str, object]:
    snapshot: dict[str, object] = {}
    if workspace.inputs_dir.is_dir():
        for path in sorted(item for item in workspace.inputs_dir.rglob("*") if item.is_file()):
            rel = path.relative_to(workspace.inputs_dir).as_posix()
            snapshot[rel] = {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size_bytes": path.stat().st_size,
            }
    return snapshot


def _with_artifact_refs(envelope: ForgeResultEnvelope, operation_id: str) -> ForgeResultEnvelope:
    diagnostics = dict(envelope.to_dict()["diagnostics"])  # type: ignore[arg-type]
    diagnostics["artifact_refs"] = [ArtifactRef(operation_id, artifact.id).to_dict() for artifact in envelope.artifacts]
    return ForgeResultEnvelope(
        operation=envelope.operation, workspace_rel=envelope.workspace_rel, status=envelope.status,
        artifacts=envelope.artifacts, metrics=envelope.metrics, checks=envelope.checks,
        warnings=envelope.warnings, diagnostics=diagnostics,
    )
