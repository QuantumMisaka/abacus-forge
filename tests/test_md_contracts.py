from __future__ import annotations

import json

import pytest

from abacus_forge.md_contracts import (
    MdCollectRequest,
    MdExecuteRequest,
    MdModifyRequest,
    MdPrepareRequest,
)


OPERATION_ID = "123e4567-e89b-42d3-a456-426614174000"


@pytest.mark.parametrize(
    ("request_type", "operation", "extra"),
    [
        (MdPrepareRequest, "prepare", {"structure_path_rel": "source.STRU"}),
        (MdModifyRequest, "modify", {}),
        (MdExecuteRequest, "execute", {}),
        (MdCollectRequest, "collect", {}),
    ],
)
def test_md_requests_are_typed_and_round_trip(request_type, operation, extra):
    request = request_type(operation_id=OPERATION_ID, workspace_rel="md", capability="md", **extra)

    assert request.operation == operation
    assert request.capability == "md"
    assert request_type.from_dict(request.to_dict()) == request
    assert json.loads(json.dumps(request.to_dict(), allow_nan=False))["capability"] == "md"


def test_md_prepare_accepts_only_md_calculation_when_explicit():
    request = MdPrepareRequest(
        operation_id=OPERATION_ID,
        workspace_rel="md",
        capability="md",
        structure_path_rel="source.STRU",
        parameters={"calculation": "md", "md_nstep": 10},
    )
    assert request.parameters["calculation"] == "md"

    with pytest.raises(ValueError, match="calculation"):
        MdPrepareRequest(
            operation_id=OPERATION_ID,
            workspace_rel="md",
            capability="md",
            structure_path_rel="source.STRU",
            parameters={"calculation": "scf"},
        )


def test_md_modify_rejects_calculation_update_or_removal():
    with pytest.raises(ValueError, match="calculation"):
        MdModifyRequest(
            operation_id=OPERATION_ID,
            workspace_rel="md",
            capability="md",
            input_updates={"calculation": "md"},
        )
    with pytest.raises(ValueError, match="calculation"):
        MdModifyRequest(
            operation_id=OPERATION_ID,
            workspace_rel="md",
            capability="md",
            remove_parameters=("calculation",),
        )


@pytest.mark.parametrize("request_type", [MdPrepareRequest, MdModifyRequest, MdExecuteRequest, MdCollectRequest])
def test_md_requests_reject_other_capabilities(request_type):
    extra = {"structure_path_rel": "source.STRU"} if request_type is MdPrepareRequest else {}
    with pytest.raises(ValueError, match="capability"):
        request_type(operation_id=OPERATION_ID, workspace_rel="md", capability="scf", **extra)
