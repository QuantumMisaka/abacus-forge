"""Typed band and DOS postprocess services.

The service boundary owns workspace admission, path containment and durable
audit.  The explicit algorithms in :mod:`abacus_forge.postprocess_algorithms`
only parse the already selected files and write the already admitted output
directory.
"""

from __future__ import annotations

import hashlib
import mimetypes
import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from abacus_forge.contracts import (
    ArtifactRecord,
    ForgeErrorEnvelope,
    ForgeResultEnvelope,
    JSONValue,
    Observation,
    OperationOutcome,
    OperationStatus,
    canonical_relative_path,
)
from abacus_forge.errors import (
    ForgePathError,
    ForgePersistenceError,
    ForgePreconditionError,
    ForgeRequestError,
)
from abacus_forge.postprocess_algorithms import (
    ExplicitPostprocessResult,
    PostprocessParseError,
    PostprocessPreconditionError,
    process_band_files,
    process_dos_files,
)
from abacus_forge.postprocess_contracts import BandPostprocessRequest, DosPostprocessRequest
from abacus_forge.service_support import ServiceContext
from abacus_forge.workspace import Workspace


PostprocessRequest = BandPostprocessRequest | DosPostprocessRequest
ServiceResult = OperationOutcome | ForgeErrorEnvelope
BandAlgorithm = Callable[..., ExplicitPostprocessResult]
DosAlgorithm = Callable[..., ExplicitPostprocessResult]


@runtime_checkable
class PostprocessService(Protocol):
    """Narrow postprocess protocol exposed to machine integrations."""

    def postprocess(self, request: PostprocessRequest) -> ServiceResult: ...


_RESERVED_FILES = (
    "reports/forge-workspace.json",
    "reports/.forge-workspace.lock",
    "reports/.forge-operation.lock",
)
_RESERVED_DIRECTORIES = ("reports/events", "reports/claims")
_REPORT_DIRECTORY = "reports/postprocess"


class BandPostprocessService:
    """Typed service for explicit band source files."""

    def __init__(self, context: ServiceContext, *, algorithm: BandAlgorithm | None = None) -> None:
        self._context = context
        self._algorithm = algorithm

    def postprocess(self, request: PostprocessRequest) -> ServiceResult:
        if not isinstance(request, BandPostprocessRequest):
            return self._context.error("request.invalid", "expected BandPostprocessRequest", request)
        return _run_postprocess(
            context=self._context,
            request=request,
            source_paths_rel=request.source_paths_rel,
            optional_paths_rel=(),
            output_dir_rel=request.output_dir_rel,
            output_names=_band_output_names(request),
            algorithm=self._algorithm or process_band_files,
            algorithm_kwargs={
                "plot_emin": request.plot_emin,
                "plot_emax": request.plot_emax,
                "save_data": request.save_data,
                "save_plot": request.save_plot,
            },
            capability="band",
        )


class DosPostprocessService:
    """Typed service for explicit total- and projected-DOS source files."""

    def __init__(self, context: ServiceContext, *, algorithm: DosAlgorithm | None = None) -> None:
        self._context = context
        self._algorithm = algorithm

    def postprocess(self, request: PostprocessRequest) -> ServiceResult:
        if not isinstance(request, DosPostprocessRequest):
            return self._context.error("request.invalid", "expected DosPostprocessRequest", request)
        optional_paths = tuple(
            path for path in (request.pdos_path_rel, request.tdos_path_rel) if path is not None
        )
        return _run_postprocess(
            context=self._context,
            request=request,
            source_paths_rel=request.dos_paths_rel,
            optional_paths_rel=optional_paths,
            output_dir_rel=request.output_dir_rel,
            output_names=_dos_output_names(request),
            algorithm=self._algorithm or process_dos_files,
            algorithm_kwargs={
                "include_tdos": request.include_tdos,
                "include_pdos": request.include_pdos,
                "pdos_mode": request.pdos_mode,
                "pdos_atom_indices": request.pdos_atom_indices,
                "plot_emin": request.plot_emin,
                "plot_emax": request.plot_emax,
                "save_data": request.save_data,
                "save_plot": request.save_plot,
                "suffix": request.suffix,
                "pdos_path": None,  # replaced with resolved paths below
                "tdos_path": None,
            },
            capability="dos",
            optional_argument_names=("pdos_path", "tdos_path"),
            optional_argument_values=(request.pdos_path_rel, request.tdos_path_rel),
        )


