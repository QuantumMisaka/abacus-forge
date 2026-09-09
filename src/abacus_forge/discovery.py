"""Static, side-effect-free capability and request-schema discovery."""

from __future__ import annotations

import dataclasses
import json
from typing import Any, Mapping

from abacus_forge.contracts import (
    JSONValue,
    REQUEST_SCHEMA_VERSION,
    CapabilityDescriptor,
    ScfCollectRequest,
    ScfExecuteRequest,
    ScfModifyRequest,
    ScfPrepareRequest,
    AtstNebPrepareRequest,
    AtstNebExecuteRequest,
    AtstNebPostprocessRequest,
)
from abacus_forge.errors import ForgeRequestError


CAPABILITIES_SCHEMA_VERSION = "forge.capabilities/v1"
SCHEMA_DISCOVERY_VERSION = "forge.schema-discovery/v1"

SCF_REQUEST_TYPES = {
    "prepare": ScfPrepareRequest,
    "modify": ScfModifyRequest,
    "execute": ScfExecuteRequest,
    "collect": ScfCollectRequest,
}
ATST_NEB_REQUEST_TYPES = {
    "prepare": AtstNebPrepareRequest,
    "execute": AtstNebExecuteRequest,
    "postprocess": AtstNebPostprocessRequest,
}

REQUIRED_WIRE_FIELDS = {
    "prepare": frozenset({"schema_version", "operation", "operation_id", "workspace_rel", "structure_path_rel"}),
    "modify": frozenset({"schema_version", "operation", "operation_id", "workspace_rel"}),
    "execute": frozenset({"schema_version", "operation", "operation_id", "workspace_rel"}),
    "collect": frozenset({"schema_version", "operation", "operation_id", "workspace_rel"}),
}

_SCF_DESCRIPTOR = CapabilityDescriptor(
    name="scf",
    maturity="experimental",
    engine="abacus",
    operations=("prepare", "modify", "execute", "collect"),
    inputs={
        "prepare": ("structure",),
        "modify": ("prepared_workspace",),
        "execute": ("prepared_workspace",),
        "collect": ("workspace_outputs",),
    },
    artifact_roles=("input", "provenance_manifest", "output"),
    optional_dependencies=(),
)
_ATST_NEB_DESCRIPTOR = CapabilityDescriptor(
    name="atst-neb",
    maturity="experimental",
    engine="atst-tools",
    operations=("prepare", "execute", "postprocess"),
    inputs={
        "prepare": ("initial_structure", "final_structure"),
        "execute": ("workflow_config",),
        "postprocess": ("trajectory",),
    },
    artifact_roles=("input", "provenance_manifest", "output"),
    optional_dependencies=("atst-tools",),
)

_OPERATION_IDS = {
    "type": "string",
    "format": "uuid",
    "pattern": r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
}
_CANONICAL_WORKSPACE_PATTERN = (
    r"^(?:\.(?=$)|(?!(?:\.{1,2})(?:/|$))[^/\\]+"
    r"(?:/(?!\.{1,2}(?:/|$))[^/\\]+)*)$"
)
_CANONICAL_FILE_PATTERN = (
    r"^(?:(?!\.{1,2}(?:/|$))[^/\\]+)"
    r"(?:/(?!\.{1,2}(?:/|$))[^/\\]+)*$"
)
_WORKSPACE_REL = {"type": "string", "minLength": 1, "pattern": _CANONICAL_WORKSPACE_PATTERN}
_JSON_OBJECT = {"type": "object"}


def _base_properties(operation: str) -> dict[str, JSONValue]:
    return {
        "schema_version": {"type": "string", "const": REQUEST_SCHEMA_VERSION},
        "operation": {"type": "string", "const": operation},
        "operation_id": dict(_OPERATION_IDS),
        "workspace_rel": dict(_WORKSPACE_REL),
    }


