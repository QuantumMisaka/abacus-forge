"""Typed, immutable request contracts for ABACUS molecular-dynamics operations."""

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


_MD_CAPABILITIES = frozenset({"md"})


def _require_md_calculation(values: Mapping[str, JSONValue], field_name: str) -> None:
    """Accept an omitted calculation, but reject any non-MD explicit value."""
    if "calculation" not in values:
        return
    calculation = values["calculation"]
    if not isinstance(calculation, str) or calculation != "md":
        raise ValueError(f"{field_name} calculation must match capability 'md'")


class _MdCapabilityMixin:
    """Add and validate the single required MD capability selector."""

    __slots__ = ()

    capability: Literal["md"]

    def __post_init__(self) -> None:
        _require_literal(self.capability, _MD_CAPABILITIES, "capability")
        super().__post_init__()  # type: ignore[misc]

    def to_dict(self) -> dict[str, JSONValue]:
        payload = super().to_dict()  # type: ignore[misc]
        payload["capability"] = self.capability
        return payload


@dataclass(frozen=True, slots=True)
class MdPrepareRequest(_MdCapabilityMixin, ScfPrepareRequest):
    """Typed request for preparing one MD workspace."""

    capability: Literal["md"] = field(kw_only=True)

    def __post_init__(self) -> None:
        super(MdPrepareRequest, self).__post_init__()
        _require_md_calculation(self.parameters, "parameters")


@dataclass(frozen=True, slots=True)
class MdModifyRequest(_MdCapabilityMixin, ScfModifyRequest):
    """Typed request for modifying one MD workspace."""

    capability: Literal["md"] = field(kw_only=True)

    def __post_init__(self) -> None:
        super(MdModifyRequest, self).__post_init__()
        _require_md_calculation(self.input_updates, "input_updates")
        if "calculation" in self.remove_parameters:
            raise ValueError("remove_parameters cannot include calculation")


@dataclass(frozen=True, slots=True)
class MdExecuteRequest(_MdCapabilityMixin, ScfExecuteRequest):
    """Typed request for executing one MD workspace."""

    capability: Literal["md"] = field(kw_only=True)


@dataclass(frozen=True, slots=True)
class MdCollectRequest(_MdCapabilityMixin, ScfCollectRequest):
    """Typed request for collecting one MD workspace."""

    capability: Literal["md"] = field(kw_only=True)


__all__ = [
    "MdCollectRequest",
    "MdExecuteRequest",
    "MdModifyRequest",
    "MdPrepareRequest",
]