class PostprocessServiceSet:
    """Band and DOS services sharing one context and admission path."""

    def __init__(
        self,
        *,
        workspace_root: str | Path = ".",
        context: ServiceContext | None = None,
        band_algorithm: BandAlgorithm | None = None,
        dos_algorithm: DosAlgorithm | None = None,
    ) -> None:
        shared_context = context if context is not None else ServiceContext(workspace_root=workspace_root)
        self._context = shared_context
        self.band: PostprocessService = BandPostprocessService(shared_context, algorithm=band_algorithm)
        self.dos: PostprocessService = DosPostprocessService(shared_context, algorithm=dos_algorithm)

    @classmethod
    def default(cls, workspace_root: str | Path = ".") -> "PostprocessServiceSet":
        return cls(workspace_root=workspace_root)


def _run_postprocess(
    *,
    context: ServiceContext,
    request: PostprocessRequest,
    source_paths_rel: Sequence[str],
    optional_paths_rel: Sequence[str],
    output_dir_rel: str,
    output_names: Sequence[str],
    algorithm: Callable[..., ExplicitPostprocessResult],
    algorithm_kwargs: dict[str, object],
    capability: str,
    optional_argument_names: Sequence[str] = (),
    optional_argument_values: Sequence[str | None] = (),
) -> ServiceResult:
    """Run the common preflight/admission/algorithm/persistence sequence."""

    try:
        workspace = context.workspace(request.workspace_rel)
        source_paths = tuple(
            context.workspace_path(workspace, path_rel, "source_paths_rel")
            for path_rel in source_paths_rel
        )
        optional_paths = tuple(
            context.workspace_path(workspace, path_rel, "optional source path")
            for path_rel in optional_paths_rel
        )
        output_dir = context.workspace_path(workspace, output_dir_rel, "output_dir_rel")
        report_rel = f"{_REPORT_DIRECTORY}/{request.operation_id}.json"
        report_path = context.workspace_path(workspace, report_rel, "postprocess report")

        # This is deliberately a side-effect-free phase.  It resolves every
        # declared path and rejects symlink aliases, audit destinations and
        # source/output collisions before operation_guard can create a claim.
        _preflight_paths(
            workspace=workspace,
            source_paths=source_paths,
            source_paths_rel=source_paths_rel,
            optional_paths=optional_paths,
            optional_paths_rel=optional_paths_rel,
            output_dir=output_dir,
            output_dir_rel=output_dir_rel,
            output_names=output_names,
            report_path=report_path,
        )

        resolved_optional: dict[str, Path | None] = {}
        for name, path_rel in zip(optional_argument_names, optional_argument_values, strict=True):
            resolved_optional[name] = (
                context.workspace_path(workspace, path_rel, f"{name}_rel") if path_rel is not None else None
            )

        with workspace.operation_guard(request.operation_id, request.operation) as owner_token:
            # Existence is intentionally checked after durable admission.  A
            # missing declared source therefore cannot be replayed under the
            # same operation ID.
            for path, path_rel in zip(source_paths, source_paths_rel, strict=True):
                context.require_file(path, path_rel, "source_paths_rel")
            for path, path_rel in zip(optional_paths, optional_paths_rel, strict=True):
                context.require_file(path, path_rel, "optional source path")

            artifact_source_paths = tuple(source_paths) + tuple(optional_paths)
            artifact_source_paths_rel = tuple(source_paths_rel) + tuple(optional_paths_rel)
            output_state = _output_state(output_dir, output_names)

            algorithm_call_kwargs = dict(algorithm_kwargs)
            if optional_argument_names:
                algorithm_call_kwargs.update(resolved_optional)
            try:
                if capability == "dos":
                    pdos_argument = algorithm_call_kwargs.pop(
                        "pdos_path", resolved_optional.get("pdos_path")
                    )
                    tdos_argument = algorithm_call_kwargs.pop(
                        "tdos_path", resolved_optional.get("tdos_path")
                    )
                    result = algorithm(
                        source_paths,
                        pdos_argument,
                        tdos_argument,
                        output_dir,
                        **algorithm_call_kwargs,
                    )
                else:
                    result = algorithm(source_paths, output_dir, **algorithm_call_kwargs)
            except PostprocessParseError as error:
                missing_source_paths_rel = _missing_source_paths(
                    artifact_source_paths, artifact_source_paths_rel
                )
                if _has_os_error_cause(error) and not missing_source_paths_rel:
                    raise ForgePersistenceError("postprocess input/output persistence failed") from error
                diagnostics = _failure_diagnostics(
                    request=request,
                    source_paths_rel=artifact_source_paths_rel,
                    output_dir_rel=output_dir_rel,
                    error=error,
                    capability=capability,
                    generated_paths=_changed_generated_paths(
                        workspace, output_dir, output_names, before=output_state
                    ),
                )
                generated_paths = _paths_from_relative_names(workspace, diagnostics["generated_paths_rel"])
                if missing_source_paths_rel:
                    diagnostics["missing_source_paths_rel"] = list(missing_source_paths_rel)
                    diagnostics["collection_reason"] = "declared_source_disappeared_after_admission"
                    present_source_paths, present_source_paths_rel = _present_source_artifacts(
                        artifact_source_paths, artifact_source_paths_rel
                    )
                    return _persist_outcome(
                        context=context,
                        workspace=workspace,
                        request=request,
                        owner_token=owner_token,
                        source_paths=present_source_paths,
                        source_paths_rel=present_source_paths_rel,
                        generated_paths=generated_paths,
                        report_path=report_path,
                        report_rel=report_rel,
                        summary={},
                        diagnostics=diagnostics,
                        capability=capability,
                        status=OperationStatus(
                            execution="not_run", scientific="unassessed", collection="missing_output"
                        ),
                    )
                return _persist_outcome(
                    context=context,
                    workspace=workspace,
                    request=request,
                    owner_token=owner_token,
                    source_paths=artifact_source_paths,
                    source_paths_rel=artifact_source_paths_rel,
                    generated_paths=generated_paths,
                    report_path=report_path,
                    report_rel=report_rel,
                    summary={},
                    diagnostics=diagnostics,
                    capability=capability,
                    status=OperationStatus(
                        execution="not_run", scientific="unassessed", collection="partial"
                    ),
                )
            except PostprocessPreconditionError as error:
                raise _translate_algorithm_precondition(error) from error
            except OSError as error:
                raise ForgePersistenceError("postprocess output persistence failed") from error

            diagnostics = _success_diagnostics(
                result=result,
                request=request,
                source_paths_rel=artifact_source_paths_rel,
                output_dir_rel=output_dir_rel,
                workspace=workspace,
                output_dir=output_dir,
                capability=capability,
            )
            generated_paths = tuple(result.generated_paths)
            _validate_generated_paths(workspace, output_dir, generated_paths, output_names)
            missing_source_paths_rel = _missing_source_paths(
                artifact_source_paths, artifact_source_paths_rel
            )
            if missing_source_paths_rel:
                diagnostics["missing_source_paths_rel"] = list(missing_source_paths_rel)
                diagnostics["collection_reason"] = "declared_source_disappeared_after_admission"
                present_source_paths, present_source_paths_rel = _present_source_artifacts(
                    artifact_source_paths, artifact_source_paths_rel
                )
                return _persist_outcome(
                    context=context,
                    workspace=workspace,
                    request=request,
                    owner_token=owner_token,
                    source_paths=present_source_paths,
                    source_paths_rel=present_source_paths_rel,
                    generated_paths=generated_paths,
                    report_path=report_path,
                    report_rel=report_rel,
                    summary=result.summary,
                    diagnostics=diagnostics,
                    capability=capability,
                    status=OperationStatus(
                        execution="not_run", scientific="unassessed", collection="missing_output"
                    ),
                )
            usable = _has_usable_result(result, capability=capability, request=request)
            collection = _collection_status(
                result,
                capability=capability,
                request=request,
                usable=usable,
                output_dir=output_dir,
                output_names=output_names,
            )
            return _persist_outcome(
                context=context,
                workspace=workspace,
                request=request,
                owner_token=owner_token,
                source_paths=artifact_source_paths,
                source_paths_rel=artifact_source_paths_rel,
                generated_paths=generated_paths,
                report_path=report_path,
                report_rel=report_rel,
                summary=result.summary,
                diagnostics=diagnostics,
                capability=capability,
                status=OperationStatus(
                    execution="not_run", scientific="unassessed", collection=collection
                ),
            )
    except Exception as error:
        return context.error_from_exception(error, request)


