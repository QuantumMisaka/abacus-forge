from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from abacus_forge import MdExecuteRequest, MdPrepareRequest, OperationOutcome
from abacus_forge.discovery import capabilities_document, request_schema_document
from abacus_forge.machine_cli import decode_operation_request, run_machine_cli


OPERATION_ID = "123e4567-e89b-42d3-a456-426614174000"


def _payload(operation: str, **extra: object) -> dict[str, object]:
    return {
        "schema_version": "forge.request/v1",
        "operation": operation,
        "operation_id": OPERATION_ID,
        "workspace_rel": ".",
        "capability": "md",
        **extra,
    }


def test_md_is_discoverable_and_has_four_operation_schemas() -> None:
    descriptors = capabilities_document()["capabilities"]
    md = next(item for item in descriptors if item["name"] == "md")
    assert md["maturity"] == "experimental"
    assert md["engine"] == "abacus"
    assert md["operations"] == ["prepare", "modify", "execute", "collect"]
    assert md["artifact_roles"] == ["input", "provenance_manifest", "output"]
    for operation in md["operations"]:
        schema = request_schema_document("md", operation)["request_schema"]
        assert schema["title"] == f"Md{operation.title()}Request"
        assert schema["properties"]["capability"]["const"] == "md"


@pytest.mark.parametrize("operation,request_type", [
    ("prepare", MdPrepareRequest),
    ("execute", MdExecuteRequest),
])
def test_md_request_is_decoded_by_capability(operation: str, request_type: type) -> None:
    extra = {"structure_path_rel": "source.STRU"} if operation == "prepare" else {"dry_run": True}
    request = decode_operation_request(operation, _payload(operation, **extra))
    assert isinstance(request, request_type)
    assert request.capability == "md"


def test_md_postprocess_and_export_are_rejected_as_request_invalid(tmp_path: Path) -> None:
    for operation in ("postprocess", "export"):
        stdout, stderr = io.StringIO(), io.StringIO()
        code = run_machine_cli(
            ["operation", operation, "--stdin"],
            stdin=io.StringIO(json.dumps(_payload(operation))), stdout=stdout, stderr=stderr, cwd=tmp_path,
        )
        assert code == 2
        assert json.loads(stdout.getvalue())["error"]["class"] == "request.invalid"
        assert stderr.getvalue() == ""


def test_md_dry_run_and_prepare_use_machine_envelope(tmp_path: Path) -> None:
    source = tmp_path / "source.STRU"
    source.write_text(
        "ATOMIC_SPECIES\nSi 28.0855 Si.upf\n\nLATTICE_CONSTANT\n1.0\n"
        "LATTICE_CONSTANT_UNIT\nAngstrom\n\nLATTICE_VECTORS\n"
        "1 0 0\n0 1 0\n0 0 1\n\nATOMIC_POSITIONS\nDirect\nSi\n0\n1\n0 0 0 m 1 1 1\n",
        encoding="utf-8",
    )
    for operation, extra, operation_id in (
        ("prepare", {"structure_path_rel": "source.STRU"}, OPERATION_ID),
        ("execute", {"dry_run": True}, "123e4567-e89b-42d3-a456-426614174001"),
    ):
        stdout, stderr = io.StringIO(), io.StringIO()
        code = run_machine_cli(
            ["operation", operation, "--stdin"],
            stdin=io.StringIO(json.dumps({**_payload(operation, **extra), "operation_id": operation_id})),
            stdout=stdout, stderr=stderr, cwd=tmp_path,
        )
        assert code == 0
        result = json.loads(stdout.getvalue())
        assert result["operation_id"] == operation_id
        assert result["envelope"]["operation"] == operation
        assert result["envelope"]["status"]["scientific"] == "unassessed"
        assert stderr.getvalue() == ""
