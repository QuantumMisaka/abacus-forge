"""Typed ABACUS services over event-free workspace primitives."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol, runtime_checkable

from abacus_forge.collection import collect_contained as collect
from abacus_forge.preparation import prepare_with_assets
from abacus_forge.modify import modify_input
from abacus_forge.compatibility_records import unit_manifest, modification_record
from abacus_forge.service_support import (
    ServiceContext, _with_workspace, _prepare_artifacts, _input_snapshot,
)
from abacus_forge import collection_results
from abacus_forge import md_results
from abacus_forge.contracts import (
    ArtifactRecord,
    ForgeErrorEnvelope,
    ForgeResultEnvelope,
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
from abacus_forge.md_contracts import (
    MdCollectRequest,
    MdExecuteRequest,
    MdModifyRequest,
    MdPrepareRequest,
)
from abacus_forge.runner import LocalRunner
from abacus_forge.errors import ForgePreconditionError
from abacus_forge.workspace import Workspace


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


class _AbacusServiceContext(ServiceContext):
    """ABACUS capability matching and INPUT calculation preconditions."""

    def __init__(
        self,
        *,
        workspace_root: str | Path = ".",
        runner_factory: RunnerFactory = LocalRunner,
        validate_input_calculation: bool = False,
    ) -> None:
        super().__init__(workspace_root=workspace_root)
        self.runner_factory = runner_factory
        self.validate_input_calculation = validate_input_calculation

    @staticmethod
    def task_for(request: object) -> str:
        if isinstance(
            request,
            (RelaxPrepareRequest, RelaxModifyRequest, RelaxExecuteRequest, RelaxCollectRequest),
        ):
            return request.capability
        if isinstance(request, (MdPrepareRequest, MdModifyRequest, MdExecuteRequest, MdCollectRequest)):
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
        md_types = {
            ScfPrepareRequest: MdPrepareRequest,
            ScfModifyRequest: MdModifyRequest,
            ScfExecuteRequest: MdExecuteRequest,
            ScfCollectRequest: MdCollectRequest,
        }
        md_excluded_type = md_types.get(request_type)
        return (
            (excluded_type is None or not isinstance(request, excluded_type))
            and (md_excluded_type is None or not isinstance(request, md_excluded_type))
        )

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


class _PrepareService:
    def __init__(self, context: _AbacusServiceContext, request_type: type[object]) -> None:
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
                task = self._context.task_for(typed_request)
                _, materialization = prepare_with_assets(
                    workspace,
                    task=task,
                    structure=structure_path,
                    structure_format=typed_request.structure_format,  # type: ignore[attr-defined]
                    parameters=dict(typed_request.parameters),  # type: ignore[attr-defined]
                    metadata={"unit": "default"},
                    pseudo_sources=dict(typed_request.pseudo_sources),  # type: ignore[attr-defined]
                    orbital_sources=dict(typed_request.orbital_sources),  # type: ignore[attr-defined]
                    asset_mode=typed_request.asset_mode,  # type: ignore[attr-defined]
                )
                asset_provenance = [record.to_dict() for record in materialization]
                manifest_metadata = (
                    {"asset_materialization": asset_provenance}
                    if asset_provenance
                    else None
                )
                workspace.write_json(
                    "forge-unit.json",
                    unit_manifest(task=task, metadata=manifest_metadata),
                )
                envelope = ForgeResultEnvelope(
                    operation="prepare",
                    workspace_rel=typed_request.workspace_rel,  # type: ignore[attr-defined]
                    status=OperationStatus(
                        execution="not_run", scientific="unassessed", collection="not_collected"
                    ),
                    artifacts=_prepare_artifacts(workspace),
                    diagnostics={
                        "task": task,
                        "unit": "default",
                        "prepare_manifest": "forge-unit.json",
                        "asset_materialization": asset_provenance,
                    },
                )
                return self._context.persist(
                    workspace, typed_request, envelope, owner_token=owner_token  # type: ignore[arg-type]
                )
        except Exception as error:
            return self._context.error_from_exception(error, request)


class ScfPrepareService(_PrepareService):
    def __init__(self, context: _AbacusServiceContext) -> None:
        super().__init__(context, ScfPrepareRequest)


class _ModifyService:
    def __init__(self, context: _AbacusServiceContext, request_type: type[object]) -> None:
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
                task = self._context.task_for(typed_request)
                updates = dict(typed_request.input_updates)  # type: ignore[attr-defined]
                removed = typed_request.remove_parameters  # type: ignore[attr-defined]
                modified_files: list[str] = []
                changes: dict[str, object] = {}
                if updates or removed:
                    modify_input(
                        input_path, updates=updates, remove_keys=removed,
                        destination=input_path,
                    )
                    modified_files.append("INPUT")
                    changes["INPUT"] = {
                        "updates": updates, "removed": [str(key) for key in removed or ()],
                    }
                workspace.write_json(
                    "forge-result.json",
                    {"step": "modify", **modification_record(
                        workspace=workspace.root, task=task,
                        modified_files=modified_files, changes=changes,
                    )},
                )
                after = _input_snapshot(workspace)
                artifacts = tuple(
                    ArtifactRecord(
                        id=f"artifact-{name.lower()}",
                        path_rel=f"inputs/{name}",
                        role="input",
                        stage="modify",
                    )
                    for name in modified_files
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
                        "task": task,
                        "unit": "default",
                        "modified_files": modified_files,
                        "changes": changes,
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
    def __init__(self, context: _AbacusServiceContext) -> None:
        super().__init__(context, ScfModifyRequest)


class _ExecuteService:
    def __init__(self, context: _AbacusServiceContext, request_type: type[object]) -> None:
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
                        diagnostics={
                            "dry_run": True,
                            **({"task": task} if self._request_type is RelaxExecuteRequest else {}),
                        },
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
    def __init__(self, context: _AbacusServiceContext) -> None:
        super().__init__(context, ScfExecuteRequest)


class _CollectService:
    def __init__(self, context: _AbacusServiceContext, request_type: type[object]) -> None:
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
                elif isinstance(typed_request, MdCollectRequest):
                    envelope = md_results.collection_envelope(result, typed_request.workspace_rel)
                    extra_observations = md_results.collection_observations(result)
                else:
                    envelope = collection_results.collection_envelope(result, typed_request.workspace_rel)
                    extra_observations = collection_results.collection_observations(result)
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
    def __init__(self, context: _AbacusServiceContext) -> None:
        super().__init__(context, ScfCollectRequest)


class ScfServiceSet:
    """Per-operation SCF services sharing one private execution context."""

    def __init__(self, *, workspace_root: str | Path = ".", runner_factory: RunnerFactory = LocalRunner) -> None:
        context = _AbacusServiceContext(workspace_root=workspace_root, runner_factory=runner_factory)
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
        context = _AbacusServiceContext(
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


class MdServiceSet:
    """Per-operation molecular-dynamics services with MD input validation."""

    def __init__(
        self,
        *,
        workspace_root: str | Path = ".",
        runner_factory: RunnerFactory = LocalRunner,
    ) -> None:
        context = _AbacusServiceContext(
            workspace_root=workspace_root,
            runner_factory=runner_factory,
            validate_input_calculation=True,
        )
        self.prepare: PrepareService = _PrepareService(context, MdPrepareRequest)
        self.modify: ModifyService = _ModifyService(context, MdModifyRequest)
        self.execute: ExecuteService = _ExecuteService(context, MdExecuteRequest)
        self.collect: CollectService = _CollectService(context, MdCollectRequest)

    @classmethod
    def default(
        cls,
        workspace_root: str | Path = ".",
        runner_factory: RunnerFactory = LocalRunner,
    ) -> "MdServiceSet":
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