def _preflight_paths(
    *,
    workspace: Workspace,
    source_paths: Sequence[Path],
    source_paths_rel: Sequence[str],
    optional_paths: Sequence[Path],
    optional_paths_rel: Sequence[str],
    output_dir: Path,
    output_dir_rel: str,
    output_names: Sequence[str],
    report_path: Path,
) -> None:
    _reject_symlink_components(workspace, workspace.root / "reports", "Forge audit paths")
    raw_output_dir = workspace.root / output_dir_rel
    _reject_symlink_components(workspace, raw_output_dir, "output_dir_rel")
    _reject_symlink_components(workspace, workspace.root / _REPORT_DIRECTORY, "postprocess report")
    if _is_reserved(workspace, output_dir) or _is_reserved(workspace, report_path):
        raise ForgePathError("postprocess output must not overlap Forge audit paths")
    if output_dir in source_paths or output_dir in optional_paths:
        raise ForgeRequestError("postprocess output directory collides with a source file")

    source_all = tuple(source_paths) + tuple(optional_paths)
    source_rel_all = tuple(source_paths_rel) + tuple(optional_paths_rel)
    for source, source_rel in zip(source_all, source_rel_all, strict=True):
        if _is_reserved(workspace, source):
            raise ForgePathError(f"source path is reserved for Forge audit: {Path(source_rel).name}")
        if source == report_path:
            raise ForgeRequestError("postprocess report collides with a source file")

    targets: list[Path] = []
    for name in output_names:
        # Output names come from typed flags and the explicit algorithms, but
        # still pass through containment and symlink checks at this boundary.
        target = workspace.root / output_dir_rel / name
        _reject_symlink_components(workspace, target, "postprocess output")
        resolved = target.resolve(strict=False)
        try:
            resolved.relative_to(workspace.root.resolve())
        except ValueError as error:
            raise ForgePathError("postprocess output must remain under workspace_rel") from error
        if _is_reserved(workspace, resolved):
            raise ForgePathError("postprocess output must not overlap Forge audit paths")
        if resolved == report_path:
            raise ForgeRequestError("postprocess output collides with report")
        if any(resolved == source for source in source_all):
            raise ForgeRequestError("postprocess output collides with a source file")
        targets.append(resolved)
    if len(targets) != len(set(targets)):
        raise ForgeRequestError("postprocess output targets must be distinct")


