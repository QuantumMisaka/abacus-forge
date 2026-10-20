"""Workspace-safe typed collection of ABACUS polarization and BEC results."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath

from abacus_forge.contracts import ArtifactRecord, ForgeErrorEnvelope, ForgeResultEnvelope, OperationOutcome, OperationStatus
from abacus_forge.errors import ForgePathError, ForgePersistenceError, ForgeRequestError
from abacus_forge.export_io import _destination, _new_temporary_file, _open_destination_directory
from abacus_forge.polarization_contracts import BecPostprocessRequest, PolarizationCollectRequest
from abacus_forge.service_support import ServiceContext
from abacus_forge.workspace import Workspace

ServiceResult = OperationOutcome | ForgeErrorEnvelope
PolarizationParser = Callable[[Path, Path, Path], dict]
BecAlgorithm = Callable[..., dict]


def _artifact(path_rel: str, payload: bytes, *, role: str, stage: str) -> ArtifactRecord:
    return ArtifactRecord(
        id=f"{role}-{hashlib.sha256(path_rel.encode('utf-8')).hexdigest()[:16]}",
        path_rel=path_rel, role=role, stage=stage,
        media_type="application/json" if path_rel.endswith(".json") else "application/octet-stream",
        sha256=hashlib.sha256(payload).hexdigest(), size_bytes=len(payload),
    )


def _preflight(context: ServiceContext, workspace: Workspace, output_rel: str, sources: tuple[str, ...]) -> Path:
    _, output = _destination(workspace, output_rel)
    # A contained parent alias is permitted, but a final symlink is an
    # already-occupied target and a parent alias may never reach audit files.
    _destination(workspace, output.relative_to(workspace.root).as_posix())
    if (workspace.root / output_rel).is_symlink():
        raise ForgeRequestError("output path already exists")
    for source_rel in sources:
        source = context.workspace_path(workspace, source_rel, "source path")
        if source == output or source_rel == output_rel:
            raise ForgePathError("output path must not overlap a source")
    if output.exists() or output.is_symlink():
        raise ForgeRequestError("output path already exists")
    return output


def _write_json_new(workspace: Workspace, path_rel: str, value: Mapping[str, object]) -> bytes:
    try:
        payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ForgeRequestError("result is not JSON-safe") from error
    # Resolve a contained parent symlink once, then anchor publication to its
    # physical workspace-relative directory with no-follow directory FDs.
    _, destination = _destination(workspace, path_rel)
    physical_rel = destination.relative_to(workspace.root).as_posix()
    parent_fd = _open_destination_directory(workspace, physical_rel)
    target_name = PurePosixPath(physical_rel).name
    temporary_name: str | None = None
    temporary_fd: int | None = None
    try:
        temporary_name, temporary_fd = _new_temporary_file(parent_fd, target_name)
        with os.fdopen(temporary_fd, "wb") as stream:
            temporary_fd = None
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary_name, target_name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd, follow_symlinks=False)
        except FileExistsError as error:
            raise ForgeRequestError("output path already exists") from error
        os.fsync(parent_fd)
        return payload
    except OSError as error:
        raise ForgePersistenceError("unable to publish property result") from error
    finally:
        if temporary_fd is not None:
            os.close(temporary_fd)
        if temporary_name is not None:
            try:
                os.unlink(temporary_name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        os.close(parent_fd)


def _outcome(context: ServiceContext, workspace: Workspace, request: PolarizationCollectRequest | BecPostprocessRequest,
             owner_token: str, *, collection: str, artifacts: list[ArtifactRecord], diagnostics: dict) -> OperationOutcome:
    envelope = ForgeResultEnvelope(
        operation=request.operation, workspace_rel=request.workspace_rel,
        status=OperationStatus(execution="not_run", scientific="unassessed", collection=collection),
        artifacts=tuple(artifacts), diagnostics=diagnostics,
    )
    return context.persist(workspace, request, envelope, owner_token=owner_token)


def _replace_source_path(fact: dict, path_rel: str) -> dict:
    normalized = dict(fact)
    normalized["source_log_path"] = path_rel
    rows = normalized.get("rows")
    if isinstance(rows, Mapping):
        normalized["rows"] = {
            key: {**row, "source_log_path": path_rel} if isinstance(row, Mapping) else row
            for key, row in rows.items()
        }
    return normalized


class PolarizationCollectService:
    def __init__(self, context: ServiceContext, *, parser: PolarizationParser | None = None) -> None:
        self._context = context
        self._parser = parser

    def collect(self, request: PolarizationCollectRequest) -> ServiceResult:
        if not isinstance(request, PolarizationCollectRequest):
            return self._context.error("request.invalid", "expected PolarizationCollectRequest", request)
        try:
            context = self._context
            workspace = context.workspace(request.workspace_rel)
            source_rels = (request.log_path_rel, request.structure_path_rel, request.input_path_rel)
            output = _preflight(context, workspace, request.output_path_rel, source_rels)
            sources = [context.workspace_path(workspace, rel, "source path") for rel in source_rels]
            with workspace.operation_guard(request.operation_id, request.operation) as token:
                artifacts: list[ArtifactRecord] = []
                missing: list[str] = []
                for rel, path in zip(source_rels, sources, strict=True):
                    if not path.is_file():
                        missing.append(rel)
                        continue
                    artifacts.append(_artifact(rel, path.read_bytes(), role="input", stage="collect"))
                diagnostics: dict = {"missing_source_paths_rel": missing, "output_path_rel": request.output_path_rel}
                if missing:
                    return _outcome(context, workspace, request, token, collection="missing_output",
                                    artifacts=artifacts, diagnostics=diagnostics)
                if self._parser is None:
                    from abacus_forge.polarization import collect_polarization_facts
                    parser = collect_polarization_facts
                else:
                    parser = self._parser
                try:
                    fact = parser(*sources)
                    if not isinstance(fact, Mapping) or fact.get("schema_version") != "forge.polarization/v1":
                        raise ValueError("parser did not return forge.polarization/v1 facts")
                    fact = _replace_source_path(dict(fact), request.log_path_rel)
                    output_payload = _write_json_new(workspace, request.output_path_rel, fact)
                except (ValueError, OSError) as error:
                    diagnostics["collection_error"] = str(error)
                    return _outcome(context, workspace, request, token, collection="partial",
                                    artifacts=artifacts, diagnostics=diagnostics)
                artifacts.append(_artifact(request.output_path_rel, output_payload, role="output", stage="collect"))
                diagnostics["fact_schema_version"] = fact["schema_version"]
                return _outcome(context, workspace, request, token, collection="complete",
                                artifacts=artifacts, diagnostics=diagnostics)
        except Exception as error:
            return self._context.error_from_exception(error, request)


class BecPostprocessService:
    def __init__(self, context: ServiceContext, *, algorithm: BecAlgorithm | None = None) -> None:
        self._context = context
        self._algorithm = algorithm

    def postprocess(self, request: BecPostprocessRequest) -> ServiceResult:
        if not isinstance(request, BecPostprocessRequest):
            return self._context.error("request.invalid", "expected BecPostprocessRequest", request)
        try:
            context = self._context
            workspace = context.workspace(request.workspace_rel)
            columns = request.to_dict()["columns"]
            source_rels = tuple(dict.fromkeys(
                path for column in columns for sample in column["samples"]
                for path in sample["polarization_paths_rel"]
            ))
            _preflight(context, workspace, request.output_path_rel, source_rels)
            paths = {rel: context.workspace_path(workspace, rel, "polarization_paths_rel") for rel in source_rels}
            with workspace.operation_guard(request.operation_id, request.operation) as token:
                artifacts: list[ArtifactRecord] = []
                facts: dict[str, dict] = {}
                missing: list[str] = []
                invalid: list[str] = []
                for rel, path in paths.items():
                    if not path.is_file():
                        missing.append(rel)
                        continue
                    try:
                        payload = path.read_bytes()
                        artifacts.append(_artifact(rel, payload, role="input", stage="postprocess"))
                        fact = json.loads(payload, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
                        if not isinstance(fact, dict) or fact.get("schema_version") != "forge.polarization/v1":
                            raise ValueError("not a polarization fact")
                        facts[rel] = fact
                    except (OSError, ValueError, UnicodeError):
                        invalid.append(rel)
                        # The numerical boundary distinguishes an explicitly
                        # invalid fact from an absent path in each column.
                        facts[rel] = {"schema_version": "forge.invalid-polarization/v1"}
                if self._algorithm is None:
                    from abacus_forge.bec import calculate_bec
                    algorithm = calculate_bec
                else:
                    algorithm = self._algorithm
                result = algorithm(columns, facts, branch_mode=request.branch_mode,
                                   max_step_fraction=request.max_step_fraction)
                if not isinstance(result, Mapping) or result.get("schema_version") != "forge.bec/v1" or not isinstance(result.get("requested_complete"), bool):
                    raise ForgeRequestError("BEC algorithm returned invalid result")
                output_payload = _write_json_new(workspace, request.output_path_rel, result)
                artifacts.append(_artifact(request.output_path_rel, output_payload, role="output", stage="postprocess"))
                usable_facts = len(facts) - len(invalid)
                collection = "complete" if result["requested_complete"] else (
                    "partial" if usable_facts or result.get("computed_columns") else "missing_output"
                )
                diagnostics = {"missing_source_paths_rel": missing, "invalid_source_paths_rel": invalid,
                               "requested_complete": result["requested_complete"],
                               "full_tensor_complete": result.get("full_tensor_complete"),
                               "output_path_rel": request.output_path_rel}
                return _outcome(context, workspace, request, token, collection=collection,
                                artifacts=artifacts, diagnostics=diagnostics)
        except Exception as error:
            return self._context.error_from_exception(error, request)


class PolarizationServiceSet:
    def __init__(self, *, workspace_root: str | Path = ".", parser: PolarizationParser | None = None) -> None:
        self.collect = PolarizationCollectService(ServiceContext(workspace_root=workspace_root), parser=parser)

    @classmethod
    def default(cls, workspace_root: str | Path = ".", *, parser: PolarizationParser | None = None) -> PolarizationServiceSet:
        return cls(workspace_root=workspace_root, parser=parser)


class BecServiceSet:
    def __init__(self, *, workspace_root: str | Path = ".", algorithm: BecAlgorithm | None = None) -> None:
        self.postprocess = BecPostprocessService(ServiceContext(workspace_root=workspace_root), algorithm=algorithm)

    @classmethod
    def default(cls, workspace_root: str | Path = ".", *, algorithm: BecAlgorithm | None = None) -> BecServiceSet:
        return cls(workspace_root=workspace_root, algorithm=algorithm)
