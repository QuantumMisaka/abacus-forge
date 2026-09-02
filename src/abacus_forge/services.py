"""Typed, policy-aware SCF services over the legacy Forge primitives."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TypeVar

from abacus_forge.api import UnitModifySpec, UnitSpec, collect, modify_unit, prepare_unit, execute
from abacus_forge.contracts import (
    ArtifactRecord,
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
            workspace = self._workspace(request.workspace_rel)
            result = prepare_unit(UnitSpec(task="scf", workdir=workspace.root))
            envelope = ForgeResultEnvelope(
                operation="prepare",
                workspace_rel=request.workspace_rel,
                status=OperationStatus(execution="not_run", scientific="unassessed", collection="not_collected"),
                artifacts=_manifest_artifact(workspace),
                diagnostics={"policy_id": request.policy_id, "task": result.task, "unit": result.unit},
            )
            return self._persist(workspace, request, envelope)
        except Exception as error:
            return self._error_from_exception(error, request)

    def modify_scf(self, request: ScfModifyRequest) -> ForgeResultEnvelope | ForgeErrorEnvelope:
        if not isinstance(request, ScfModifyRequest):
            return self._error("request.type", "expected ScfModifyRequest", request)
        try:
            workspace = self._workspace(request.workspace_rel)
            result = modify_unit(UnitModifySpec(task="scf", workdir=workspace.root))
            artifacts = tuple(
                ArtifactRecord(
                    id=f"artifact-{name.lower()}",
                    path_rel=f"inputs/{name}",
                    role="input",
                    stage="modify",
                )
                for name in result.modified_files
                if (workspace.inputs_dir / name).is_file()
            )
            envelope = ForgeResultEnvelope(
                operation="modify",
                workspace_rel=request.workspace_rel,
                status=OperationStatus(execution="completed", scientific="unassessed", collection="not_collected"),
                artifacts=artifacts,
                diagnostics={"policy_id": request.policy_id, "task": result.task, "unit": result.unit},
            )
            return self._persist(workspace, request, envelope)
        except Exception as error:
            return self._error_from_exception(error, request)

    def execute_scf(self, request: ScfExecuteRequest) -> ForgeResultEnvelope | ForgeErrorEnvelope:
        if not isinstance(request, ScfExecuteRequest):
            return self._error("request.type", "expected ScfExecuteRequest", request)
        try:
            workspace = self._workspace(request.workspace_rel)
            result = execute(workspace, runner=self.runner)
            self._execution[workspace.root] = "completed" if result.status == "completed" and result.returncode == 0 else "failed"
            workspace.write_json(
                "forge-result.json",
                {
                    "step": "execute",
                    "task": "scf",
                    "unit": "default",
                    "engine": "abacus",
                    "status": result.status,
                    "returncode": result.returncode,
                    "command": result.command,
                },
            )
            envelope = _with_workspace(result.to_envelope(), request.workspace_rel, policy_id=request.policy_id)
            return self._persist(workspace, request, envelope)
        except Exception as error:
            return self._error_from_exception(error, request)

    def collect_scf(self, request: ScfCollectRequest) -> ForgeResultEnvelope | ForgeErrorEnvelope:
        if not isinstance(request, ScfCollectRequest):
            return self._error("request.type", "expected ScfCollectRequest", request)
        try:
            if request.policy_id != "abacus.scf/v1":
                raise ValueError("unsupported policy_id; expected 'abacus.scf/v1'")
            workspace = self._workspace(request.workspace_rel)
            result = collect(workspace)
            envelope = self._policy_envelope(workspace, request, result)
            return self._persist(workspace, request, envelope)
        except Exception as error:
            return self._error_from_exception(error, request)

    def _policy_envelope(
        self, workspace: Workspace, request: ScfCollectRequest, result: CollectionResult
    ) -> ForgeResultEnvelope:
        base = result.to_envelope()
        execution = self._execution_for(workspace)
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

    def _execution_for(self, workspace: Workspace) -> str:
        if workspace.root in self._execution:
            return self._execution[workspace.root]
        record = workspace.root / "forge-result.json"
        if record.is_file():
            try:
                payload = json.loads(record.read_text(encoding="utf-8"))
                if payload.get("step") == "execute" and payload.get("status") in {"completed", "failed"}:
                    return "completed" if payload["status"] == "completed" else "failed"
            except (OSError, ValueError, TypeError):
                pass
        return "not_run"

    def _workspace(self, workspace_rel: str) -> Workspace:
        candidate = (self.workspace_root / workspace_rel).resolve()
        try:
            candidate.relative_to(self.workspace_root)
        except ValueError as error:
            raise ValueError("workspace_rel must remain under workspace_root") from error
        return Workspace(candidate)

    def _persist(self, workspace: Workspace, request: RequestT, envelope: ForgeResultEnvelope) -> ForgeResultEnvelope:
        workspace.append_v1_operation_event(request.operation_id, envelope.operation, envelope.to_dict())  # type: ignore[attr-defined]
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
        error_class = "request.invalid" if isinstance(error, (TypeError, ValueError)) else "service.error"
        affected = tuple(
            field
            for field in ("workspace_rel", "operation_id", "policy_id")
            if field in str(error)
        ) or ("request",)
        result = self._error(error_class, str(error), request)
        return ForgeErrorEnvelope(
            error_class=result.error_class,
            message=result.message,
            affected_fields=affected,
            operation_id=result.operation_id,
            workspace_rel=result.workspace_rel,
        )


def _with_workspace(envelope: ForgeResultEnvelope, workspace_rel: str, *, policy_id: str) -> ForgeResultEnvelope:
    diagnostics = dict(envelope.to_dict()["diagnostics"])  # type: ignore[arg-type]
    diagnostics["policy_id"] = policy_id
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
