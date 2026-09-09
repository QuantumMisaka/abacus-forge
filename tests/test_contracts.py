from __future__ import annotations

import dataclasses
import inspect
import json
import re

import pytest

from abacus_forge import contracts
from abacus_forge import (
    BandPostprocessRequest,
    DosPostprocessRequest,
    RelaxCollectRequest,
    RelaxExecuteRequest,
    RelaxModifyRequest,
    RelaxPrepareRequest,
)
from abacus_forge.contracts import (
    ArtifactRecord,
    ArtifactRef,
    CheckRecord,
    ForgeRequest,
    ForgeResultEnvelope,
    MetricRecord,
    Observation,
    OperationOutcome,
    OperationRef,
    OperationStatus,
    ScfCollectRequest,
    ScfExecuteRequest,
    ScfModifyRequest,
    ScfPrepareRequest,
    CapabilityDescriptor,
)
from abacus_forge.discovery import (
    ATST_NEB_REQUEST_TYPES,
    POSTPROCESS_REQUEST_TYPES,
    REQUEST_TYPES_BY_CAPABILITY,
    SCF_REQUEST_TYPES,
    capabilities_document,
    request_schema_document,
)
from abacus_forge.pyatb_contracts import (
    PyatbBandCollectRequest,
    PyatbBandExecuteRequest,
    PyatbBandPrepareRequest,
)
from abacus_forge.errors import ForgeRequestError


OPERATION_ID = "123e4567-e89b-42d3-a456-426614174000"
RELAX_CAPABILITIES = ("relax", "cell-relax")


def _pyatb_prepare_request(**updates: object) -> PyatbBandPrepareRequest:
    values: dict[str, object] = {
        "operation_id": OPERATION_ID,
        "workspace_rel": "job",
        "structure_path_rel": "inputs/STRU",
        "hr_paths_rel": ["inputs/HR.dat"],
        "sr_path_rel": "inputs/SR.dat",
        "rr_path_rel": "inputs/rR.dat",
        "fermi_energy": 1.25,
        "line_kpoints": [
            {"coords": [0, 0, 0], "label": "G"},
            {"coords": [0.5, 0.0, 0.0], "label": "X"},
        ],
    }
    values.update(updates)
    return PyatbBandPrepareRequest(**values)


RELAX_REQUEST_CASES = (
    (RelaxPrepareRequest, "prepare", {"structure_path_rel": "source.STRU"}),
    (RelaxModifyRequest, "modify", {}),
    (RelaxExecuteRequest, "execute", {}),
    (RelaxCollectRequest, "collect", {}),
)


SCF_WIRE_KEYS = {
    ScfPrepareRequest: {
        "schema_version", "operation", "operation_id", "workspace_rel",
        "structure_path_rel", "structure_format", "parameters",
        "pseudo_sources", "orbital_sources", "asset_mode",
    },
    ScfModifyRequest: {
        "schema_version", "operation", "operation_id", "workspace_rel",
        "input_updates", "remove_parameters",
    },
    ScfExecuteRequest: {
        "schema_version", "operation", "operation_id", "workspace_rel",
        "executable", "mpi_ranks", "omp_threads", "timeout_seconds", "dry_run",
    },
    ScfCollectRequest: {"schema_version", "operation", "operation_id", "workspace_rel"},
}


def _outcome() -> OperationOutcome:
    envelope = ForgeResultEnvelope(
        operation="collect",
        workspace_rel=".",
        status=OperationStatus(execution="not_run", scientific="unassessed", collection="partial"),
        checks=[CheckRecord(name="converged", status="warning")],
    )
    return OperationOutcome(
        operation_id=OPERATION_ID,
        envelope=envelope,
        observations=[Observation(name="convergence", value=False, source="parser")],
    )


def test_operation_outcome_round_trips_without_changing_embedded_result_keys() -> None:
    outcome = _outcome()
    payload = outcome.to_dict()
    assert payload["schema_version"] == "forge.operation-outcome/v1"
    assert payload["operation_id"] == OPERATION_ID
    assert payload["observations"] == [{"name": "convergence", "value": False, "source": "parser"}]
    assert set(payload["envelope"]) == {
        "schema_version", "operation", "workspace_rel", "status", "artifacts",
        "metrics", "checks", "warnings", "diagnostics",
    }
    restored = OperationOutcome.from_dict(json.loads(json.dumps(payload, allow_nan=False)))
    assert restored == outcome
    assert restored.status is restored.envelope.status


def test_observation_is_frozen_and_rejects_non_json_values() -> None:
    observation = Observation(name="nested", value={"values": [1]}, source="runtime")
    with pytest.raises(TypeError):
        observation.value["values"] = []  # type: ignore[index]
    with pytest.raises(ValueError, match="JSON-safe"):
        Observation(name="bad", value=float("nan"), source="runtime")


@pytest.mark.parametrize("request_type", [ScfPrepareRequest, ScfModifyRequest, ScfExecuteRequest, ScfCollectRequest])
def test_typed_scf_request_schema_has_no_policy_id(request_type) -> None:
    extra = {"structure_path_rel": "source.STRU"} if request_type is ScfPrepareRequest else {}
    request = request_type(operation_id=OPERATION_ID, workspace_rel=".", **extra)
    assert "policy_id" not in request.to_dict()
    with pytest.raises(ValueError, match="unknown"):
        request_type.from_dict({**request.to_dict(), "policy_id": "abacus.scf/v1"})


def test_result_envelope_round_trips_with_relative_artifacts() -> None:
    result = ForgeResultEnvelope(
        operation="collect",
        workspace_rel=".",
        status=OperationStatus(execution="completed", scientific="accepted", collection="complete"),
        artifacts=[ArtifactRecord(id="runtime_log", path_rel="outputs/stdout.log", role="runtime_log", stage="abacus")],
        metrics=[MetricRecord(name="total_energy", value=-5.0, unit="eV", kind="reported", source_artifact_id="runtime_log")],
    )
    payload = result.to_dict()
    assert payload["schema_version"] == "forge.result/v1"
    assert ForgeResultEnvelope.from_dict(json.loads(json.dumps(payload, allow_nan=False))).to_dict() == payload


@pytest.mark.parametrize("path_rel", ["../outside", "/tmp/out", "outputs/../stdout.log", "", "./stdout.log"])
def test_artifact_record_rejects_noncanonical_paths(path_rel: str) -> None:
    with pytest.raises(ValueError, match="path_rel"):
        ArtifactRecord(id="bad", path_rel=path_rel, role="runtime_log", stage="abacus")


def test_request_rejects_non_json_payload() -> None:
    with pytest.raises(ValueError, match="JSON-safe"):
        ForgeRequest(operation="prepare", workspace_rel=".", payload={"value": float("nan")})


