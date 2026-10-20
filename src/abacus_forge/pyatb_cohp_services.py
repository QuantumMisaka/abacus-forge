"""Typed prepare, execute and collect services for direct NAO PyATB COHP."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Callable

from abacus_forge.compatibility_records import unit_manifest
from abacus_forge.contracts import ForgeErrorEnvelope, ForgeResultEnvelope, OperationOutcome, OperationStatus
from abacus_forge.errors import ForgePreconditionError
from abacus_forge.pyatb_cohp import collect_pyatb_cohp, prepare_pyatb_cohp, _orbital_names
from abacus_forge.pyatb_cohp_contracts import (
    PyatbCohpCollectRequest, PyatbCohpExecuteRequest, PyatbCohpPrepareRequest,
)
from abacus_forge.pyatb_typed import _typed_destination
from abacus_forge.runner import LocalRunner
from abacus_forge.service_support import ServiceContext, _prepare_artifacts
from abacus_forge.workspace import Workspace

ServiceResult = OperationOutcome | ForgeErrorEnvelope


class _CohpContext(ServiceContext):
    def __init__(self, *, workspace_root: str | Path = ".",
                 runner_factory: Callable[..., object] = LocalRunner) -> None:
        super().__init__(workspace_root=workspace_root)
        self.runner_factory = runner_factory


class PyatbCohpPrepareService:
    def __init__(self, context: _CohpContext) -> None:
        self._context = context

    def prepare(self, request: PyatbCohpPrepareRequest) -> ServiceResult:
        if not isinstance(request, PyatbCohpPrepareRequest):
            return self._context.error("request.invalid", "expected PyatbCohpPrepareRequest", request)
        try:
            workspace = self._context.workspace(request.workspace_rel)
            with workspace.operation_guard(request.operation_id, request.operation) as owner_token:
                handoff = prepare_pyatb_cohp(workspace, request)
                workspace.write_json("forge-unit.json", unit_manifest(
                    task="cohp", unit="pyatb", engine="pyatb",
                    metadata={"pyatb_handoff": list(handoff)}))
                envelope = ForgeResultEnvelope(
                    operation="prepare", workspace_rel=request.workspace_rel,
                    status=OperationStatus(execution="not_run", scientific="unassessed",
                                           collection="not_collected"),
                    artifacts=_prepare_artifacts(workspace),
                    diagnostics={"capability": "pyatb-cohp", "engine": "pyatb",
                                 "method": "direct_nao", "population": "COHP",
                                 "pyatb_handoff": list(handoff)})
                return self._context.persist(workspace, request, envelope, owner_token=owner_token)
        except Exception as error:
            return self._context.error_from_exception(error, request)


def _require_prepared(context: _CohpContext, workspace: Workspace) -> None:
    root = workspace.root.resolve()
    for rel in ("inputs/Input", "inputs/STRU"):
        context.require_file(context.workspace_path(workspace, rel, rel), rel, rel)
    input_path = root / "inputs/Input"
    text = input_path.read_text(encoding="utf-8")
    blocks = re.findall(r"(?m)^\s*([A-Z][A-Z_]*)\s*\{", text)
    if blocks != ["INPUT_PARAMETERS", "LATTICE", "COHP"]:
        raise ForgePreconditionError("prepared COHP Input has unexpected blocks")
    routes = {}
    for row in text.splitlines():
        tokens = row.strip().split()
        if tokens and tokens[0] in {"HR_route", "SR_route", "stru_file", "orbital_dir", "output_prefix",
                                    "method", "kpoint_mode", "HR_unit", "sparse_format", "package"}:
            if tokens[0] in routes:
                raise ForgePreconditionError(f"prepared COHP Input duplicates {tokens[0]}")
            routes[tokens[0]] = tokens[1:]
    expected = {"stru_file": ["STRU"], "orbital_dir": ["."], "output_prefix": ["COHP"],
                "method": ["COHP"], "kpoint_mode": ["direct"], "HR_unit": ["Ry"],
                "sparse_format": ["1"], "package": ["ABACUS"]}
    if any(routes.get(name) != values for name, values in expected.items()):
        raise ForgePreconditionError("prepared COHP Input has unsafe routes")
    for name in ("HR_route", "SR_route"):
        values = routes.get(name)
        if not values:
            raise ForgePreconditionError(f"prepared COHP Input is missing {name}")
        for value in values:
            if not value.startswith("pyatb_sources/") or Path(value).name != value.split("/", 1)[1]:
                raise ForgePreconditionError(f"prepared COHP {name} has unsafe route")
            rel = "inputs/" + value
            context.require_file(context.workspace_path(workspace, rel, name), rel, name)
    for orbital in _orbital_names(root / "inputs/STRU"):
        rel = "inputs/" + orbital
        context.require_file(context.workspace_path(workspace, rel, "orbital"), rel, "orbital")
    # PyATB creates Out and clears Out/COHP on initialization.  LocalRunner
    # writes stdout/stderr with replacement, so those paths must also be new.
    for rel in ("inputs/Out", "outputs/stdout.log", "outputs/stderr.log"):
        path = _typed_destination(root, rel, "PyATB output")
        if path.exists() or path.is_symlink():
            raise ForgePreconditionError(f"PyATB output target already exists: {rel}")


class PyatbCohpExecuteService:
    def __init__(self, context: _CohpContext) -> None:
        self._context = context

    def execute(self, request: PyatbCohpExecuteRequest) -> ServiceResult:
        if not isinstance(request, PyatbCohpExecuteRequest):
            return self._context.error("request.invalid", "expected PyatbCohpExecuteRequest", request)
        try:
            workspace = self._context.workspace(request.workspace_rel)
            with workspace.operation_guard(request.operation_id, request.operation) as owner_token:
                _require_prepared(self._context, workspace)
                if request.dry_run:
                    status = OperationStatus(execution="skipped", scientific="unassessed", collection="not_collected")
                    envelope = ForgeResultEnvelope(operation="execute", workspace_rel=request.workspace_rel,
                        status=status, diagnostics={"capability": "pyatb-cohp", "engine": "pyatb",
                                                    "method": "direct_nao", "dry_run": True})
                else:
                    runner = self._context.runner_factory(
                        executable=request.executable, mpi_ranks=request.mpi_ranks,
                        omp_threads=request.omp_threads, timeout_seconds=request.timeout_seconds)
                    preflight = getattr(runner, "preflight", None)
                    if callable(preflight):
                        try:
                            preflight(workspace)
                        except FileNotFoundError as error:
                            raise ForgePreconditionError("configured PyATB executable is missing or not executable") from error
                    run = runner.run(workspace)
                    base = run.to_envelope()
                    diagnostics = dict(base.to_dict()["diagnostics"])
                    diagnostics.update(capability="pyatb-cohp", engine="pyatb", method="direct_nao",
                                       dry_run=False, returncode=run.returncode)
                    envelope = ForgeResultEnvelope(operation="execute", workspace_rel=request.workspace_rel,
                        status=base.status, artifacts=base.artifacts, metrics=base.metrics,
                        checks=base.checks, warnings=base.warnings, diagnostics=diagnostics)
                return self._context.persist(workspace, request, envelope, owner_token=owner_token)
        except Exception as error:
            return self._context.error_from_exception(error, request)


class PyatbCohpCollectService:
    def __init__(self, context: _CohpContext) -> None:
        self._context = context

    def collect(self, request: PyatbCohpCollectRequest) -> ServiceResult:
        if not isinstance(request, PyatbCohpCollectRequest):
            return self._context.error("request.invalid", "expected PyatbCohpCollectRequest", request)
        try:
            workspace = self._context.workspace(request.workspace_rel)
            with workspace.operation_guard(request.operation_id, request.operation) as owner_token:
                envelope = collect_pyatb_cohp(workspace, request)
                return self._context.persist(workspace, request, envelope, owner_token=owner_token)
        except Exception as error:
            return self._context.error_from_exception(error, request)


class PyatbCohpServiceSet:
    def __init__(self, *, workspace_root: str | Path = ".",
                 runner_factory: Callable[..., object] = LocalRunner,
                 context: _CohpContext | None = None) -> None:
        shared = context if context is not None else _CohpContext(
            workspace_root=workspace_root, runner_factory=runner_factory)
        self.prepare = PyatbCohpPrepareService(shared)
        self.execute = PyatbCohpExecuteService(shared)
        self.collect = PyatbCohpCollectService(shared)

    @classmethod
    def default(cls, workspace_root: str | Path = ".",
                runner_factory: Callable[..., object] = LocalRunner) -> PyatbCohpServiceSet:
        return cls(workspace_root=workspace_root, runner_factory=runner_factory)
