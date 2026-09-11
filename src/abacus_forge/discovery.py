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
from abacus_forge.md_contracts import (
    MdCollectRequest,
    MdExecuteRequest,
    MdModifyRequest,
    MdPrepareRequest,
)
from abacus_forge.md_postprocess_contracts import MD_ANALYSIS_MODES, MdPostprocessRequest
from abacus_forge.postprocess_contracts import BandPostprocessRequest, DosPostprocessRequest
from abacus_forge.pyatb_contracts import (
    _PYATB_NSPIN_HR_CARDINALITY,
    PyatbBandCollectRequest,
    PyatbBandExecuteRequest,
    PyatbBandPrepareRequest,
)
from abacus_forge.export_contracts import ExportRequest
from abacus_forge.errors import ForgeRequestError
from abacus_forge.relax_contracts import (
    RelaxCollectRequest,
    RelaxExecuteRequest,
    RelaxModifyRequest,
    RelaxPrepareRequest,
)


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

RELAX_REQUEST_TYPES = {
    "prepare": RelaxPrepareRequest,
    "modify": RelaxModifyRequest,
    "execute": RelaxExecuteRequest,
    "collect": RelaxCollectRequest,
}
MD_REQUEST_TYPES = {
    "prepare": MdPrepareRequest,
    "modify": MdModifyRequest,
    "execute": MdExecuteRequest,
    "collect": MdCollectRequest,
    "postprocess": MdPostprocessRequest,
}
POSTPROCESS_REQUEST_TYPES = {
    "band": {"postprocess": BandPostprocessRequest},
    "dos": {"postprocess": DosPostprocessRequest},
}
PYATB_BAND_REQUEST_TYPES = {
    "prepare": PyatbBandPrepareRequest,
    "execute": PyatbBandExecuteRequest,
    "collect": PyatbBandCollectRequest,
}
EXPORT_REQUEST_TYPES = {"export": ExportRequest}

REQUEST_TYPES_BY_CAPABILITY = {
    "scf": SCF_REQUEST_TYPES,
    "relax": RELAX_REQUEST_TYPES,
    "cell-relax": RELAX_REQUEST_TYPES,
    "md": MD_REQUEST_TYPES,
    **POSTPROCESS_REQUEST_TYPES,
    "pyatb-band": PYATB_BAND_REQUEST_TYPES,
    "export": EXPORT_REQUEST_TYPES,
}

REQUIRED_WIRE_FIELDS = {
    "prepare": frozenset({"schema_version", "operation", "operation_id", "workspace_rel", "structure_path_rel"}),
    "modify": frozenset({"schema_version", "operation", "operation_id", "workspace_rel"}),
    "execute": frozenset({"schema_version", "operation", "operation_id", "workspace_rel"}),
    "collect": frozenset({"schema_version", "operation", "operation_id", "workspace_rel"}),
    "postprocess": frozenset({"schema_version", "operation", "operation_id", "workspace_rel"}),
    "export": frozenset({"schema_version", "operation", "operation_id", "workspace_rel"}),
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
    artifact_roles=("input", "output"),
    optional_dependencies=("atst-tools",),
)
_MD_DESCRIPTOR = CapabilityDescriptor(
    name="md",
    maturity="experimental",
    engine="abacus",
    operations=("prepare", "modify", "execute", "collect", "postprocess"),
    inputs={
        "prepare": ("structure",),
        "modify": ("prepared_workspace",),
        "execute": ("prepared_workspace",),
        "collect": ("workspace_outputs",),
        "postprocess": ("trajectory",),
    },
    artifact_roles=("input", "provenance_manifest", "output"),
    optional_dependencies=(),
)
_BAND_DESCRIPTOR = CapabilityDescriptor(
    name="band",
    maturity="experimental",
    engine="abacus",
    operations=("postprocess",),
    inputs={"postprocess": ("band_files",)},
    artifact_roles=("input", "output"),
    optional_dependencies=(),
)
_DOS_DESCRIPTOR = CapabilityDescriptor(
    name="dos",
    maturity="experimental",
    engine="abacus",
    operations=("postprocess",),
    inputs={"postprocess": ("dos_files", "pdos", "tdos")},
    artifact_roles=("input", "output"),
    optional_dependencies=(),
)
_PYATB_BAND_DESCRIPTOR = CapabilityDescriptor(
    name="pyatb-band",
    maturity="experimental",
    engine="pyatb",
    operations=("prepare", "execute", "collect"),
    inputs={
        "prepare": ("structure", "hr", "sr", "fermi_energy", "line_kpoints"),
        "execute": ("prepared_workspace",),
        "collect": ("workspace_outputs",),
    },
    artifact_roles=("input", "provenance_manifest", "output"),
    optional_dependencies=("pyatb",),
)
_EXPORT_DESCRIPTOR = CapabilityDescriptor(
    name="export",
    maturity="experimental",
    engine="forge",
    operations=("export",),
    inputs={"export": ("source_artifact_refs",)},
    artifact_roles=("output",),
    optional_dependencies=(),
)


