from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from abacus_forge import machine_cli
from abacus_forge.contracts import (
    ArtifactRecord,
    ForgeErrorEnvelope,
    ForgeResultEnvelope,
    MetricRecord,
    OperationOutcome,
    OperationStatus,
    ScfCollectRequest,
    ScfExecuteRequest,
    ScfModifyRequest,
    ScfPrepareRequest,
)
from abacus_forge.discovery import capabilities_document, request_schema_document
from abacus_forge.machine_cli import decode_scf_request, exit_code_for, run_machine_cli
from abacus_forge.errors import (
    ForgeInternalError,
    ForgePathError,
    ForgePreconditionError,
    ForgeRequestError,
    ForgeSchemaError,
)
from abacus_forge.relax_contracts import (
    RelaxCollectRequest,
    RelaxExecuteRequest,
    RelaxModifyRequest,
    RelaxPrepareRequest,
)


OPERATION_ID = "123e4567-e89b-42d3-a456-426614174000"


def _decode_operation_request(operation: str, payload: object):
    decoder = getattr(machine_cli, "decode_operation_request", None)
    assert decoder is not None, "machine adapter must expose capability-aware decoding"
    return decoder(operation, payload)


def _request() -> dict[str, object]:
    return {
        "schema_version": "forge.request/v1",
        "operation": "collect",
        "operation_id": OPERATION_ID,
        "workspace_rel": ".",
    }


def _outcome(*, execution: str = "completed") -> OperationOutcome:
    return _outcome_for("collect", OPERATION_ID, execution=execution)


def _outcome_for(operation: str, operation_id: str, *, execution: str = "completed") -> OperationOutcome:
    envelope = ForgeResultEnvelope(
        operation=operation,
        workspace_rel=".",
        status=OperationStatus(execution=execution, scientific="unassessed", collection="complete"),
        artifacts=(ArtifactRecord(id="stdout", path_rel="outputs/stdout.log", role="output", stage=operation),),
        metrics=(MetricRecord(name="returncode", value=0, unit=None, kind="runtime"),),
    )
    return OperationOutcome(operation_id=operation_id, envelope=envelope)


class _RecordingServices:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[tuple[str, object]] = []
        self.collect = _RecordingCollectService(self)

    def collect(self, request: object) -> object:
        raise AssertionError("the operation service should be called through its narrow member")


class _RecordingCollectService:
    def __init__(self, owner: _RecordingServices) -> None:
        self.owner = owner

    def collect(self, request: object) -> object:
        self.owner.calls.append(("collect", request))
        return self.owner.result


class _RaisingCollectService:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def collect(self, request: object) -> object:
        raise self.error


class _RaisingServices:
    def __init__(self, error: Exception) -> None:
        self.collect = _RaisingCollectService(error)


class _RecordingOperationService:
    def __init__(self, owner: "_AllRecordingServices", operation: str) -> None:
        self.owner = owner
        self.operation = operation

    def __getattr__(self, name: str):
        if name != self.operation:
            raise AttributeError(name)
        return self._call

    def _call(self, request: object) -> object:
        self.owner.calls.append((self.operation, request))
        return self.owner.results[self.operation]


class _AllRecordingServices:
    def __init__(self, results: dict[str, object]) -> None:
        self.results = results
        self.calls: list[tuple[str, object]] = []
        self.prepare = _RecordingOperationService(self, "prepare")
        self.modify = _RecordingOperationService(self, "modify")
        self.execute = _RecordingOperationService(self, "execute")
        self.collect = _RecordingOperationService(self, "collect")


def _invoke(
    argv: list[str],
    *,
    request_text: str = "",
    services: object | None = None,
    cwd: Path = Path("/tmp/forge-machine-test"),
):
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = run_machine_cli(
        argv,
        stdin=io.StringIO(request_text),
        stdout=stdout,
        stderr=stderr,
        cwd=cwd,
        services=services,  # type: ignore[arg-type]
    )
    return code, stdout.getvalue(), stderr.getvalue()


def test_discovery_documents_are_json_safe_and_deterministic() -> None:
    capabilities = capabilities_document()
    schema = request_schema_document("scf", "execute")
    assert json.dumps(capabilities, allow_nan=False, sort_keys=True)
    assert json.dumps(schema, allow_nan=False, sort_keys=True)
    assert capabilities == capabilities_document()
    assert schema == request_schema_document("scf", "execute")


def test_discovery_advertises_exactly_three_experimental_abacus_capabilities() -> None:
    descriptors = capabilities_document()["capabilities"]
    assert [descriptor["name"] for descriptor in descriptors] == ["scf", "relax", "cell-relax"]
    for descriptor in descriptors:
        assert descriptor["maturity"] == "experimental"
        assert descriptor["engine"] == "abacus"
        assert descriptor["operations"] == ["prepare", "modify", "execute", "collect"]
        assert descriptor["artifact_roles"] == ["input", "provenance_manifest", "output"]


