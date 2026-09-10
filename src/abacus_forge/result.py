"""Structured results for run and collect primitives."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from abacus_forge.contracts import ArtifactRecord, CheckRecord, ForgeResultEnvelope, MetricRecord, OperationStatus


@dataclass(slots=True)
class RunResult:
    """Outcome of one runner invocation."""

    workspace: Path
    command: list[str]
    returncode: int
    status: str
    stdout_path: Path
    stderr_path: Path
    omp_threads: int
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {
            **payload,
            "workspace": str(self.workspace),
            "stdout_path": str(self.stdout_path),
            "stderr_path": str(self.stderr_path),
        }

    def to_envelope(self) -> ForgeResultEnvelope:
        execution = "completed" if self.status == "completed" and self.returncode == 0 else "failed"
        diagnostics, warnings = _diagnostics(self.diagnostics)
        warnings += _outside_artifact_warnings(self.workspace, {"stdout_log": str(self.stdout_path), "stderr_log": str(self.stderr_path)})
        if warnings:
            diagnostics["warnings"] = list(warnings)
        return ForgeResultEnvelope(
            operation="execute", workspace_rel=".",
            status=OperationStatus(execution=execution, scientific="unassessed", collection="not_collected"),
            artifacts=_workspace_artifact_records(self.workspace, {"stdout_log": str(self.stdout_path), "stderr_log": str(self.stderr_path)}, stage="execute"),
            metrics=_scalar_metric_records({"returncode": self.returncode, "omp_threads": self.omp_threads}, kind="runtime")[0],
            warnings=warnings, diagnostics=diagnostics,
        )


@dataclass(slots=True)
class TaskResult:
    """Outcome of one local composite task pack operation."""

    task: str
    workspace: Path
    status: str
    subtasks: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "workspace": str(self.workspace),
            "status": self.status,
            "subtasks": self.subtasks,
            "summary": self.summary,
            "artifacts": self.artifacts,
            "diagnostics": self.diagnostics,
        }

    def to_envelope(self) -> ForgeResultEnvelope:
        diagnostics, warnings = _diagnostics(self.diagnostics)
        dry_run = self.diagnostics.get("dry_run") is True
        execution = "skipped" if dry_run else ("completed" if self.status in {"completed", "prepared"} else "failed")
        # Legacy result envelopes retain the historical field for decoding,
        # but Forge never derives a scientific assessment from task status.
        scientific = "unassessed"
        collection = "not_collected" if dry_run else ("complete" if self.status == "completed" else "partial")
        artifacts = _workspace_artifact_records(self.workspace, self.artifacts)
        warnings += _outside_artifact_warnings(self.workspace, self.artifacts)
        if warnings:
            diagnostics["warnings"] = list(warnings)
        metrics, legacy_metrics = _scalar_metric_records(self.summary)
        diagnostics["legacy_metrics"] = legacy_metrics
        return ForgeResultEnvelope(operation="task", workspace_rel=".", status=OperationStatus(execution=execution, scientific=scientific, collection=collection), artifacts=artifacts, metrics=metrics, warnings=warnings, diagnostics=diagnostics)


@dataclass(slots=True)
class CollectionResult:
    """Parsed metrics and file index from one workspace."""

    workspace: Path
    status: str
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    inputs_snapshot: dict[str, Any] = field(default_factory=dict)
    structure_snapshot: dict[str, Any] | None = None
    final_structure_snapshot: dict[str, Any] | None = None
    # Parser provenance is an internal bridge to the typed collection
    # projection.  These trailing fields intentionally do not participate in
    # either legacy serialization surface below.
    metric_origins: dict[str, str] = field(default_factory=dict, repr=False, compare=False)
    derived_metrics: set[str] = field(default_factory=set, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace": str(self.workspace),
            "status": self.status,
            "metrics": self.metrics,
            "artifacts": self.artifacts,
            "diagnostics": self.diagnostics,
            "inputs_snapshot": self.inputs_snapshot,
            "structure_snapshot": self.structure_snapshot,
            "final_structure_snapshot": self.final_structure_snapshot,
        }

    def to_envelope(self) -> ForgeResultEnvelope:
        artifacts = _workspace_artifact_records(self.workspace, self.artifacts)
        metrics, legacy_metrics = _scalar_metric_records(self.metrics)
        converged = self.metrics.get("converged") is True
        diagnostics, warnings = _diagnostics(self.diagnostics)
        warnings += _outside_artifact_warnings(self.workspace, self.artifacts)
        if warnings:
            diagnostics["warnings"] = list(warnings)
        dry_run = self.status == "dry-run"
        diagnostics["legacy_metrics"] = legacy_metrics
        return ForgeResultEnvelope(
            operation="collect", workspace_rel=".",
            # Collection is an observation-only legacy projection.  It has no
            # policy context, so even a convergence marker is not acceptance.
            status=OperationStatus(execution="skipped" if dry_run else "not_run", scientific="unassessed", collection="not_collected" if dry_run else _collection_state(self.status)),
            artifacts=artifacts, metrics=metrics,
            checks=(CheckRecord(name="converged", status="passed" if converged else "warning"),),
            warnings=warnings, diagnostics=diagnostics,
        )


def _collection_state(legacy_status: str) -> str:
    return {"completed": "complete", "unfinished": "partial", "failed": "partial", "missing-output": "missing_output"}.get(legacy_status, "partial")


def _json_mapping(value: Any) -> dict[str, Any]:
    try:
        import json
        result = json.loads(json.dumps(value, allow_nan=False))
        return result if isinstance(result, dict) else {"value": result}
    except (TypeError, ValueError):
        return {"value": str(value)}


def _diagnostics(value: Any) -> tuple[dict[str, Any], tuple[str, ...]]:
    diagnostics = _json_mapping(value)
    raw_warnings = diagnostics.pop("warnings", [])
    warnings = tuple(str(item) for item in raw_warnings) if isinstance(raw_warnings, list) else (str(raw_warnings),)
    return diagnostics, warnings


def _scalar_metric_records(values: dict[str, Any], *, kind: str = "reported") -> tuple[tuple[MetricRecord, ...], dict[str, Any]]:
    metrics: list[MetricRecord] = []
    legacy: dict[str, Any] = {}
    for name, value in values.items():
        if value is None or isinstance(value, (bool, int, float, str)):
            metrics.append(MetricRecord(name=str(name), value=value, unit=None, kind=kind))
        else:
            legacy[str(name)] = _json_mapping(value).get("value", value)
    return tuple(metrics), legacy


def _workspace_artifact_records(workspace: Path, artifacts: dict[str, str], *, stage: str = "collect") -> tuple[ArtifactRecord, ...]:
    root = Path(workspace).resolve()
    records: list[ArtifactRecord] = []
    alias_counts: dict[str, int] = {}
    for name, raw_path in artifacts.items():
        path = Path(raw_path)
        try:
            resolved = path.resolve()
            rel = resolved.relative_to(root).as_posix()
        except (ValueError, OSError):
            continue
        if not rel or rel == ".":
            continue
        alias = "stdout_log" if rel in {"outputs/stdout.log", "stdout.log"} else "stderr_log" if rel in {"outputs/stderr.log", "stderr.log"} else None
        if alias is not None:
            alias_counts[alias] = alias_counts.get(alias, 0) + 1
            artifact_id = alias if alias_counts[alias] == 1 else f"{alias}__{alias_counts[alias]}"
        else:
            artifact_id = f"artifact-{__import__('hashlib').sha256(rel.encode()).hexdigest()[:12]}"
        size = resolved.stat().st_size if resolved.is_file() else None
        digest = None
        if resolved.is_file():
            digest = __import__('hashlib').sha256(resolved.read_bytes()).hexdigest()
        records.append(ArtifactRecord(id=artifact_id, path_rel=rel, role="output", stage=stage, sha256=digest, size_bytes=size))
    return tuple(records)


def _outside_artifact_warnings(workspace: Path, artifacts: dict[str, str]) -> tuple[str, ...]:
    root = Path(workspace).resolve()
    warnings: list[str] = []
    for name, raw_path in artifacts.items():
        try:
            Path(raw_path).resolve().relative_to(root)
        except (ValueError, OSError):
            warnings.append(f"Omitted artifact outside workspace: {name}")
    return tuple(warnings)