def _reject_symlink_components(workspace: Workspace, path: Path, field_name: str) -> None:
    """Reject symlink aliases for destinations while allowing absent leaves."""

    root = workspace.root.resolve()
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise ForgePathError(f"{field_name} must remain under workspace_rel") from error
    current = root
    for component in relative.parts:
        current = current / component
        if current.is_symlink():
            # ``workspace_path`` has already checked the resolved destination;
            # this additional check prevents an in-workspace symlink from
            # silently changing the logical output/report path.
            raise ForgePathError(f"{field_name} must not use a symlink")


def _is_reserved(workspace: Workspace, path: Path) -> bool:
    resolved = path.resolve(strict=False)
    root = workspace.root.resolve()
    for relative in _RESERVED_FILES:
        if resolved == (root / relative).resolve(strict=False):
            return True
    for relative in _RESERVED_DIRECTORIES:
        directory = (root / relative).resolve(strict=False)
        try:
            resolved.relative_to(directory)
        except ValueError:
            continue
        return True
    return False


def _band_output_names(request: BandPostprocessRequest) -> tuple[str, ...]:
    names: list[str] = []
    if request.save_data:
        names.append("band.dat")
    if request.save_plot:
        names.append("band.png")
    return tuple(names)


def _dos_output_names(request: DosPostprocessRequest) -> tuple[str, ...]:
    suffix = f"_{request.suffix}" if request.suffix else ""
    names: list[str] = []
    if request.include_tdos:
        if request.save_data:
            names.append(f"DOS{suffix}.dat")
        if request.save_plot:
            names.append(f"DOS{suffix}.png")
    if request.include_pdos and request.pdos_path_rel is not None:
        if request.save_data:
            names.append(f"PDOS{suffix}.dat")
        if request.save_plot:
            names.append(f"PDOS{suffix}.png")
    return tuple(names)


