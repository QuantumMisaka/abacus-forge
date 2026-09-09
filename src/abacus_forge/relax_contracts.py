"""Typed, immutable request contracts for ABACUS ionic relaxation operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping

from abacus_forge.contracts import (
    JSONValue,
    ScfCollectRequest,
    ScfExecuteRequest,
    ScfModifyRequest,
    ScfPrepareRequest,
    _require_literal,
)


_RELAX_CAPABILITIES = frozenset({"relax", "cell-relax"})


def _require_matching_calculation(
    values: Mapping[str, JSONValue], capability: str, field_name: str
) -> None:
    """Reject an explicitly supplied INPUT calculation for another phase."""
    if "calculation" not in values:
        return
    calculation = values["calculation"]
    if not isinstance(calculation, str) or calculation != capability:
        raise ValueError(f"{field_name} calculation must match capability {capability!r}")


class _RelaxCapabilityMixin:
    """Add and validate the required Relax capability selector."""

    __slots__ = ()

    capability: Literal["relax", "cell-relax"]

    def __post_init__(self) -> None:
        _require_literal(self.capability, _RELAX_CAPABILITIES, "capability")
        super().__post_init__()  # type: ignore[misc]

    def to_dict(self) -> dict[str, JSONValue]:
        payload = super().to_dict()  # type: ignore[misc]
        payload["capability"] = self.capability
        return payload


@dataclass(frozen=True, slots=True)
class RelaxPrepareRequest(_RelaxCapabilityMixin, ScfPrepareRequest):
    """Typed request for preparing one Relax workspace."""

    capability: Literal["relax", "cell-relax"] = field(kw_only=True)

    def __post_init__(self) -> None:
        super(RelaxPrepareRequest, self).__post_init__()
        _require_matching_calculation(self.parameters, self.capability, "parameters")


@dataclass(frozen=True, slots=True)
class RelaxModifyRequest(_RelaxCapabilityMixin, ScfModifyRequest):
    """Typed request for modifying one Relax workspace."""

    capability: Literal["relax", "cell-relax"] = field(kw_only=True)

    def __post_init__(self) -> None:
        super(RelaxModifyRequest, self).__post_init__()
        _require_matching_calculation(self.input_updates, self.capability, "input_updates")
        if "calculation" in self.remove_parameters:
            raise ValueError("remove_parameters cannot include calculation")


@dataclass(frozen=True, slots=True)
class RelaxExecuteRequest(_RelaxCapabilityMixin, ScfExecuteRequest):
    """Typed request for executing one Relax workspace."""

    capability: Literal["relax", "cell-relax"] = field(kw_only=True)


@dataclass(frozen=True, slots=True)
class RelaxCollectRequest(_RelaxCapabilityMixin, ScfCollectRequest):
    """Typed request for collecting one Relax workspace."""

    capability: Literal["relax", "cell-relax"] = field(kw_only=True)


__all__ = [
    "RelaxCollectRequest",
    "RelaxExecuteRequest",
    "RelaxModifyRequest",
    "RelaxPrepareRequest",
]
