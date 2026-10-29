"""Phase A capability and integration contracts for the Forge backend.

This module is the Python source of truth for the Computation Factory's
capability-output, workspace-plan, resource, identity, diagnostic, and Paimon
projection contracts.  It is intentionally read-only metadata: no function here
prepares inputs, starts a process, writes a workspace, or decides scientific
acceptance.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from typing import Any, Literal

from abacus_forge.contracts import (
    JSONValue,
    canonical_relative_path,
)
from abacus_forge.errors import ForgeSchemaError

WORKSPACE_PLAN_SCHEMA_VERSION = "forge.workspace-plan/v1"
RESOURCE_SPEC_SCHEMA_VERSION = "forge.resource-spec/v1"
EXECUTION_IDENTITY_SCHEMA_VERSION = "forge.execution-identity/v1"
DIAGNOSTIC_SCHEMA_VERSION = "forge.diagnostic/v1"
CAPABILITY_CONTRACT_SCHEMA_VERSION = "forge.capability-contract/v1"
CAPABILITY_CONTRACTS_SCHEMA_VERSION = "forge.capability-contracts/v1"
TOOL_PROJECTION_SCHEMA_VERSION = "forge.tool-projection/v1"

_WORKSPACE_ROLES = frozenset({"inputs", "run", "next_inputs", "analysis"})
_WORKSPACE_STRATEGIES = frozenset({"explicit"})
_LOCALITIES = frozenset({"single-node", "multi-node"})
_SEVERITIES = frozenset({"info", "warning", "error"})
_OUTPUT_KINDS = frozenset({"file", "directory"})
_METRIC_KINDS = frozenset({"reported", "derived"})
_DIAGNOSTIC_CLASSES = frozenset({
    "missing_output",
    "unparseable_output",
    "engine_nonzero_exit",
    "resource_oom",
    "resource_timeout",
    "identity_mismatch",
})

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FORGE_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def _mapping_payload(payload: object, record_name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{record_name} must be a JSON object")
    return dict(payload)


def _construct_strict(cls: type, payload: object, record_name: str):
    values = _mapping_payload(payload, record_name)
    allowed = {field.name for field in fields(cls)}
    unknown = sorted((key for key in values if key not in allowed), key=str)
    if unknown:
        raise ValueError(f"{record_name} contains unknown fields: {', '.join(unknown)}")
    try:
        return cls(**values)
    except ValueError:
        raise
    except (TypeError, KeyError) as error:
        raise ValueError(f"{record_name} contains invalid fields") from error


def _require_schema_version(value: object, expected: str, record_name: str) -> None:
    if value != expected:
        raise ValueError(f"{record_name} schema_version must be {expected!r}")


def _require_nonempty_string(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_literal(value: object, allowed: frozenset[str] | set[str], field_name: str) -> None:
    if not isinstance(value, str) or value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"{field_name} must be one of: {choices}")


def _require_positive_int(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


def _require_positive_timeout(value: object, field_name: str = "timeout_seconds") -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{field_name} must be a positive finite number")


def _require_path(value: object, field_name: str) -> str:
    _require_nonempty_string(value, field_name)
    try:
        return canonical_relative_path(value)
    except ValueError as error:
        raise ValueError(f"{field_name} must be a canonical relative POSIX path") from error


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError(f"{field_name} must be a sequence of non-empty strings")
    items: list[str] = []
    for item in value:
        _require_nonempty_string(item, field_name)
        items.append(item)
    if len(items) != len(set(items)):
        raise ValueError(f"{field_name} must not contain duplicates")
    return tuple(items)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
    if isinstance(value, Sequence) and not isinstance(value, str):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> JSONValue:
    if isinstance(value, tuple) and all(isinstance(item, tuple) and len(item) == 2 for item in value):
        return {key: _thaw(item) for key, item in value}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, list):
        return [_thaw(item) for item in value]
    if isinstance(value, dict):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ValueError(f"value is not JSON-safe: {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class WorkspacePlan:
    """Explicit local directory intent for one Forge workspace."""

    schema_version: str = WORKSPACE_PLAN_SCHEMA_VERSION
    project_root: str = "."
    workspace_rel: str = "."
    role: Literal["inputs", "run", "next_inputs", "analysis"] = "run"
    strategy: Literal["explicit"] = "explicit"
    contained_paths: bool = True
    allow_existing: bool = False

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version, WORKSPACE_PLAN_SCHEMA_VERSION, "workspace plan")
        object.__setattr__(self, "project_root", _require_path(self.project_root, "project_root"))
        object.__setattr__(self, "workspace_rel", _require_path(self.workspace_rel, "workspace_rel"))
        _require_literal(self.role, _WORKSPACE_ROLES, "role")
        _require_literal(self.strategy, _WORKSPACE_STRATEGIES, "strategy")
        if not isinstance(self.contained_paths, bool):
            raise ValueError("contained_paths must be a boolean")
        if not isinstance(self.allow_existing, bool):
            raise ValueError("allow_existing must be a boolean")

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "project_root": self.project_root,
            "workspace_rel": self.workspace_rel,
            "role": self.role,
            "strategy": self.strategy,
            "contained_paths": self.contained_paths,
            "allow_existing": self.allow_existing,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> "WorkspacePlan":
        return _construct_strict(cls, payload, "workspace plan")


@dataclass(frozen=True, slots=True)
class ResourceSpec:
    """An explicit execution resource request; never a scheduler decision."""

    schema_version: str = RESOURCE_SPEC_SCHEMA_VERSION
    mpi_ranks: int = 1
    omp_threads: int = 1
    gpu_count: int = 1
    gpu_shape: str = "1gpu"
    expected_locality: Literal["single-node", "multi-node"] = "single-node"
    environment_ref: str | None = None
    timeout_seconds: float | None = None
    dry_run: bool = False

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version, RESOURCE_SPEC_SCHEMA_VERSION, "resource spec")
        _require_positive_int(self.mpi_ranks, "mpi_ranks")
        _require_positive_int(self.omp_threads, "omp_threads")
        _require_positive_int(self.gpu_count, "gpu_count")
        _require_nonempty_string(self.gpu_shape, "gpu_shape")
        _require_literal(self.expected_locality, _LOCALITIES, "expected_locality")
        if self.environment_ref is not None:
            object.__setattr__(self, "environment_ref", _require_path(self.environment_ref, "environment_ref"))
        if self.timeout_seconds is not None:
            _require_positive_timeout(self.timeout_seconds)
        if not isinstance(self.dry_run, bool):
            raise ValueError("dry_run must be a boolean")

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "mpi_ranks": self.mpi_ranks,
            "omp_threads": self.omp_threads,
            "gpu_count": self.gpu_count,
            "gpu_shape": self.gpu_shape,
            "expected_locality": self.expected_locality,
            "environment_ref": self.environment_ref,
            "timeout_seconds": self.timeout_seconds,
            "dry_run": self.dry_run,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> "ResourceSpec":
        return _construct_strict(cls, payload, "resource spec")


@dataclass(frozen=True, slots=True)
class ExecutionIdentity:
    """Immutable identity of the engine and Forge runtime that produced evidence."""

    schema_version: str = EXECUTION_IDENTITY_SCHEMA_VERSION
    engine: str = "abacus"
    engine_version: str = ""
    engine_build: str = ""
    executable_sha256: str = ""
    container_image: str | None = None
    container_digest: str | None = None
    forge_version: str = ""
    forge_commit: str = ""
    parser_backend: str = "native"
    python_lock_ref: str = "reports/python-lock.json"
    resource_spec_ref: str = "reports/resource-spec.json"

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version, EXECUTION_IDENTITY_SCHEMA_VERSION, "execution identity")
        for field_name in ("engine", "engine_version", "engine_build", "forge_version", "parser_backend"):
            _require_nonempty_string(getattr(self, field_name), field_name)
        if not isinstance(self.executable_sha256, str) or not _SHA256_RE.fullmatch(self.executable_sha256):
            raise ValueError("executable_sha256 must be a lowercase 64-hex SHA-256")
        if self.container_image is not None:
            _require_nonempty_string(self.container_image, "container_image")
        if self.container_digest is not None:
            digest = self.container_digest
            if not isinstance(digest, str) or not digest.startswith("sha256:") or not _SHA256_RE.fullmatch(digest[7:]):
                raise ValueError("container_digest must be 'sha256:' followed by 64 lowercase hex digits")
        if not isinstance(self.forge_commit, str) or not _FORGE_COMMIT_RE.fullmatch(self.forge_commit):
            raise ValueError("forge_commit must be a lowercase 40-hex Git commit")
        for field_name in ("python_lock_ref", "resource_spec_ref"):
            object.__setattr__(self, field_name, _require_path(getattr(self, field_name), field_name))

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "engine": self.engine,
            "engine_version": self.engine_version,
            "engine_build": self.engine_build,
            "executable_sha256": self.executable_sha256,
            "container_image": self.container_image,
            "container_digest": self.container_digest,
            "forge_version": self.forge_version,
            "forge_commit": self.forge_commit,
            "parser_backend": self.parser_backend,
            "python_lock_ref": self.python_lock_ref,
            "resource_spec_ref": self.resource_spec_ref,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> "ExecutionIdentity":
        return _construct_strict(cls, payload, "execution identity")


@dataclass(frozen=True, slots=True)
class DiagnosticRecord:
    """A typed observation about an operation failure or incompleteness."""

    schema_version: str = DIAGNOSTIC_SCHEMA_VERSION
    operation_id: str = ""
    stage: str = ""
    error_class: str = ""
    severity: Literal["info", "warning", "error"] = "error"
    message: str = ""
    observed_facts: Mapping[str, JSONValue] | tuple[tuple[str, JSONValue], ...] = ()
    workdir_ref: str = "."
    artifact_refs: Sequence[str] = ()
    resource_evidence_ref: str | None = None
    safe_next_actions: Sequence[str] = ()
    scientific_interpretation: Literal["unassessed"] = "unassessed"

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version, DIAGNOSTIC_SCHEMA_VERSION, "diagnostic")
        try:
            parsed = uuid.UUID(self.operation_id)
        except (ValueError, AttributeError, TypeError) as error:
            raise ValueError("operation_id must be a lowercase UUIDv4") from error
        if parsed.version != 4 or str(parsed) != self.operation_id:
            raise ValueError("operation_id must be a lowercase UUIDv4")
        for field_name in ("stage", "error_class", "message"):
            _require_nonempty_string(getattr(self, field_name), field_name)
        _require_literal(self.severity, _SEVERITIES, "severity")
        if self.error_class not in _DIAGNOSTIC_CLASSES:
            choices = ", ".join(sorted(_DIAGNOSTIC_CLASSES))
            raise ValueError(f"error_class must be one of: {choices}")
        frozen_facts = _freeze(self.observed_facts)
        if not isinstance(frozen_facts, tuple):
            raise ValueError("observed_facts must be a JSON object")
        object.__setattr__(self, "observed_facts", frozen_facts)
        object.__setattr__(self, "workdir_ref", _require_path(self.workdir_ref, "workdir_ref"))
        object.__setattr__(self, "artifact_refs", _string_tuple(self.artifact_refs, "artifact_refs"))
        if self.resource_evidence_ref is not None:
            object.__setattr__(
                self, "resource_evidence_ref",
                _require_path(self.resource_evidence_ref, "resource_evidence_ref"),
            )
        object.__setattr__(self, "safe_next_actions", _string_tuple(self.safe_next_actions, "safe_next_actions"))
        _require_literal(self.scientific_interpretation, {"unassessed"}, "scientific_interpretation")

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "operation_id": self.operation_id,
            "stage": self.stage,
            "error_class": self.error_class,
            "severity": self.severity,
            "message": self.message,
            "observed_facts": _thaw(self.observed_facts),
            "workdir_ref": self.workdir_ref,
            "artifact_refs": list(self.artifact_refs),
            "resource_evidence_ref": self.resource_evidence_ref,
            "safe_next_actions": list(self.safe_next_actions),
            "scientific_interpretation": self.scientific_interpretation,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> "DiagnosticRecord":
        return _construct_strict(cls, payload, "diagnostic")


@dataclass(frozen=True, slots=True)
class CapabilityOutputContract:
    """One canonical Forge output exposed to human or adapter consumers."""

    name: str
    kind: Literal["file", "directory"]
    required: bool
    availability: str
    artifact_role: str

    def __post_init__(self) -> None:
        _require_nonempty_string(self.name, "name")
        _require_literal(self.kind, _OUTPUT_KINDS, "kind")
        if not isinstance(self.required, bool):
            raise ValueError("required must be a boolean")
        _require_nonempty_string(self.availability, "availability")
        _require_nonempty_string(self.artifact_role, "artifact_role")

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "name": self.name,
            "kind": self.kind,
            "required": self.required,
            "availability": self.availability,
            "artifact_role": self.artifact_role,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> "CapabilityOutputContract":
        return _construct_strict(cls, payload, "capability output contract")


@dataclass(frozen=True, slots=True)
class CapabilityMetricContract:
    """A canonical metric and its unit/kind semantics."""

    name: str
    unit: str | None
    kind: Literal["reported", "derived"]
    source_marker_ref: str | None = None

    def __post_init__(self) -> None:
        _require_nonempty_string(self.name, "name")
        if self.unit is not None:
            _require_nonempty_string(self.unit, "unit")
        _require_literal(self.kind, _METRIC_KINDS, "kind")
        if self.source_marker_ref is not None:
            _require_nonempty_string(self.source_marker_ref, "source_marker_ref")

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "name": self.name,
            "unit": self.unit,
            "kind": self.kind,
            "source_marker_ref": self.source_marker_ref,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> "CapabilityMetricContract":
        return _construct_strict(cls, payload, "capability metric contract")


@dataclass(frozen=True, slots=True)
class CapabilityMaturityEvidence:
    """Evidence levels that currently support a capability maturity claim."""

    offline: bool
    installed: bool
    real_smoke: bool
    parity: bool

    def __post_init__(self) -> None:
        for field_name in ("offline", "installed", "real_smoke", "parity"):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean")

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "offline": self.offline,
            "installed": self.installed,
            "real_smoke": self.real_smoke,
            "parity": self.parity,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> "CapabilityMaturityEvidence":
        return _construct_strict(cls, payload, "capability maturity evidence")


@dataclass(frozen=True, slots=True)
class CapabilityContract:
    """Canonical contract for one Forge capability."""

    schema_version: str = CAPABILITY_CONTRACT_SCHEMA_VERSION
    capability: str = ""
    engine: str = "abacus"
    driver: str = "native"
    operations: Sequence[str] = ()
    maturity: Literal["experimental", "stable"] = "experimental"
    request_schema_ref: str = ""
    canonical_outputs: Sequence[CapabilityOutputContract] = ()
    metrics: Sequence[CapabilityMetricContract] = ()
    diagnostic_classes: Sequence[str] = ()
    maturity_evidence: CapabilityMaturityEvidence | None = None

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version, CAPABILITY_CONTRACT_SCHEMA_VERSION, "capability contract")
        _require_nonempty_string(self.capability, "capability")
        _require_nonempty_string(self.engine, "engine")
        _require_nonempty_string(self.driver, "driver")
        operations = _string_tuple(self.operations, "operations")
        if not operations:
            raise ValueError("operations must not be empty")
        object.__setattr__(self, "operations", operations)
        _require_literal(self.maturity, {"experimental", "stable"}, "maturity")
        _require_nonempty_string(self.request_schema_ref, "request_schema_ref")
        if not isinstance(self.canonical_outputs, Sequence) or isinstance(self.canonical_outputs, str):
            raise ValueError("canonical_outputs must be a sequence")
        outputs = tuple(
            item if isinstance(item, CapabilityOutputContract) else CapabilityOutputContract.from_dict(item)
            for item in self.canonical_outputs
        )
        names = [item.name for item in outputs]
        if len(names) != len(set(names)):
            raise ValueError("canonical_outputs must not contain duplicate names")
        object.__setattr__(self, "canonical_outputs", outputs)
        if not isinstance(self.metrics, Sequence) or isinstance(self.metrics, str):
            raise ValueError("metrics must be a sequence")
        metrics = tuple(
            item if isinstance(item, CapabilityMetricContract) else CapabilityMetricContract.from_dict(item)
            for item in self.metrics
        )
        metric_names = [item.name for item in metrics]
        if len(metric_names) != len(set(metric_names)):
            raise ValueError("metrics must not contain duplicate names")
        object.__setattr__(self, "metrics", metrics)
        diagnostic_classes = _string_tuple(self.diagnostic_classes, "diagnostic_classes")
        unknown = sorted(set(diagnostic_classes) - _DIAGNOSTIC_CLASSES)
        if unknown:
            raise ValueError(f"unknown diagnostic classes: {', '.join(unknown)}")
        object.__setattr__(self, "diagnostic_classes", diagnostic_classes)
        if self.maturity_evidence is not None and not isinstance(
            self.maturity_evidence, CapabilityMaturityEvidence
        ):
            object.__setattr__(
                self, "maturity_evidence",
                CapabilityMaturityEvidence.from_dict(self.maturity_evidence),
            )

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "capability": self.capability,
            "engine": self.engine,
            "driver": self.driver,
            "operations": list(self.operations),
            "maturity": self.maturity,
            "request_schema_ref": self.request_schema_ref,
            "canonical_outputs": [item.to_dict() for item in self.canonical_outputs],
            "metrics": [item.to_dict() for item in self.metrics],
            "diagnostic_classes": list(self.diagnostic_classes),
            "maturity_evidence": self.maturity_evidence.to_dict() if self.maturity_evidence else None,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> "CapabilityContract":
        return _construct_strict(cls, payload, "capability contract")


@dataclass(frozen=True, slots=True)
class ToolProjection:
    """A declared consumer projection from Forge facts to an adapter tool."""

    schema_version: str = TOOL_PROJECTION_SCHEMA_VERSION
    capability: str = ""
    operation: str = ""
    target: Literal["paimon.tool/v1"] = "paimon.tool/v1"
    tool_name: str = ""
    declared_outputs: Mapping[str, str] | tuple[tuple[str, str], ...] = ()
    diagnostic_mapping: Mapping[str, str] | tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _require_schema_version(self.schema_version, TOOL_PROJECTION_SCHEMA_VERSION, "tool projection")
        _require_nonempty_string(self.capability, "capability")
        _require_nonempty_string(self.operation, "operation")
        _require_literal(self.target, {"paimon.tool/v1"}, "target")
        _require_nonempty_string(self.tool_name, "tool_name")
        frozen_outputs = _freeze(self.declared_outputs)
        if not isinstance(frozen_outputs, tuple):
            raise ValueError("declared_outputs must be a JSON object")
        object.__setattr__(self, "declared_outputs", frozen_outputs)
        frozen_mapping = _freeze(self.diagnostic_mapping)
        if not isinstance(frozen_mapping, tuple):
            raise ValueError("diagnostic_mapping must be a JSON object")
        object.__setattr__(self, "diagnostic_mapping", frozen_mapping)

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "capability": self.capability,
            "operation": self.operation,
            "target": self.target,
            "tool_name": self.tool_name,
            "declared_outputs": _thaw(self.declared_outputs),
            "diagnostic_mapping": _thaw(self.diagnostic_mapping),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JSONValue]) -> "ToolProjection":
        return _construct_strict(cls, payload, "tool projection")


_SCF_CONTRACT = CapabilityContract(
    capability="scf",
    engine="abacus",
    driver="native",
    operations=("prepare", "modify", "execute", "collect"),
    maturity="experimental",
    request_schema_ref="forge.schema.scf/v1",
    canonical_outputs=(
        CapabilityOutputContract("work_dir", "directory", True, "always", "output"),
        CapabilityOutputContract("running_log_file", "file", False, "when_produced", "runtime_log"),
        CapabilityOutputContract("raw_artifacts_manifest_file", "file", False, "when_produced", "raw_artifacts_manifest"),
        CapabilityOutputContract("result_evidence_file", "file", False, "when_produced", "result_evidence"),
    ),
    metrics=(
        CapabilityMetricContract("total_energy", "eV", "reported", "abacus.marker.final_etot"),
        CapabilityMetricContract("fermi_energy", "eV", "reported", "abacus.marker.fermi_energy"),
        CapabilityMetricContract("scf_steps", None, "derived", "abacus.marker.scf_steps"),
    ),
    diagnostic_classes=(
        "missing_output", "unparseable_output", "engine_nonzero_exit",
        "resource_oom", "resource_timeout", "identity_mismatch",
    ),
    maturity_evidence=CapabilityMaturityEvidence(
        offline=True, installed=False, real_smoke=False, parity=False,
    ),
)

_CAPABILITIES: Mapping[str, CapabilityContract] = {
    _SCF_CONTRACT.capability: _SCF_CONTRACT,
}


def capability_contract(name: str) -> CapabilityContract:
    """Return an immutable capability contract or fail with a schema error."""
    try:
        return _CAPABILITIES[name]
    except (KeyError, TypeError) as error:
        raise ForgeSchemaError(f"unknown capability contract: {name}") from error


def capability_contracts() -> tuple[CapabilityContract, ...]:
    """Return all contracts sorted by capability name."""
    return tuple(_CAPABILITIES[name] for name in sorted(_CAPABILITIES))


def capability_contracts_document() -> dict[str, JSONValue]:
    """Return the deterministic registry document."""
    return {
        "schema_version": CAPABILITY_CONTRACTS_SCHEMA_VERSION,
        "capabilities": [item.to_dict() for item in capability_contracts()],
        "completeness": {
            "status": "seed",
            "note": "Phase A registry currently contains only the SCF reference capability",
        },
    }


def export_capability_contracts() -> str:
    """Return deterministic UTF-8 JSON for consumers and regression snapshots."""
    return json.dumps(
        capability_contracts_document(),
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"


def sha256_json_text(text: str) -> str:
    """Utility used by release inventory consumers to pin a registry snapshot."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


__all__ = [
    "CAPABILITY_CONTRACT_SCHEMA_VERSION",
    "CAPABILITY_CONTRACTS_SCHEMA_VERSION",
    "DIAGNOSTIC_SCHEMA_VERSION",
    "EXECUTION_IDENTITY_SCHEMA_VERSION",
    "RESOURCE_SPEC_SCHEMA_VERSION",
    "TOOL_PROJECTION_SCHEMA_VERSION",
    "WORKSPACE_PLAN_SCHEMA_VERSION",
    "CapabilityContract",
    "CapabilityMaturityEvidence",
    "CapabilityMetricContract",
    "CapabilityOutputContract",
    "DiagnosticRecord",
    "ExecutionIdentity",
    "ResourceSpec",
    "ToolProjection",
    "WorkspacePlan",
    "capability_contracts",
    "capability_contracts_document",
    "capability_contract",
    "export_capability_contracts",
    "sha256_json_text",
]