def _success_diagnostics(
    *,
    result: ExplicitPostprocessResult,
    request: PostprocessRequest,
    source_paths_rel: Sequence[str],
    output_dir_rel: str,
    workspace: Workspace,
    output_dir: Path,
    capability: str,
) -> dict[str, JSONValue]:
    diagnostics = _safe_json_mapping(result.diagnostics)
    diagnostics["summary"] = _safe_json_mapping(result.summary)
    diagnostics["selected_source_paths"] = list(source_paths_rel)
    diagnostics["output_dir_rel"] = output_dir_rel
    diagnostics["generated_paths_rel"] = [
        _relative_path(workspace, path) for path in result.generated_paths
    ]
    diagnostics["report_path_rel"] = f"{_REPORT_DIRECTORY}/{request.operation_id}.json"
    diagnostics["capability"] = capability
    # Keep the algorithm's basename facts, but normalize the path-bearing
    # generated list to workspace-relative paths for the typed envelope.
    diagnostics["generated_files"] = [Path(path).name for path in result.generated_paths]
    del output_dir
    return diagnostics


def _failure_diagnostics(
    *,
    request: PostprocessRequest,
    source_paths_rel: Sequence[str],
    output_dir_rel: str,
    error: Exception,
    capability: str,
    generated_paths: Sequence[str],
) -> dict[str, JSONValue]:
    return {
        "capability": capability,
        "summary": {},
        "source_files": [Path(path).name for path in source_paths_rel],
        "source_count": len(source_paths_rel),
        "selected_source_paths": list(source_paths_rel),
        "output_dir_rel": output_dir_rel,
        "generated_files": [Path(path).name for path in generated_paths],
        "generated_paths_rel": list(generated_paths),
        "parse_error": _safe_error_message(error),
        "report_path_rel": f"{_REPORT_DIRECTORY}/{request.operation_id}.json",
    }