@pytest.mark.parametrize("capability", ["relax", "cell-relax"])
@pytest.mark.parametrize(
    ("operation", "request_type", "extra"),
    [
        ("prepare", RelaxPrepareRequest, {"structure_path_rel": "source.STRU"}),
        ("modify", RelaxModifyRequest, {}),
        ("execute", RelaxExecuteRequest, {}),
        ("collect", RelaxCollectRequest, {}),
    ],
)
def test_relax_schema_reflects_typed_wire_and_calculation_constraints(
    capability: str,
    operation: str,
    request_type: type[object],
    extra: dict[str, object],
) -> None:
    request = request_type(
        operation_id=OPERATION_ID,
        workspace_rel="job",
        capability=capability,
        **extra,
    )
    schema = request_schema_document(capability, operation)["request_schema"]
    assert set(schema["properties"]) == set(request.to_dict())
    assert "capability" in schema["required"]
    assert schema["properties"]["capability"] == {
        "type": "string",
        "const": capability,
    }
    if operation == "prepare":
        assert schema["properties"]["parameters"]["properties"]["calculation"]["const"] == capability
    if operation == "modify":
        assert schema["properties"]["input_updates"]["properties"]["calculation"]["const"] == capability
        assert schema["properties"]["remove_parameters"]["items"]["not"] == {"const": "calculation"}


def test_machine_adapter_calls_one_service_and_writes_one_json_document() -> None:
    expected = _outcome()
    services = _RecordingServices(expected)
    code, output, diagnostics = _invoke(
        ["operation", "collect", "--stdin"], request_text=json.dumps(_request()), services=services
    )
    assert code == 0
    assert json.loads(output) == expected.to_dict()
    assert output.endswith("\n")
    assert output.count("\n") == 1
    assert diagnostics == ""
    assert len(services.calls) == 1
    assert services.calls[0][0] == "collect"
    assert isinstance(services.calls[0][1], ScfCollectRequest)


@pytest.mark.parametrize(
    ("operation", "payload", "request_type"),
    [
        (
            "prepare",
            {
                "schema_version": "forge.request/v1",
                "operation": "prepare",
                "operation_id": "123e4567-e89b-42d3-a456-426614174010",
                "workspace_rel": ".",
                "structure_path_rel": "source.STRU",
            },
            ScfPrepareRequest,
        ),
        (
            "modify",
            {
                "schema_version": "forge.request/v1",
                "operation": "modify",
                "operation_id": "123e4567-e89b-42d3-a456-426614174011",
                "workspace_rel": ".",
            },
            ScfModifyRequest,
        ),
        (
            "execute",
            {
                "schema_version": "forge.request/v1",
                "operation": "execute",
                "operation_id": "123e4567-e89b-42d3-a456-426614174012",
                "workspace_rel": ".",
            },
            ScfExecuteRequest,
        ),
        ("collect", _request(), ScfCollectRequest),
    ],
)
def test_machine_dispatches_each_narrow_service_exactly_once(
    operation: str, payload: dict[str, object], request_type: type[object]
) -> None:
    operation_id = payload["operation_id"]
    assert isinstance(operation_id, str)
    results = {name: _outcome_for(name, operation_id) for name in ("prepare", "modify", "execute", "collect")}
    services = _AllRecordingServices(results)
    code, output, diagnostics = _invoke(
        ["operation", operation, "--stdin"], request_text=json.dumps(payload), services=services
    )
    assert code == 0
    assert json.loads(output) == results[operation].to_dict()
    assert diagnostics == ""
    assert len(services.calls) == 1
    assert services.calls[0][0] == operation
    assert isinstance(services.calls[0][1], request_type)


def test_machine_request_file_and_stdin_are_mutually_exclusive(tmp_path: Path) -> None:
    request_file = tmp_path / "request.json"
    request_file.write_text(json.dumps(_request()), encoding="utf-8")
    code, output, _ = _invoke(
        ["operation", "collect", "--request", str(request_file), "--stdin"], request_text=json.dumps(_request())
    )
    assert code == 2
    assert json.loads(output)["error"]["class"] == "request.invalid"


def test_machine_request_file_reads_utf8_and_rejects_malformed_utf8(tmp_path: Path) -> None:
    request_file = tmp_path / "request.json"
    request_file.write_bytes(b"\xff")
    code, output, _ = _invoke(["operation", "collect", "--request", str(request_file)])
    assert code == 2
    assert json.loads(output)["error"]["class"] == "request.invalid"


