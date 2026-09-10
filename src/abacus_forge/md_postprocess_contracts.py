"""Typed, immutable request contract for molecular-dynamics postprocessing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import ClassVar, Literal

from abacus_forge.contracts import (
    JSONValue,
    REQUEST_SCHEMA_VERSION,
    OperationRef,
    _construct_strict,
    _freeze_json,
    _json_round_trip,
    _mapping_payload,
    _require_schema_version,
    _thaw_json,
    canonical_relative_path,
)


_POSTPROCESS_OPERATION = "postprocess"


def _canonical_file_path(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must identify a workspace-relative file")
    try:
        normalized = canonical_relative_path(value)
    except ValueError as error:
        raise ValueError(f"{field_name} must be a canonical relative path") from error
    if normalized == ".":
        raise ValueError(f"{field_name} must identify a workspace-relative file")
    return normalized


def _canonical_directory_path(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a canonical relative path")
    try:
        return canonical_relative_path(value)
    except ValueError as error:
        raise ValueError(f"{field_name} must be a canonical relative path") from error


def _analysis_values(value: object) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("analysis must be a non-empty sequence of unique strings")
    values = tuple(value)
    if not values or any(not isinstance(item, str) or not item for item in values):
        raise ValueError("analysis must be a non-empty sequence of unique strings")
    if len(set(values)) != len(values):
        raise ValueError("analysis must contain unique strings")
    return values


def _sampling_integer(value: object, field_name: str, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        if minimum == 0:
            requirement = "non-negative"
        else:
            requirement = "positive"
        raise ValueError(f"{field_name} must be a {requirement} integer")
    return value


def _optional_positive_integer(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    return _sampling_integer(value, field_name, minimum=1)


def _parameters(value: object) -> Mapping[str, JSONValue]:
    if not isinstance(value, Mapping):
        raise ValueError("parameters must be a JSON-safe object")
    try:
        source = dict(value)
    except (TypeError, ValueError) as error:
        raise ValueError("parameters must be a JSON-safe object") from error
    if not all(isinstance(key, str) for key in source):
        raise ValueError("parameters keys must be strings")
    try:
        normalized = _json_round_trip(source)
    except ValueError as error:
        raise ValueError("parameters must be a JSON-safe object") from error
    if not isinstance(normalized, dict):
        raise ValueError("parameters must be a JSON-safe object")
    return _freeze_json(normalized)  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class MdPostprocessRequest(OperationRef):
    """Request to analyze an explicitly selected MD trajectory."""

    capability: ClassVar[Literal["md"]] = "md"
    schema_version: str = REQUEST_SCHEMA_VERSION
    trajectory_path_rel: str = ""
    analysis: tuple[str, ...] = field(default_factory=tuple)
    output_dir_rel: str = "outputs/md-postprocess"
    start: int = 0
    end: int | None = None
    stride: int = 1
    parameters: Mapping[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        OperationRef.__post_init__(self)
        _require_schema_version(self.schema_version, REQUEST_SCHEMA_VERSION)
        object.__setattr__(
            self,
            "trajectory_path_rel",
            _canonical_file_path(self.trajectory_path_rel, "trajectory_path_rel"),
        )
        object.__setattr__(self, "analysis", _analysis_values(self.analysis))
        object.__setattr__(
            self,
            "output_dir_rel",
            _canonical_directory_path(self.output_dir_rel, "output_dir_rel"),
        )
        object.__setattr__(self, "start", _sampling_integer(self.start, "start", minimum=0))
        object.__setattr__(self, "end", _optional_positive_integer(self.end, "end"))
        object.__setattr__(self, "stride", _sampling_integer(self.stride, "stride", minimum=1))
        object.__setattr__(self, "parameters", _parameters(self.parameters))

    @property
    def operation(self) -> Literal["postprocess"]:
        return _POSTPROCESS_OPERATION

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "capability": self.capability,
            "operation": self.operation,
            "operation_id": self.operation_id,
            "workspace_rel": self.workspace_rel,
            "trajectory_path_rel": self.trajectory_path_rel,
            "analysis": list(self.analysis),
            "output_dir_rel": self.output_dir_rel,
            "start": self.start,
            "end": self.end,
            "stride": self.stride,
            "parameters": _thaw_json(self.parameters),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> MdPostprocessRequest:
        record_name = "MD postprocess request"
        values = _mapping_payload(payload, record_name)
        operation = values.pop("operation", None)
        if operation != _POSTPROCESS_OPERATION:
            raise ValueError(f"{record_name} operation must be {_POSTPROCESS_OPERATION!r}")
        capability = values.pop("capability", None)
        if capability != cls.capability:
            raise ValueError(f"{record_name} capability must be {cls.capability!r}")
        return _construct_strict(cls, values, record_name)


__all__ = ["MdPostprocessRequest"]
