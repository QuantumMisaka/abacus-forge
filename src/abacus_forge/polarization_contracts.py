"""Typed requests for native polarization collection and BEC postprocessing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import ClassVar, Literal

from abacus_forge.contracts import (
    JSONValue, REQUEST_SCHEMA_VERSION, OperationRef, _construct_strict,
    _freeze_json, _mapping_payload, _require_schema_version, _thaw_json,
    canonical_relative_path,
)
from abacus_forge.postprocess_contracts import _finite_number, _positive_atom_index


def _file_path(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a canonical workspace-relative file")
    path = canonical_relative_path(value)
    if path == ".":
        raise ValueError(f"{field_name} must name a file")
    return path


@dataclass(frozen=True, slots=True)
class _PropertyRequest(OperationRef):
    capability: ClassVar[str]
    schema_version: str = REQUEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        OperationRef.__post_init__(self)
        _require_schema_version(self.schema_version, REQUEST_SCHEMA_VERSION)

    def to_dict(self) -> dict[str, JSONValue]:
        return {"schema_version": self.schema_version, "capability": self.capability,
                "operation": self.operation, "operation_id": self.operation_id,
                "workspace_rel": self.workspace_rel}

    @classmethod
    def _from_dict(cls, payload: Mapping[str, JSONValue]):
        values = _mapping_payload(payload, f"{cls.capability} request")
        if values.pop("capability", None) != cls.capability:
            raise ValueError(f"capability must be {cls.capability!r}")
        if values.pop("operation", None) != cls._operation:
            raise ValueError(f"operation must be {cls._operation!r}")
        return _construct_strict(cls, values, f"{cls.capability} request")


@dataclass(frozen=True, slots=True)
class PolarizationCollectRequest(_PropertyRequest):
    capability: ClassVar[Literal["polarization"]] = "polarization"
    _operation: ClassVar[Literal["collect"]] = "collect"
    log_path_rel: str = ""
    structure_path_rel: str = ""
    input_path_rel: str = ""
    output_path_rel: str = "outputs/polarization.json"

    def __post_init__(self) -> None:
        _PropertyRequest.__post_init__(self)
        for name in ("log_path_rel", "structure_path_rel", "input_path_rel", "output_path_rel"):
            object.__setattr__(self, name, _file_path(getattr(self, name), name))

    @property
    def operation(self) -> Literal["collect"]:
        return "collect"

    def to_dict(self) -> dict[str, JSONValue]:
        return {**_PropertyRequest.to_dict(self), "log_path_rel": self.log_path_rel,
                "structure_path_rel": self.structure_path_rel,
                "input_path_rel": self.input_path_rel, "output_path_rel": self.output_path_rel}

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> PolarizationCollectRequest:
        return cls._from_dict(payload)


def _columns(value: object, *, branch_mode: str) -> object:
    if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, Sequence) or not value:
        raise ValueError("columns must be a non-empty array")
    columns: list[dict[str, JSONValue]] = []
    seen_columns: set[tuple[int, str]] = set()
    for index, raw_column in enumerate(value):
        if not isinstance(raw_column, Mapping) or set(raw_column) != {"atom_index", "direction", "samples"}:
            raise ValueError(f"columns[{index}] must have atom_index, direction and samples only")
        atom_index = _positive_atom_index(raw_column["atom_index"], "atom_index")
        direction = raw_column["direction"]
        if not isinstance(direction, str) or direction not in ("x", "y", "z"):
            raise ValueError("direction must be x, y or z")
        key = (atom_index, direction)
        if key in seen_columns:
            raise ValueError("columns must not contain duplicate atom/direction pairs")
        seen_columns.add(key)
        raw_samples = raw_column["samples"]
        if isinstance(raw_samples, (str, bytes, Mapping)) or not isinstance(raw_samples, Sequence) or not raw_samples:
            raise ValueError("samples must be a non-empty array")
        samples: list[dict[str, JSONValue]] = []
        seen_displacements: set[int | float] = set()
        for sample_index, raw_sample in enumerate(raw_samples):
            if not isinstance(raw_sample, Mapping) or not {"displacement_angstrom", "polarization_paths_rel"} <= set(raw_sample) or set(raw_sample) - {"displacement_angstrom", "polarization_paths_rel", "branch_offsets"}:
                raise ValueError(f"columns[{index}].samples[{sample_index}] has invalid fields")
            displacement = _finite_number(raw_sample["displacement_angstrom"], "displacement_angstrom")
            if displacement in seen_displacements:
                raise ValueError("sample displacements must be unique within a column")
            seen_displacements.add(displacement)
            raw_paths = raw_sample["polarization_paths_rel"]
            if isinstance(raw_paths, (str, bytes, Mapping)) or not isinstance(raw_paths, Sequence) or not raw_paths:
                raise ValueError("polarization_paths_rel must be a non-empty array")
            paths = [_file_path(item, "polarization_paths_rel") for item in raw_paths]
            if len(set(paths)) != len(paths):
                raise ValueError("polarization_paths_rel must not contain duplicates")
            sample: dict[str, JSONValue] = {"displacement_angstrom": displacement, "polarization_paths_rel": paths}
            offsets = raw_sample.get("branch_offsets")
            if branch_mode == "explicit":
                if "branch_offsets" in raw_sample:
                    if not isinstance(offsets, Mapping) or set(offsets) != {"1", "2", "3"} or any(isinstance(item, bool) or not isinstance(item, int) for item in offsets.values()):
                        raise ValueError("branch_offsets must contain integer entries for gdir 1, 2 and 3")
                    sample["branch_offsets"] = dict(offsets)
            elif "branch_offsets" in raw_sample:
                raise ValueError("branch_offsets are only valid for explicit mode")
            samples.append(sample)
        columns.append({"atom_index": atom_index, "direction": direction, "samples": samples})
    return _freeze_json(columns)


@dataclass(frozen=True, slots=True)
class BecPostprocessRequest(_PropertyRequest):
    capability: ClassVar[Literal["bec"]] = "bec"
    _operation: ClassVar[Literal["postprocess"]] = "postprocess"
    columns: Sequence[Mapping[str, JSONValue]] = field(default_factory=tuple)
    branch_mode: Literal["auto", "explicit"] = "auto"
    max_step_fraction: float | None = None
    output_path_rel: str = "outputs/bec.json"

    def __post_init__(self) -> None:
        _PropertyRequest.__post_init__(self)
        if not isinstance(self.branch_mode, str) or self.branch_mode not in ("auto", "explicit"):
            raise ValueError("branch_mode must be auto or explicit")
        if self.branch_mode == "auto":
            fraction = _finite_number(self.max_step_fraction, "max_step_fraction")
            if not 0 < fraction < 0.5:
                raise ValueError("max_step_fraction must satisfy 0 < f < 0.5")
            object.__setattr__(self, "max_step_fraction", fraction)
        elif self.max_step_fraction is not None:
            raise ValueError("max_step_fraction is only valid for auto mode")
        object.__setattr__(self, "columns", _columns(self.columns, branch_mode=self.branch_mode))
        object.__setattr__(self, "output_path_rel", _file_path(self.output_path_rel, "output_path_rel"))

    @property
    def operation(self) -> Literal["postprocess"]:
        return "postprocess"

    def to_dict(self) -> dict[str, JSONValue]:
        return {**_PropertyRequest.to_dict(self), "columns": _thaw_json(self.columns),
                "branch_mode": self.branch_mode, "max_step_fraction": self.max_step_fraction,
                "output_path_rel": self.output_path_rel}

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> BecPostprocessRequest:
        return cls._from_dict(payload)
