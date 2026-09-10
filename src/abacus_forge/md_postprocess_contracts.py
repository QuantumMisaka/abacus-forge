"""Typed, immutable request contract for molecular-dynamics postprocessing."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import ClassVar, Literal

from abacus_forge.contracts import (
    JSONValue,
    REQUEST_SCHEMA_VERSION,
    OperationRef,
    _construct_strict,
    _freeze_json,
    _mapping_payload,
    _require_schema_version,
    _thaw_json,
    canonical_relative_path,
)


_POSTPROCESS_OPERATION = "postprocess"
MD_ANALYSIS_MODES = (
    "rdf",
    "msd_diffusion",
    "vacf_vdos",
    "bond_length",
    "bond_angle",
)

_RECOGNIZED_PARAMETERS = frozenset(
    {"timestep", "selection", "elements", "rmax", "nbins", "save_data", "save_plot"}
)
_CHEMICAL_SYMBOL = re.compile(r"^[A-Z][a-z]?$")


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
    if any(item not in MD_ANALYSIS_MODES for item in values):
        raise ValueError("analysis must contain only canonical MD analysis modes")
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


def _json_value(value: object, _active: set[int] | None = None) -> JSONValue:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("parameters must contain only finite JSON numbers")
        return value
    active = _active if _active is not None else set()
    if isinstance(value, list):
        marker = id(value)
        if marker in active:
            raise ValueError("parameters must not contain cyclic containers")
        active.add(marker)
        try:
            return [_json_value(item, active) for item in value]
        finally:
            active.remove(marker)
    if isinstance(value, dict):
        marker = id(value)
        if marker in active:
            raise ValueError("parameters must not contain cyclic containers")
        active.add(marker)
        try:
            if not all(isinstance(key, str) for key in value):
                raise ValueError("parameters object keys must be strings")
            return {key: _json_value(item, active) for key, item in value.items()}
        finally:
            active.remove(marker)
    raise ValueError("parameters must contain only JSON-safe values")


def _parameters(value: object) -> Mapping[str, JSONValue]:
    if not isinstance(value, Mapping):
        raise ValueError("parameters must be a JSON-safe object")
    try:
        source = dict(value)
    except (TypeError, ValueError) as error:
        raise ValueError("parameters must be a JSON-safe object") from error
    try:
        normalized = _json_value(source)
    except ValueError as error:
        raise ValueError("parameters must be a JSON-safe object") from error
    if not isinstance(normalized, dict):
        raise ValueError("parameters must be a JSON-safe object")
    return _freeze_json(normalized)  # type: ignore[return-value]


def _positive_number(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be finite and positive")
    try:
        valid = math.isfinite(value) and value > 0
    except (OverflowError, TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError(f"{field_name} must be finite and positive")


def _rdf_parameter_pairs(value: object) -> None:
    """Validate RDF element-pair syntax without importing the algorithm layer."""
    if value is None:
        return
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or not value:
        raise ValueError("elements must be a non-empty list of A-B strings")
    pairs: list[str] = []
    for item in value:
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
            item = tuple(item)
            if len(item) != 2:
                raise ValueError("elements RDF pairs must contain two symbols")
            item = f"{item[0]}-{item[1]}"
        if not isinstance(item, str) or item.count("-") != 1:
            raise ValueError("elements RDF pairs must use the A-B form")
        left, right = item.split("-")
        if not _CHEMICAL_SYMBOL.fullmatch(left) or not _CHEMICAL_SYMBOL.fullmatch(right):
            raise ValueError("elements RDF pairs must contain safe chemical symbols")
        pairs.append(f"{left}-{right}")
    if len(set(pairs)) != len(pairs):
        raise ValueError("elements RDF pairs must be unique")


def _selection_entries(value: object, field_name: str, hyphens: int) -> None:
    if value is None:
        return
    if isinstance(value, str):
        values = (value,)
    elif isinstance(value, (bytes,)) or not isinstance(value, Sequence):
        raise ValueError(f"selection.{field_name} must contain strings")
    else:
        values = tuple(value)
    for item in values:
        if not isinstance(item, str) or item.count("-") != hyphens:
            raise ValueError(f"selection.{field_name} entries have invalid syntax")
        if any(not _CHEMICAL_SYMBOL.fullmatch(symbol) for symbol in item.split("-")):
            raise ValueError(f"selection.{field_name} entries must contain safe chemical symbols")


def _validate_selection(value: object) -> None:
    if isinstance(value, Mapping):
        _selection_entries(value.get("pairs"), "pairs", 1)
        _selection_entries(value.get("angles"), "angles", 2)
        if "indices" in value:
            indices = value["indices"]
            if isinstance(indices, (str, bytes)) or not isinstance(indices, Sequence) or not indices:
                raise ValueError("selection.indices must be a non-empty sequence of atom indices")
            if any(isinstance(item, bool) or not isinstance(item, int) or item < 1 for item in indices):
                raise ValueError("selection.indices must contain positive integers")
        return
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("selection must be an object or list")
    for item in value:
        if not isinstance(item, str) or item.count("-") not in (1, 2):
            raise ValueError("selection entries must use A-B or A-B-C strings")
        if any(not _CHEMICAL_SYMBOL.fullmatch(symbol) for symbol in item.split("-")):
            raise ValueError("selection entries must contain safe chemical symbols")


def _validate_parameters(parameters: Mapping[str, JSONValue], analysis: Sequence[str]) -> None:
    """Validate all recognized MD parameter shapes before workspace admission.

    ``parameters`` is already frozen by :func:`_parameters`, so list-valued
    fields are tuples and nested objects are mapping proxies.  This validator
    intentionally depends only on the standard library and validates the
    request-independent portion of the parameter contract.  Trajectory facts
    such as atom-index upper bounds remain algorithm preconditions.
    """
    recognized = {key: parameters[key] for key in parameters if key in _RECOGNIZED_PARAMETERS}
    if any(mode in analysis for mode in ("msd_diffusion", "vacf_vdos")):
        if "timestep" not in recognized:
            raise ValueError("timestep is required for MSD/VACF")
    if "timestep" in recognized:
        _positive_number(recognized["timestep"], "timestep")
    if "rmax" in recognized:
        _positive_number(recognized["rmax"], "rmax")
    if "nbins" in recognized:
        value = recognized["nbins"]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError("nbins must be positive")
    if "elements" in recognized:
        _rdf_parameter_pairs(recognized["elements"])
    for field_name in ("save_data", "save_plot"):
        if field_name in recognized and not isinstance(recognized[field_name], bool):
            raise ValueError(f"{field_name} must be boolean")
    if "selection" in recognized:
        _validate_selection(recognized["selection"])


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
        normalized_parameters = _parameters(self.parameters)
        _validate_parameters(normalized_parameters, self.analysis)
        object.__setattr__(self, "parameters", normalized_parameters)

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


__all__ = ["MD_ANALYSIS_MODES", "MdPostprocessRequest"]