def _persist_outcome(
    *,
    context: ServiceContext,
    workspace: Workspace,
    request: PostprocessRequest,
    owner_token: str,
    source_paths: Sequence[Path],
    source_paths_rel: Sequence[str],
    generated_paths: Sequence[Path],
    report_path: Path,
    report_rel: str,
    summary: dict[str, JSONValue],
    diagnostics: dict[str, JSONValue],
    capability: str,
    status: OperationStatus,
) -> OperationOutcome:
    # Write the factual report before assembling hashes so the report itself
    # can be represented as an output artifact.  This is the sole report write
    # for the operation and remains outside events/claims.
    report_diagnostics = _safe_json_mapping(diagnostics)
    # The operation ID is already part of the report filename and durable
    # event identity.  Omitting it from report contents keeps factual report
    # bytes stable across API/CLI parity runs with different operation IDs.
    report_diagnostics.pop("report_path_rel", None)
    report_payload: dict[str, JSONValue] = {
        "schema_version": "forge.postprocess-report/v1",
        "operation": request.operation,
        "workspace_rel": request.workspace_rel,
        "capability": capability,
        "summary": _safe_json_mapping(summary),
        "diagnostics": report_diagnostics,
    }
    try:
        workspace.write_json(report_rel, report_payload)
    except OSError as error:
        raise ForgePersistenceError("unable to persist postprocess report") from error

    raced_missing_source_paths: list[str] = []
    artifacts = _artifact_records(
        workspace=workspace,
        source_paths=source_paths,
        source_paths_rel=source_paths_rel,
        generated_paths=generated_paths,
        report_path=report_path,
        report_rel=report_rel,
        missing_source_paths_rel=raced_missing_source_paths,
    )
    envelope_diagnostics = dict(diagnostics)
    if raced_missing_source_paths:
        existing_missing = envelope_diagnostics.get("missing_source_paths_rel", ())
        if not isinstance(existing_missing, (list, tuple)):
            existing_missing = ()
        envelope_diagnostics["missing_source_paths_rel"] = sorted(
            set(list(existing_missing) + raced_missing_source_paths)
        )
        envelope_diagnostics["collection_reason"] = "declared_source_disappeared_after_admission"
        status = OperationStatus(execution="not_run", scientific="unassessed", collection="missing_output")
    envelope_diagnostics["report_path_rel"] = report_rel
    envelope = ForgeResultEnvelope(
        operation=request.operation,
        workspace_rel=request.workspace_rel,
        status=status,
        artifacts=artifacts,
        diagnostics=envelope_diagnostics,
    )
    extra_observations = _postprocess_observations(
        summary=summary,
        diagnostics=envelope_diagnostics,
        source_paths_rel=source_paths_rel,
    )
    return context.persist(
        workspace,
        request,
        envelope,
        owner_token=owner_token,
        extra_observations=extra_observations,
    )


def _artifact_records(
    *,
    workspace: Workspace,
    source_paths: Sequence[Path],
    source_paths_rel: Sequence[str],
    generated_paths: Sequence[Path],
    report_path: Path,
    report_rel: str,
    missing_source_paths_rel: list[str] | None = None,
) -> tuple[ArtifactRecord, ...]:
    records: list[ArtifactRecord] = []
    seen_paths: set[str] = set()
    seen_ids: set[str] = set()

    def add(
        path: Path,
        path_rel: str,
        role: str,
        prefix: str,
        *,
        stable_id: str | None = None,
    ) -> None:
        normalized = canonical_relative_path(path_rel)
        if normalized == "." or normalized in seen_paths:
            return
        if role == "input" and (not path.is_file() or path.is_symlink()):
            if missing_source_paths_rel is not None:
                missing_source_paths_rel.append(normalized)
            return
        if role == "output" and normalized != report_rel and (not path.is_file() or path.is_symlink()):
            # A parser/writer seam may report a requested target that vanished
            # before collection.  Keep the durable outcome factual and let the
            # collection predicate classify it as ``missing_output``.
            return
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            if role == "input" and missing_source_paths_rel is not None:
                missing_source_paths_rel.append(normalized)
                return
            raise
        try:
            resolved.relative_to(workspace.root.resolve())
        except ValueError as error:
            raise ForgePathError("artifact path escapes workspace") from error
        if not resolved.is_file():
            if role == "input" and missing_source_paths_rel is not None:
                missing_source_paths_rel.append(normalized)
                return
            raise ForgePreconditionError(f"artifact file not found: {normalized}")
        artifact_id = stable_id or _artifact_id(prefix, normalized)
        attempt = 1
        base_id = artifact_id
        while artifact_id in seen_ids:
            artifact_id = f"{base_id}-{attempt}"
            attempt += 1
        try:
            digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
            size = resolved.stat().st_size
        except FileNotFoundError:
            if role == "input" and missing_source_paths_rel is not None:
                missing_source_paths_rel.append(normalized)
                return
            raise
        except OSError as error:
            raise ForgePersistenceError("unable to hash postprocess artifact") from error
        records.append(
            ArtifactRecord(
                id=artifact_id,
                path_rel=normalized,
                role=role,
                stage="postprocess",
                media_type=mimetypes.guess_type(normalized)[0] or "application/octet-stream",
                sha256=digest,
                size_bytes=size,
            )
        )
        seen_paths.add(normalized)
        seen_ids.add(artifact_id)

    for path, path_rel in zip(source_paths, source_paths_rel, strict=True):
        add(path, path_rel, "input", "input")
    for path in generated_paths:
        add(path, _relative_path(workspace, path), "output", "output")
    add(report_path, report_rel, "output", "postprocess-report", stable_id="postprocess-report")
    return tuple(records)