def test_request_payload_is_deeply_immutable_and_remains_json_safe() -> None:
    request = ForgeRequest(operation="prepare", workspace_rel=".", payload={"nested": {"items": [1]}})
    with pytest.raises(TypeError):
        request.payload["nested"] = {}  # type: ignore[index]
    with pytest.raises(TypeError):
        request.payload["nested"]["items"] = float("nan")  # type: ignore[index]
    with pytest.raises(AttributeError):
        request.payload["nested"]["items"].append(float("nan"))  # type: ignore[union-attr]
    assert json.dumps(request.to_dict(), allow_nan=False)


def test_scf_collect_request_requires_lowercase_uuid4_and_round_trips() -> None:
    request = contracts.ScfCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174000",
        workspace_rel=".",
    )

    assert contracts.ScfCollectRequest.from_dict(request.to_dict()).to_dict() == request.to_dict()


def _valid_execute_request_dict() -> dict[str, object]:
    return ScfExecuteRequest(operation_id=OPERATION_ID, workspace_rel="scf").to_dict()


def test_scf_execute_request_round_trips_local_runner_configuration() -> None:
    request = ScfExecuteRequest(
        operation_id=OPERATION_ID,
        workspace_rel="scf",
        executable="/opt/abacus/bin/abacus",
        mpi_ranks=4,
        omp_threads=2,
        timeout_seconds=120.0,
    )
    assert ScfExecuteRequest.from_dict(request.to_dict()) == request


@pytest.mark.parametrize(
    "field,value",
    [
        ("executable", ""),
        ("executable", ["abacus"]),
        ("executable", {"path": "abacus"}),
        ("mpi_ranks", 0),
        ("mpi_ranks", -1),
        ("mpi_ranks", True),
        ("mpi_ranks", "4"),
        ("omp_threads", 0),
        ("omp_threads", -1),
        ("omp_threads", True),
        ("omp_threads", "2"),
        ("timeout_seconds", 0.0),
        ("timeout_seconds", -1.0),
        ("timeout_seconds", float("inf")),
        ("timeout_seconds", float("nan")),
        ("timeout_seconds", "120"),
        ("timeout_seconds", {"seconds": 120}),
    ],
)
def test_scf_execute_request_rejects_invalid_runner_configuration(field: str, value: object) -> None:
    payload = _valid_execute_request_dict()
    payload[field] = value
    with pytest.raises(ValueError):
        ScfExecuteRequest.from_dict(payload)


@pytest.mark.parametrize("field", ["executable", "mpi_ranks", "omp_threads", "timeout_seconds"])
def test_scf_execute_request_rejects_non_json_runner_values_at_constructor(field: str) -> None:
    kwargs = {field: object()}
    with pytest.raises(ValueError):
        ScfExecuteRequest(operation_id=OPERATION_ID, workspace_rel="scf", **kwargs)


def test_scf_execute_request_rejects_unknown_runner_fields() -> None:
    payload = _valid_execute_request_dict()
    payload["launcher"] = "mpirun"
    with pytest.raises(ValueError, match="unknown"):
        ScfExecuteRequest.from_dict(payload)


@pytest.mark.parametrize(
    "operation_id",
    [
        "x",
        "123E4567-E89B-42D3-A456-426614174000",
        # These are canonically formatted, lowercase UUIDs, but are not v4.
        "c232dad3-7f13-11f0-8000-426614174000",  # UUIDv1
        "6fa459ea-ee8a-3ca4-894e-db77e160355e",  # UUIDv3
    ],
)
def test_scf_collect_request_rejects_noncanonical_uuid4(operation_id: str) -> None:
    with pytest.raises(ValueError, match="operation_id"):
        contracts.ScfCollectRequest(operation_id=operation_id, workspace_rel=".")


@pytest.mark.parametrize(
    "request_type,operation",
    [
        (ScfPrepareRequest, "prepare"),
        (ScfModifyRequest, "modify"),
        (ScfExecuteRequest, "execute"),
        (ScfCollectRequest, "collect"),
    ],
)
def test_typed_scf_requests_are_immutable_and_round_trip(request_type, operation) -> None:
    extra = {"structure_path_rel": "source.STRU"} if request_type is ScfPrepareRequest else {}
    request = request_type(
        operation_id="123e4567-e89b-42d3-a456-426614174000",
        workspace_rel="work",
        **extra,
    )

    assert request.operation == operation
    assert request.operation_id == "123e4567-e89b-42d3-a456-426614174000"
    assert request.workspace_rel == "work"
    assert request_type.from_dict(request.to_dict()) == request


def test_operation_ref_round_trips_and_rejects_unknown_fields() -> None:
    ref = OperationRef(operation_id="123e4567-e89b-42d3-a456-426614174000", workspace_rel=".")
    assert OperationRef.from_dict(ref.to_dict()) == ref
    with pytest.raises(ValueError, match="unknown"):
        OperationRef.from_dict({**ref.to_dict(), "extra": True})


def test_artifact_ref_is_strict_and_operation_scoped() -> None:
    ref = ArtifactRef(
        operation_id="123e4567-e89b-42d3-a456-426614174000",
        artifact_id="stdout_log",
    )
    assert ArtifactRef.from_dict(ref.to_dict()) == ref
    with pytest.raises(ValueError, match="unknown"):
        ArtifactRef.from_dict({**ref.to_dict(), "path_rel": "outputs/stdout.log"})
    with pytest.raises(ValueError, match="artifact_id"):
        ArtifactRef(operation_id=ref.operation_id, artifact_id="")


@pytest.mark.parametrize("request_type", [ScfPrepareRequest, ScfModifyRequest, ScfExecuteRequest, ScfCollectRequest])
def test_typed_scf_requests_reject_unknown_fields(request_type) -> None:
    kwargs = {"operation_id": "123e4567-e89b-42d3-a456-426614174000", "workspace_rel": "."}
    extra = {"structure_path_rel": "source.STRU"} if request_type is ScfPrepareRequest else {}
    request = request_type(**kwargs, **extra)
    with pytest.raises(ValueError, match="unknown"):
        request_type.from_dict({**request.to_dict(), "extra": True})
    with pytest.raises(ValueError, match="operation"):
        request_type.from_dict({**request.to_dict(), "operation": "export"})


def test_typed_prepare_request_requires_workspace_relative_structure() -> None:
    with pytest.raises(ValueError, match="structure_path_rel"):
        ScfPrepareRequest(
            operation_id="123e4567-e89b-42d3-a456-426614174000",
            workspace_rel=".",
        )

    request = ScfPrepareRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174000",
        workspace_rel="scf",
        structure_path_rel="source/STRU",
        parameters={"ecutwfc": 80},
    )
    assert request.to_dict()["structure_path_rel"] == "source/STRU"
    assert request.to_dict()["parameters"] == {"ecutwfc": 80}
    assert request.to_dict()["pseudo_sources"] == {}
    assert request.to_dict()["orbital_sources"] == {}
    assert request.to_dict()["asset_mode"] == "copy"
    assert ScfPrepareRequest.from_dict(request.to_dict()) == request


