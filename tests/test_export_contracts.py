import json

import pytest

from abacus_forge.export_contracts import ExportDocument, ExportRequest
from abacus_forge.discovery import capabilities_document, request_schema_document
from abacus_forge.machine_cli import decode_operation_request


OP = "123e4567-e89b-42d3-a456-426614174000"
SRC = "123e4567-e89b-42d3-a456-426614174001"


def request_payload(**overrides):
    payload = {
        "schema_version": "forge.request/v1",
        "capability": "export",
        "operation": "export",
        "operation_id": OP,
        "workspace_rel": ".",
        "source_artifact_refs": [{"operation_id": SRC, "artifact_id": "energy"}],
        "destination_path_rel": "exports/result.json",
        "format": "json",
        "pretty": False,
        "overwrite_policy": "fail",
    }
    payload.update(overrides)
    return payload


def test_export_request_round_trip_and_immutable_refs():
    request = ExportRequest.from_dict(request_payload())
    assert request.to_dict() == request_payload()
    assert request.source_artifact_refs[0].artifact_id == "energy"
    assert json.dumps(request.to_dict(), allow_nan=False)


@pytest.mark.parametrize(
    "changes",
    [
        {"capability": "scf"},
        {"operation": "collect"},
        {"source_artifact_refs": []},
        {"source_artifact_refs": [{"operation_id": SRC, "artifact_id": "a"}, {"operation_id": SRC, "artifact_id": "a"}]},
        {"source_artifact_refs": [{"operation_id": SRC, "artifact_id": "a"}, {"operation_id": OP, "artifact_id": "b"}]},
        {"destination_path_rel": "../result.json"},
        {"destination_path_rel": "/tmp/result.json"},
        {"format": "yaml"},
        {"overwrite_policy": "replace"},
        {"pretty": 1},
        {"unknown": True},
    ],
)
def test_export_request_rejects_invalid_payload(changes):
    with pytest.raises(ValueError):
        ExportRequest.from_dict(request_payload(**changes))


def test_export_document_round_trip_is_json_safe_and_strict():
    payload = {
        "schema_version": "forge.export/v1",
        "source_operation_id": SRC,
        "source_artifact_refs": [{"operation_id": SRC, "artifact_id": "energy"}],
        "source_outcome": {
            "schema_version": "forge.operation-outcome/v1",
            "operation_id": SRC,
            "envelope": {"operation": "collect", "artifacts": [], "metrics": []},
            "observations": [],
        },
    }
    document = ExportDocument.from_dict(payload)
    assert document.to_dict() == payload
    assert json.dumps(document.to_dict(), allow_nan=False)
    with pytest.raises(ValueError):
        ExportDocument.from_dict({**payload, "extra": True})


def test_export_document_requires_source_identity_consistency():
    payload = {
        "schema_version": "forge.export/v1",
        "source_operation_id": SRC,
        "source_artifact_refs": [{"operation_id": SRC, "artifact_id": "energy"}],
        "source_outcome": {"schema_version": "forge.operation-outcome/v1", "operation_id": SRC},
    }
    with pytest.raises(ValueError):
        ExportDocument.from_dict({**payload, "source_artifact_refs": []})
    with pytest.raises(ValueError):
        ExportDocument.from_dict({**payload, "source_outcome": {"schema_version": "forge.result/v1", "operation_id": SRC}})


def test_export_is_explicitly_discoverable_and_decodable():
    descriptor = next(item for item in capabilities_document()["capabilities"] if item["name"] == "export")
    assert descriptor["operations"] == ["export"]
    schema = request_schema_document("export", "export")["request_schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "schema_version", "capability", "operation", "operation_id", "workspace_rel",
        "source_artifact_refs", "destination_path_rel",
    }
    assert isinstance(decode_operation_request("export", request_payload()), ExportRequest)
