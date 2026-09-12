"""Typed, immutable request contracts for ABACUS postprocessing."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import ClassVar, Literal, Mapping

from abacus_forge.contracts import (
    JSONValue,
    REQUEST_SCHEMA_VERSION,
    OperationRef,
    _construct_strict,
    _mapping_payload,
    _require_schema_version,
    canonical_relative_path,
)
from abacus_forge.dos_postprocess import PDOSMode


_POSTPROCESS_OPERATION = "postprocess"
_PDOS_MODES = frozenset({"species", "species+shell", "species+orbital", "atom", "atoms"})


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


def _canonical_file_paths(value: object, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} must be a non-empty list of relative paths")
    values = tuple(value)
    if not values:
        raise ValueError(f"{field_name} must be a non-empty list of relative paths")
    return tuple(_canonical_file_path(item, field_name) for item in values)


def _optional_file_path(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _canonical_file_path(value, field_name)


def _finite_number(value: object, field_name: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a finite number")
    try:
        finite = math.isfinite(value)
    except (OverflowError, TypeError):
        finite = False
    if not finite:
        raise ValueError(f"{field_name} must be a finite number")
    return value


def _boolean(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _atom_indices(value: object) -> tuple[int, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("pdos_atom_indices must be a tuple of non-negative integers")
    values = tuple(value)
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in values):
        raise ValueError("pdos_atom_indices must be a tuple of non-negative integers")
    return values


def _suffix(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("suffix must be a non-empty safe filename component or None")
    if "/" in value or "\\" in value or any(part in {".", ".."} for part in value.split("/")):
        raise ValueError("suffix must be a non-empty safe filename component or None")
    return value


@dataclass(frozen=True, slots=True)
class _PostprocessRequest(OperationRef):
    """Shared identity and strict wire decoding for typed postprocess requests."""

    capability: ClassVar[Literal["band", "dos"]]
    schema_version: str = REQUEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        OperationRef.__post_init__(self)
        _require_schema_version(self.schema_version, REQUEST_SCHEMA_VERSION)

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "capability": self.capability,
            "operation": self.operation,
            "operation_id": self.operation_id,
            "workspace_rel": self.workspace_rel,
        }

    @classmethod
    def _from_dict(cls, payload: Mapping[str, JSONValue]):
        record_name = f"{cls.capability} postprocess request"
        values = _mapping_payload(payload, record_name)
        operation = values.pop("operation", None)
        if operation != _POSTPROCESS_OPERATION:
            raise ValueError(f"{record_name} operation must be {_POSTPROCESS_OPERATION!r}")
        capability = values.pop("capability", None)
        if capability != cls.capability:
            raise ValueError(f"{record_name} capability must be {cls.capability!r}")
        return _construct_strict(cls, values, record_name)


@dataclass(frozen=True, slots=True)
class BandPostprocessRequest(_PostprocessRequest):
    """Request to parse and render explicitly selected ABACUS band files."""

    capability: ClassVar[Literal["band"]] = "band"
    source_paths_rel: tuple[str, ...] = field(default_factory=tuple)
    output_dir_rel: str = "outputs"
    plot_emin: float = -10.0
    plot_emax: float = 10.0
    save_data: bool = True
    save_plot: bool = True

    def __post_init__(self) -> None:
        _PostprocessRequest.__post_init__(self)
        object.__setattr__(self, "source_paths_rel", _canonical_file_paths(self.source_paths_rel, "source_paths_rel"))
        object.__setattr__(self, "output_dir_rel", _canonical_directory_path(self.output_dir_rel, "output_dir_rel"))
        emin = _finite_number(self.plot_emin, "plot_emin")
        emax = _finite_number(self.plot_emax, "plot_emax")
        if emin >= emax:
            raise ValueError("plot_emin must be less than plot_emax")
        object.__setattr__(self, "plot_emin", emin)
        object.__setattr__(self, "plot_emax", emax)
        object.__setattr__(self, "save_data", _boolean(self.save_data, "save_data"))
        object.__setattr__(self, "save_plot", _boolean(self.save_plot, "save_plot"))

    @property
    def operation(self) -> Literal["postprocess"]:
        return _POSTPROCESS_OPERATION

    def to_dict(self) -> dict[str, JSONValue]:
        payload = _PostprocessRequest.to_dict(self)
        payload.update(
            {
                "source_paths_rel": list(self.source_paths_rel),
                "output_dir_rel": self.output_dir_rel,
                "plot_emin": self.plot_emin,
                "plot_emax": self.plot_emax,
                "save_data": self.save_data,
                "save_plot": self.save_plot,
            }
        )
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> BandPostprocessRequest:
        return cls._from_dict(payload)


@dataclass(frozen=True, slots=True)
class DosPostprocessRequest(_PostprocessRequest):
    """Request to parse and render explicitly selected ABACUS DOS families."""

    capability: ClassVar[Literal["dos"]] = "dos"
    dos_paths_rel: tuple[str, ...] = field(default_factory=tuple)
    pdos_path_rel: str | None = None
    tdos_path_rel: str | None = None
    output_dir_rel: str = "outputs"
    include_tdos: bool = True
    include_pdos: bool = True
    pdos_mode: PDOSMode = "species"
    pdos_atom_indices: tuple[int, ...] = field(default_factory=tuple)
    plot_emin: float = -10.0
    plot_emax: float = 10.0
    save_data: bool = True
    save_plot: bool = True
    suffix: str | None = None

    def __post_init__(self) -> None:
        _PostprocessRequest.__post_init__(self)
        object.__setattr__(self, "dos_paths_rel", _canonical_file_paths(self.dos_paths_rel, "dos_paths_rel"))
        object.__setattr__(self, "pdos_path_rel", _optional_file_path(self.pdos_path_rel, "pdos_path_rel"))
        object.__setattr__(self, "tdos_path_rel", _optional_file_path(self.tdos_path_rel, "tdos_path_rel"))
        object.__setattr__(self, "output_dir_rel", _canonical_directory_path(self.output_dir_rel, "output_dir_rel"))
        object.__setattr__(self, "include_tdos", _boolean(self.include_tdos, "include_tdos"))
        object.__setattr__(self, "include_pdos", _boolean(self.include_pdos, "include_pdos"))
        if not isinstance(self.pdos_mode, str) or self.pdos_mode not in _PDOS_MODES:
            raise ValueError("pdos_mode must be one of the existing PDOSMode values")
        object.__setattr__(self, "pdos_atom_indices", _atom_indices(self.pdos_atom_indices))
        emin = _finite_number(self.plot_emin, "plot_emin")
        emax = _finite_number(self.plot_emax, "plot_emax")
        if emin >= emax:
            raise ValueError("plot_emin must be less than plot_emax")
        object.__setattr__(self, "plot_emin", emin)
        object.__setattr__(self, "plot_emax", emax)
        object.__setattr__(self, "save_data", _boolean(self.save_data, "save_data"))
        object.__setattr__(self, "save_plot", _boolean(self.save_plot, "save_plot"))
        object.__setattr__(self, "suffix", _suffix(self.suffix))

    @property
    def operation(self) -> Literal["postprocess"]:
        return _POSTPROCESS_OPERATION

    def to_dict(self) -> dict[str, JSONValue]:
        payload = _PostprocessRequest.to_dict(self)
        payload.update(
            {
                "dos_paths_rel": list(self.dos_paths_rel),
                "pdos_path_rel": self.pdos_path_rel,
                "tdos_path_rel": self.tdos_path_rel,
                "output_dir_rel": self.output_dir_rel,
                "include_tdos": self.include_tdos,
                "include_pdos": self.include_pdos,
                "pdos_mode": self.pdos_mode,
                "pdos_atom_indices": list(self.pdos_atom_indices),
                "plot_emin": self.plot_emin,
                "plot_emax": self.plot_emax,
                "save_data": self.save_data,
                "save_plot": self.save_plot,
                "suffix": self.suffix,
            }
        )
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> DosPostprocessRequest:
        return cls._from_dict(payload)


__all__ = ["BandPostprocessRequest", "DosPostprocessRequest"]
