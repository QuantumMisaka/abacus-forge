from __future__ import annotations

import json

import pytest

from abacus_forge.contracts import ArtifactRecord, ForgeRequest, ForgeResultEnvelope, MetricRecord, OperationStatus


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