def _request_properties(operation: str) -> dict[str, JSONValue]:
    properties = _base_properties(operation)
    if operation == "prepare":
        properties.update(
            {
                "structure_path_rel": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": _CANONICAL_FILE_PATTERN,
                },
                "structure_format": {"type": ["string", "null"], "minLength": 1, "default": None},
                "parameters": dict(_JSON_OBJECT, **{"propertyNames": {"type": "string"}, "default": {}}),
            }
        )
    elif operation == "modify":
        properties.update(
            {
                "input_updates": dict(_JSON_OBJECT, **{"propertyNames": {"minLength": 1}, "default": {}}),
                "remove_parameters": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "default": [],
                },
            }
        )
    elif operation == "execute":
        properties.update(
            {
                "executable": {"type": "string", "minLength": 1, "default": "abacus"},
                "mpi_ranks": {"type": "integer", "minimum": 1, "default": 1},
                "omp_threads": {"type": "integer", "minimum": 1, "default": 1},
                "timeout_seconds": {
                    "type": ["number", "null"],
                    "exclusiveMinimum": 0,
                    "default": None,
                },
                "dry_run": {"type": "boolean", "default": False},
            }
        )
    return properties


def _atst_request_properties(operation: str) -> dict[str, JSONValue]:
    properties = _base_properties(operation)
    properties["capability"] = {"type": "string", "const": "atst-neb"}
    if operation == "prepare":
        properties.update({
            "init_structure_path_rel": {"type": "string", "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN},
            "final_structure_path_rel": {"type": "string", "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN},
            "n_images": {"type": "integer", "minimum": 1, "default": 1},
            "chain_path_rel": {"type": "string", "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN, "default": "inputs/init_neb_chain.traj"},
            "method": {"type": "string", "enum": ["IDPP", "linear"], "default": "IDPP"},
            "no_align": {"type": "boolean", "default": False},
        })
    elif operation == "execute":
        properties.update({
            "config_path_rel": {"type": "string", "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN},
            "dry_run": {"type": "boolean", "default": False},
            "check_input": {"type": "boolean", "default": False},
            "check_input_timeout": {"type": "number", "exclusiveMinimum": 0, "default": 30.0},
            "abacus_executable": {"type": ["string", "null"], "minLength": 1, "default": None},
            "timeout_seconds": {"type": ["number", "null"], "exclusiveMinimum": 0, "default": None},
        })
    elif operation == "postprocess":
        properties.update({
            "trajectory_path_rel": {"type": "string", "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN},
            "n_max": {"type": "integer", "minimum": 0, "default": 0},
            "summary_path_rel": {"type": "string", "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN, "default": "reports/atst/neb-summary.json"},
            "output_prefix": {"type": "string", "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN, "default": "outputs/atst/neb-ts"},
            "write_latest": {"type": "boolean", "default": False},
            "write_neb_init_chain": {"type": "boolean", "default": False},
            "plot": {"type": "boolean", "default": False},
            "plot_label": {"type": ["string", "null"], "minLength": 1, "default": None},
            "energy_profile": {"type": "boolean", "default": False},
            "vib_analysis": {"type": "boolean", "default": False},
            "vib_thr": {"type": "number", "exclusiveMinimum": 0, "default": 0.01},
            "strict_band": {"type": "boolean", "default": False},
        })
    return properties


def _representative_request(operation: str) -> Any:
    request_type = SCF_REQUEST_TYPES[operation]
    kwargs: dict[str, Any] = {
        "operation_id": "123e4567-e89b-42d3-a456-426614174000",
        "workspace_rel": ".",
    }
    if operation == "prepare":
        kwargs["structure_path_rel"] = "source.STRU"
    return request_type(**kwargs)


def _atst_representative_request(operation: str) -> Any:
    request_type = ATST_NEB_REQUEST_TYPES[operation]
    kwargs: dict[str, Any] = {"operation_id": "123e4567-e89b-42d3-a456-426614174000", "workspace_rel": "."}
    if operation == "prepare":
        kwargs.update(init_structure_path_rel="initial.cif", final_structure_path_rel="final.cif")
    elif operation == "execute":
        kwargs["config_path_rel"] = "workflow.yaml"
    else:
        kwargs["trajectory_path_rel"] = "neb.traj"
    return request_type(**kwargs)


def _schema_for(operation: str) -> dict[str, JSONValue]:
    request_type = SCF_REQUEST_TYPES[operation]
    request = _representative_request(operation)
    field_names = {record_field.name for record_field in dataclasses.fields(request_type)} | {"operation"}
    wire_names = set(request.to_dict())
    if field_names != wire_names:
        raise RuntimeError(
            f"{request_type.__name__} dataclass fields and wire serialization drifted: "
            f"fields={sorted(field_names)} wire={sorted(wire_names)}"
        )
    properties = _request_properties(operation)
    if set(properties) != field_names:
        raise RuntimeError(
            f"static schema properties and {request_type.__name__} fields drifted: "
            f"schema={sorted(properties)} fields={sorted(field_names)}"
        )
    required = [name for name in ("schema_version", "operation", "operation_id", "workspace_rel", "structure_path_rel") if name in REQUIRED_WIRE_FIELDS[operation]]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": request_type.__name__,
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


def _atst_schema_for(operation: str) -> dict[str, JSONValue]:
    request_type = ATST_NEB_REQUEST_TYPES[operation]
    request = _atst_representative_request(operation)
    field_names = {record_field.name for record_field in dataclasses.fields(request_type)} | {"operation", "capability"}
    wire_names = set(request.to_dict())
    if field_names != wire_names:
        raise RuntimeError(f"{request_type.__name__} dataclass fields and wire serialization drifted")
    properties = _atst_request_properties(operation)
    if set(properties) != field_names:
        raise RuntimeError(f"static schema properties and {request_type.__name__} fields drifted")
    required = [name for name in ("schema_version", "capability", "operation", "operation_id", "workspace_rel",
                                  "init_structure_path_rel", "final_structure_path_rel", "config_path_rel", "trajectory_path_rel") if name in field_names or name in {"capability", "operation"}]
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": request_type.__name__, "type": "object",
            "additionalProperties": False, "properties": properties, "required": required}
    if operation == "execute":
        schema["allOf"] = [{
            "if": {"required": ["check_input"], "properties": {"check_input": {"const": True}}},
            "then": {"required": ["dry_run"], "properties": {"dry_run": {"const": True}}},
        }]
    return schema


def _fresh(value: Mapping[str, JSONValue]) -> dict[str, JSONValue]:
    """Return a detached JSON-safe copy of a static discovery document."""
    return json.loads(json.dumps(value, allow_nan=False))


def capabilities_document() -> dict[str, JSONValue]:
    """Return the deterministic v1 capability registry document."""
    return _fresh(
        {
            "schema_version": CAPABILITIES_SCHEMA_VERSION,
            "capabilities": [_SCF_DESCRIPTOR.to_dict(), _ATST_NEB_DESCRIPTOR.to_dict()],
        }
    )


def request_schema_document(capability: str, operation: str) -> dict[str, JSONValue]:
    """Return a static request schema, rejecting unsupported selectors."""
    if capability == _SCF_DESCRIPTOR.name and operation in SCF_REQUEST_TYPES:
        schema = _schema_for(operation)
    elif capability == _ATST_NEB_DESCRIPTOR.name and operation in ATST_NEB_REQUEST_TYPES:
        schema = _atst_schema_for(operation)
    else:
        raise ForgeRequestError(f"unknown capability or operation: {capability!r}/{operation!r}")
    return _fresh(
        {
            "schema_version": SCHEMA_DISCOVERY_VERSION,
            "capability": capability,
            "operation": operation,
            "request_schema": schema,
        }
    )
