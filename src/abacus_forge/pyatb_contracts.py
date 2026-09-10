"""Typed request contracts for the explicit PyATB band handoff."""

from __future__ import annotations

import math
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
    _require_nonempty_string,
    _require_schema_version,
    canonical_relative_path,
)


_PYATB_CAPABILITY = "pyatb-band"
# PyATB uses one HR route for collinear nspin=1 and non-collinear nspin=4,
# while collinear nspin=2 uses separate up/down routes.  Keep this rule in
# the request contract so callers and discovery cannot silently diverge.
_PYATB_NSPIN_HR_CARDINALITY = {1: 1, 2: 2, 4: 1}
_MISSING = object()


def _expected_hr_count(nspin: object) -> int:
    if (
        isinstance(nspin, bool)
        or not isinstance(nspin, int)
        or nspin not in _PYATB_NSPIN_HR_CARDINALITY
    ):
        raise ValueError("nspin must be one of: 1, 2, 4")
    return _PYATB_NSPIN_HR_CARDINALITY[nspin]


def _file_path(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must identify a workspace-relative file")
    try:
        path = canonical_relative_path(value)
    except ValueError as error:
        raise ValueError(f"{field_name} must be a canonical relative path") from error
    if path == ".":
        raise ValueError(f"{field_name} must identify a workspace-relative file")
    return path


def _file_paths(value: object, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} must be a list of workspace-relative files")
    return tuple(_file_path(item, field_name) for item in value)


def _finite_number(value: object, field_name: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a finite number")
    try:
        valid = math.isfinite(value)
    except (OverflowError, TypeError):
        valid = False
    if not valid:
        raise ValueError(f"{field_name} must be a finite number")
    return value


def _positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _line_points(value: object) -> object:
    """Validate and freeze line points while retaining a JSON-shaped wire form."""
    try:
        detached = _json_round_trip(value)
    except ValueError as error:
        raise ValueError("line_kpoints must be a JSON list of point objects") from error
    if not isinstance(detached, list) or len(detached) < 2:
        raise ValueError("line_kpoints must contain at least two points")

    normalized: list[dict[str, JSONValue]] = []
    for point in detached:
        if not isinstance(point, dict):
            raise ValueError("line_kpoints entries must be objects")
        keys = set(point)
        if keys - {"coords", "label"} or "coords" not in point:
            raise ValueError("line_kpoints entries require exactly coords and optional label")
        coords = point["coords"]
        if not isinstance(coords, list) or len(coords) != 3:
            raise ValueError("line_kpoints coords must contain exactly three finite numbers")
        normalized_coords = [_finite_number(item, "line_kpoints.coords") for item in coords]
        normalized_point: dict[str, JSONValue] = {"coords": normalized_coords}
        if "label" in point:
            label = point["label"]
            if not isinstance(label, str) or not label:
                raise ValueError("line_kpoints label must be a non-empty string")
            normalized_point["label"] = label
        normalized.append(normalized_point)
    return _freeze_json(normalized)


@dataclass(frozen=True, slots=True)
class _PyatbBandRequest(OperationRef):
    """Shared identity, version and strict wire decoding for PyATB requests."""

    capability: ClassVar[str] = _PYATB_CAPABILITY
    schema_version: str = field(default=REQUEST_SCHEMA_VERSION, kw_only=True)

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
    def _from_dict(cls, payload: Mapping[str, JSONValue], expected_operation: str):
        record_name = f"PyATB band {expected_operation} request"
        values = _mapping_payload(payload, record_name)
        if values.pop("operation", None) != expected_operation:
            raise ValueError(f"{record_name} operation must be {expected_operation!r}")
        if values.pop("capability", None) != cls.capability:
            raise ValueError(f"{record_name} capability must be {cls.capability!r}")
        return _construct_strict(cls, values, record_name)

    @staticmethod
    def _boolean(value: object, field_name: str) -> bool:
        if not isinstance(value, bool):
            raise ValueError(f"{field_name} must be a boolean")
        return value


@dataclass(frozen=True, slots=True)
class PyatbBandPrepareRequest(_PyatbBandRequest):
    """Request to stage explicit matrix inputs and a PyATB band path."""

    structure_path_rel: str = field(default=_MISSING)  # type: ignore[arg-type]
    hr_paths_rel: Sequence[str] = field(default=_MISSING)  # type: ignore[arg-type]
    sr_path_rel: str = field(default=_MISSING)  # type: ignore[arg-type]
    rr_path_rel: str = field(default=_MISSING)  # type: ignore[arg-type]
    fermi_energy: float = field(default=_MISSING)  # type: ignore[arg-type]
    line_kpoints: Sequence[Mapping[str, object]] = field(default=_MISSING)  # type: ignore[arg-type]
    nspin: int = 1
    line_segments: int = 20
    max_kpoint_num: int = 4000
    handoff_mode: Literal["link", "copy"] = "link"

    def __post_init__(self) -> None:
        _PyatbBandRequest.__post_init__(self)
        object.__setattr__(self, "structure_path_rel", _file_path(self.structure_path_rel, "structure_path_rel"))
        if self.hr_paths_rel is _MISSING:
            raise ValueError("hr_paths_rel is required")
        hr_paths = _file_paths(self.hr_paths_rel, "hr_paths_rel")
        expected_hr_count = _expected_hr_count(self.nspin)
        if len(hr_paths) != expected_hr_count:
            raise ValueError(
                f"hr_paths_rel must contain exactly {expected_hr_count} path(s) for nspin={self.nspin}"
            )
        object.__setattr__(self, "hr_paths_rel", hr_paths)
        object.__setattr__(self, "sr_path_rel", _file_path(self.sr_path_rel, "sr_path_rel"))
        object.__setattr__(self, "rr_path_rel", _file_path(self.rr_path_rel, "rr_path_rel"))
        _finite_number(self.fermi_energy, "fermi_energy")
        object.__setattr__(self, "line_kpoints", _line_points(self.line_kpoints))
        object.__setattr__(self, "line_segments", _positive_integer(self.line_segments, "line_segments"))
        object.__setattr__(self, "max_kpoint_num", _positive_integer(self.max_kpoint_num, "max_kpoint_num"))
        if not isinstance(self.handoff_mode, str) or self.handoff_mode not in {"link", "copy"}:
            raise ValueError("handoff_mode must be one of: copy, link")

    @property
    def operation(self) -> Literal["prepare"]:
        return "prepare"

    def to_dict(self) -> dict[str, JSONValue]:
        payload = _PyatbBandRequest.to_dict(self)
        payload.update(
            {
                "structure_path_rel": self.structure_path_rel,
                "hr_paths_rel": list(self.hr_paths_rel),
                "sr_path_rel": self.sr_path_rel,
                "rr_path_rel": self.rr_path_rel,
                "fermi_energy": self.fermi_energy,
                "line_kpoints": self._thaw(self.line_kpoints),
                "nspin": self.nspin,
                "line_segments": self.line_segments,
                "max_kpoint_num": self.max_kpoint_num,
                "handoff_mode": self.handoff_mode,
            }
        )
        return payload

    @staticmethod
    def _thaw(value: object) -> JSONValue:
        if isinstance(value, Mapping):
            return {str(key): PyatbBandPrepareRequest._thaw(item) for key, item in value.items()}
        if isinstance(value, tuple):
            return [PyatbBandPrepareRequest._thaw(item) for item in value]
        return value  # type: ignore[return-value]

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> PyatbBandPrepareRequest:
        return cls._from_dict(payload, "prepare")


@dataclass(frozen=True, slots=True)
class PyatbBandExecuteRequest(_PyatbBandRequest):
    """Request to run exactly one PyATB process in a prepared workspace."""

    executable: str = "pyatb"
    mpi_ranks: int = 1
    omp_threads: int = 1
    timeout_seconds: float | None = None
    dry_run: bool = False

    def __post_init__(self) -> None:
        _PyatbBandRequest.__post_init__(self)
        _require_nonempty_string(self.executable, "executable")
        object.__setattr__(self, "mpi_ranks", _positive_integer(self.mpi_ranks, "mpi_ranks"))
        object.__setattr__(self, "omp_threads", _positive_integer(self.omp_threads, "omp_threads"))
        if self.timeout_seconds is not None:
            value = _finite_number(self.timeout_seconds, "timeout_seconds")
            if value <= 0:
                raise ValueError("timeout_seconds must be a positive finite number or None")
        object.__setattr__(self, "dry_run", self._boolean(self.dry_run, "dry_run"))

    @property
    def operation(self) -> Literal["execute"]:
        return "execute"

    def to_dict(self) -> dict[str, JSONValue]:
        payload = _PyatbBandRequest.to_dict(self)
        payload.update(
            {
                "executable": self.executable,
                "mpi_ranks": self.mpi_ranks,
                "omp_threads": self.omp_threads,
                "timeout_seconds": self.timeout_seconds,
                "dry_run": self.dry_run,
            }
        )
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> PyatbBandExecuteRequest:
        return cls._from_dict(payload, "execute")


@dataclass(frozen=True, slots=True)
class PyatbBandCollectRequest(_PyatbBandRequest):
    """Request to collect explicitly declared PyATB band output files."""

    band_info_path_rel: str = "inputs/Out/Band_Structure/band_info.dat"
    band_data_paths_rel: Sequence[str] = field(default_factory=tuple)
    band_picture_paths_rel: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _PyatbBandRequest.__post_init__(self)
        object.__setattr__(self, "band_info_path_rel", _file_path(self.band_info_path_rel, "band_info_path_rel"))
        object.__setattr__(self, "band_data_paths_rel", _file_paths(self.band_data_paths_rel, "band_data_paths_rel"))
        object.__setattr__(self, "band_picture_paths_rel", _file_paths(self.band_picture_paths_rel, "band_picture_paths_rel"))

    @property
    def operation(self) -> Literal["collect"]:
        return "collect"

    def to_dict(self) -> dict[str, JSONValue]:
        payload = _PyatbBandRequest.to_dict(self)
        payload.update(
            {
                "band_info_path_rel": self.band_info_path_rel,
                "band_data_paths_rel": list(self.band_data_paths_rel),
                "band_picture_paths_rel": list(self.band_picture_paths_rel),
            }
        )
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> PyatbBandCollectRequest:
        return cls._from_dict(payload, "collect")


__all__ = [
    "PyatbBandCollectRequest",
    "PyatbBandExecuteRequest",
    "PyatbBandPrepareRequest",
]
