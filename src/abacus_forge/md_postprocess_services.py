"""Service boundary for the explicit typed MD postprocess operation."""
from __future__ import annotations

import hashlib
import json
import mimetypes
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, runtime_checkable

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
            trajectory = self._context.workspace_path(workspace, request.trajectory_path_rel, "trajectory_path_rel")
            output_dir = self._context.workspace_path(workspace, request.output_dir_rel, "output_dir_rel")
            report_rel = f"{_REPORT_DIR}/{request.operation_id}.json"
            report = self._context.workspace_path(workspace, report_rel, "postprocess report")
            self._preflight(workspace, trajectory, output_dir, report)
            with workspace.operation_guard(request.operation_id, request.operation) as owner_token:
                self._context.require_file(trajectory, request.trajectory_path_rel, "trajectory_path_rel")
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
                try:
                    json.dumps(result.results, allow_nan=False, default=lambda value: value.tolist())
                except (TypeError, ValueError) as error:
                    raise ForgePreconditionError("MD algorithm returned non-finite or non-JSON results") from error
                try:
                    json.dumps({"summary": result.summary, "diagnostics": result.diagnostics, "sampling": result.sampling}, allow_nan=False, default=lambda value: value.tolist())
                except (TypeError, ValueError) as error:
                    raise ForgePreconditionError("MD algorithm returned invalid factual metadata") from error
                source_path = output_dir / "trajectory_source.json"
                try:
                    source_path.parent.mkdir(parents=True, exist_ok=True)
                    source_path.write_text(json.dumps({"schema_version": "forge.md-trajectory-source/v1", "trajectory_path_rel": request.trajectory_path_rel, "sampling": result.sampling}, sort_keys=True, allow_nan=False, indent=2) + "\n", encoding="utf-8")
                except OSError as error:
                    raise ForgePersistenceError("unable to persist trajectory source manifest") from error
                names = tuple(result.generated_files)
                if len(names) != len(set(names)):
                    raise ForgeRequestError("generated MD output names must be unique")
                if any(not isinstance(name, str) or not name or Path(name).is_absolute() or Path(name).name != name or name in {".", "..", "trajectory_source.json"} for name in names):
                    raise ForgePathError("generated MD output names must be direct relative files")
                if "analysis.json" not in names:
                    names = names + ("analysis.json",)
                generated = tuple(output_dir / name for name in names) + (source_path,)
                for path in generated:
                    if path.resolve().parent != output_dir.resolve():
                        raise ForgePathError("generated MD output must remain directly under output_dir")
                present_generated = tuple(path for path in generated if path.is_file() and not path.is_symlink())
                missing_generated = len(present_generated) < len(generated)
                diagnostics = dict(result.diagnostics)
                diagnostics.update({"canonical_modes": list(request.analysis), "sampling": dict(result.sampling), "selected_trajectory_path_rel": request.trajectory_path_rel, "output_dir_rel": request.output_dir_rel, "generated_paths_rel": [path.relative_to(workspace.root).as_posix() for path in generated], "analysis_results": dict(result.summary), "report_path_rel": report_rel})
                expected_by_mode = self._expected_mode_files(request, result)
                missing_modes = [mode for mode, expected in expected_by_mode.items() if mode not in result.results or any(not (output_dir / name).is_file() for name in expected)]
                collection = "missing_output" if len(missing_modes) == len(request.analysis) else ("partial" if missing_modes or missing_generated else "complete")
                checks = tuple(CheckRecord(name=f"analysis.{mode}", status="warning" if mode in missing_modes or missing_generated else "passed", message="analysis output incomplete" if mode in missing_modes or missing_generated else None) for mode in request.analysis)
                metrics = (MetricRecord(name="sampled_frames", value=result.sampling["frame_count"], unit="frames", kind="runtime"),)
                artifacts = self._artifacts(workspace, trajectory, request.trajectory_path_rel, present_generated, report, report_rel)
                try:
                    report.parent.mkdir(parents=True, exist_ok=True)
                    report.write_text(json.dumps({"schema_version": "forge.md-postprocess-report/v1", "operation": request.operation, "workspace_rel": request.workspace_rel, "diagnostics": diagnostics}, sort_keys=True, allow_nan=False, indent=2) + "\n", encoding="utf-8")
                except OSError as error:
                    raise ForgePersistenceError("unable to persist MD postprocess report") from error
                artifacts = artifacts + (self._artifact(workspace, report, report_rel, "output", "postprocess-report"),)
                envelope = ForgeResultEnvelope(operation=request.operation, workspace_rel=request.workspace_rel, status=OperationStatus(execution="not_run", scientific="unassessed", collection=collection), artifacts=artifacts, metrics=metrics, checks=checks, diagnostics=diagnostics)
                return self._context.persist(workspace, request, envelope, owner_token=owner_token)
        except Exception as error:
            return self._context.error_from_exception(error, request)

    @staticmethod
    def _preflight(workspace: Workspace, trajectory: Path, output_dir: Path, report: Path) -> None:
        root = workspace.root.resolve()
        for path in (trajectory, output_dir, report):
            try: path.resolve(strict=False).relative_to(root)
            except ValueError as error: raise ForgePathError("MD postprocess path escapes workspace") from error
        if _overlap(output_dir, trajectory): raise ForgeRequestError("trajectory and output directory overlap")
        if _overlap(trajectory, report): raise ForgeRequestError("trajectory and report overlap")
        if _overlap(output_dir, report): raise ForgePathError("output overlaps audit report")
        reports = (root / "reports").resolve()
        for reserved in (reports, reports / "events", reports / "claims", reports / "forge-workspace.json", reports / ".forge-workspace.lock", reports / ".forge-operation.lock"):
            if _overlap(trajectory, reserved) or _overlap(output_dir, reserved):
                raise ForgePathError("MD postprocess path must not overlap Forge audit paths")
        for candidate in (trajectory, output_dir, report):
            current = root
            try: parts = candidate.relative_to(root).parts
            except ValueError as error: raise ForgePathError("MD postprocess path escapes workspace") from error
            for component in parts:
                current = current / component
                if current.is_symlink(): raise ForgePathError("MD postprocess paths must not use symlinks")

    @staticmethod
    def _expected_mode_files(request: MdPostprocessRequest, result: MdPostprocessResult) -> dict[str, tuple[str, ...]]:
        params = request.parameters
        data = params.get("save_data", True)
        plot = params.get("save_plot", True)
        expected: dict[str, tuple[str, ...]] = {}
        for mode in request.analysis:
            names: list[str] = []
            if data:
                if mode == "rdf":
                    names.extend(f"rdf_{pair.replace('-', '_')}.txt" for pair in result.results.get("rdf", {}))
                else:
                    names.append({"msd_diffusion": "msd.txt", "vacf_vdos": "vacf_vdos.txt", "bond_length": "bond_lengths.txt", "bond_angle": "bond_angles.txt"}[mode])
            if plot:
                if mode == "rdf":
                    names.extend(f"rdf_{pair.replace('-', '_')}.png" for pair in result.results.get("rdf", {}))
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


class MdPostprocessServiceSet:
    def __init__(self, *, workspace_root: str | Path = ".", context: ServiceContext | None = None, algorithm: Algorithm | None = None) -> None:
        context = context or ServiceContext(workspace_root=workspace_root)
        self.postprocess: MdPostprocessServiceProtocol = MdPostprocessService(context, algorithm=algorithm)

    @classmethod
    def default(cls, workspace_root: str | Path = ".") -> "MdPostprocessServiceSet":
        return cls(workspace_root=workspace_root)


__all__ = ["MdPostprocessServiceProtocol", "MdPostprocessService", "MdPostprocessServiceSet"]
