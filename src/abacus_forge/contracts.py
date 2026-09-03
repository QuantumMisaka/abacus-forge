"""Versioned, JSON-safe records at the Forge public boundary."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, fields
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Literal, Mapping, Sequence, TypeAlias


JSONValue: TypeAlias = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]

REQUEST_SCHEMA_VERSION = "forge.request/v1"
RESULT_SCHEMA_VERSION = "forge.result/v1"
OPERATION_OUTCOME_SCHEMA_VERSION = "forge.operation-outcome/v1"
WORKSPACE_SCHEMA_VERSION = "forge.workspace/v1"
ERROR_SCHEMA_VERSION = "forge.error/v1"
ERROR_CLASSES = frozenset({
    "request.invalid",
    "request.schema",
    "request.path",
    "operation.conflict",
    "precondition.missing",
    "persistence.failure",
    "internal.failure",
})

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


def _freeze_json(value: JSONValue) -> object:
    """Recursively protect a JSON value retained by an immutable record."""
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: object) -> JSONValue:
    """Build a fresh standard JSON value for public serialization."""
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value  # type: ignore[return-value]


def _require_nonempty_string(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_literal(value: str, allowed: frozenset[str], field_name: str) -> None:
    try:
        valid = value in allowed
    except TypeError as error:
        raise ValueError(f"{field_name} has invalid value") from error
    if not valid:
        allowed_values = ", ".join(sorted(allowed))
        raise ValueError(f"{field_name} must be one of: {allowed_values}")


def _require_schema_version(value: str, expected: str) -> None:
    if value != expected:
        raise ValueError(f"schema_version must be {expected!r}")


def _require_uuid4(value: str, field_name: str = "operation_id") -> None:
    _require_nonempty_string(value, field_name)
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a lowercase UUIDv4") from error
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError(f"{field_name} must be a lowercase UUIDv4")


def _mapping_payload(payload: object, record_name: str) -> dict[str, JSONValue]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{record_name} must be a mapping")
    try:
        return dict(payload)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{record_name} must be a mapping") from error


def _construct(cls, payload: object, record_name: str):
    try:
        return cls(**_mapping_payload(payload, record_name))
    except ValueError:
        raise
    except (TypeError, KeyError) as error:
        raise ValueError(f"{record_name} contains invalid fields") from error


def _construct_strict(cls, payload: object, record_name: str):
    """Construct a public record while rejecting unknown serialized fields."""
    values = _mapping_payload(payload, record_name)
    allowed = {record_field.name for record_field in fields(cls)}
    unknown = sorted((key for key in values if key not in allowed), key=str)
    if unknown:
        raise ValueError(f"{record_name} contains unknown fields: {', '.join(map(str, unknown))}")
    try:
        return cls(**values)
    except ValueError:
        raise
    except (TypeError, KeyError) as error:
        raise ValueError(f"{record_name} contains invalid fields") from error


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
        return _construct(cls, payload, "artifact")


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """Stable cross-operation reference to an artifact."""

    operation_id: str
    artifact_id: str

    def __post_init__(self) -> None:
        _require_uuid4(self.operation_id)
        _require_nonempty_string(self.artifact_id, "artifact_id")

    def to_dict(self) -> dict[str, JSONValue]:
        return {"operation_id": self.operation_id, "artifact_id": self.artifact_id}

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> ArtifactRef:
        return _construct_strict(cls, payload, "artifact reference")


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
        object.__setattr__(self, "value", _freeze_json(_json_round_trip(self.value)))

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "name": self.name,
            "value": _thaw_json(self.value),
            "unit": self.unit,
            "kind": self.kind,
            "source_artifact_id": self.source_artifact_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> MetricRecord:
        return _construct(cls, payload, "metric")


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
        return _construct(cls, payload, "check")


@dataclass(frozen=True, slots=True)
class Observation:
    """One factual observation emitted by a Forge operation."""

    name: str
    value: JSONValue
    source: Literal["log", "file", "parser", "runtime"]

    def __post_init__(self) -> None:
        _require_nonempty_string(self.name, "name")
        _require_literal(self.source, frozenset({"log", "file", "parser", "runtime"}), "source")
        object.__setattr__(self, "value", _freeze_json(_json_round_trip(self.value)))

    def to_dict(self) -> dict[str, JSONValue]:
        return {"name": self.name, "value": _thaw_json(self.value), "source": self.source}

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> Observation:
        return _construct_strict(cls, payload, "observation")


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
        return _construct(cls, payload, "status")


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
        object.__setattr__(self, "payload", _freeze_json(payload))

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "operation": self.operation,
            "workspace_rel": self.workspace_rel,
            "payload": _thaw_json(self.payload),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> ForgeRequest:
        return _construct(cls, payload, "request")


@dataclass(frozen=True, slots=True)
class OperationRef:
    """Immutable identity and workspace scope shared by SCF operations."""

    operation_id: str
    workspace_rel: str

    def __post_init__(self) -> None:
        _require_uuid4(self.operation_id)
        canonical_relative_path(self.workspace_rel)

    def to_dict(self) -> dict[str, JSONValue]:
        return {"operation_id": self.operation_id, "workspace_rel": self.workspace_rel}

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> OperationRef:
        return _construct_strict(cls, payload, "operation reference")


@dataclass(frozen=True, slots=True)
class _ScfRequest(OperationRef):
    """Shared validation for the narrow, typed SCF request variants."""

    schema_version: str = REQUEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        OperationRef.__post_init__(self)
        _require_schema_version(self.schema_version, REQUEST_SCHEMA_VERSION)

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "operation": self.operation,
            "operation_id": self.operation_id,
            "workspace_rel": self.workspace_rel,
        }

    @classmethod
    def _from_dict(cls, payload: Mapping[str, JSONValue], expected_operation: str):
        values = _mapping_payload(payload, f"SCF {expected_operation} request")
        operation = values.pop("operation", None)
        if operation != expected_operation:
            raise ValueError(f"SCF {expected_operation} request operation must be {expected_operation!r}")
        return _construct_strict(cls, values, f"SCF {expected_operation} request")


@dataclass(frozen=True, slots=True)
class ScfPrepareRequest(_ScfRequest):
    """Typed request for preparing one SCF workspace."""

    # A preparation is only useful when it has a structure to normalize.  The
    # empty sentinel keeps dataclass inheritance ergonomic while __post_init__
    # still makes the field mandatory at the public boundary.
    structure_path_rel: str = ""
    structure_format: str | None = None
    parameters: Mapping[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ScfRequest.__post_init__(self)
        if not self.structure_path_rel:
            raise ValueError("structure_path_rel is required")
        if canonical_relative_path(self.structure_path_rel) == ".":
            raise ValueError("structure_path_rel must identify a workspace-relative file")
        if self.structure_format is not None:
            _require_nonempty_string(self.structure_format, "structure_format")
        parameters = _json_round_trip(self.parameters)
        if not isinstance(parameters, dict):
            raise ValueError("parameters must be a JSON-safe object")
        object.__setattr__(self, "parameters", _freeze_json(parameters))

    def to_dict(self) -> dict[str, JSONValue]:
        payload = _ScfRequest.to_dict(self)
        payload.update(
            {
                "structure_path_rel": self.structure_path_rel,
                "structure_format": self.structure_format,
                "parameters": _thaw_json(self.parameters),
            }
        )
        return payload

    @property
    def operation(self) -> Literal["prepare"]:
        return "prepare"

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> ScfPrepareRequest:
        return cls._from_dict(payload, "prepare")


@dataclass(frozen=True, slots=True)
class ScfModifyRequest(_ScfRequest):
    """Typed request for modifying one SCF workspace."""

    # Keep modification input-specific: this maps directly to the existing
    # INPUT key editing primitive without exposing UnitModifySpec itself.
    input_updates: Mapping[str, JSONValue] = field(default_factory=dict)
    remove_parameters: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _ScfRequest.__post_init__(self)
        updates = _json_round_trip(self.input_updates)
        if not isinstance(updates, dict):
            raise ValueError("input_updates must be a JSON-safe object")
        if not all(isinstance(key, str) and key for key in updates):
            raise ValueError("input_updates keys must be non-empty strings")
        object.__setattr__(self, "input_updates", _freeze_json(updates))
        if isinstance(self.remove_parameters, (str, bytes)):
            raise ValueError("remove_parameters must contain non-empty strings")
        try:
            removed = tuple(self.remove_parameters)
        except TypeError as error:
            raise ValueError("remove_parameters must contain non-empty strings") from error
        if not all(isinstance(key, str) and key for key in removed):
            raise ValueError("remove_parameters must contain non-empty strings")
        object.__setattr__(self, "remove_parameters", removed)

    def to_dict(self) -> dict[str, JSONValue]:
        payload = _ScfRequest.to_dict(self)
        payload.update(
            {
                "input_updates": _thaw_json(self.input_updates),
                "remove_parameters": list(self.remove_parameters),
            }
        )
        return payload

    @property
    def operation(self) -> Literal["modify"]:
        return "modify"

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> ScfModifyRequest:
        return cls._from_dict(payload, "modify")


@dataclass(frozen=True, slots=True)
class ScfExecuteRequest(_ScfRequest):
    """Typed request for executing one SCF workspace."""

    dry_run: bool = False

    def __post_init__(self) -> None:
        _ScfRequest.__post_init__(self)
        if not isinstance(self.dry_run, bool):
            raise ValueError("dry_run must be a boolean")

    def to_dict(self) -> dict[str, JSONValue]:
        payload = _ScfRequest.to_dict(self)
        payload["dry_run"] = self.dry_run
        return payload

    @property
    def operation(self) -> Literal["execute"]:
        return "execute"

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> ScfExecuteRequest:
        return cls._from_dict(payload, "execute")


@dataclass(frozen=True, slots=True)
class ScfCollectRequest(_ScfRequest):
    """Typed request for collecting one SCF workspace."""

    @property
    def operation(self) -> Literal["collect"]:
        return "collect"

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> ScfCollectRequest:
        return cls._from_dict(payload, "collect")


@dataclass(frozen=True, slots=True)
class ForgeErrorEnvelope:
    """Machine-readable outcome for an expected Forge request or runtime error."""

    error_class: str
    message: str
    affected_fields: Sequence[str]
    operation_id: str | None = None
    workspace_rel: str | None = None
    schema_version: str = ERROR_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_literal(self.error_class, ERROR_CLASSES, "error_class")
        _require_nonempty_string(self.message, "message")
        if self.operation_id is not None:
            _require_uuid4(self.operation_id)
        if self.workspace_rel is not None:
            canonical_relative_path(self.workspace_rel)
        _require_schema_version(self.schema_version, ERROR_SCHEMA_VERSION)
        if isinstance(self.affected_fields, (str, bytes)):
            raise ValueError("affected_fields must contain non-empty strings")
        try:
            affected_fields = tuple(self.affected_fields)
        except TypeError as error:
            raise ValueError("affected_fields must contain non-empty strings") from error
        if not all(isinstance(field_name, str) and field_name for field_name in affected_fields):
            raise ValueError("affected_fields must contain non-empty strings")
        object.__setattr__(self, "affected_fields", affected_fields)

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "error": {
                "class": self.error_class,
                "message": self.message,
                "affected_fields": list(self.affected_fields),
            },
            "operation_id": self.operation_id,
            "workspace_rel": self.workspace_rel,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> ForgeErrorEnvelope:
        values = _mapping_payload(payload, "error envelope")
        error = values.pop("error", None)
        if not isinstance(error, Mapping):
            raise ValueError("error envelope must contain an error object")
        nested_unknown = sorted(
            (key for key in error if key not in {"class", "message", "affected_fields"}),
            key=str,
        )
        if nested_unknown:
            raise ValueError(
                "error envelope error object contains unknown fields: "
                + ", ".join(map(str, nested_unknown))
            )
        try:
            values["error_class"] = error["class"]
            values["message"] = error["message"]
            values["affected_fields"] = error["affected_fields"]
        except KeyError as exc:
            raise ValueError("error envelope error object is incomplete") from exc
        return _construct_strict(cls, values, "error envelope")


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
        object.__setattr__(self, "diagnostics", _freeze_json(diagnostics))
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
            "diagnostics": _thaw_json(self.diagnostics),
        }
        return _json_round_trip(payload)  # type: ignore[return-value]

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> ForgeResultEnvelope:
        values = _mapping_payload(payload, "result envelope")
        try:
            values["status"] = OperationStatus.from_dict(values["status"])  # type: ignore[arg-type]
            values["artifacts"] = tuple(ArtifactRecord.from_dict(item) for item in values.get("artifacts", ()))  # type: ignore[arg-type]
            values["metrics"] = tuple(MetricRecord.from_dict(item) for item in values.get("metrics", ()))  # type: ignore[arg-type]
            values["checks"] = tuple(CheckRecord.from_dict(item) for item in values.get("checks", ()))  # type: ignore[arg-type]
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError("result envelope must contain valid record objects") from error
        try:
            return cls(**values)  # type: ignore[arg-type]
        except (TypeError, KeyError) as error:
            raise ValueError("result envelope contains invalid fields") from error


@dataclass(frozen=True, slots=True)
class OperationOutcome:
    """Stable typed success carrier for an admitted Forge operation."""

    operation_id: str
    envelope: ForgeResultEnvelope
    observations: Sequence[Observation] = ()
    schema_version: str = OPERATION_OUTCOME_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_uuid4(self.operation_id)
        _require_schema_version(self.schema_version, OPERATION_OUTCOME_SCHEMA_VERSION)
        if not isinstance(self.envelope, ForgeResultEnvelope):
            raise ValueError("envelope must be a ForgeResultEnvelope")
        observations = tuple(self.observations)
        if not all(isinstance(observation, Observation) for observation in observations):
            raise ValueError("observations must contain Observation values")
        object.__setattr__(self, "observations", observations)
        _json_round_trip(self.to_dict())

    @property
    def status(self) -> OperationStatus:
        """Delegate status access to the embedded compatibility envelope."""

        return self.envelope.status

    def to_dict(self) -> dict[str, JSONValue]:
        payload: dict[str, JSONValue] = {
            "schema_version": self.schema_version,
            "operation_id": self.operation_id,
            "envelope": self.envelope.to_dict(),
            "observations": [observation.to_dict() for observation in self.observations],
        }
        return _json_round_trip(payload)  # type: ignore[return-value]

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> OperationOutcome:
        values = _mapping_payload(payload, "operation outcome")
        try:
            values["envelope"] = ForgeResultEnvelope.from_dict(values["envelope"])  # type: ignore[arg-type]
            values["observations"] = tuple(
                Observation.from_dict(item) for item in values.get("observations", ())  # type: ignore[arg-type]
            )
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError("operation outcome must contain valid envelope and observations") from error
        return _construct_strict(cls, values, "operation outcome")
