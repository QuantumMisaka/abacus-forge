"""Typed, factual SCF services over the legacy Forge primitives."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable, Protocol, TypeVar, runtime_checkable

from abacus_forge.api import UnitModifySpec, UnitSpec, collect, modify_unit, prepare_unit, execute, suppress_legacy_events
from abacus_forge.contracts import (
    ArtifactRecord, ArtifactRef,
    ForgeErrorEnvelope,
    ForgeResultEnvelope,
    Observation,
    OperationOutcome,
    OperationStatus,
    ScfCollectRequest,
    ScfExecuteRequest,
    ScfModifyRequest,
    ScfPrepareRequest,
)
from abacus_forge.input_io import read_input
from abacus_forge.relax_contracts import (
    RelaxCollectRequest,
    RelaxExecuteRequest,
    RelaxModifyRequest,
    RelaxPrepareRequest,
)
from abacus_forge.relax_results import collection_envelope, collection_observations
from abacus_forge.runner import LocalRunner
from abacus_forge.errors import (
    ForgeInternalError,
    ForgePathError,
    ForgePersistenceError,
    ForgePreconditionError,
    ForgeRequestError,
    ForgeSchemaError,
    normalize_error_message,
    OperationConflictError,
)
from abacus_forge.workspace import Workspace


RequestT = TypeVar("RequestT")
ServiceResult = OperationOutcome | ForgeErrorEnvelope
RunnerFactory = Callable[..., object]


@runtime_checkable
class PrepareService(Protocol):
    def prepare(self, request: ScfPrepareRequest) -> ServiceResult: ...


@runtime_checkable
class ModifyService(Protocol):
    def modify(self, request: ScfModifyRequest) -> ServiceResult: ...


@runtime_checkable
class ExecuteService(Protocol):
    def execute(self, request: ScfExecuteRequest) -> ServiceResult: ...


@runtime_checkable
class CollectService(Protocol):
    def collect(self, request: ScfCollectRequest) -> ServiceResult: ...


class _ScfServiceContext:
    """Private shared context for typed ABACUS operation services.

    The historical name is retained because it is private but appears in a
    few downstream debugging traces.  ``request_type`` and ``task_resolver``
    are supplied by each operation adapter, so the mechanics stay shared by
    SCF and Relax without allowing a Relax request to fall through to SCF.
    """

    def __init__(
        self,
        *,
        workspace_root: str | Path = ".",
        runner_factory: RunnerFactory = LocalRunner,
        validate_input_calculation: bool = False,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.runner_factory = runner_factory
        self.validate_input_calculation = validate_input_calculation

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

    @staticmethod
    def task_for(request: object) -> str:
        if isinstance(
            request,
            (RelaxPrepareRequest, RelaxModifyRequest, RelaxExecuteRequest, RelaxCollectRequest),
        ):
            return request.capability
        return "scf"

    @staticmethod
    def accepts_request(request: object, request_type: type[object]) -> bool:
        """Keep SCF subclass compatibility while fencing off Relax requests."""
        if not isinstance(request, request_type):
            return False
        relax_types = {
            ScfPrepareRequest: RelaxPrepareRequest,
            ScfModifyRequest: RelaxModifyRequest,
            ScfExecuteRequest: RelaxExecuteRequest,
            ScfCollectRequest: RelaxCollectRequest,
        }
        excluded_type = relax_types.get(request_type)
        return excluded_type is None or not isinstance(request, excluded_type)

    def require_matching_calculation(self, workspace: Workspace, task: str) -> None:
        """Require an existing INPUT to select the requested ABACUS phase."""
        input_path = self.workspace_path(workspace, "inputs/INPUT", "inputs/INPUT")
        self.require_file(input_path, "inputs/INPUT", "inputs/INPUT")
        try:
            calculation = read_input(input_path).get("calculation")
        except (OSError, ValueError) as error:
            raise ForgePreconditionError("inputs/INPUT calculation cannot be read") from error
        if calculation != task:
            raise ForgePreconditionError(
                f"inputs/INPUT calculation must match capability {task!r}"
            )

    def validate_collect_calculation(self, workspace: Workspace, task: str) -> None:
        """Validate INPUT when present while allowing external output-only collects."""
        raw_input = workspace.inputs_dir / "INPUT"
        if not raw_input.exists() and not raw_input.is_symlink():
            return
        self.require_matching_calculation(workspace, task)

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
        result = self.error(error_class, str(error), request)
        return ForgeErrorEnvelope(
            error_class=result.error_class,
            message=result.message,
            affected_fields=affected,
            operation_id=result.operation_id,
            workspace_rel=result.workspace_rel,
        )


class _PrepareService:
    def __init__(self, context: _ScfServiceContext, request_type: type[object]) -> None:
        self._context = context
        self._request_type = request_type

    def prepare(self, request: object) -> ServiceResult:
        if not self._context.accepts_request(request, self._request_type):
            return self._context.error(
                "request.invalid", f"expected {self._request_type.__name__}", None
            )
        try:
            typed_request = request  # type: ignore[assignment]
            workspace = self._context.workspace(typed_request.workspace_rel)  # type: ignore[attr-defined]
            # Resolve and validate containment before admission.  Existence and
            # file type are operation preconditions and must be checked after
            # the ID is durably admitted, so a failed request cannot replay.
            structure_path = self._context.workspace_path(
                workspace, typed_request.structure_path_rel, "structure_path_rel"  # type: ignore[attr-defined]
            )
            with workspace.operation_guard(typed_request.operation_id, typed_request.operation) as owner_token:  # type: ignore[attr-defined]
                self._context.require_file(
                    structure_path, typed_request.structure_path_rel, "structure_path_rel"  # type: ignore[attr-defined]
                )
                with suppress_legacy_events():
                    result = prepare_unit(
                        UnitSpec(
                            task=self._context.task_for(typed_request),
                            workdir=workspace.root,
                            structure=structure_path,
                            structure_format=typed_request.structure_format,  # type: ignore[attr-defined]
                            parameters=dict(typed_request.parameters),  # type: ignore[attr-defined]
                        )
                    )
                envelope = ForgeResultEnvelope(
                    operation="prepare",
                    workspace_rel=typed_request.workspace_rel,  # type: ignore[attr-defined]
                    status=OperationStatus(
                        execution="not_run", scientific="unassessed", collection="not_collected"
                    ),
                    artifacts=_prepare_artifacts(workspace),
                    diagnostics={
                        "task": result.task,
                        "unit": result.unit,
                        "prepare_manifest": "forge-unit.json",
                    },
                )
                return self._context.persist(
                    workspace, typed_request, envelope, owner_token=owner_token  # type: ignore[arg-type]
                )
        except Exception as error:
            return self._context.error_from_exception(error, request)


class ScfPrepareService(_PrepareService):
    def __init__(self, context: _ScfServiceContext) -> None:
        super().__init__(context, ScfPrepareRequest)


class _ModifyService:
    def __init__(self, context: _ScfServiceContext, request_type: type[object]) -> None:
        self._context = context
        self._request_type = request_type

    def modify(self, request: object) -> ServiceResult:
        if not self._context.accepts_request(request, self._request_type):
            return self._context.error(
                "request.invalid", f"expected {self._request_type.__name__}", None
            )
        try:
            typed_request = request  # type: ignore[assignment]
            workspace = self._context.workspace(typed_request.workspace_rel)  # type: ignore[attr-defined]
            with workspace.operation_guard(typed_request.operation_id, typed_request.operation) as owner_token:  # type: ignore[attr-defined]
                input_path = self._context.workspace_path(workspace, "inputs/INPUT", "inputs/INPUT")
                self._context.require_file(input_path, "inputs/INPUT", "inputs/INPUT")
                before = _input_snapshot(workspace)
                with suppress_legacy_events():
                    result = modify_unit(
                        UnitModifySpec(
                            task=self._context.task_for(typed_request),
                            workdir=workspace.root,
                            input_updates=dict(typed_request.input_updates),  # type: ignore[attr-defined]
                            remove_parameters=typed_request.remove_parameters,  # type: ignore[attr-defined]
                        )
                    )
                after = _input_snapshot(workspace)
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
                    workspace_rel=typed_request.workspace_rel,  # type: ignore[attr-defined]
                    status=OperationStatus(
                        execution="not_run", scientific="unassessed", collection="not_collected"
                    ),
                    artifacts=artifacts,
                    diagnostics={
                        "task": result.task,
                        "unit": result.unit,
                        "modified_files": result.modified_files,
                        "changes": result.changes,
                        "input_snapshot_before": before,
                        "input_snapshot_after": after,
                    },
                )
                return self._context.persist(
                    workspace, typed_request, envelope, owner_token=owner_token  # type: ignore[arg-type]
                )
        except Exception as error:
            return self._context.error_from_exception(error, request)


class ScfModifyService(_ModifyService):
    def __init__(self, context: _ScfServiceContext) -> None:
        super().__init__(context, ScfModifyRequest)


class _ExecuteService:
    def __init__(self, context: _ScfServiceContext, request_type: type[object]) -> None:
        self._context = context
        self._request_type = request_type

    def execute(self, request: object) -> ServiceResult:
        if not self._context.accepts_request(request, self._request_type):
            return self._context.error(
                "request.invalid", f"expected {self._request_type.__name__}", None
            )
        try:
            typed_request = request  # type: ignore[assignment]
            workspace = self._context.workspace(typed_request.workspace_rel)  # type: ignore[attr-defined]
            with workspace.operation_guard(typed_request.operation_id, typed_request.operation) as owner_token:  # type: ignore[attr-defined]
                task = self._context.task_for(typed_request)
                if self._context.validate_input_calculation:
                    self._context.validate_collect_calculation(workspace, task)
                if typed_request.dry_run:  # type: ignore[attr-defined]
                    # Dry-run is an explicit typed-service fact.  Do not inspect
                    # existing logs or invoke the runner.
                    workspace.ensure_layout()
                    workspace.write_json(
                        "forge-result.json",
                        {
                            "step": "execute",
                            "task": task,
                            "unit": "default",
                            "engine": "abacus",
                            "status": "skipped",
                            "returncode": None,
                            "command": [],
                            "dry_run": True,
                        },
                    )
                    envelope = ForgeResultEnvelope(
                        operation="execute",
                        workspace_rel=typed_request.workspace_rel,  # type: ignore[attr-defined]
                        status=OperationStatus(
                            execution="skipped", scientific="unassessed", collection="not_collected"
                        ),
                        diagnostics={"dry_run": True, "task": task},
                    )
                else:
                    for input_name in ("INPUT", "STRU", "KPT"):
                        input_path = self._context.workspace_path(
                            workspace, f"inputs/{input_name}", f"inputs/{input_name}"
                        )
                        self._context.require_file(
                            input_path, f"inputs/{input_name}", f"inputs/{input_name}"
                        )
                    # Build each default runner from this request.  The factory
                    # hook is only for integration/test doubles; request fields
                    # remain the sole configuration source for normal callers.
                    runner = self._context.runner_factory(
                        executable=typed_request.executable,  # type: ignore[attr-defined]
                        mpi_ranks=typed_request.mpi_ranks,  # type: ignore[attr-defined]
                        omp_threads=typed_request.omp_threads,  # type: ignore[attr-defined]
                        timeout_seconds=typed_request.timeout_seconds,  # type: ignore[attr-defined]
                    )
                    preflight = getattr(runner, "preflight", None)
                    if callable(preflight):
                        try:
                            preflight(workspace)
                        except FileNotFoundError as error:
                            raise ForgePreconditionError(str(error)) from error
                    runner_result = runner.run(workspace)
                    if runner_result.diagnostics.get("failure_class") == "missing_executable":
                        raise ForgePreconditionError("configured executable is missing or not executable")
                    workspace.write_json(
                        "forge-result.json",
                        {
                            "step": "execute",
                            "task": task,
                            "unit": "default",
                            "engine": "abacus",
                            "status": runner_result.status,
                            "returncode": runner_result.returncode,
                            "command": runner_result.command,
                        },
                    )
                    envelope = _with_workspace(runner_result.to_envelope(), typed_request.workspace_rel)  # type: ignore[attr-defined]
                return self._context.persist(
                    workspace, typed_request, envelope, owner_token=owner_token  # type: ignore[arg-type]
                )
        except Exception as error:
            return self._context.error_from_exception(error, request)


class ScfExecuteService(_ExecuteService):
    def __init__(self, context: _ScfServiceContext) -> None:
        super().__init__(context, ScfExecuteRequest)


class _CollectService:
    def __init__(self, context: _ScfServiceContext, request_type: type[object]) -> None:
        self._context = context
        self._request_type = request_type

    def collect(self, request: object) -> ServiceResult:
        if not self._context.accepts_request(request, self._request_type):
            return self._context.error(
                "request.invalid", f"expected {self._request_type.__name__}", None
            )
        try:
            typed_request = request  # type: ignore[assignment]
            workspace = self._context.workspace(typed_request.workspace_rel)  # type: ignore[attr-defined]
            with workspace.operation_guard(typed_request.operation_id, typed_request.operation) as owner_token:  # type: ignore[attr-defined]
                task = self._context.task_for(typed_request)
                if self._context.validate_input_calculation:
                    self._context.validate_collect_calculation(workspace, task)
                result = collect(workspace)
                if isinstance(typed_request, RelaxCollectRequest):
                    envelope = collection_envelope(result, typed_request.workspace_rel)
                    extra_observations = collection_observations(result)
                else:
                    envelope = _with_workspace(result.to_envelope(), typed_request.workspace_rel)
                    extra_observations = ()
                return self._context.persist(
                    workspace,
                    typed_request,
                    envelope,
                    owner_token=owner_token,  # type: ignore[arg-type]
                    extra_observations=extra_observations,
                )
        except Exception as error:
            return self._context.error_from_exception(error, request)


class ScfCollectService(_CollectService):
    def __init__(self, context: _ScfServiceContext) -> None:
        super().__init__(context, ScfCollectRequest)


class ScfServiceSet:
    """Per-operation SCF services sharing one private execution context."""

    def __init__(self, *, workspace_root: str | Path = ".", runner_factory: RunnerFactory = LocalRunner) -> None:
        context = _ScfServiceContext(workspace_root=workspace_root, runner_factory=runner_factory)
        self.prepare: PrepareService = ScfPrepareService(context)
        self.modify: ModifyService = ScfModifyService(context)
        self.execute: ExecuteService = ScfExecuteService(context)
        self.collect: CollectService = ScfCollectService(context)

    @classmethod
    def default(cls, workspace_root: str | Path = ".", runner_factory: RunnerFactory = LocalRunner) -> "ScfServiceSet":
        return cls(workspace_root=workspace_root, runner_factory=runner_factory)


class RelaxServiceSet:
    """Per-operation Relax services sharing the SCF operation mechanics."""

    def __init__(
        self,
        *,
        workspace_root: str | Path = ".",
        runner_factory: RunnerFactory = LocalRunner,
    ) -> None:
        context = _ScfServiceContext(
            workspace_root=workspace_root,
            runner_factory=runner_factory,
            validate_input_calculation=True,
        )
        self.prepare: PrepareService = _PrepareService(context, RelaxPrepareRequest)
        self.modify: ModifyService = _ModifyService(context, RelaxModifyRequest)
        self.execute: ExecuteService = _ExecuteService(context, RelaxExecuteRequest)
        self.collect: CollectService = _CollectService(context, RelaxCollectRequest)

    @classmethod
    def default(
        cls,
        workspace_root: str | Path = ".",
        runner_factory: RunnerFactory = LocalRunner,
    ) -> "RelaxServiceSet":
        return cls(workspace_root=workspace_root, runner_factory=runner_factory)


class ForgeServices:
    """Source-compatible facade delegating to :class:`ScfServiceSet`."""

    def __init__(self, *, workspace_root: str | Path = ".", runner: object | None = None) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.runner = runner or LocalRunner()
        if runner is None:
            runner_factory: RunnerFactory = LocalRunner
        else:
            runner_factory = lambda **_: self.runner
        self._service_set = ScfServiceSet.default(workspace_root=self.workspace_root, runner_factory=runner_factory)

    @classmethod
    def default(
        cls, *, workspace_root: str | Path = ".", runner: object | None = None
    ) -> "ForgeServices":
        return cls(workspace_root=workspace_root, runner=runner)

    def prepare_scf(self, request: ScfPrepareRequest) -> ServiceResult:
        return self._service_set.prepare.prepare(request)

    def modify_scf(self, request: ScfModifyRequest) -> ServiceResult:
        return self._service_set.modify.modify(request)

    def execute_scf(self, request: ScfExecuteRequest) -> ServiceResult:
        return self._service_set.execute.execute(request)

    def collect_scf(self, request: ScfCollectRequest) -> ServiceResult:
        return self._service_set.collect.collect(request)


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
                source = "runtime" if name in {"failure_class", "dry_run", "termination"} else "parser"
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
    if workspace.inputs_dir.is_dir():
        for path, resolved in _contained_files(workspace, workspace.inputs_dir):
            relative = path.relative_to(workspace.root.resolve()).as_posix()
            records.append(ArtifactRecord(
                id=f"input-{path.relative_to(workspace.inputs_dir).as_posix().replace('/', '-').lower()}",
                path_rel=relative, role="input", stage="prepare",
                sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(), size_bytes=resolved.stat().st_size,
            ))
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
