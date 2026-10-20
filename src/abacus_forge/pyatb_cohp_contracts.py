"""Strict requests for the experimental direct NAO PyATB COHP handoff."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
import re
from typing import ClassVar, Literal

from abacus_forge.contracts import (
    JSONValue, REQUEST_SCHEMA_VERSION, OperationRef, _construct_strict,
    _mapping_payload, _require_nonempty_string, _require_schema_version,
)
from abacus_forge.pyatb_contracts import _file_path, _file_paths, _finite_number, _positive_integer

_MISSING = object()
_ORBITAL_TOKEN = r"(?:all|\*|[spdfg]|[0-9]+[spdfg]|[0-9]+)"
_ORBITAL_SELECTOR = re.compile(rf"{_ORBITAL_TOKEN}(?:[\s,]+{_ORBITAL_TOKEN})*", re.IGNORECASE)


def _numbers(value: object, name: str, *, size: int | None = None) -> tuple[int | float, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{name} must be a list of finite numbers")
    result = tuple(_finite_number(item, name) for item in value)
    if size is not None and len(result) != size:
        raise ValueError(f"{name} must contain exactly {size} numbers")
    return result


@dataclass(frozen=True, slots=True)
class _CohpRequest(OperationRef):
    capability: ClassVar[str] = "pyatb-cohp"
    schema_version: str = field(default=REQUEST_SCHEMA_VERSION, kw_only=True)

    def __post_init__(self) -> None:
        OperationRef.__post_init__(self)
        _require_schema_version(self.schema_version, REQUEST_SCHEMA_VERSION)

    def to_dict(self) -> dict[str, JSONValue]:
        return dict(schema_version=self.schema_version, capability=self.capability,
                    operation=self.operation, operation_id=self.operation_id,
                    workspace_rel=self.workspace_rel)

    @classmethod
    def _from_dict(cls, payload: Mapping[str, JSONValue], operation: str):
        name = f"PyATB COHP {operation} request"
        values = _mapping_payload(payload, name)
        if values.pop("operation", None) != operation:
            raise ValueError(f"{name} operation must be {operation!r}")
        if values.pop("capability", None) != cls.capability:
            raise ValueError(f"{name} capability must be {cls.capability!r}")
        return _construct_strict(cls, values, name)


@dataclass(frozen=True, slots=True)
class PyatbCohpPrepareRequest(_CohpRequest):
    structure_path_rel: str = field(default=_MISSING)  # type: ignore[arg-type]
    hr_paths_rel: Sequence[str] = field(default=_MISSING)  # type: ignore[arg-type]
    sr_path_rel: str = field(default=_MISSING)  # type: ignore[arg-type]
    orbital_paths_rel: Sequence[str] = field(default=_MISSING)  # type: ignore[arg-type]
    fermi_energy: float = field(default=_MISSING)  # type: ignore[arg-type]
    atom_i_index: int = field(default=_MISSING)  # type: ignore[arg-type]
    atom_j_index: int = field(default=_MISSING)  # type: ignore[arg-type]
    kpoints: Sequence[Sequence[float]] = field(default=_MISSING)  # type: ignore[arg-type]
    kpoint_weights: Sequence[float] = field(default=_MISSING)  # type: ignore[arg-type]
    e_range: Sequence[float] = field(default=_MISSING)  # type: ignore[arg-type]
    atom_i_orbs: str = "all"
    atom_j_orbs: str = "all"
    nspin: int = 1
    spin: Literal["sum", "up", "down"] = "sum"
    de: float = 0.05
    sigma: float = 0.15
    invert: bool = True
    shift_to_efermi: bool = True
    max_kpoint_num: int = 4000

    def __post_init__(self) -> None:
        _CohpRequest.__post_init__(self)
        object.__setattr__(self, "structure_path_rel", _file_path(self.structure_path_rel, "structure_path_rel"))
        if self.hr_paths_rel is _MISSING or self.orbital_paths_rel is _MISSING:
            raise ValueError("hr_paths_rel and orbital_paths_rel are required")
        hrs = _file_paths(self.hr_paths_rel, "hr_paths_rel")
        orbitals = _file_paths(self.orbital_paths_rel, "orbital_paths_rel")
        if isinstance(self.nspin, bool) or not isinstance(self.nspin, int) or self.nspin not in (1, 2):
            raise ValueError("nspin must be 1 or 2")
        if len(hrs) != self.nspin or not orbitals:
            raise ValueError("HR count must equal nspin and orbital_paths_rel must be nonempty")
        object.__setattr__(self, "hr_paths_rel", hrs)
        object.__setattr__(self, "orbital_paths_rel", orbitals)
        object.__setattr__(self, "sr_path_rel", _file_path(self.sr_path_rel, "sr_path_rel"))
        _finite_number(self.fermi_energy, "fermi_energy")
        for name in ("atom_i_index", "atom_j_index", "max_kpoint_num"):
            _positive_integer(getattr(self, name), name)
        for name in ("atom_i_orbs", "atom_j_orbs"):
            value = getattr(self, name)
            _require_nonempty_string(value, name)
            if len(value) > 128 or _ORBITAL_SELECTOR.fullmatch(value.strip()) is None:
                raise ValueError(f"{name} is not a safe PyATB selector")
        if self.spin not in ("sum", "up", "down") or (self.nspin == 1 and self.spin != "sum"):
            raise ValueError("spin up/down requires nspin=2")
        for name in ("de", "sigma"):
            if _finite_number(getattr(self, name), name) <= 0:
                raise ValueError(f"{name} must be positive")
        if not isinstance(self.invert, bool) or not isinstance(self.shift_to_efermi, bool):
            raise ValueError("invert and shift_to_efermi must be booleans")
        if isinstance(self.kpoints, (str, bytes)) or not isinstance(self.kpoints, Sequence):
            raise ValueError("kpoints must be a list of fractional coordinate triples")
        points = tuple(_numbers(point, "kpoints", size=3) for point in self.kpoints)
        if not points:
            raise ValueError("kpoints must be nonempty")
        object.__setattr__(self, "kpoints", points)
        weights = _numbers(self.kpoint_weights, "kpoint_weights")
        if len(weights) != len(points) or any(weight < 0 for weight in weights) or not any(weight > 0 for weight in weights):
            raise ValueError("kpoint_weights must match kpoints, be nonnegative, and have positive sum")
        object.__setattr__(self, "kpoint_weights", weights)
        bounds = _numbers(self.e_range, "e_range", size=2)
        span_steps = (bounds[1] - bounds[0]) / self.de
        if bounds[1] <= bounds[0] or not math.isfinite(span_steps) or span_steps < 1:
            raise ValueError("e_range must increase and span at least one de")
        object.__setattr__(self, "e_range", bounds)

    @property
    def operation(self) -> Literal["prepare"]:
        return "prepare"

    def to_dict(self) -> dict[str, JSONValue]:
        value = _CohpRequest.to_dict(self)
        value.update(structure_path_rel=self.structure_path_rel, hr_paths_rel=list(self.hr_paths_rel),
                     sr_path_rel=self.sr_path_rel, orbital_paths_rel=list(self.orbital_paths_rel),
                     fermi_energy=self.fermi_energy, atom_i_index=self.atom_i_index,
                     atom_j_index=self.atom_j_index, atom_i_orbs=self.atom_i_orbs,
                     atom_j_orbs=self.atom_j_orbs, kpoints=[list(p) for p in self.kpoints],
                     kpoint_weights=list(self.kpoint_weights), e_range=list(self.e_range),
                     nspin=self.nspin, spin=self.spin, de=self.de, sigma=self.sigma,
                     invert=self.invert, shift_to_efermi=self.shift_to_efermi,
                     max_kpoint_num=self.max_kpoint_num)
        return value

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> PyatbCohpPrepareRequest:
        return cls._from_dict(payload, "prepare")


@dataclass(frozen=True, slots=True)
class PyatbCohpExecuteRequest(_CohpRequest):
    executable: str = "pyatb"
    mpi_ranks: int = 1
    omp_threads: int = 1
    timeout_seconds: float | None = None
    dry_run: bool = False

    def __post_init__(self) -> None:
        _CohpRequest.__post_init__(self)
        _require_nonempty_string(self.executable, "executable")
        _positive_integer(self.mpi_ranks, "mpi_ranks")
        _positive_integer(self.omp_threads, "omp_threads")
        if self.timeout_seconds is not None and _finite_number(self.timeout_seconds, "timeout_seconds") <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not isinstance(self.dry_run, bool):
            raise ValueError("dry_run must be boolean")

    @property
    def operation(self) -> Literal["execute"]:
        return "execute"

    def to_dict(self) -> dict[str, JSONValue]:
        value = _CohpRequest.to_dict(self)
        value.update(executable=self.executable, mpi_ranks=self.mpi_ranks,
                     omp_threads=self.omp_threads, timeout_seconds=self.timeout_seconds,
                     dry_run=self.dry_run)
        return value

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> PyatbCohpExecuteRequest:
        return cls._from_dict(payload, "execute")


@dataclass(frozen=True, slots=True)
class PyatbCohpCollectRequest(_CohpRequest):
    spectrum_path_rel: str = "inputs/Out/COHP/COHP.dat"
    metadata_path_rel: str = "inputs/Out/COHP/COHP.meta.json"

    def __post_init__(self) -> None:
        _CohpRequest.__post_init__(self)
        object.__setattr__(self, "spectrum_path_rel", _file_path(self.spectrum_path_rel, "spectrum_path_rel"))
        object.__setattr__(self, "metadata_path_rel", _file_path(self.metadata_path_rel, "metadata_path_rel"))
        if self.spectrum_path_rel == self.metadata_path_rel:
            raise ValueError("spectrum and metadata paths must differ")

    @property
    def operation(self) -> Literal["collect"]:
        return "collect"

    def to_dict(self) -> dict[str, JSONValue]:
        value = _CohpRequest.to_dict(self)
        value.update(spectrum_path_rel=self.spectrum_path_rel,
                     metadata_path_rel=self.metadata_path_rel)
        return value

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> PyatbCohpCollectRequest:
        return cls._from_dict(payload, "collect")