def _artifact_id(prefix: str, path_rel: str) -> str:
    safe = path_rel.replace("/", "-").replace(".", "-").lower()
    return f"{prefix}-{safe}"


def _validate_generated_paths(
    workspace: Workspace,
    output_dir: Path,
    generated_paths: Sequence[Path],
    output_names: Sequence[str],
) -> None:
    expected = {output_dir / name for name in output_names}
    for path in generated_paths:
        resolved = path.resolve(strict=False)
        try:
            resolved.relative_to(workspace.root.resolve())
            resolved.relative_to(output_dir.resolve())
        except ValueError as error:
            raise ForgePathError("generated output must remain under output_dir") from error
        if resolved not in {item.resolve(strict=False) for item in expected}:
            raise ForgeRequestError("algorithm returned an undeclared postprocess output")
        if path.is_symlink():
            raise ForgePathError("generated output must not be a symlink")


def _changed_generated_paths(
    workspace: Workspace,
    output_dir: Path,
    output_names: Sequence[str],
    *,
    before: dict[Path, tuple[int, int]],
) -> tuple[str, ...]:
    values: list[str] = []
    for name in output_names:
        path = output_dir / name
        if not path.is_file() or path.is_symlink():
            continue
        current = (path.stat().st_size, path.stat().st_mtime_ns)
        if path.resolve(strict=False) in before and before[path.resolve(strict=False)] == current:
            continue
        values.append(_relative_path(workspace, path))
    return tuple(values)


def _output_state(output_dir: Path, output_names: Sequence[str]) -> dict[Path, tuple[int, int]]:
    state: dict[Path, tuple[int, int]] = {}
    for name in output_names:
        path = output_dir / name
        if path.is_file() and not path.is_symlink():
            state[path.resolve(strict=False)] = (path.stat().st_size, path.stat().st_mtime_ns)
    return state


def _missing_source_paths(
    source_paths: Sequence[Path], source_paths_rel: Sequence[str]
) -> tuple[str, ...]:
    return tuple(
        path_rel
        for path, path_rel in zip(source_paths, source_paths_rel, strict=True)
        if not path.is_file() or path.is_symlink()
    )


def _present_source_artifacts(
    source_paths: Sequence[Path], source_paths_rel: Sequence[str]
) -> tuple[tuple[Path, ...], tuple[str, ...]]:
    pairs = tuple(
        (path, path_rel)
        for path, path_rel in zip(source_paths, source_paths_rel, strict=True)
        if path.is_file() and not path.is_symlink()
    )
    return tuple(path for path, _ in pairs), tuple(path_rel for _, path_rel in pairs)


def _paths_from_relative_names(workspace: Workspace, values: object) -> tuple[Path, ...]:
    if not isinstance(values, list):
        return ()
    paths: list[Path] = []
    for value in values:
        if isinstance(value, str):
            paths.append(workspace.resolve_relative(value))
    return tuple(paths)


def _relative_path(workspace: Workspace, path: Path) -> str:
    try:
        return canonical_relative_path(path.resolve(strict=False).relative_to(workspace.root.resolve()).as_posix())
    except (OSError, RuntimeError, ValueError) as error:
        raise ForgePathError("artifact path escapes workspace") from error


