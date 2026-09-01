"""Versioned, JSON-safe records at the Forge public boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Literal, Mapping, Sequence, TypeAlias


JSONValue: TypeAlias = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]

REQUEST_SCHEMA_VERSION = "forge.request/v1"
RESULT_SCHEMA_VERSION = "forge.result/v1"
WORKSPACE_SCHEMA_VERSION = "forge.workspace/v1"

_OPERATIONS = frozenset({"prepare", "modify", "execute", "collect", "export"})
_EXECUTION_STATUSES = frozenset({"not_run", "completed", "failed", "skipped"})
_SCIENTIFIC_STATUSES = frozenset({"unassessed", "accepted", "guarded", "rejected"})
_COLLECTION_STATUSES = frozenset({"not_collected", "complete", "partial", "missing_output"})
_CHECK_STATUSES = frozenset({"passed", "failed", "warning", "unavailable"})
_METRIC_KINDS = frozenset({"reported", "derived", "runtime"})


def _json_round_trip(value: object) -> JSONValue:
    """Return a canonical JSON value or raise a contract-level error."""
    try:
        serialized = json.dumps(value, allow_nan=False)
        return json.loads(serialized)
    except (TypeError, ValueError) as error:
        raise ValueError("value must be JSON-safe") from error


def _require_nonempty_string(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_literal(value: str, allowed: frozenset[str], field_name: str) -> None:
    if value not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise ValueError(f"{field_name} must be one of: {allowed_values}")


def _require_schema_version(value: str, expected: str) -> None:
    if value != expected:
        raise ValueError(f"schema_version must be {expected!r}")


def canonical_relative_path(value: str) -> str:
    """Validate and return a canonical relative POSIX path.

    ``.`` is reserved for a workspace root.  Artifact paths must additionally
    reject it in :class:`ArtifactRecord`.
    """
    if not isinstance(value, str):
        raise ValueError("path_rel must be a canonical relative POSIX path")
    if value == ".":
        return value

    path = PurePosixPath(value)
    components = value.split("/")
    if (
        not value
        or path.is_absolute()
        or "\\" in value
        or any(component in {"", ".", ".."} for component in components)
    ):
        raise ValueError("path_rel must be a canonical relative POSIX path")
    return path.as_posix()


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    id: str
    path_rel: str
    role: str
    stage: str
    availability: str = "available"
    media_type: str = "application/octet-stream"
    sha256: str | None = None
    size_bytes: int | None = None

    def __post_init__(self) -> None:
        _require_nonempty_string(self.id, "id")
        _require_nonempty_string(self.role, "role")
        _require_nonempty_string(self.stage, "stage")
        _require_nonempty_string(self.availability, "availability")
        _require_nonempty_string(self.media_type, "media_type")
        if canonical_relative_path(self.path_rel) == ".":
            raise ValueError("path_rel must not be the workspace root")
        if self.sha256 is not None:
            _require_nonempty_string(self.sha256, "sha256")
        if self.size_bytes is not None and (isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int) or self.size_bytes < 0):
            raise ValueError("size_bytes must be a non-negative integer")

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "id": self.id,
            "path_rel": self.path_rel,
            "role": self.role,
            "stage": self.stage,
            "availability": self.availability,
            "media_type": self.media_type,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> ArtifactRecord:
        return cls(**dict(payload))  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class MetricRecord:
    name: str
    value: JSONValue
    unit: str | None
    kind: Literal["reported", "derived", "runtime"]
    source_artifact_id: str | None = None

    def __post_init__(self) -> None:
        _require_nonempty_string(self.name, "name")
        if self.unit is not None:
            _require_nonempty_string(self.unit, "unit")
        _require_literal(self.kind, _METRIC_KINDS, "kind")
        if self.source_artifact_id is not None:
            _require_nonempty_string(self.source_artifact_id, "source_artifact_id")
        object.__setattr__(self, "value", _json_round_trip(self.value))

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "kind": self.kind,
            "source_artifact_id": self.source_artifact_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> MetricRecord:
        return cls(**dict(payload))  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class CheckRecord:
    name: str
    status: Literal["passed", "failed", "warning", "unavailable"]
    message: str | None = None

    def __post_init__(self) -> None:
        _require_nonempty_string(self.name, "name")
        _require_literal(self.status, _CHECK_STATUSES, "status")
        if self.message is not None and not isinstance(self.message, str):
            raise ValueError("message must be a string or None")

    def to_dict(self) -> dict[str, JSONValue]:
        return {"name": self.name, "status": self.status, "message": self.message}

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> CheckRecord:
        return cls(**dict(payload))  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class OperationStatus:
    execution: Literal["not_run", "completed", "failed", "skipped"]
    scientific: Literal["unassessed", "accepted", "guarded", "rejected"]
    collection: Literal["not_collected", "complete", "partial", "missing_output"]

    def __post_init__(self) -> None:
        _require_literal(self.execution, _EXECUTION_STATUSES, "execution")
        _require_literal(self.scientific, _SCIENTIFIC_STATUSES, "scientific")
        _require_literal(self.collection, _COLLECTION_STATUSES, "collection")

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "execution": self.execution,
            "scientific": self.scientific,
            "collection": self.collection,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> OperationStatus:
        return cls(**dict(payload))  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class ForgeRequest:
    operation: Literal["prepare", "modify", "execute", "collect", "export"]
    workspace_rel: str
    payload: Mapping[str, JSONValue]
    schema_version: str = REQUEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_literal(self.operation, _OPERATIONS, "operation")
        canonical_relative_path(self.workspace_rel)
        _require_schema_version(self.schema_version, REQUEST_SCHEMA_VERSION)
        payload = _json_round_trip(self.payload)
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON-safe object")
        object.__setattr__(self, "payload", payload)

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "operation": self.operation,
            "workspace_rel": self.workspace_rel,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> ForgeRequest:
        return cls(**dict(payload))  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class ForgeResultEnvelope:
    operation: str
    workspace_rel: str
    status: OperationStatus
    artifacts: Sequence[ArtifactRecord] = ()
    metrics: Sequence[MetricRecord] = ()
    checks: Sequence[CheckRecord] = ()
    warnings: Sequence[str] = ()
    diagnostics: Mapping[str, JSONValue] = field(default_factory=dict)
    schema_version: str = RESULT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_nonempty_string(self.operation, "operation")
        canonical_relative_path(self.workspace_rel)
        _require_schema_version(self.schema_version, RESULT_SCHEMA_VERSION)
        if not isinstance(self.status, OperationStatus):
            raise ValueError("status must be an OperationStatus")

        artifacts = tuple(self.artifacts)
        metrics = tuple(self.metrics)
        checks = tuple(self.checks)
        warnings = tuple(self.warnings)
        if not all(isinstance(artifact, ArtifactRecord) for artifact in artifacts):
            raise ValueError("artifacts must contain ArtifactRecord values")
        if not all(isinstance(metric, MetricRecord) for metric in metrics):
            raise ValueError("metrics must contain MetricRecord values")
        if not all(isinstance(check, CheckRecord) for check in checks):
            raise ValueError("checks must contain CheckRecord values")
        if not all(isinstance(warning, str) for warning in warnings):
            raise ValueError("warnings must contain strings")

        artifact_ids = {artifact.id for artifact in artifacts}
        if len(artifact_ids) != len(artifacts):
            raise ValueError("artifacts must not contain duplicate ids")
        if any(metric.source_artifact_id not in artifact_ids for metric in metrics if metric.source_artifact_id is not None):
            raise ValueError("metric source_artifact_id must reference an artifact")

        diagnostics = _json_round_trip(self.diagnostics)
        if not isinstance(diagnostics, dict):
            raise ValueError("diagnostics must be a JSON-safe object")
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(self, "checks", checks)
        object.__setattr__(self, "warnings", warnings)
        object.__setattr__(self, "diagnostics", diagnostics)
        _json_round_trip(self.to_dict())

    def to_dict(self) -> dict[str, JSONValue]:
        payload: dict[str, JSONValue] = {
            "schema_version": self.schema_version,
            "operation": self.operation,
            "workspace_rel": self.workspace_rel,
            "status": self.status.to_dict(),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "metrics": [metric.to_dict() for metric in self.metrics],
            "checks": [check.to_dict() for check in self.checks],
            "warnings": list(self.warnings),
            "diagnostics": dict(self.diagnostics),
        }
        return _json_round_trip(payload)  # type: ignore[return-value]

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> ForgeResultEnvelope:
        values = dict(payload)
        try:
            values["status"] = OperationStatus.from_dict(values["status"])  # type: ignore[arg-type]
            values["artifacts"] = tuple(ArtifactRecord.from_dict(item) for item in values.get("artifacts", ()))  # type: ignore[arg-type]
            values["metrics"] = tuple(MetricRecord.from_dict(item) for item in values.get("metrics", ()))  # type: ignore[arg-type]
            values["checks"] = tuple(CheckRecord.from_dict(item) for item in values.get("checks", ()))  # type: ignore[arg-type]
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError("result envelope must contain valid record objects") from error
        return cls(**values)  # type: ignore[arg-type]
