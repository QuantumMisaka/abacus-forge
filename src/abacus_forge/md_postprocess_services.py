"""Service boundary for the explicit typed MD postprocess operation."""
from __future__ import annotations

import hashlib
import json
import mimetypes
import math
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .contracts import ArtifactRecord, CheckRecord, ForgeErrorEnvelope, ForgeResultEnvelope, MetricRecord, OperationOutcome, OperationStatus
from .errors import ForgePathError, ForgePersistenceError, ForgePreconditionError, ForgeRequestError
from .md_postprocess import MdPostprocessResult, run_md_postprocess
from .md_postprocess_contracts import MdPostprocessRequest
from .service_support import ServiceContext
from .workspace import Workspace

ServiceResult = OperationOutcome | ForgeErrorEnvelope
Algorithm = Callable[..., MdPostprocessResult]
_REPORT_DIR = "reports/postprocess"


@runtime_checkable
class MdPostprocessServiceProtocol(Protocol):
    def postprocess(self, request: MdPostprocessRequest) -> ServiceResult: ...


class MdPostprocessService:
    def __init__(self, context: ServiceContext, *, algorithm: Algorithm | None = None) -> None:
        self._context = context
        self._algorithm = algorithm or run_md_postprocess

    def postprocess(self, request: MdPostprocessRequest) -> ServiceResult:
        if not isinstance(request, MdPostprocessRequest):
            return self._context.error("request.invalid", "expected MdPostprocessRequest", request)
        try:
            workspace = self._context.workspace(request.workspace_rel)
            report_rel = f"{_REPORT_DIR}/{request.operation_id}.json"
            # Keep the declared lexical paths until preflight has inspected
            # every component.  ``ServiceContext.workspace_path`` resolves
            # symlinks eagerly, which would otherwise make an in-workspace
            # symlink indistinguishable from the exact path the caller named.
            trajectory_raw = workspace.root / request.trajectory_path_rel
            output_dir_raw = workspace.root / request.output_dir_rel
            report_raw = workspace.root / report_rel
            self._preflight(workspace, trajectory_raw, output_dir_raw, report_raw)
            trajectory = trajectory_raw.resolve(strict=False)
            output_dir = output_dir_raw.resolve(strict=False)
            report = report_raw.resolve(strict=False)
            with workspace.operation_guard(request.operation_id, request.operation) as owner_token:
                # Recheck lexical components after durable admission so a
                # path mutation between preflight and admission cannot turn a
                # previously safe declaration into a symlink alias.
                self._preflight(workspace, trajectory_raw, output_dir_raw, report_raw)
                trajectory = trajectory_raw.resolve(strict=False)
                output_dir = output_dir_raw.resolve(strict=False)
                report = report_raw.resolve(strict=False)
                self._context.require_file(trajectory, request.trajectory_path_rel, "trajectory_path_rel")
                output_before = _output_snapshot(output_dir)
                try:
                    result = self._algorithm(
                        trajectory, request.analysis, output_dir=output_dir, start=request.start,
                        end=request.end, stride=request.stride, parameters=request.parameters,
                    )
                except ValueError as error:
                    # Once admitted, malformed trajectory content, sampling,
                    # cell, or analysis preconditions are durable operation
                    # facts rather than request/path validation failures.
                    raise ForgePreconditionError(str(error)) from error
                except OSError as error:
                    raise ForgePersistenceError("MD algorithm I/O failed") from error
                if not isinstance(result, MdPostprocessResult):
                    raise ForgeRequestError("MD algorithm returned an invalid result")
                safe_results = _safe_json_mapping(result.results, "MD algorithm results")
                safe_summary = _safe_json_mapping(result.summary, "MD algorithm summary")
                safe_diagnostics = _safe_json_mapping(result.diagnostics, "MD algorithm diagnostics")
                safe_sampling = _safe_json_mapping(result.sampling, "MD algorithm sampling")
                frame_count = safe_sampling.get("frame_count")
                if isinstance(frame_count, bool) or not isinstance(frame_count, int) or frame_count < 1:
                    raise ForgeRequestError("MD algorithm sampling must include a positive frame_count")
                try:
                    names = tuple(result.generated_files)
                except (TypeError, ValueError) as error:
                    raise ForgeRequestError("MD algorithm generated_files must be a sequence") from error
                if any(not isinstance(name, str) for name in names):
                    raise ForgeRequestError("MD algorithm generated_files must contain strings")
                if len(names) != len(set(names)):
                    raise ForgeRequestError("generated MD output names must be unique")
                if any(
                    not name
                    or Path(name).is_absolute()
                    or Path(name).name != name
                    or "\\" in name
                    or "\x00" in name
                    or name in {".", "..", "trajectory_source.json"}
                    for name in names
                ):
                    raise ForgePathError("generated MD output names must be direct relative files")
                expected_by_mode = self._expected_mode_files(request, safe_results)
                allowed_names = {name for values in expected_by_mode.values() for name in values}
                allowed_names.add("analysis.json")
                if any(name not in allowed_names for name in names):
                    raise ForgeRequestError("MD algorithm returned an undeclared output")
                if "analysis.json" not in names:
                    names = names + ("analysis.json",)
                source_path = output_dir / "trajectory_source.json"
                generated = tuple(output_dir / name for name in names) + (source_path,)
                for path in generated:
                    if path.is_symlink() or path.resolve().parent != output_dir.resolve():
                        raise ForgePathError("generated MD output must remain directly under output_dir")
                try:
                    source_path.parent.mkdir(parents=True, exist_ok=True)
                    source_path.write_text(json.dumps({"schema_version": "forge.md-trajectory-source/v1", "trajectory_path_rel": request.trajectory_path_rel, "sampling": safe_sampling}, sort_keys=True, allow_nan=False, indent=2) + "\n", encoding="utf-8")
                except OSError as error:
                    raise ForgePersistenceError("unable to persist trajectory source manifest") from error
                present_generated = tuple(
                    path
                    for path in generated
                    if path.is_file()
                    and not path.is_symlink()
                    and (path == source_path or _output_changed(path, output_before))
                )
                missing_generated = len(present_generated) < len(generated)
                diagnostics = dict(safe_diagnostics)
                diagnostics.update({"canonical_modes": list(request.analysis), "sampling": safe_sampling, "selected_trajectory_path_rel": request.trajectory_path_rel, "output_dir_rel": request.output_dir_rel, "generated_paths_rel": [path.relative_to(workspace.root).as_posix() for path in generated], "analysis_results": safe_summary, "report_path_rel": report_rel})
                fresh_names = {path.name for path in present_generated}
                missing_modes = [mode for mode, expected in expected_by_mode.items() if mode not in safe_results or any(name not in fresh_names for name in expected)]
                collection = "missing_output" if len(missing_modes) == len(request.analysis) else ("partial" if missing_modes or missing_generated else "complete")
                checks = tuple(CheckRecord(name=f"analysis.{mode}", status="warning" if mode in missing_modes or missing_generated else "passed", message="analysis output incomplete" if mode in missing_modes or missing_generated else None) for mode in request.analysis)
                artifacts = self._artifacts(workspace, trajectory, request.trajectory_path_rel, present_generated, report, report_rel)
                metrics = [MetricRecord(name="sampled_frames", value=frame_count, unit="frames", kind="runtime")]
                analysis_artifact = next(
                    (
                        artifact
                        for artifact in artifacts
                        if artifact.path_rel
                        == f"{request.output_dir_rel}/analysis.json"
                    ),
                    None,
                )
                diffusion = _reported_diffusion_metric(
                    request,
                    safe_results,
                    analysis_artifact,
                )
                if diffusion is not None:
                    metrics.append(diffusion)
                try:
                    report.parent.mkdir(parents=True, exist_ok=True)
                    report_diagnostics = dict(diagnostics)
                    # The operation ID already identifies the report path and
                    # event.  Keeping it out of the report bytes makes the
                    # factual API/CLI projections comparable across isolated
                    # workspaces with different IDs.
                    report_diagnostics.pop("report_path_rel", None)
                    report.write_text(json.dumps({"schema_version": "forge.md-postprocess-report/v1", "operation": request.operation, "workspace_rel": request.workspace_rel, "diagnostics": report_diagnostics}, sort_keys=True, allow_nan=False, indent=2) + "\n", encoding="utf-8")
                except OSError as error:
                    raise ForgePersistenceError("unable to persist MD postprocess report") from error
                artifacts = artifacts + (self._artifact(workspace, report, report_rel, "output", "postprocess-report"),)
                envelope = ForgeResultEnvelope(operation=request.operation, workspace_rel=request.workspace_rel, status=OperationStatus(execution="not_run", scientific="unassessed", collection=collection), artifacts=artifacts, metrics=tuple(metrics), checks=checks, diagnostics=diagnostics)
                return self._context.persist(workspace, request, envelope, owner_token=owner_token)
        except Exception as error:
            return self._context.error_from_exception(error, request)

    @staticmethod
    def _preflight(workspace: Workspace, trajectory: Path, output_dir: Path, report: Path) -> None:
        root = workspace.root.resolve()
        for path in (trajectory, output_dir, report):
            try:
                relative = path.relative_to(root)
            except ValueError as error:
                raise ForgePathError("MD postprocess path escapes workspace") from error
            current = root
            for component in relative.parts:
                current = current / component
                if current.is_symlink():
                    raise ForgePathError("MD postprocess paths must not use symlinks")
            try: path.resolve(strict=False).relative_to(root)
            except ValueError as error: raise ForgePathError("MD postprocess path escapes workspace") from error
        if _overlap(output_dir, trajectory): raise ForgeRequestError("trajectory and output directory overlap")
        if _overlap(trajectory, report): raise ForgeRequestError("trajectory and report overlap")
        if _overlap(output_dir, report): raise ForgePathError("output overlaps audit report")
        reports = (root / "reports").resolve()
        for reserved in (reports, reports / "events", reports / "claims", reports / "forge-workspace.json", reports / ".forge-workspace.lock", reports / ".forge-operation.lock"):
            if _overlap(trajectory, reserved) or _overlap(output_dir, reserved):
                raise ForgePathError("MD postprocess path must not overlap Forge audit paths")
        if output_dir.is_dir():
            try:
                if any(child.is_symlink() for child in output_dir.iterdir()):
                    raise ForgePathError("MD postprocess output directory must not contain symlinks")
            except OSError as error:
                raise ForgePersistenceError("unable to inspect MD postprocess output directory") from error

    @staticmethod
    def _expected_mode_files(request: MdPostprocessRequest, results: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
        params = request.parameters
        data = params.get("save_data", True)
        plot = params.get("save_plot", True)
        expected: dict[str, tuple[str, ...]] = {}
        for mode in request.analysis:
            names: list[str] = []
            if data:
                if mode == "rdf":
                    names.extend(_rdf_output_name(pair, suffix="txt") for pair in _rdf_result_pairs(results.get("rdf", {})))
                else:
                    names.append({"msd_diffusion": "msd.txt", "vacf_vdos": "vacf_vdos.txt", "bond_length": "bond_lengths.txt", "bond_angle": "bond_angles.txt"}[mode])
            if plot:
                if mode == "rdf":
                    names.extend(_rdf_output_name(pair, suffix="png") for pair in _rdf_result_pairs(results.get("rdf", {})))
                else:
                    names.append({"msd_diffusion": "msd.png", "vacf_vdos": "vacf_vdos.png", "bond_length": "bond_lengths.png", "bond_angle": "bond_angles.png"}[mode])
            expected[mode] = tuple(names)
        return expected

    @classmethod
    def _artifacts(cls, workspace: Workspace, trajectory: Path, trajectory_rel: str, generated: tuple[Path, ...], report: Path, report_rel: str) -> tuple[ArtifactRecord, ...]:
        values = [cls._artifact(workspace, trajectory, trajectory_rel, "input", "trajectory")]
        values.extend(cls._artifact(workspace, path, path.relative_to(workspace.root).as_posix(), "provenance_manifest" if path.name == "trajectory_source.json" else "output", "md-postprocess") for path in generated)
        return tuple(values)

    @staticmethod
    def _artifact(workspace: Workspace, path: Path, rel: str, role: str, prefix: str) -> ArtifactRecord:
        try:
            content = path.read_bytes(); size = path.stat().st_size
        except OSError as error:
            raise ForgePersistenceError("unable to hash MD postprocess artifact") from error
        digest = hashlib.sha256(content).hexdigest()
        return ArtifactRecord(id=f"{prefix}-{rel.replace('/', '-').replace('.', '-')}", path_rel=rel, role=role, stage="postprocess", media_type=mimetypes.guess_type(rel)[0] or "application/octet-stream", sha256=digest, size_bytes=size)


def _overlap(left: Path, right: Path) -> bool:
    """Return true when either path is an ancestor of the other."""
    a, b = left.resolve(strict=False), right.resolve(strict=False)
    return a == b or a in b.parents or b in a.parents


_ABSOLUTE_PATH = re.compile(r"(?<![A-Za-z0-9_])/(?:[^\s/:]+/)*[^\s/:]+")


def _safe_json_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ForgeRequestError(f"{label} must be a JSON object")
    normalized = _safe_json_value(value, label=label, active=set())
    if not isinstance(normalized, dict):
        raise ForgeRequestError(f"{label} must be a JSON object")
    return normalized


def _safe_json_value(value: object, *, label: str, active: set[int]) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        if isinstance(value, str):
            return _ABSOLUTE_PATH.sub("<path>", value)
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ForgeRequestError(f"{label} must contain finite JSON values")
        return value
    if isinstance(value, Path):
        return value.name
    marker = id(value)
    if marker in active:
        raise ForgeRequestError(f"{label} must not contain cyclic values")
    if isinstance(value, Mapping):
        active.add(marker)
        try:
            normalized: dict[str, Any] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise ForgeRequestError(f"{label} object keys must be strings")
                normalized[key] = _safe_json_value(item, label=label, active=active)
            return normalized
        finally:
            active.remove(marker)
    if isinstance(value, (list, tuple)):
        active.add(marker)
        try:
            return [_safe_json_value(item, label=label, active=active) for item in value]
        finally:
            active.remove(marker)
    # Numpy scalars and arrays are the only non-stdlib values produced by the
    # pure analysis layer.  Convert them without importing numpy at the
    # service boundary, then run the same finite/cycle checks recursively.
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        try:
            return _safe_json_value(tolist(), label=label, active=active)
        except (TypeError, ValueError, RecursionError) as error:
            raise ForgeRequestError(f"{label} must contain JSON-safe values") from error
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return _safe_json_value(item(), label=label, active=active)
        except (TypeError, ValueError, RecursionError) as error:
            raise ForgeRequestError(f"{label} must contain JSON-safe values") from error
    raise ForgeRequestError(f"{label} must contain JSON-safe values")


def _rdf_result_pairs(value: object) -> tuple[str, ...]:
    if not isinstance(value, Mapping):
        raise ForgeRequestError("MD algorithm RDF results must be an object")
    pairs: list[str] = []
    for pair in value:
        if not isinstance(pair, str) or pair.count("-") != 1 or not pair or "/" in pair or "\\" in pair:
            raise ForgeRequestError("MD algorithm RDF result pair is invalid")
        pairs.append(pair)
    return tuple(pairs)


def _rdf_output_name(pair: str, *, suffix: str) -> str:
    return f"rdf_{pair.replace('-', '_')}.{suffix}"


def _reported_diffusion_metric(
    request: MdPostprocessRequest,
    results: Mapping[str, Any],
    analysis_artifact: ArtifactRecord | None,
) -> MetricRecord | None:
    """Project only a finite, freshly contained MSD result as a metric."""
    if "msd_diffusion" not in request.analysis or analysis_artifact is None:
        return None
    value = results.get("msd_diffusion")
    if not isinstance(value, Mapping):
        return None
    diffusion = value.get("diffusion_angstrom2_per_fs")
    if (
        isinstance(diffusion, bool)
        or not isinstance(diffusion, (int, float))
    ):
        return None
    try:
        if not math.isfinite(diffusion):
            return None
    except (OverflowError, TypeError, ValueError):
        return None
    return MetricRecord(
        name="diffusion_coefficient",
        value=diffusion,
        unit="Angstrom^2/fs",
        kind="reported",
        source_artifact_id=analysis_artifact.id,
    )


def _output_snapshot(output_dir: Path) -> dict[Path, tuple[int, int, int]]:
    if not output_dir.is_dir():
        return {}
    try:
        return {
            path: (stat.st_size, stat.st_mtime_ns, stat.st_ino)
            for path in output_dir.iterdir()
            if path.is_file() and not path.is_symlink()
            for stat in (path.stat(),)
        }
    except OSError as error:
        raise ForgePersistenceError("unable to inspect MD postprocess output directory") from error


def _output_changed(path: Path, before: Mapping[Path, tuple[int, int, int]]) -> bool:
    try:
        stat = path.stat()
    except OSError:
        return False
    return before.get(path) != (stat.st_size, stat.st_mtime_ns, stat.st_ino)


class MdPostprocessServiceSet:
    def __init__(self, *, workspace_root: str | Path = ".", context: ServiceContext | None = None, algorithm: Algorithm | None = None) -> None:
        context = context or ServiceContext(workspace_root=workspace_root)
        self.postprocess: MdPostprocessServiceProtocol = MdPostprocessService(context, algorithm=algorithm)

    @classmethod
    def default(cls, workspace_root: str | Path = ".") -> "MdPostprocessServiceSet":
        return cls(workspace_root=workspace_root)


__all__ = ["MdPostprocessServiceProtocol", "MdPostprocessService", "MdPostprocessServiceSet"]
