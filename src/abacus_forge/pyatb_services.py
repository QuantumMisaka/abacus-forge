"""Typed services for the explicit PyATB band capability.

The legacy PyATB helpers provide a compatibility workflow which discovers an
SCF output directory.  This module is the deliberately narrower v1 service
boundary: preparation consumes an already-declared handoff, execution runs
one local process, and collection reports only explicitly selected files.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol, runtime_checkable

from abacus_forge.compatibility_records import unit_manifest
from abacus_forge.contracts import (
    ForgeErrorEnvelope,
    ForgeResultEnvelope,
    OperationOutcome,
    OperationStatus,
)
from abacus_forge.errors import ForgePreconditionError
from abacus_forge.pyatb import collect_typed_pyatb_band, prepare_typed_pyatb_band
from abacus_forge.pyatb_contracts import (
    PyatbBandCollectRequest,
    PyatbBandExecuteRequest,
    PyatbBandPrepareRequest,
)
from abacus_forge.runner import LocalRunner
from abacus_forge.service_support import (
    ServiceContext,
    _prepare_artifacts,
)
from abacus_forge.workspace import Workspace


ServiceResult = OperationOutcome | ForgeErrorEnvelope
RunnerFactory = Callable[..., object]


@runtime_checkable
class PyatbBandPrepareServiceProtocol(Protocol):
    """Service protocol for one typed PyATB preparation operation."""

    def prepare(self, request: PyatbBandPrepareRequest) -> ServiceResult: ...


@runtime_checkable
class PyatbBandExecuteServiceProtocol(Protocol):
    """Service protocol for one typed PyATB execution operation."""

    def execute(self, request: PyatbBandExecuteRequest) -> ServiceResult: ...


@runtime_checkable
class PyatbBandCollectServiceProtocol(Protocol):
    """Service protocol for one typed PyATB collection operation."""

    def collect(self, request: PyatbBandCollectRequest) -> ServiceResult: ...


class _PyatbContext(ServiceContext):
    """Shared workspace and runner dependencies for a PyATB service set."""

    def __init__(
        self,
        *,
        workspace_root: str | Path = ".",
        runner_factory: RunnerFactory = LocalRunner,
    ) -> None:
        super().__init__(workspace_root=workspace_root)
        self.runner_factory = runner_factory


class PyatbBandPrepareService:
    """Prepare one explicit PyATB handoff and persist its operation outcome."""

    def __init__(self, context: _PyatbContext) -> None:
        self._context = context

    def prepare(self, request: PyatbBandPrepareRequest) -> ServiceResult:
        if not isinstance(request, PyatbBandPrepareRequest):
            return self._context.error(
                "request.invalid", "expected PyatbBandPrepareRequest", request
            )
        try:
            workspace = self._context.workspace(request.workspace_rel)
            # Source existence and STRU parsing belong after admission.  The
            # helper itself performs all side-effect-free validation before it
            # creates a staged file, so a failed operation remains durably
            # admitted without leaving a partial handoff.
            with workspace.operation_guard(request.operation_id, request.operation) as owner_token:
                _, handoff = prepare_typed_pyatb_band(workspace, request)
                workspace.write_json(
                    "forge-unit.json",
                    unit_manifest(
                        task="band",
                        unit="pyatb",
                        engine="pyatb",
                        metadata={"pyatb_handoff": list(handoff)},
                    ),
                )
                envelope = ForgeResultEnvelope(
                    operation="prepare",
                    workspace_rel=request.workspace_rel,
                    status=OperationStatus(
                        execution="not_run",
                        scientific="unassessed",
                        collection="not_collected",
                    ),
                    artifacts=_prepare_artifacts(workspace),
                    diagnostics={
                        "capability": "pyatb-band",
                        "task": "band",
                        "unit": "pyatb",
                        "engine": "pyatb",
                        "pyatb_handoff": list(handoff),
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


class PyatbBandExecuteService:
    """Run exactly one local PyATB process in a prepared workspace."""

    def __init__(self, context: _PyatbContext) -> None:
        self._context = context

    def execute(self, request: PyatbBandExecuteRequest) -> ServiceResult:
        if not isinstance(request, PyatbBandExecuteRequest):
            return self._context.error(
                "request.invalid", "expected PyatbBandExecuteRequest", request
            )
        try:
            workspace = self._context.workspace(request.workspace_rel)
            with workspace.operation_guard(request.operation_id, request.operation) as owner_token:
                # Both normal and dry-run paths validate the declared prepared
                # workspace.  Dry-run never reads old stdout/stderr logs and
                # never constructs or invokes a runner.
                _require_prepared_pyatb_inputs(self._context, workspace)
                if request.dry_run:
                    workspace.write_json(
                        "forge-result.json",
                        {
                            "step": "execute",
                            "task": "band",
                            "unit": "pyatb",
                            "engine": "pyatb",
                            "status": "skipped",
                            "returncode": None,
                            "command": [],
                            "dry_run": True,
                        },
                    )
                    envelope = ForgeResultEnvelope(
                        operation="execute",
                        workspace_rel=request.workspace_rel,
                        status=OperationStatus(
                            execution="skipped",
                            scientific="unassessed",
                            collection="not_collected",
                        ),
                        diagnostics={
                            "capability": "pyatb-band",
                            "task": "band",
                            "unit": "pyatb",
                            "engine": "pyatb",
                            "dry_run": True,
                        },
                    )
                else:
                    runner = self._context.runner_factory(
                        executable=request.executable,
                        mpi_ranks=request.mpi_ranks,
                        omp_threads=request.omp_threads,
                        timeout_seconds=request.timeout_seconds,
                    )
                    preflight = getattr(runner, "preflight", None)
                    if callable(preflight):
                        try:
                            preflight(workspace)
                        except FileNotFoundError as error:
                            raise ForgePreconditionError(
                                "configured PyATB executable is missing or not executable"
                            ) from error
                    runner_result = runner.run(workspace)
                    workspace.write_json(
                        "forge-result.json",
                        {
                            "step": "execute",
                            "task": "band",
                            "unit": "pyatb",
                            "engine": "pyatb",
                            "status": runner_result.status,
                            "returncode": runner_result.returncode,
                            "command": list(runner_result.command),
                            "dry_run": False,
                        },
                    )
                    envelope = _runner_envelope(
                        runner_result,
                        workspace_rel=request.workspace_rel,
                    )
                return self._context.persist(
                    workspace,
                    request,
                    envelope,
                    owner_token=owner_token,
                )
        except Exception as error:
            return self._context.error_from_exception(error, request)


class PyatbBandCollectService:
    """Collect selected PyATB band outputs without task or science inference."""

    def __init__(self, context: _PyatbContext) -> None:
        self._context = context

    def collect(self, request: PyatbBandCollectRequest) -> ServiceResult:
        if not isinstance(request, PyatbBandCollectRequest):
            return self._context.error(
                "request.invalid", "expected PyatbBandCollectRequest", request
            )
        try:
            workspace = self._context.workspace(request.workspace_rel)
            with workspace.operation_guard(request.operation_id, request.operation) as owner_token:
                raw_envelope = collect_typed_pyatb_band(workspace, request)
                diagnostics = dict(raw_envelope.to_dict()["diagnostics"])
                diagnostics.update(
                    {
                        "capability": "pyatb-band",
                        "task": "band",
                        "unit": "pyatb",
                        "engine": "pyatb",
                    }
                )
                envelope = ForgeResultEnvelope(
                    operation="collect",
                    workspace_rel=request.workspace_rel,
                    status=raw_envelope.status,
                    artifacts=raw_envelope.artifacts,
                    metrics=raw_envelope.metrics,
                    checks=raw_envelope.checks,
                    warnings=raw_envelope.warnings,
                    diagnostics=diagnostics,
                )
                return self._context.persist(
                    workspace,
                    request,
                    envelope,
                    owner_token=owner_token,
                )
        except Exception as error:
            return self._context.error_from_exception(error, request)


class PyatbBandServiceSet:
    """Typed PyATB prepare/execute/collect services sharing one context."""

    def __init__(
        self,
        *,
        workspace_root: str | Path = ".",
        runner_factory: RunnerFactory = LocalRunner,
        context: _PyatbContext | None = None,
    ) -> None:
        shared_context = context if context is not None else _PyatbContext(
            workspace_root=workspace_root,
            runner_factory=runner_factory,
        )
        self._context = shared_context
        self.prepare: PyatbBandPrepareServiceProtocol = PyatbBandPrepareService(shared_context)
        self.execute: PyatbBandExecuteServiceProtocol = PyatbBandExecuteService(shared_context)
        self.collect: PyatbBandCollectServiceProtocol = PyatbBandCollectService(shared_context)

    @classmethod
    def default(
        cls,
        workspace_root: str | Path = ".",
        runner_factory: RunnerFactory = LocalRunner,
    ) -> "PyatbBandServiceSet":
        return cls(workspace_root=workspace_root, runner_factory=runner_factory)


def _require_prepared_pyatb_inputs(context: ServiceContext, workspace: Workspace) -> None:
    """Require the files emitted by typed preparation before execution.

    The routes are read from the generated ``inputs/Input`` rather than from
    a directory scan.  This verifies every declared handoff file while
    keeping execution independent from a prior event or task ID.
    """

    input_path = context.workspace_path(workspace, "inputs/Input", "inputs/Input")
    context.require_file(input_path, "inputs/Input", "inputs/Input")
    for relative in ("inputs/STRU", "inputs/KPT_band"):
        path = context.workspace_path(workspace, relative, relative)
        context.require_file(path, relative, relative)

    try:
        input_text = input_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ForgePreconditionError("prepared inputs/Input cannot be read") from error

    route_values: dict[str, tuple[str, ...]] = {}
    for line in input_text.splitlines():
        fields = line.strip().split(None, 1)
        if len(fields) != 2 or fields[0] not in {"HR_route", "SR_route", "rR_route"}:
            continue
        values = tuple(fields[1].split())
        if not values:
            raise ForgePreconditionError(f"prepared inputs/Input has an empty {fields[0]}")
        route_values[fields[0]] = values

    missing_routes = [name for name in ("HR_route", "SR_route", "rR_route") if name not in route_values]
    if missing_routes:
        raise ForgePreconditionError(
            "prepared inputs/Input is missing PyATB routes: " + ", ".join(missing_routes)
        )
    for route_name, routes in route_values.items():
        for route in routes:
            if Path(route).is_absolute():
                raise ForgePreconditionError(
                    f"prepared {route_name} must use workspace-relative routes"
                )
            relative = (Path("inputs") / route).as_posix()
            path = context.workspace_path(workspace, relative, route_name)
            context.require_file(path, relative, route_name)


def _runner_envelope(runner_result: object, *, workspace_rel: str) -> ForgeResultEnvelope:
    """Project a ``RunResult`` envelope while adding typed unit facts."""

    base = runner_result.to_envelope()  # type: ignore[attr-defined]
    diagnostics = dict(base.to_dict()["diagnostics"])
    diagnostics.update(
        {
            "capability": "pyatb-band",
            "task": "band",
            "unit": "pyatb",
            "engine": "pyatb",
            "dry_run": False,
            "returncode": runner_result.returncode,  # type: ignore[attr-defined]
        }
    )
    return ForgeResultEnvelope(
        operation="execute",
        workspace_rel=workspace_rel,
        status=base.status,
        artifacts=base.artifacts,
        metrics=base.metrics,
        checks=base.checks,
        warnings=base.warnings,
        diagnostics=diagnostics,
    )


__all__ = [
    "PyatbBandCollectService",
    "PyatbBandCollectServiceProtocol",
    "PyatbBandExecuteService",
    "PyatbBandExecuteServiceProtocol",
    "PyatbBandPrepareService",
    "PyatbBandPrepareServiceProtocol",
    "PyatbBandServiceSet",
]