def _relax_descriptor(name: str) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        name=name,
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


_CAPABILITY_DESCRIPTORS = (
    _SCF_DESCRIPTOR,
    _relax_descriptor("relax"),
    _relax_descriptor("cell-relax"),
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


def _base_properties(operation: str) -> dict[str, JSONValue]:
    return {
        "schema_version": {"type": "string", "const": REQUEST_SCHEMA_VERSION},
        "operation": {"type": "string", "const": operation},
        "operation_id": dict(_OPERATION_IDS),
        "workspace_rel": dict(_WORKSPACE_REL),
    }


def _request_properties(capability: str, operation: str) -> dict[str, JSONValue]:
    properties = _base_properties(operation)
    if capability != "scf":
        properties["capability"] = {"type": "string", "const": capability}
    if capability == "pyatb-band" and operation == "prepare":
        properties.update(
            {
                "structure_path_rel": {"type": "string", "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN},
                "hr_paths_rel": {
                    "type": "array", "minItems": 1, "maxItems": 2,
                    "items": {"type": "string", "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN},
                },
                "sr_path_rel": {"type": "string", "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN},
                "rr_path_rel": {
                    "type": ["string", "null"],
                    "minLength": 1,
                    "pattern": _CANONICAL_FILE_PATTERN,
                    "default": None,
                },
                "fermi_energy": {"type": "number"},
                "line_kpoints": {
                    "type": "array", "minItems": 2,
                    "items": {
                        "type": "object", "additionalProperties": False,
                        "properties": {
                            "coords": {"type": "array", "minItems": 3, "maxItems": 3, "items": {"type": "number"}},
                            "label": {"type": "string", "minLength": 1},
                        },
                        "required": ["coords"],
                    },
                },
                "nspin": {"type": "integer", "enum": list(_PYATB_NSPIN_HR_CARDINALITY), "default": 1},
                "line_segments": {"type": "integer", "minimum": 1, "default": 20},
                "max_kpoint_num": {"type": "integer", "minimum": 1, "default": 4000},
                "handoff_mode": {"type": "string", "enum": ["link", "copy"], "default": "link"},
            }
        )
    elif capability == "export" and operation == "export":
        properties.update(
            {
                "capability": {"type": "string", "const": "export"},
                "source_artifact_refs": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "operation_id": dict(_OPERATION_IDS),
                            "artifact_id": {"type": "string", "minLength": 1},
                        },
                        "required": ["operation_id", "artifact_id"],
                    },
                },
                "destination_path_rel": {"type": "string", "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN},
                "format": {"type": "string", "const": "json", "default": "json"},
                "pretty": {"type": "boolean", "default": False},
                "overwrite_policy": {"type": "string", "const": "fail", "default": "fail"},
            }
        )
    elif capability == "pyatb-band" and operation == "execute":
        properties.update(
            {
                "executable": {"type": "string", "minLength": 1, "default": "pyatb"},
                "mpi_ranks": {"type": "integer", "minimum": 1, "default": 1},
                "omp_threads": {"type": "integer", "minimum": 1, "default": 1},
                "timeout_seconds": {"type": ["number", "null"], "exclusiveMinimum": 0, "default": None},
                "dry_run": {"type": "boolean", "default": False},
            }
        )
    elif capability == "pyatb-band" and operation == "collect":
        properties.update(
            {
                "band_info_path_rel": {
                    "type": "string", "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN,
                    "default": "inputs/Out/Band_Structure/band_info.dat",
                },
                "band_data_paths_rel": {
                    "type": "array", "items": {"type": "string", "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN},
                    "default": [],
                },
                "band_picture_paths_rel": {
                    "type": "array", "items": {"type": "string", "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN},
                    "default": [],
                },
            }
        )
    elif capability == "band" and operation == "postprocess":
        properties.update(
            {
                "source_paths_rel": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN},
                },
                "output_dir_rel": {"type": "string", "minLength": 1, "pattern": _CANONICAL_WORKSPACE_PATTERN, "default": "outputs"},
                "plot_emin": {"type": "number", "default": -10.0},
                "plot_emax": {"type": "number", "default": 10.0},
                "save_data": {"type": "boolean", "default": True},
                "save_plot": {"type": "boolean", "default": True},
            }
        )
    elif capability == "dos" and operation == "postprocess":
        properties.update(
            {
                "dos_paths_rel": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN},
                },
                "pdos_path_rel": {"type": ["string", "null"], "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN, "default": None},
                "tdos_path_rel": {"type": ["string", "null"], "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN, "default": None},
                "output_dir_rel": {"type": "string", "minLength": 1, "pattern": _CANONICAL_WORKSPACE_PATTERN, "default": "outputs"},
                "include_tdos": {"type": "boolean", "default": True},
                "include_pdos": {"type": "boolean", "default": True},
                "pdos_mode": {"type": "string", "enum": ["species", "species+shell", "species+orbital", "atom", "atoms"], "default": "species"},
                "pdos_atom_indices": {"type": "array", "items": {"type": "integer", "minimum": 0}, "default": []},
                "plot_emin": {"type": "number", "default": -10.0},
                "plot_emax": {"type": "number", "default": 10.0},
                "save_data": {"type": "boolean", "default": True},
                "save_plot": {"type": "boolean", "default": True},
                "suffix": {"type": ["string", "null"], "minLength": 1, "pattern": r"^(?!\.{1,2}$)[^/\\]+$", "default": None},
            }
        )
    elif capability == "md" and operation == "postprocess":
        properties.update(
            {
                "trajectory_path_rel": {
                    "type": "string", "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN,
                },
                "analysis": {
                    "type": "array", "minItems": 1, "uniqueItems": True,
                    "items": {"type": "string", "enum": list(MD_ANALYSIS_MODES)},
                },
                "output_dir_rel": {
                    "type": "string", "minLength": 1, "pattern": _CANONICAL_WORKSPACE_PATTERN,
                    "default": "outputs/md-postprocess",
                },
                "start": {"type": "integer", "minimum": 0, "default": 0},
                "end": {"type": ["integer", "null"], "exclusiveMinimum": 0, "default": None},
                "stride": {"type": "integer", "minimum": 1, "default": 1},
                "parameters": {
                    "type": "object", "propertyNames": {"type": "string"}, "default": {},
                    "additionalProperties": True,
                    "properties": {
                        "timestep": {
                            "type": "number", "exclusiveMinimum": 0,
                            "description": "Sampling frame interval; required for MSD/VACF analyses.",
                        },
                        "selection": {
                            "type": ["object", "array"],
                            "description": "Optional atom-pair, angle, or index selection.",
                        },
                        "elements": {
                            "type": "array",
                            "description": "Optional RDF element-pair selection.",
                            "items": {"oneOf": [{"type": "string"}, {"type": "array"}]},
                        },
                        "rmax": {
                            "type": "number", "exclusiveMinimum": 0,
                            "description": "Positive RDF maximum distance.",
                        },
                        "nbins": {
                            "type": "integer", "minimum": 1,
                            "description": "Positive RDF histogram bin count.",
                        },
                        "save_data": {
                            "type": "boolean",
                            "description": "Whether to write analysis data files.",
                        },
                        "save_plot": {
                            "type": "boolean",
                            "description": "Whether to write analysis plots.",
                        },
                    },
                },
            }
        )
    elif operation == "prepare":
        parameters: dict[str, JSONValue] = {
            "type": "object",
            "propertyNames": {"type": "string"},
            "default": {},
        }
        if capability != "scf":
            parameters["properties"] = {
                "calculation": {"type": "string", "const": capability}
            }
        properties.update(
            {
                "structure_path_rel": {
                    "type": "string",
                    "minLength": 1,
                    "pattern": _CANONICAL_FILE_PATTERN,
                },
                "structure_format": {"type": ["string", "null"], "minLength": 1, "default": None},
                "parameters": parameters,
                "pseudo_sources": {
                    "type": "object",
                    "propertyNames": {"type": "string", "minLength": 1},
                    "additionalProperties": {"type": "string", "minLength": 1},
                    "default": {},
                },
                "orbital_sources": {
                    "type": "object",
                    "propertyNames": {"type": "string", "minLength": 1},
                    "additionalProperties": {"type": "string", "minLength": 1},
                    "default": {},
                },
                "asset_mode": {
                    "type": "string",
                    "enum": ["copy", "link"],
                    "default": "copy",
                },
            }
        )
    elif operation == "modify":
        input_updates: dict[str, JSONValue] = {
            "type": "object",
            "propertyNames": {"minLength": 1},
            "default": {},
        }
        remove_item: dict[str, JSONValue] = {"type": "string", "minLength": 1}
        if capability != "scf":
            input_updates["properties"] = {
                "calculation": {"type": "string", "const": capability}
            }
            remove_item["not"] = {"const": "calculation"}
        properties.update(
            {
                "input_updates": input_updates,
                "remove_parameters": {
                    "type": "array",
                    "items": remove_item,
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
            "n_images": {"type": "integer", "minimum": 1, "default": 5},
            "chain_path_rel": {"type": "string", "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN, "default": "inputs/init_neb_chain.traj"},
            "method": {"type": "string", "enum": ["IDPP", "linear"], "default": "IDPP"},
            "no_align": {"type": "boolean", "default": False},
        })
    elif operation == "execute":
        properties.update({
            "config_path_rel": {"type": "string", "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN},
            "dry_run": {"type": "boolean", "default": False},
            "check_input": {"type": "boolean", "default": False},
            "check_input_timeout": {"type": "integer", "exclusiveMinimum": 0, "default": 120},
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
            "plot_label": {"type": ["string", "null"], "minLength": 1, "pattern": _CANONICAL_FILE_PATTERN, "default": None},
            "energy_profile": {"type": "boolean", "default": False},
            "vib_analysis": {"type": "boolean", "default": False},
            "vib_thr": {"type": "number", "exclusiveMinimum": 0, "default": 0.10},
            "strict_band": {"type": "boolean", "default": False},
        })
    return properties


def _representative_request(capability: str, operation: str) -> Any:
    request_type = REQUEST_TYPES_BY_CAPABILITY[capability][operation]
    kwargs: dict[str, Any] = {
        "operation_id": "123e4567-e89b-42d3-a456-426614174000",
        "workspace_rel": ".",
    }
    if capability == "pyatb-band" and operation == "prepare":
        kwargs.update(
            {
                "structure_path_rel": "inputs/STRU",
                "hr_paths_rel": ("inputs/HR.dat",),
                "sr_path_rel": "inputs/SR.dat",
                "rr_path_rel": "inputs/rR.dat",
                "fermi_energy": 0.0,
                "line_kpoints": ({"coords": (0.0, 0.0, 0.0)}, {"coords": (0.5, 0.0, 0.0)}),
            }
        )
    elif operation == "prepare":
        kwargs["structure_path_rel"] = "source.STRU"
    elif capability == "band" and operation == "postprocess":
        kwargs["source_paths_rel"] = ("BANDS_1.dat",)
    elif capability == "dos" and operation == "postprocess":
        kwargs["dos_paths_rel"] = ("DOS1_smearing.dat",)
    elif capability == "md" and operation == "postprocess":
        kwargs.update({"trajectory_path_rel": "outputs/md.traj", "analysis": ("rdf",)})
    elif capability == "export" and operation == "export":
        from abacus_forge.contracts import ArtifactRef

        kwargs.update(
            {
                "source_artifact_refs": (ArtifactRef("123e4567-e89b-42d3-a456-426614174001", "artifact"),),
                "destination_path_rel": "exports/result.json",
            }
        )
    if capability not in {"scf", "band", "dos", "pyatb-band"} and not (
        capability == "md" and operation == "postprocess"
    ):
        kwargs["capability"] = capability
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


def _schema_for(capability: str, operation: str) -> dict[str, JSONValue]:
    request_type = REQUEST_TYPES_BY_CAPABILITY[capability][operation]
    request = _representative_request(capability, operation)
    field_names = {record_field.name for record_field in dataclasses.fields(request_type)} | {"operation"}
    if capability != "scf":
        field_names.add("capability")
    wire_names = set(request.to_dict())
    if field_names != wire_names:
        raise RuntimeError(
            f"{request_type.__name__} dataclass fields and wire serialization drifted: "
            f"fields={sorted(field_names)} wire={sorted(wire_names)}"
        )
    properties = _request_properties(capability, operation)
    if set(properties) != field_names:
        raise RuntimeError(
            f"static schema properties and {request_type.__name__} fields drifted: "
            f"schema={sorted(properties)} fields={sorted(field_names)}"
        )
    required = [
        name
        for name in (
            "schema_version",
            "operation",
            "operation_id",
            "workspace_rel",
            "structure_path_rel",
            "capability",
        )
        if name in REQUIRED_WIRE_FIELDS[operation]
        or (name == "capability" and capability != "scf")
    ]
    if capability == "pyatb-band" and operation == "prepare":
        required.extend(
            ["hr_paths_rel", "sr_path_rel", "fermi_energy", "line_kpoints"]
        )
    elif capability == "band" and operation == "postprocess":
        required.append("source_paths_rel")
    elif capability == "dos" and operation == "postprocess":
        required.append("dos_paths_rel")
    elif capability == "md" and operation == "postprocess":
        required.extend(["trajectory_path_rel", "analysis"])
    elif capability == "export" and operation == "export":
        required.extend(["source_artifact_refs", "destination_path_rel"])
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": request_type.__name__,
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }
    if capability == "pyatb-band" and operation == "prepare":
        spin_two_hr_count = _PYATB_NSPIN_HR_CARDINALITY[2]
        default_hr_count = _PYATB_NSPIN_HR_CARDINALITY[1]
        schema["allOf"] = [
            {
                "if": {
                    "required": ["nspin"],
                    "properties": {"nspin": {"const": 2}},
                },
                "then": {
                    "properties": {
                        "hr_paths_rel": {
                            "minItems": spin_two_hr_count,
                            "maxItems": spin_two_hr_count,
                        }
                    }
                },
                "else": {
                    "properties": {
                        "hr_paths_rel": {
                            "minItems": default_hr_count,
                            "maxItems": default_hr_count,
                        }
                    }
                },
            }
        ]
    return schema


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
    if operation == "postprocess":
        schema["allOf"] = [{"if": {"required": ["plot_label"], "properties": {"plot_label": {"type": "string"}}}, "then": {"required": ["plot"], "properties": {"plot": {"const": True}}}}]
    return schema


def _fresh(value: Mapping[str, JSONValue]) -> dict[str, JSONValue]:
    """Return a detached JSON-safe copy of a static discovery document."""
    return json.loads(json.dumps(value, allow_nan=False))


def capabilities_document() -> dict[str, JSONValue]:
    """Return the deterministic v1 capability registry document."""
    return _fresh(
        {
            "schema_version": CAPABILITIES_SCHEMA_VERSION,
            "capabilities": [
                descriptor.to_dict()
                for descriptor in (
                    *_CAPABILITY_DESCRIPTORS,
                    _ATST_NEB_DESCRIPTOR,
                    _MD_DESCRIPTOR,
                    _BAND_DESCRIPTOR,
                    _DOS_DESCRIPTOR,
                    _PYATB_BAND_DESCRIPTOR,
                    _EXPORT_DESCRIPTOR,
                )
            ],
        }
    )


def request_schema_document(capability: str, operation: str) -> dict[str, JSONValue]:
    """Return a static request schema, rejecting unsupported selectors."""
    if capability == _ATST_NEB_DESCRIPTOR.name and operation in ATST_NEB_REQUEST_TYPES:
        schema = _atst_schema_for(operation)
    elif capability in REQUEST_TYPES_BY_CAPABILITY and operation in REQUEST_TYPES_BY_CAPABILITY[capability]:
        schema = _schema_for(capability, operation)
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