def _collection_status(
    result: ExplicitPostprocessResult,
    *,
    capability: str,
    request: PostprocessRequest,
    usable: bool,
    output_dir: Path,
    output_names: Sequence[str],
) -> str:
    if not usable:
        return "missing_output"
    if output_names:
        generated = {
            path.resolve(strict=False)
            for path in result.generated_paths
            if path.is_file() and not path.is_symlink()
        }
        expected = {(output_dir / name).resolve(strict=False) for name in output_names}
        if not expected.issubset(generated):
            return "missing_output"
    if capability == "dos" and isinstance(request, DosPostprocessRequest):
        missing = result.diagnostics.get("missing_families")
        if isinstance(missing, list) and missing:
            return "partial"
    return "complete"


def _has_usable_result(
    result: ExplicitPostprocessResult,
    *,
    capability: str,
    request: PostprocessRequest,
) -> bool:
    if capability == "band":
        return bool(result.summary.get("num_points", 0))
    if isinstance(request, DosPostprocessRequest):
        total = result.summary.get("total_dos")
        projected = result.summary.get("projected_dos")
        return isinstance(total, dict) or isinstance(projected, dict)
    return False


def _translate_algorithm_precondition(error: PostprocessPreconditionError) -> Exception:
    message = str(error)
    lowered = message.lower()
    if "source" in lowered and ("not a regular file" in lowered or "not found" in lowered):
        return ForgePreconditionError(message)
    if "escape" in lowered or "symlink" in lowered:
        return ForgePathError(message)
    return ForgeRequestError(message)


def _has_os_error_cause(error: BaseException) -> bool:
    """Detect parser wrappers that intentionally preserve an I/O cause."""

    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, OSError):
            return True
        current = current.__cause__ or current.__context__
    return False


def _safe_json_mapping(value: object) -> dict[str, JSONValue]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _safe_json_value(item) for key, item in value.items()}


def _safe_json_value(value: object) -> JSONValue:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, str):
        return _redact_path_text(value)
    if isinstance(value, float):
        return value if value == value and value not in {float("inf"), float("-inf")} else None
    if isinstance(value, Mapping):
        return {str(key): _safe_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_json_value(item) for item in value]
    if isinstance(value, Path):
        return value.name
    if hasattr(value, "item"):
        try:
            return _safe_json_value(value.item())
        except (AttributeError, TypeError, ValueError):
            pass
    if hasattr(value, "tolist"):
        try:
            return _safe_json_value(value.tolist())
        except (AttributeError, TypeError, ValueError):
            pass
    return str(value)


def _safe_error_message(error: Exception) -> str:
    message = _redact_path_text(str(error))
    return message or "postprocess parser failed"


def _redact_path_text(message: str) -> str:
    # Algorithms are expected to report basenames, but this final redaction
    # protects the typed envelope if a lower-level parser includes a host path.
    return re.sub(r"(?<![A-Za-z0-9_])/(?:[^\s/:]+/)+[^\s/:]+", "<path>", message)


def _postprocess_observations(
    *,
    summary: dict[str, JSONValue],
    diagnostics: dict[str, JSONValue],
    source_paths_rel: Sequence[str],
) -> tuple[Observation, ...]:
    values: dict[str, JSONValue] = {
        "selected_source_paths": list(source_paths_rel),
    }
    for name in (
        "source_count",
        "numeric_rows",
        "generated_files",
        "generated_paths_rel",
        "missing_families",
        "parsed_families",
        "parse_error",
    ):
        if name in diagnostics:
            values[name] = diagnostics[name]
    for name in ("num_points", "num_kpoints", "num_bands", "num_columns"):
        if name in summary:
            values[name] = summary[name]
    total = summary.get("total_dos")
    if isinstance(total, dict):
        for name in ("points", "spin_channels", "energy_min", "energy_max"):
            if name in total:
                values[name] = total[name]
    projected = summary.get("projected_dos")
    if isinstance(projected, dict):
        for name in ("points", "orbitals", "spin_channels"):
            if name in projected and name not in values:
                values[name] = projected[name]
    return tuple(Observation(name=name, value=value, source="parser") for name, value in values.items())


__all__ = [
    "BandPostprocessService",
    "DosPostprocessService",
    "PostprocessService",
    "PostprocessServiceSet",
    "PostprocessRequest",
    "ServiceResult",
]