def test_typed_prepare_request_round_trips_and_freezes_asset_sources() -> None:
    pseudo_sources = {"Si": "/assets/Si.upf"}
    orbital_sources = {"Si": "assets/Si.orb"}
    request = ScfPrepareRequest(
        operation_id=OPERATION_ID,
        workspace_rel="scf",
        structure_path_rel="source.STRU",
        pseudo_sources=pseudo_sources,
        orbital_sources=orbital_sources,
        asset_mode="link",
    )

    pseudo_sources["Si"] = "/assets/changed.upf"
    orbital_sources.clear()

    assert request.pseudo_sources == {"Si": "/assets/Si.upf"}
    assert request.orbital_sources == {"Si": "assets/Si.orb"}
    with pytest.raises(TypeError):
        request.pseudo_sources["Si"] = "/assets/changed.upf"  # type: ignore[index]
    with pytest.raises(TypeError):
        request.orbital_sources["Si"] = "assets/changed.orb"  # type: ignore[index]
    assert ScfPrepareRequest.from_dict(json.loads(json.dumps(request.to_dict()))) == request


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pseudo_sources", None),
        ("pseudo_sources", []),
        ("pseudo_sources", "Si.upf"),
        ("pseudo_sources", {"": "Si.upf"}),
        ("pseudo_sources", {"Si": ""}),
        ("pseudo_sources", {1: "Si.upf"}),
        ("pseudo_sources", {"Si": 1}),
        ("orbital_sources", None),
        ("orbital_sources", []),
        ("orbital_sources", "Si.orb"),
        ("orbital_sources", {"": "Si.orb"}),
        ("orbital_sources", {"Si": ""}),
        ("orbital_sources", {1: "Si.orb"}),
        ("orbital_sources", {"Si": 1}),
    ],
)
def test_typed_prepare_request_rejects_invalid_asset_source_maps(field: str, value: object) -> None:
    with pytest.raises(ValueError, match=field):
        ScfPrepareRequest(
            operation_id=OPERATION_ID,
            workspace_rel="scf",
            structure_path_rel="source.STRU",
            **{field: value},
        )


@pytest.mark.parametrize("asset_mode", ["", "symlink", None, 1, [], {"mode": "copy"}])
def test_typed_prepare_request_rejects_invalid_asset_mode(asset_mode: object) -> None:
    with pytest.raises(ValueError, match="asset_mode"):
        ScfPrepareRequest(
            operation_id=OPERATION_ID,
            workspace_rel="scf",
            structure_path_rel="source.STRU",
            asset_mode=asset_mode,  # type: ignore[arg-type]
        )


def test_typed_modify_request_exposes_narrow_input_changes() -> None:
    request = ScfModifyRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174000",
        workspace_rel="scf",
        input_updates={"ecutwfc": 90},
        remove_parameters=("smearing_sigma",),
    )
    assert request.to_dict()["input_updates"] == {"ecutwfc": 90}
    assert request.to_dict()["remove_parameters"] == ["smearing_sigma"]
    assert ScfModifyRequest.from_dict(request.to_dict()) == request


def test_error_envelope_round_trips_with_known_request_identity() -> None:
    error = contracts.ForgeErrorEnvelope(
        error_class="request.path",
        message="workspace must be canonical",
        affected_fields=("workspace_rel",),
        operation_id="123e4567-e89b-42d3-a456-426614174000",
        workspace_rel=".",
    )

    assert contracts.ForgeErrorEnvelope.from_dict(error.to_dict()).to_dict() == error.to_dict()


def test_error_envelope_rejects_error_classes_outside_frozen_v1_set() -> None:
    allowed = {
        "request.invalid", "request.schema", "request.path", "operation.conflict",
        "precondition.missing", "persistence.failure", "internal.failure",
    }
    for error_class in sorted(allowed):
        contracts.ForgeErrorEnvelope(error_class=error_class, message="bad", affected_fields=("request",))
    with pytest.raises(ValueError, match="error_class"):
        contracts.ForgeErrorEnvelope(error_class="request.unknown", message="bad", affected_fields=("request",))


def test_error_envelope_requires_affected_fields_and_strictly_decodes_error() -> None:
    with pytest.raises(TypeError, match="affected_fields"):
        contracts.ForgeErrorEnvelope(error_class="request.path", message="bad")

    error = contracts.ForgeErrorEnvelope(
        error_class="request.path", message="bad", affected_fields=("workspace_rel",)
    )
    payload = error.to_dict()
    with pytest.raises(ValueError, match="unknown"):
        contracts.ForgeErrorEnvelope.from_dict(
            {**payload, "error": {**payload["error"], "extra": "reject"}}
        )
    missing_affected_fields = {**payload, "error": {**payload["error"]}}
    missing_affected_fields["error"].pop("affected_fields")
    with pytest.raises(ValueError, match="incomplete"):
        contracts.ForgeErrorEnvelope.from_dict(missing_affected_fields)
    with pytest.raises(ValueError, match="unknown"):
        contracts.ForgeErrorEnvelope.from_dict({**payload, "extra": "reject"})


def test_result_diagnostics_are_deeply_immutable_and_remain_json_safe() -> None:
    result = ForgeResultEnvelope(
        operation="collect",
        workspace_rel=".",
        status=OperationStatus(execution="completed", scientific="accepted", collection="complete"),
        diagnostics={"parser": {"warnings": ["incomplete"]}},
    )
    with pytest.raises(TypeError):
        result.diagnostics["parser"] = {}  # type: ignore[index]
    with pytest.raises(TypeError):
        result.diagnostics["parser"]["warnings"] = float("nan")  # type: ignore[index]
    with pytest.raises(AttributeError):
        result.diagnostics["parser"]["warnings"].append(float("nan"))  # type: ignore[union-attr]
    assert json.dumps(result.to_dict(), allow_nan=False)


def test_contract_records_reject_wrong_schema_versions_and_status_values() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        ForgeRequest(operation="prepare", workspace_rel=".", payload={}, schema_version="forge.request/v2")
    with pytest.raises(ValueError, match="execution"):
        OperationStatus(execution="running", scientific="unassessed", collection="not_collected")  # type: ignore[arg-type]


