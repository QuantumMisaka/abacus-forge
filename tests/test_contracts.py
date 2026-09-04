from __future__ import annotations

import json

import pytest

from abacus_forge import contracts
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
)


OPERATION_ID = "123e4567-e89b-42d3-a456-426614174000"


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
        ("mpi_ranks", 0),
        ("mpi_ranks", True),
        ("omp_threads", 0),
        ("omp_threads", True),
        ("timeout_seconds", 0.0),
        ("timeout_seconds", float("inf")),
        ("timeout_seconds", float("nan")),
    ],
)
def test_scf_execute_request_rejects_invalid_runner_configuration(field: str, value: object) -> None:
    payload = _valid_execute_request_dict()
    payload[field] = value
    with pytest.raises(ValueError):
        ScfExecuteRequest.from_dict(payload)


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
    assert ScfPrepareRequest.from_dict(request.to_dict()) == request


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