def test_machine_request_file_path_failure_is_request_path(tmp_path: Path) -> None:
    code, output, _ = _invoke(["operation", "collect", "--request", str(tmp_path / "missing.json")])
    assert code == 2
    assert json.loads(output)["error"]["class"] == "request.path"


@pytest.mark.parametrize(
    ("payload", "error_class"),
    [
        ("{", "request.invalid"),
        ("[]", "request.invalid"),
        (json.dumps({**_request(), "schema_version": "wrong"}), "request.schema"),
        (json.dumps({**_request(), "operation": "execute"}), "request.invalid"),
        (json.dumps({**_request(), "workspace_rel": "../escape"}), "request.path"),
    ],
)
def test_machine_decoding_maps_distinct_request_phases(payload: str, error_class: str) -> None:
    code, output, _ = _invoke(["operation", "collect", "--stdin"], request_text=payload)
    assert code == 2
    assert json.loads(output)["error"]["class"] == error_class


def test_machine_json_reader_rejects_a_second_document() -> None:
    services = _RecordingServices(_outcome())
    request_text = json.dumps(_request()) + "\n" + json.dumps(_request())
    code, output, _ = _invoke(["operation", "collect", "--stdin"], request_text=request_text, services=services)
    assert code == 2
    assert json.loads(output)["error"]["class"] == "request.invalid"
    assert services.calls == []


def test_machine_json_reader_accepts_trailing_whitespace() -> None:
    services = _RecordingServices(_outcome())
    request_text = json.dumps(_request()) + " \t\n"
    code, output, _ = _invoke(["operation", "collect", "--stdin"], request_text=request_text, services=services)
    assert code == 0
    assert json.loads(output) == _outcome().to_dict()
    assert len(services.calls) == 1


@pytest.mark.parametrize(
    ("capability", "operation"),
    [("md", "execute"), ("relax", "postprocess"), ("pyatb", "prepare")],
)
def test_machine_schema_unknown_selector_is_one_request_invalid_document(
    capability: str, operation: str
) -> None:
    code, output, diagnostics = _invoke(["schema", capability, operation])
    assert code == 2
    assert json.loads(output)["error"]["class"] == "request.invalid"
    assert diagnostics == ""


@pytest.mark.parametrize("operation", ["postprocess", "export"])
def test_machine_unsupported_operation_is_structured_request_invalid(operation: str) -> None:
    code, output, _ = _invoke(["operation", operation, "--stdin"], request_text=json.dumps(_request()))
    assert code == 2
    assert json.loads(output)["error"]["class"] == "request.invalid"


def test_machine_json_pretty_and_text_render_the_same_operation_result() -> None:
    expected = _outcome()
    services = _RecordingServices(expected)
    compact_code, compact, _ = _invoke(
        ["operation", "collect", "--stdin"], request_text=json.dumps(_request()), services=services
    )
    pretty_code, pretty, _ = _invoke(
        ["operation", "collect", "--stdin", "--pretty"], request_text=json.dumps(_request()), services=services
    )
    text_code, text, _ = _invoke(
        ["operation", "collect", "--stdin", "--format", "text"],
        request_text=json.dumps(_request()),
        services=services,
    )
    assert compact_code == pretty_code == text_code == 0
    assert json.loads(compact) == json.loads(pretty) == expected.to_dict()
    assert len(pretty.splitlines()) > 1
    assert "operation: collect" in text
    assert "execution: completed" in text
    assert "collection: complete" in text
    assert "converged" not in text.lower()
    assert len(services.calls) == 3


def test_machine_pretty_text_conflict_is_invalid_without_service_call() -> None:
    services = _RecordingServices(_outcome())
    code, output, _ = _invoke(
        ["operation", "collect", "--stdin", "--format", "text", "--pretty"],
        request_text=json.dumps(_request()),
        services=services,
    )
    assert code == 2
    assert "--pretty" in output
    assert services.calls == []


def test_machine_error_envelope_rendering_preserves_context_and_exit() -> None:
    error = ForgeErrorEnvelope(
        "precondition.missing", "inputs/INPUT is missing", ("request",), OPERATION_ID, "."
    )
    services = _RecordingServices(error)
    code, output, _ = _invoke(
        ["operation", "collect", "--stdin"], request_text=json.dumps(_request()), services=services
    )
    assert code == 3
    assert json.loads(output) == error.to_dict()