def test_capability_descriptor_round_trips_strictly() -> None:
    descriptor = CapabilityDescriptor(
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
    payload = descriptor.to_dict()
    assert payload["schema_version"] == "forge.capability/v1"
    assert CapabilityDescriptor.from_dict(json.loads(json.dumps(payload))) == descriptor
    with pytest.raises(ValueError, match="unknown"):
        CapabilityDescriptor.from_dict({**payload, "extra": True})
    with pytest.raises(ValueError, match="schema_version"):
        missing_version = dict(payload)
        missing_version.pop("schema_version")
        CapabilityDescriptor.from_dict(missing_version)


def test_capability_descriptor_rejects_invalid_values() -> None:
    kwargs = dict(
        name="scf",
        maturity="experimental",
        engine="abacus",
        operations=("prepare",),
        inputs={"prepare": ("structure",)},
        artifact_roles=("input",),
        optional_dependencies=(),
    )
    with pytest.raises(ValueError, match="maturity"):
        CapabilityDescriptor(**{**kwargs, "maturity": "stable-ish"})
    with pytest.raises(ValueError, match="operations"):
        CapabilityDescriptor(**{**kwargs, "operations": ()})
    with pytest.raises(ValueError, match="schema_version"):
        CapabilityDescriptor(**{**kwargs, "schema_version": "forge.capability/v2"})


def test_capabilities_document_is_fresh_and_advertises_all_capabilities() -> None:
    payload = capabilities_document()
    assert payload["schema_version"] == "forge.capabilities/v1"
    assert [item["name"] for item in payload["capabilities"]] == [
        "scf", "relax", "cell-relax", "atst-neb", "md", "band", "dos", "pyatb-band",
    ]
    assert payload["capabilities"][0]["maturity"] == "experimental"
    assert payload["capabilities"][0]["operations"] == ["prepare", "modify", "execute", "collect"]
    assert payload["capabilities"][0]["artifact_roles"] == ["input", "provenance_manifest", "output"]
    payload["capabilities"][0]["operations"].append("export")
    payload["capabilities"][0]["inputs"]["prepare"].append("mutated")
    assert capabilities_document()["capabilities"][0]["operations"] == ["prepare", "modify", "execute", "collect"]
    assert capabilities_document()["capabilities"][0]["inputs"]["prepare"] == ["structure"]
    assert payload["capabilities"][4]["maturity"] == "experimental"
    assert payload["capabilities"][4]["engine"] == "abacus"
    assert payload["capabilities"][4]["operations"] == ["prepare", "modify", "execute", "collect"]
    assert payload["capabilities"][4]["artifact_roles"] == ["input", "provenance_manifest", "output"]
    assert payload["capabilities"][5]["operations"] == ["postprocess"]
    assert payload["capabilities"][6]["operations"] == ["postprocess"]
    assert payload["capabilities"][7]["operations"] == ["prepare", "execute", "collect"]


def test_atst_neb_requests_round_trip_strictly() -> None:
    from abacus_forge.contracts import AtstNebExecuteRequest, AtstNebPostprocessRequest, AtstNebPrepareRequest
    requests = (
        AtstNebPrepareRequest(operation_id=OPERATION_ID, workspace_rel=".", init_structure_path_rel="a.cif", final_structure_path_rel="b.cif"),
        AtstNebExecuteRequest(operation_id=OPERATION_ID, workspace_rel=".", config_path_rel="workflow.yaml", dry_run=True, check_input=True),
        AtstNebPostprocessRequest(operation_id=OPERATION_ID, workspace_rel=".", trajectory_path_rel="neb.traj", plot=True, energy_profile=True, vib_analysis=True, strict_band=True),
    )
    for request in requests:
        payload = request.to_dict()
        assert payload["capability"] == "atst-neb"
        assert type(request).from_dict(json.loads(json.dumps(payload))) == request
        with pytest.raises(ValueError, match="unknown"):
            type(request).from_dict({**payload, "unknown": True})


def test_atst_neb_defaults_match_atst_tools_224() -> None:
    from abacus_forge.contracts import AtstNebExecuteRequest, AtstNebPostprocessRequest, AtstNebPrepareRequest

    prepare = AtstNebPrepareRequest(operation_id=OPERATION_ID, workspace_rel=".", init_structure_path_rel="a.cif", final_structure_path_rel="b.cif")
    execute = AtstNebExecuteRequest(operation_id=OPERATION_ID, workspace_rel=".", config_path_rel="workflow.yaml")
    postprocess = AtstNebPostprocessRequest(operation_id=OPERATION_ID, workspace_rel=".", trajectory_path_rel="neb.traj")
    assert prepare.n_images == 5
    assert execute.check_input_timeout == 120
    assert postprocess.vib_thr == 0.10


def test_atst_neb_request_rejects_wrong_capability_and_invalid_options() -> None:
    from abacus_forge.contracts import AtstNebExecuteRequest, AtstNebPrepareRequest, AtstNebPostprocessRequest
    request = AtstNebPrepareRequest(operation_id=OPERATION_ID, workspace_rel=".", init_structure_path_rel="a.cif", final_structure_path_rel="b.cif")
    with pytest.raises(ValueError, match="capability"):
        AtstNebPrepareRequest.from_dict({**request.to_dict(), "capability": "scf"})
    with pytest.raises(ValueError):
        AtstNebPrepareRequest(operation_id=OPERATION_ID, workspace_rel=".", init_structure_path_rel="a.cif", final_structure_path_rel="b.cif", n_images=0)
    with pytest.raises(ValueError):
        AtstNebPrepareRequest(operation_id=OPERATION_ID, workspace_rel=".", init_structure_path_rel="a.cif", final_structure_path_rel="b.cif", method="bad")
    with pytest.raises(ValueError, match="dry_run"):
        AtstNebExecuteRequest(operation_id=OPERATION_ID, workspace_rel=".", config_path_rel="workflow.yaml", check_input=True)
    with pytest.raises(ValueError):
        AtstNebPostprocessRequest(operation_id=OPERATION_ID, workspace_rel=".", trajectory_path_rel="../neb.traj")


def test_atst_neb_contracts_validate_paths_and_positive_timeouts() -> None:
    from abacus_forge.contracts import AtstNebExecuteRequest, AtstNebPostprocessRequest, AtstNebPrepareRequest
    for path in ("../a.cif", "/tmp/a.cif", "a/../b.cif", "a//b.cif", "a\\b.cif"):
        with pytest.raises(ValueError):
            AtstNebPrepareRequest(operation_id=OPERATION_ID, workspace_rel=".", init_structure_path_rel=path, final_structure_path_rel="b.cif")
        with pytest.raises(ValueError):
            AtstNebPostprocessRequest(operation_id=OPERATION_ID, workspace_rel=".", trajectory_path_rel=path)
    for field in ("check_input_timeout", "timeout_seconds"):
        with pytest.raises(ValueError):
            AtstNebExecuteRequest(operation_id=OPERATION_ID, workspace_rel=".", config_path_rel="workflow.yaml", **{field: 0})
        with pytest.raises(ValueError):
            AtstNebExecuteRequest(operation_id=OPERATION_ID, workspace_rel=".", config_path_rel="workflow.yaml", **{field: -1})


def test_atst_neb_postprocess_serializes_every_output_flag() -> None:
    from abacus_forge.contracts import AtstNebPostprocessRequest
    request = AtstNebPostprocessRequest(
        operation_id=OPERATION_ID, workspace_rel=".", trajectory_path_rel="neb.traj", n_max=5,
        summary_path_rel="reports/summary.json", output_prefix="outputs/neb-ts", write_latest=True,
        write_neb_init_chain=True, plot=True, plot_label="test", energy_profile=True, vib_analysis=True,
        vib_thr=0.02, strict_band=True,
    )
    payload = request.to_dict()
    assert all(payload[name] == value for name, value in {
        "write_latest": True, "write_neb_init_chain": True, "plot": True, "plot_label": "test",
        "energy_profile": True, "vib_analysis": True, "vib_thr": 0.02, "strict_band": True,
    }.items())


def _discovery_request(operation: str):
    kwargs = {"operation_id": OPERATION_ID, "workspace_rel": "."}
    if operation == "prepare":
        kwargs["structure_path_rel"] = "source.STRU"
    return SCF_REQUEST_TYPES[operation](**kwargs)


@pytest.mark.parametrize("operation", ["prepare", "modify", "execute", "collect"])
def test_request_schema_matches_contract_fields_and_wire_keys(operation: str) -> None:
    document = request_schema_document("scf", operation)
    schema = document["request_schema"]
    request_type = SCF_REQUEST_TYPES[operation]
    field_keys = {item.name for item in dataclasses.fields(request_type)} | {"operation"}
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == field_keys
    assert set(schema["properties"]) == set(_discovery_request(operation).to_dict())


@pytest.mark.parametrize("operation", ["prepare", "execute", "postprocess"])
def test_atst_neb_request_schema_matches_contract_fields_and_required_paths(operation: str) -> None:
    document = request_schema_document("atst-neb", operation)
    schema = document["request_schema"]
    request_type = ATST_NEB_REQUEST_TYPES[operation]
    kwargs = {"operation_id": OPERATION_ID, "workspace_rel": "."}
    kwargs.update({"init_structure_path_rel": "a.cif", "final_structure_path_rel": "b.cif"} if operation == "prepare" else {})
    kwargs.update({"config_path_rel": "workflow.yaml"} if operation == "execute" else {})
    kwargs.update({"trajectory_path_rel": "neb.traj"} if operation == "postprocess" else {})
    request = request_type(**kwargs)
    assert set(schema["properties"]) == {field.name for field in dataclasses.fields(request_type)} | {"operation", "capability"}
    assert set(schema["properties"]) == set(request.to_dict())
    assert set(schema["required"]) >= {"schema_version", "capability", "operation", "operation_id", "workspace_rel"}


def test_atst_neb_execute_schema_freezes_check_input_dry_run_dependency() -> None:
    schema = request_schema_document("atst-neb", "execute")["request_schema"]
    dependency = schema["allOf"][0]
    assert dependency["if"]["properties"]["check_input"]["const"] is True
    assert dependency["then"]["properties"]["dry_run"]["const"] is True


def test_atst_neb_schema_publishes_atst_tools_defaults() -> None:
    assert request_schema_document("atst-neb", "prepare")["request_schema"]["properties"]["n_images"]["default"] == 5
    assert request_schema_document("atst-neb", "execute")["request_schema"]["properties"]["check_input_timeout"]["default"] == 120
    assert request_schema_document("atst-neb", "postprocess")["request_schema"]["properties"]["vib_thr"]["default"] == 0.10


@pytest.mark.parametrize("operation", ["prepare", "modify", "execute", "collect"])
def test_request_schema_freezes_required_constants_and_bounds(operation: str) -> None:
    schema = request_schema_document("scf", operation)["request_schema"]
    required = {"schema_version", "operation", "operation_id", "workspace_rel"}
    if operation == "prepare":
        required.add("structure_path_rel")
    assert set(schema["required"]) == required
    assert schema["properties"]["schema_version"]["const"] == "forge.request/v1"
    assert schema["properties"]["operation"]["const"] == operation
    if operation == "execute":
        assert schema["properties"]["mpi_ranks"]["minimum"] == 1
        assert schema["properties"]["omp_threads"]["minimum"] == 1
        assert schema["properties"]["timeout_seconds"]["exclusiveMinimum"] == 0


@pytest.mark.parametrize("path_value", ["/tmp", "a/../b", "a/./b", "a//b", "a\\b"])
def test_request_schema_describes_canonical_workspace_paths(path_value: str) -> None:
    schema = request_schema_document("scf", "execute")["request_schema"]
    pattern = schema["properties"]["workspace_rel"]["pattern"]
    assert re.fullmatch(pattern, path_value) is None


@pytest.mark.parametrize("path_value", [".", "/tmp/STRU", "a/../STRU", "a/./STRU"])
def test_prepare_schema_describes_canonical_structure_paths(path_value: str) -> None:
    schema = request_schema_document("scf", "prepare")["request_schema"]
    pattern = schema["properties"]["structure_path_rel"]["pattern"]
    assert re.fullmatch(pattern, path_value) is None


@pytest.mark.parametrize("capability", ["scf", "relax", "cell-relax", "md"])
def test_prepare_schema_exposes_typed_asset_fields(capability: str) -> None:
    schema = request_schema_document(capability, "prepare")["request_schema"]
    properties = schema["properties"]

    for field_name in ("pseudo_sources", "orbital_sources"):
        assert properties[field_name]["type"] == "object"
        assert properties[field_name]["propertyNames"] == {"type": "string", "minLength": 1}
        assert properties[field_name]["additionalProperties"] == {"type": "string", "minLength": 1}
        assert properties[field_name]["default"] == {}
    assert properties["asset_mode"]["type"] == "string"
    assert properties["asset_mode"]["enum"] == ["copy", "link"]
    assert properties["asset_mode"]["default"] == "copy"
    assert schema["additionalProperties"] is False


@pytest.mark.parametrize("capability,operation", [("unknown", "prepare"), ("scf", "postprocess")])
def test_unknown_schema_selector_raises_request_error(capability: str, operation: str) -> None:
    with pytest.raises(ForgeRequestError):
        request_schema_document(capability, operation)


def test_result_envelope_rejects_duplicate_artifacts_and_missing_metric_sources() -> None:
    artifact = ArtifactRecord(id="runtime_log", path_rel="outputs/stdout.log", role="runtime_log", stage="abacus")
    status = OperationStatus(execution="completed", scientific="accepted", collection="complete")
    with pytest.raises(ValueError, match="duplicate"):
        ForgeResultEnvelope(operation="collect", workspace_rel=".", status=status, artifacts=[artifact, artifact])
    with pytest.raises(ValueError, match="source_artifact_id"):
        ForgeResultEnvelope(
            operation="collect",
            workspace_rel=".",
            status=status,
            metrics=[MetricRecord(name="energy", value=-1.0, unit="eV", kind="reported", source_artifact_id="missing")],
        )


@pytest.mark.parametrize("factory,payload", [
    (ArtifactRecord.from_dict, []), (MetricRecord.from_dict, {"name": "x"}),
    (OperationStatus.from_dict, {"execution": [], "scientific": "unassessed", "collection": "not_collected"}),
    (ForgeRequest.from_dict, {"operation": "prepare"}),
])
def test_from_dict_normalizes_malformed_shapes_to_value_error(factory, payload) -> None:
    with pytest.raises(ValueError):
        factory(payload)


def _relax_constructor_kwargs(request_type, *, capability: str = "relax") -> dict[str, object]:
    kwargs: dict[str, object] = {
        "operation_id": OPERATION_ID,
        "workspace_rel": "job",
        "capability": capability,
    }
    if request_type is RelaxPrepareRequest:
        kwargs["structure_path_rel"] = "source.STRU"
    return kwargs


@pytest.mark.parametrize("capability", RELAX_CAPABILITIES)
@pytest.mark.parametrize(
    "request_type,operation,base_kwargs",
    RELAX_REQUEST_CASES,
)
def test_relax_requests_round_trip_with_capability(
    request_type, operation: str, base_kwargs: dict[str, object], capability: str
) -> None:
    kwargs = _relax_constructor_kwargs(request_type, capability=capability)
    kwargs.update(base_kwargs)
    if request_type is RelaxPrepareRequest:
        kwargs["parameters"] = {"calculation": capability, "nested": {"items": [1]}}
    elif request_type is RelaxModifyRequest:
        kwargs["input_updates"] = {"calculation": capability, "nested": {"items": [1]}}

    request = request_type(**kwargs)

    assert request.operation == operation
    assert request.to_dict()["capability"] == capability
    assert request_type.from_dict(json.loads(json.dumps(request.to_dict()))) == request
    assert dataclasses.is_dataclass(request)
    assert not hasattr(request, "__dict__")
    assert next(item for item in dataclasses.fields(request_type) if item.name == "capability").kw_only
    assert inspect.signature(request_type).parameters["capability"].kind is inspect.Parameter.KEYWORD_ONLY


@pytest.mark.parametrize(
    "request_type",
    [RelaxPrepareRequest, RelaxModifyRequest, RelaxExecuteRequest, RelaxCollectRequest],
)
@pytest.mark.parametrize("bad_capability", ["scf", "RELAX", "", None, 1, ["relax"], {"name": "relax"}])
def test_relax_requests_require_a_known_string_capability(request_type, bad_capability) -> None:
    kwargs = _relax_constructor_kwargs(request_type)
    with pytest.raises(ValueError, match="capability"):
        request_type(**{**kwargs, "capability": bad_capability})

    valid = request_type(**kwargs)
    payload = valid.to_dict()
    payload["capability"] = bad_capability
    with pytest.raises(ValueError, match="capability"):
        request_type.from_dict(payload)


@pytest.mark.parametrize(
    "request_type",
    [RelaxPrepareRequest, RelaxModifyRequest, RelaxExecuteRequest, RelaxCollectRequest],
)
@pytest.mark.parametrize("capability", RELAX_CAPABILITIES)
def test_relax_requests_require_capability_and_reject_unknown_fields(request_type, capability: str) -> None:
    request = request_type(**_relax_constructor_kwargs(request_type, capability=capability))
    payload = request.to_dict()

    missing_capability = dict(payload)
    missing_capability.pop("capability")
    with pytest.raises(ValueError):
        request_type.from_dict(missing_capability)
    with pytest.raises(ValueError, match="unknown"):
        request_type.from_dict({**payload, "extra": True})
    with pytest.raises(ValueError, match="operation"):
        request_type.from_dict({**payload, "operation": "export"})


@pytest.mark.parametrize(
    "request_type",
    [RelaxPrepareRequest, RelaxModifyRequest, RelaxExecuteRequest, RelaxCollectRequest],
)
@pytest.mark.parametrize("capability", RELAX_CAPABILITIES)
@pytest.mark.parametrize("field,value", [("operation_id", "x"), ("workspace_rel", "../outside")])
def test_relax_requests_reuse_scf_identity_validation(
    request_type, capability: str, field: str, value: str
) -> None:
    kwargs = _relax_constructor_kwargs(request_type, capability=capability)
    with pytest.raises(ValueError):
        request_type(**{**kwargs, field: value})


@pytest.mark.parametrize("capability", RELAX_CAPABILITIES)
@pytest.mark.parametrize("path_rel", ["../outside", "/tmp/STRU", "a/../STRU", "a/./STRU", "."])
def test_relax_prepare_reuses_scf_structure_path_validation(capability: str, path_rel: str) -> None:
    kwargs = _relax_constructor_kwargs(RelaxPrepareRequest, capability=capability)
    with pytest.raises(ValueError, match="structure_path_rel|path_rel"):
        RelaxPrepareRequest(**{**kwargs, "structure_path_rel": path_rel})


@pytest.mark.parametrize("capability", RELAX_CAPABILITIES)
def test_relax_prepare_requires_matching_calculation(capability: str) -> None:
    kwargs = _relax_constructor_kwargs(RelaxPrepareRequest, capability=capability)
    request = RelaxPrepareRequest(**{**kwargs, "parameters": {"calculation": capability}})
    assert RelaxPrepareRequest.from_dict(request.to_dict()) == request

    for calculation in ("scf", "relax" if capability == "cell-relax" else "cell-relax", None, 1):
        contradictory = {"calculation": calculation}
        with pytest.raises(ValueError, match="calculation"):
            RelaxPrepareRequest(**{**kwargs, "parameters": contradictory})
        payload = request.to_dict()
        payload["parameters"] = contradictory
        with pytest.raises(ValueError, match="calculation"):
            RelaxPrepareRequest.from_dict(payload)


@pytest.mark.parametrize("capability", RELAX_CAPABILITIES)
def test_relax_modify_requires_matching_calculation_and_cannot_remove_it(capability: str) -> None:
    kwargs = _relax_constructor_kwargs(RelaxModifyRequest, capability=capability)
    request = RelaxModifyRequest(**{**kwargs, "input_updates": {"calculation": capability}})
    assert RelaxModifyRequest.from_dict(request.to_dict()) == request

    for calculation in ("scf", "relax" if capability == "cell-relax" else "cell-relax", None, 1):
        contradictory = {"calculation": calculation}
        with pytest.raises(ValueError, match="calculation"):
            RelaxModifyRequest(**{**kwargs, "input_updates": contradictory})
        payload = request.to_dict()
        payload["input_updates"] = contradictory
        with pytest.raises(ValueError, match="calculation"):
            RelaxModifyRequest.from_dict(payload)

    with pytest.raises(ValueError, match="calculation"):
        RelaxModifyRequest(**{**kwargs, "remove_parameters": ("calculation",)})
    payload = request.to_dict()
    payload["remove_parameters"] = ["calculation"]
    with pytest.raises(ValueError, match="calculation"):
        RelaxModifyRequest.from_dict(payload)


@pytest.mark.parametrize("request_type,field", [(RelaxPrepareRequest, "parameters"), (RelaxModifyRequest, "input_updates")])
@pytest.mark.parametrize("capability", RELAX_CAPABILITIES)
def test_relax_parameter_payloads_reject_non_json_values(request_type, field: str, capability: str) -> None:
    kwargs = _relax_constructor_kwargs(request_type, capability=capability)
    value = {"value": object()}
    with pytest.raises(ValueError, match="JSON-safe"):
        request_type(**{**kwargs, field: value})

    valid = request_type(**kwargs)
    payload = valid.to_dict()
    payload[field] = {"value": float("nan")}
    with pytest.raises(ValueError, match="JSON-safe"):
        request_type.from_dict(payload)


@pytest.mark.parametrize("capability", RELAX_CAPABILITIES)
@pytest.mark.parametrize(
    "request_type",
    [RelaxPrepareRequest, RelaxModifyRequest, RelaxExecuteRequest, RelaxCollectRequest],
)
def test_relax_requests_are_frozen_and_deeply_immutable(request_type, capability: str) -> None:
    kwargs = _relax_constructor_kwargs(request_type, capability=capability)
    if request_type is RelaxPrepareRequest:
        kwargs["parameters"] = {"nested": {"items": [1]}}
    elif request_type is RelaxModifyRequest:
        kwargs["input_updates"] = {"nested": {"items": [1]}}
    request = request_type(**kwargs)

    with pytest.raises(dataclasses.FrozenInstanceError):
        request.capability = "scf"  # type: ignore[misc]
    if request_type is RelaxPrepareRequest:
        with pytest.raises(TypeError):
            request.parameters["nested"] = {}  # type: ignore[index]
        with pytest.raises(TypeError):
            request.parameters["nested"]["items"] = []  # type: ignore[index]
        with pytest.raises(AttributeError):
            request.parameters["nested"]["items"].append(2)  # type: ignore[union-attr]
    if request_type is RelaxModifyRequest:
        with pytest.raises(TypeError):
            request.input_updates["nested"] = {}  # type: ignore[index]
        with pytest.raises(TypeError):
            request.input_updates["nested"]["items"] = []  # type: ignore[index]
        with pytest.raises(AttributeError):
            request.input_updates["nested"]["items"].append(2)  # type: ignore[union-attr]


@pytest.mark.parametrize("capability", RELAX_CAPABILITIES)
@pytest.mark.parametrize(
    "field,value",
    [
        ("executable", ""),
        ("executable", ["abacus"]),
        ("mpi_ranks", 0),
        ("mpi_ranks", -1),
        ("mpi_ranks", True),
        ("mpi_ranks", "4"),
        ("omp_threads", 0),
        ("omp_threads", -1),
        ("omp_threads", True),
        ("omp_threads", "2"),
        ("timeout_seconds", 0.0),
        ("timeout_seconds", -1.0),
        ("timeout_seconds", float("inf")),
        ("timeout_seconds", float("nan")),
        ("timeout_seconds", "120"),
        ("dry_run", "false"),
    ],
)
def test_relax_execute_reuses_scf_resource_validation(capability: str, field: str, value: object) -> None:
    request = RelaxExecuteRequest(**_relax_constructor_kwargs(RelaxExecuteRequest, capability=capability))
    payload = request.to_dict()
    payload[field] = value
    with pytest.raises(ValueError, match=field):
        RelaxExecuteRequest.from_dict(payload)


@pytest.mark.parametrize(
    "request_type,expected_keys",
    SCF_WIRE_KEYS.items(),
)
def test_scf_request_wire_keys_remain_unchanged(request_type, expected_keys: set[str]) -> None:
    # Use the legacy constructor directly: no Relax selector belongs on SCF requests.
    kwargs = {"operation_id": OPERATION_ID, "workspace_rel": "job"}
    if request_type is ScfPrepareRequest:
        kwargs["structure_path_rel"] = "source.STRU"
    request = request_type(**kwargs)
    assert set(request.to_dict()) == expected_keys
    assert "capability" not in request.to_dict()
    with pytest.raises(ValueError, match="unknown"):
        request_type.from_dict({**request.to_dict(), "capability": "relax"})


POSTPROCESS_REQUEST_CASES = (
    (
        BandPostprocessRequest,
        {
            "source_paths_rel": ["outputs/OUT.ABACUS/BANDS_1.dat"],
            "output_dir_rel": "outputs/band",
        },
    ),
    (
        DosPostprocessRequest,
        {
            "dos_paths_rel": ["outputs/OUT.ABACUS/DOS1_smearing.dat"],
            "pdos_path_rel": "outputs/OUT.ABACUS/PDOS",
            "tdos_path_rel": "outputs/OUT.ABACUS/TDOS",
            "output_dir_rel": "outputs/dos",
            "include_tdos": True,
            "include_pdos": True,
            "pdos_mode": "atoms",
            "pdos_atom_indices": [0, 2],
            "plot_emin": -4.0,
            "plot_emax": 6.0,
            "save_data": True,
            "save_plot": False,
            "suffix": "selected",
        },
    ),
)


@pytest.mark.parametrize("request_type,extra", POSTPROCESS_REQUEST_CASES)
def test_postprocess_requests_round_trip_strictly_and_remain_immutable(request_type, extra) -> None:
    request = request_type(
        operation_id=OPERATION_ID,
        workspace_rel="job",
        **extra,
    )

    payload = request.to_dict()
    assert payload["schema_version"] == "forge.request/v1"
    assert payload["capability"] == request.capability
    assert payload["operation"] == "postprocess"
    assert request_type.from_dict(json.loads(json.dumps(payload))) == request
    assert dataclasses.is_dataclass(request)
    assert not hasattr(request, "__dict__")
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.operation_id = OPERATION_ID  # type: ignore[misc]
    with pytest.raises(ValueError, match="unknown"):
        request_type.from_dict({**payload, "unknown": True})


def test_postprocess_request_registries_are_separate_from_legacy_scf() -> None:
    expected = {
        "band": {"postprocess": BandPostprocessRequest},
        "dos": {"postprocess": DosPostprocessRequest},
    }
    assert POSTPROCESS_REQUEST_TYPES == expected
    assert REQUEST_TYPES_BY_CAPABILITY["band"] is POSTPROCESS_REQUEST_TYPES["band"]
    assert REQUEST_TYPES_BY_CAPABILITY["dos"] is POSTPROCESS_REQUEST_TYPES["dos"]
    assert "postprocess" not in SCF_REQUEST_TYPES
    assert set(contracts._OPERATIONS) == {"prepare", "modify", "execute", "collect", "export"}


@pytest.mark.parametrize(
    ("request_type", "field", "value"),
    [
        (BandPostprocessRequest, "source_paths_rel", []),
        (BandPostprocessRequest, "source_paths_rel", ["."]),
        (BandPostprocessRequest, "source_paths_rel", ["../outside"]),
        (BandPostprocessRequest, "source_paths_rel", ["a/../BANDS.dat"]),
        (BandPostprocessRequest, "source_paths_rel", ["a\\BANDS.dat"]),
        (BandPostprocessRequest, "source_paths_rel", "BANDS.dat"),
        (DosPostprocessRequest, "dos_paths_rel", []),
        (DosPostprocessRequest, "dos_paths_rel", ["/tmp/DOS.dat"]),
        (DosPostprocessRequest, "pdos_path_rel", "."),
        (DosPostprocessRequest, "tdos_path_rel", "a/./TDOS"),
        (DosPostprocessRequest, "output_dir_rel", "../outside"),
        (DosPostprocessRequest, "output_dir_rel", "a\\b"),
        (DosPostprocessRequest, "pdos_atom_indices", [0, -1]),
        (DosPostprocessRequest, "pdos_atom_indices", [True]),
        (DosPostprocessRequest, "pdos_atom_indices", ["0"]),
        (DosPostprocessRequest, "pdos_mode", "unknown"),
        (BandPostprocessRequest, "plot_emin", float("nan")),
        (DosPostprocessRequest, "plot_emax", float("inf")),
        (BandPostprocessRequest, "save_data", 1),
        (DosPostprocessRequest, "include_pdos", "true"),
        (DosPostprocessRequest, "suffix", ""),
        (DosPostprocessRequest, "suffix", "../escape"),
        (DosPostprocessRequest, "suffix", "a\\b"),
        (DosPostprocessRequest, "suffix", "."),
        (DosPostprocessRequest, "suffix", ".."),
    ],
)
def test_postprocess_requests_reject_invalid_paths_types_bounds_and_suffix(
    request_type, field: str, value: object
) -> None:
    base = {
        "operation_id": OPERATION_ID,
        "workspace_rel": "job",
        "source_paths_rel": ["BANDS_1.dat"],
    }
    if request_type is DosPostprocessRequest:
        base.pop("source_paths_rel")
        base["dos_paths_rel"] = ["DOS1_smearing.dat"]
    with pytest.raises(ValueError, match=field):
        request_type(**{**base, field: value})


def test_postprocess_requests_reject_inverted_or_non_numeric_plot_bounds() -> None:
    with pytest.raises(ValueError, match="plot_emin|plot_emax"):
        BandPostprocessRequest(
            operation_id=OPERATION_ID,
            workspace_rel="job",
            source_paths_rel=["BANDS_1.dat"],
            plot_emin=1.0,
            plot_emax=1.0,
        )
    with pytest.raises(ValueError, match="plot_emin|plot_emax"):
        DosPostprocessRequest(
            operation_id=OPERATION_ID,
            workspace_rel="job",
            dos_paths_rel=["DOS1_smearing.dat"],
            plot_emin=3.0,
            plot_emax=-3.0,
        )


@pytest.mark.parametrize(
    ("capability", "request_type"),
    [("band", BandPostprocessRequest), ("dos", DosPostprocessRequest)],
)
def test_postprocess_schema_matches_dataclass_wire_and_rejects_extra_fields(
    capability: str, request_type
) -> None:
    if capability == "band":
        request = request_type(
            operation_id=OPERATION_ID,
            workspace_rel="job",
            source_paths_rel=["BANDS_1.dat"],
        )
    else:
        request = request_type(
            operation_id=OPERATION_ID,
            workspace_rel="job",
            dos_paths_rel=["DOS1_smearing.dat"],
        )
    schema = request_schema_document(capability, "postprocess")["request_schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == set(request.to_dict())
    assert set(schema["required"]) >= {
        "schema_version",
        "capability",
        "operation",
        "operation_id",
        "workspace_rel",
    }


def test_pyatb_band_requests_round_trip_with_defaults_and_frozen_payloads() -> None:
    request = _pyatb_prepare_request()
    payload = request.to_dict()
    assert payload["schema_version"] == "forge.request/v1"
    assert payload["capability"] == "pyatb-band"
    assert payload["operation"] == "prepare"
    assert payload["nspin"] == 1
    assert payload["line_segments"] == 20
    assert payload["max_kpoint_num"] == 4000
    assert payload["handoff_mode"] == "link"
    assert PyatbBandPrepareRequest.from_dict(json.loads(json.dumps(payload))) == request
    payload["line_kpoints"][0]["coords"][0] = 99  # type: ignore[index]
    assert request.line_kpoints[0]["coords"][0] == 0
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.fermi_energy = 2.0  # type: ignore[misc]
    with pytest.raises(ValueError, match="unknown"):
        PyatbBandPrepareRequest.from_dict({**request.to_dict(), "unknown": True})

    execute = PyatbBandExecuteRequest(operation_id=OPERATION_ID, workspace_rel="job")
    collect = PyatbBandCollectRequest(operation_id=OPERATION_ID, workspace_rel="job")
    assert execute.to_dict()["executable"] == "pyatb"
    assert collect.to_dict()["band_info_path_rel"] == "inputs/Out/Band_Structure/band_info.dat"
    assert PyatbBandExecuteRequest.from_dict(json.loads(json.dumps(execute.to_dict()))) == execute
    assert PyatbBandCollectRequest.from_dict(json.loads(json.dumps(collect.to_dict()))) == collect


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("nspin", 3),
        ("hr_paths_rel", ["inputs/HR1.dat", "inputs/HR2.dat"]),
        ("hr_paths_rel", []),
        ("line_kpoints", [{"coords": [0, 0, 0]}]),
        ("line_kpoints", [{"coords": [0, 0, 0], "extra": 1}, {"coords": [1, 0, 0]}]),
        ("line_kpoints", [{"coords": [0, 0, float("nan")]}, {"coords": [1, 0, 0]}]),
        ("line_kpoints", [{"coords": [0, 0]}, {"coords": [1, 0, 0]}]),
        ("structure_path_rel", "../STRU"),
        ("sr_path_rel", "a/../SR.dat"),
        ("rr_path_rel", "/tmp/rR.dat"),
        ("fermi_energy", float("inf")),
        ("handoff_mode", "move"),
    ],
)
def test_pyatb_band_prepare_rejects_invalid_cardinality_numbers_and_paths(
    field: str, value: object
) -> None:
    with pytest.raises(ValueError, match=field):
        _pyatb_prepare_request(**{field: value})


def test_pyatb_band_prepare_accepts_spin_two_only_with_two_hr_paths() -> None:
    request = _pyatb_prepare_request(nspin=2, hr_paths_rel=["inputs/HR1.dat", "inputs/HR2.dat"])
    assert request.nspin == 2
    assert request.hr_paths_rel == ("inputs/HR1.dat", "inputs/HR2.dat")
    with pytest.raises(ValueError, match="hr_paths_rel"):
        _pyatb_prepare_request(nspin=2)


def test_pyatb_band_collect_rejects_invalid_output_path_lists() -> None:
    with pytest.raises(ValueError, match="band_data_paths_rel"):
        PyatbBandCollectRequest(operation_id=OPERATION_ID, workspace_rel="job", band_data_paths_rel=["../band.dat"])
    with pytest.raises(ValueError, match="band_picture_paths_rel"):
        PyatbBandCollectRequest(operation_id=OPERATION_ID, workspace_rel="job", band_picture_paths_rel=["a//band.png"])
