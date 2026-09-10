"""Typed contracts for the explicit, facts-only export operation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Literal

from abacus_forge.contracts import (
    ArtifactRef,
    JSONValue,
    OperationOutcome,
    OperationRef,
    REQUEST_SCHEMA_VERSION,
    _construct_strict,
    _freeze_json,
    _mapping_payload,
    _require_literal,
    _require_schema_version,
    _require_uuid4,
    _thaw_json,
)


EXPORT_SCHEMA_VERSION = "forge.export/v1"
_FORMATS = frozenset({"json"})
_OVERWRITE_POLICIES = frozenset({"fail"})


def _refs(value: object) -> tuple[ArtifactRef, ...]:
    if isinstance(value, (str, bytes, Mapping)):
        raise ValueError("source_artifact_refs must be a non-empty array")
    try:
        refs = tuple(
            item if isinstance(item, ArtifactRef) else ArtifactRef.from_dict(item)
            for item in value
        )  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ValueError("source_artifact_refs must contain artifact references") from error
    if not refs:
        raise ValueError("source_artifact_refs must not be empty")
    identities = {(ref.operation_id, ref.artifact_id) for ref in refs}
    if len(identities) != len(refs):
        raise ValueError("source_artifact_refs must not contain duplicates")
    operation_ids = {ref.operation_id for ref in refs}
    if len(operation_ids) != 1:
        raise ValueError("source_artifact_refs must identify one source operation")
    return refs


@dataclass(frozen=True, slots=True)
class ExportRequest(OperationRef):
    """Explicit request to serialize one prior operation outcome."""

    capability: Literal["export"] = "export"
    operation: Literal["export"] = "export"
    source_artifact_refs: tuple[ArtifactRef, ...] = ()
    destination_path_rel: str = ""
    format: Literal["json"] = "json"
    pretty: bool = False
    overwrite_policy: Literal["fail"] = "fail"
    schema_version: str = REQUEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        OperationRef.__post_init__(self)
        _require_schema_version(self.schema_version, REQUEST_SCHEMA_VERSION)
        if self.capability != "export" or self.operation != "export":
            raise ValueError("ExportRequest requires capability='export' and operation='export'")
        refs = _refs(self.source_artifact_refs)
        if not self.destination_path_rel or self.destination_path_rel == ".":
            raise ValueError("destination_path_rel must be a canonical relative file path")
        from abacus_forge.contracts import canonical_relative_path

        try:
            canonical_relative_path(self.destination_path_rel)
        except ValueError as error:
            raise ValueError("destination_path_rel must be a canonical relative file path") from error
        _require_literal(self.format, _FORMATS, "format")
        if not isinstance(self.pretty, bool):
            raise ValueError("pretty must be a boolean")
        _require_literal(self.overwrite_policy, _OVERWRITE_POLICIES, "overwrite_policy")
        object.__setattr__(self, "source_artifact_refs", refs)

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "capability": self.capability,
            "operation": self.operation,
            "operation_id": self.operation_id,
            "workspace_rel": self.workspace_rel,
            "source_artifact_refs": [ref.to_dict() for ref in self.source_artifact_refs],
            "destination_path_rel": self.destination_path_rel,
            "format": self.format,
            "pretty": self.pretty,
            "overwrite_policy": self.overwrite_policy,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> "ExportRequest":
        values = _mapping_payload(payload, "export request")
        allowed = {"schema_version", "capability", "operation", "operation_id", "workspace_rel",
                   "source_artifact_refs", "destination_path_rel", "format", "pretty", "overwrite_policy"}
        unknown = sorted(set(values) - allowed)
        if unknown:
            raise ValueError(f"export request contains unknown fields: {', '.join(unknown)}")
        required = {
            "schema_version", "capability", "operation", "operation_id", "workspace_rel",
            "source_artifact_refs", "destination_path_rel",
        }
        missing = sorted(required - set(values))
        if missing:
            raise ValueError(f"export request is missing required fields: {', '.join(missing)}")
        if "source_artifact_refs" in values:
            values["source_artifact_refs"] = _refs(values["source_artifact_refs"])
        return _construct_strict(cls, values, "export request")


@dataclass(frozen=True, slots=True)
class ExportDocument:
    """Portable JSON document containing one immutable source outcome."""

    schema_version: str
    source_operation_id: str
    source_artifact_refs: tuple[ArtifactRef, ...]
    source_outcome: Mapping[str, JSONValue]

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version, EXPORT_SCHEMA_VERSION)
        _require_uuid4(self.source_operation_id, "source_operation_id")
        refs = _refs(self.source_artifact_refs)
        if any(ref.operation_id != self.source_operation_id for ref in refs):
            raise ValueError("source_artifact_refs must match source_operation_id")
        if not isinstance(self.source_outcome, Mapping):
            raise ValueError("source_outcome must be a JSON object")
        try:
            parsed_outcome = OperationOutcome.from_dict(_json_safe_mapping(self.source_outcome))
        except (TypeError, ValueError, KeyError) as error:
            raise ValueError("source_outcome must be a valid forge.operation-outcome/v1 payload") from error
        if parsed_outcome.operation_id != self.source_operation_id:
            raise ValueError("source_outcome operation_id must match source_operation_id")
        artifact_ids = {artifact.id for artifact in parsed_outcome.envelope.artifacts}
        if any(ref.artifact_id not in artifact_ids for ref in refs):
            raise ValueError("source_artifact_refs must identify artifacts in source_outcome")
        outcome = _freeze_json(parsed_outcome.to_dict())
        object.__setattr__(self, "source_artifact_refs", refs)
        object.__setattr__(self, "source_outcome", outcome)

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "source_operation_id": self.source_operation_id,
            "source_artifact_refs": [ref.to_dict() for ref in self.source_artifact_refs],
            "source_outcome": _thaw_json(self.source_outcome),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> "ExportDocument":
        values = _mapping_payload(payload, "export document")
        allowed = {"schema_version", "source_operation_id", "source_artifact_refs", "source_outcome"}
        unknown = sorted(set(values) - allowed)
        if unknown:
            raise ValueError(f"export document contains unknown fields: {', '.join(unknown)}")
        if "source_artifact_refs" in values:
            values["source_artifact_refs"] = _refs(values["source_artifact_refs"])
        return _construct_strict(cls, values, "export document")


def _json_safe_mapping(value: Mapping[str, JSONValue]) -> dict[str, JSONValue]:
    import json

    try:
        decoded = json.loads(json.dumps(dict(value), allow_nan=False))
    except (TypeError, ValueError) as error:
        raise ValueError("source_outcome must be JSON-safe") from error
    if not isinstance(decoded, dict):
        raise ValueError("source_outcome must be a JSON object")
    return decoded


__all__ = ["EXPORT_SCHEMA_VERSION", "ExportDocument", "ExportRequest"]
