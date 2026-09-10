from __future__ import annotations

import dataclasses
import json

import pytest

from abacus_forge import MdPostprocessRequest
from abacus_forge.discovery import request_schema_document


OPERATION_ID = "123e4567-e89b-42d3-a456-426614174000"


def _request(**updates: object) -> MdPostprocessRequest:
    values: dict[str, object] = {
        "operation_id": OPERATION_ID,
        "workspace_rel": "job",
        "trajectory_path_rel": "outputs/md.traj",
        "analysis": ("rdf",),
    }
    values.update(updates)
    return MdPostprocessRequest(**values)


def test_md_postprocess_round_trips_defaults_and_detaches_serialized_values() -> None:
    request = _request()

    assert request.operation == "postprocess"
    assert request.capability == "md"
    assert request.output_dir_rel == "outputs/md-postprocess"
    assert request.start == 0
    assert request.end is None
    assert request.stride == 1
    assert request.parameters == {}
    payload = request.to_dict()
    assert payload == {
        "schema_version": "forge.request/v1",
        "capability": "md",
        "operation": "postprocess",
        "operation_id": OPERATION_ID,
        "workspace_rel": "job",
        "trajectory_path_rel": "outputs/md.traj",
        "analysis": ["rdf"],
        "output_dir_rel": "outputs/md-postprocess",
        "start": 0,
        "end": None,
        "stride": 1,
        "parameters": {},
    }
    assert MdPostprocessRequest.from_dict(json.loads(json.dumps(payload))) == request

    payload["analysis"].append("msd")  # type: ignore[union-attr]
    payload["parameters"]["nested"] = {"values": [1]}  # type: ignore[index]
    assert request.analysis == ("rdf",)
    assert request.parameters == {}
    second = request.to_dict()
    assert second["analysis"] == ["rdf"]
    assert second["parameters"] == {}
    assert second["analysis"] is not payload["analysis"]
    assert second["parameters"] is not payload["parameters"]


def test_md_postprocess_is_frozen_and_deeply_immutable() -> None:
    parameters = {"nested": {"values": [1]}}
    analysis = ["rdf", "msd"]
    request = _request(analysis=analysis, parameters=parameters)
    analysis.append("temperature")
    parameters["nested"]["values"].append(2)  # type: ignore[index]

    assert request.analysis == ("rdf", "msd")
    assert request.parameters["nested"]["values"] == (1,)  # type: ignore[index]
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.start = 1  # type: ignore[misc]
    with pytest.raises(TypeError):
        request.parameters["nested"]["values"] = (2,)  # type: ignore[index]


@pytest.mark.parametrize(
    "field",
    ["operation_id", "workspace_rel", "trajectory_path_rel", "analysis"],
)
def test_md_postprocess_from_dict_requires_identity_and_analysis_fields(field: str) -> None:
    payload = _request().to_dict()
    payload.pop(field)
    with pytest.raises(ValueError):
        MdPostprocessRequest.from_dict(payload)


@pytest.mark.parametrize(
    "update",
    [
        {"unknown": True},
        {"trajectory_path": "outputs/md.traj"},
        {"analysis_mode": "rdf"},
        {"start_frame": 1},
        {"stop": 2},
        {"step": 2},
        {"capability": "molecular-dynamics"},
        {"operation": "md-postprocess"},
    ],
)
def test_md_postprocess_from_dict_rejects_unknown_fields_and_aliases(update: dict[str, object]) -> None:
    payload = _request().to_dict()
    payload.update(update)
    with pytest.raises(ValueError):
        MdPostprocessRequest.from_dict(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("trajectory_path_rel", "."),
        ("trajectory_path_rel", "../md.traj"),
        ("trajectory_path_rel", "outputs/../md.traj"),
        ("trajectory_path_rel", "outputs//md.traj"),
        ("trajectory_path_rel", "outputs\\md.traj"),
        ("trajectory_path_rel", "/tmp/md.traj"),
        ("output_dir_rel", "../outputs"),
        ("output_dir_rel", "outputs/./md"),
        ("output_dir_rel", "outputs//md"),
        ("output_dir_rel", "/tmp"),
    ],
)
def test_md_postprocess_rejects_noncanonical_paths(field: str, value: object) -> None:
    payload = _request().to_dict()
    payload[field] = value  # type: ignore[assignment]
    with pytest.raises(ValueError, match=field):
        MdPostprocessRequest.from_dict(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("analysis", []),
        ("analysis", ["rdf", "rdf"]),
        ("analysis", [""]),
        ("analysis", ["rdf", 1]),
        ("analysis", "rdf"),
        ("start", -1),
        ("start", True),
        ("start", 1.5),
        ("end", 0),
        ("end", -1),
        ("end", True),
        ("end", 1.5),
        ("stride", 0),
        ("stride", -1),
        ("stride", True),
        ("stride", 1.5),
    ],
)
def test_md_postprocess_rejects_invalid_analysis_and_sampling(field: str, value: object) -> None:
    payload = _request().to_dict()
    payload[field] = value  # type: ignore[assignment]
    with pytest.raises(ValueError, match=field):
        MdPostprocessRequest.from_dict(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("parameters", []),
        ("parameters", "not-an-object"),
        ("parameters", None),
        ("parameters", {"value": object()}),
        ("parameters", {"value": float("nan")}),
    ],
)
def test_md_postprocess_rejects_non_json_parameters(field: str, value: object) -> None:
    payload = _request().to_dict()
    payload[field] = value  # type: ignore[assignment]
    with pytest.raises(ValueError, match="parameters|JSON-safe"):
        MdPostprocessRequest.from_dict(payload)


def test_md_postprocess_schema_matches_dataclass_and_wire_keys() -> None:
    request = _request()
    schema = request_schema_document("md", "postprocess")["request_schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == set(request.to_dict())
    assert set(schema["properties"]) == {
        field.name for field in dataclasses.fields(MdPostprocessRequest)
    } | {"capability", "operation"}
    assert set(schema["required"]) == {
        "schema_version",
        "capability",
        "operation",
        "operation_id",
        "workspace_rel",
        "trajectory_path_rel",
        "analysis",
    }
    assert schema["properties"]["analysis"]["uniqueItems"] is True
    assert schema["properties"]["output_dir_rel"]["default"] == "outputs/md-postprocess"
    assert schema["properties"]["start"]["minimum"] == 0
    assert schema["properties"]["stride"]["minimum"] == 1
    assert schema["properties"]["end"]["exclusiveMinimum"] == 0