@pytest.mark.parametrize(
    ("error", "error_class", "exit_code"),
    [
        (ForgeInternalError(), "internal.failure", 5),
        (ForgePreconditionError(), "precondition.missing", 3),
    ],
)
def test_machine_empty_exception_message_still_renders_one_error_envelope(
    error: Exception, error_class: str, exit_code: int
) -> None:
    code, output, diagnostics = _invoke(
        ["operation", "collect", "--stdin"],
        request_text=json.dumps(_request()),
        services=_RaisingServices(error),
    )

    assert code == exit_code
    payload = json.loads(output)
    assert payload["schema_version"] == "forge.error/v1"
    assert payload["error"]["class"] == error_class
    assert payload["error"]["message"]
    assert diagnostics == ""


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (ForgeErrorEnvelope("request.schema", "bad request", ("request",)), 2),
        (ForgeErrorEnvelope("precondition.missing", "missing input", ("request",)), 3),
        (_outcome(execution="failed"), 4),
        (ForgeErrorEnvelope("internal.failure", "broken forge", ("request",)), 5),
    ],
)
def test_machine_exit_mapping_is_semantic(result: object, expected: int) -> None:
    assert exit_code_for(result) == expected


def test_decode_scf_request_uses_strict_typed_decoder() -> None:
    request = decode_scf_request("collect", _request())
    assert isinstance(request, ScfCollectRequest)
    with pytest.raises(ForgeSchemaError):
        decode_scf_request("collect", {**_request(), "unknown": True})
    with pytest.raises(ForgeRequestError):
        decode_scf_request("postprocess", _request())
    with pytest.raises(ForgePathError):
        decode_scf_request("collect", {**_request(), "workspace_rel": "../escape"})


@pytest.mark.parametrize("capability", ["relax", "cell-relax"])
@pytest.mark.parametrize(
    ("operation", "request_type", "extra"),
    [
        ("prepare", RelaxPrepareRequest, {"structure_path_rel": "source.STRU"}),
        ("modify", RelaxModifyRequest, {}),
        ("execute", RelaxExecuteRequest, {}),
        ("collect", RelaxCollectRequest, {}),
    ],
)
def test_decode_operation_request_routes_relax_capabilities_to_typed_requests(
    capability: str,
    operation: str,
    request_type: type[object],
    extra: dict[str, object],
) -> None:
    payload = {
        "schema_version": "forge.request/v1",
        "operation": operation,
        "operation_id": OPERATION_ID,
        "workspace_rel": "job",
        "capability": capability,
        **extra,
    }
    request = _decode_operation_request(operation, payload)
    assert isinstance(request, request_type)
    assert request.to_dict()["capability"] == capability


@pytest.mark.parametrize(
    ("payload_update", "error_type"),
    [
        ({"capability": "md"}, ForgeRequestError),
        ({"capability": None}, ForgeRequestError),
        ({"capability": 1}, ForgeRequestError),
        ({"capability": "scf"}, ForgeSchemaError),
        ({"capability": "relax", "input_updates": {"calculation": "cell-relax"}}, ForgeSchemaError),
        ({"capability": "cell-relax", "workspace_rel": "../escape"}, ForgePathError),
        ({"capability": "relax", "schema_version": "forge.request/v2"}, ForgeSchemaError),
    ],
)
def test_machine_rejects_invalid_capability_requests_before_service_dispatch(
    payload_update: dict[str, object], error_type: type[Exception]
) -> None:
    payload = {
        "schema_version": "forge.request/v1",
        "operation": "modify",
        "operation_id": OPERATION_ID,
        "workspace_rel": "job",
        **payload_update,
    }
    with pytest.raises(error_type):
        _decode_operation_request("modify", payload)

    services = _AllRecordingServices(
        {name: _outcome_for(name, OPERATION_ID) for name in ("prepare", "modify", "execute", "collect")}
    )
    code, output, diagnostics = _invoke(
        ["operation", "modify", "--stdin"],
        request_text=json.dumps(payload),
        services=services,
    )
    assert code == 2
    expected_error_class = {
        ForgePathError: "request.path",
        ForgeSchemaError: "request.schema",
        ForgeRequestError: "request.invalid",
    }[error_type]
    assert json.loads(output)["error"]["class"] == expected_error_class
    assert diagnostics == ""
    assert services.calls == []


@pytest.mark.parametrize("capability", ["relax", "cell-relax"])
def test_machine_default_services_dispatch_relax_execute(capability: str, tmp_path: Path) -> None:
    payload = {
        "schema_version": "forge.request/v1",
        "operation": "execute",
        "operation_id": OPERATION_ID,
        "workspace_rel": capability,
        "capability": capability,
        "dry_run": True,
    }
    code, output, diagnostics = _invoke(
        ["operation", "execute", "--stdin"],
        request_text=json.dumps(payload),
        cwd=tmp_path,
    )
    assert code == 0
    assert json.loads(output)["envelope"]["status"]["execution"] == "skipped"
    assert json.loads(output)["envelope"]["diagnostics"]["task"] == capability
    assert diagnostics == ""
