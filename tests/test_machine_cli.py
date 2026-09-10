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
    AtstNebPrepareRequest,
    AtstNebExecuteRequest,
    AtstNebPostprocessRequest,
)
from abacus_forge.pyatb_contracts import (
    PyatbBandCollectRequest,
    PyatbBandExecuteRequest,
    PyatbBandPrepareRequest,
)
from abacus_forge import BandPostprocessRequest, DosPostprocessRequest
from abacus_forge.discovery import capabilities_document, request_schema_document
from abacus_forge.machine_cli import decode_atst_neb_request, decode_scf_request, exit_code_for, run_machine_cli
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


class _AllRecordingPostprocessServices:
    def __init__(self, results: dict[str, object]) -> None:
        self.results = results
        self.calls: list[tuple[str, object]] = []
        self.postprocess = _RecordingOperationService(self, "postprocess")


def _atst_payload(operation: str, operation_id: str = OPERATION_ID) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "forge.request/v1",
        "capability": "atst-neb",
        "operation": operation,
        "operation_id": operation_id,
        "workspace_rel": ".",
    }
    if operation == "prepare":
        payload.update({"init_structure_path_rel": "init.stru", "final_structure_path_rel": "final.stru"})
    elif operation == "execute":
        payload["config_path_rel"] = "workflow.yaml"
    elif operation == "postprocess":
        payload["trajectory_path_rel"] = "neb.traj"
    return payload


class _AllRecordingAtstServices:
    def __init__(self, result: object) -> None:
        self.calls: list[tuple[str, object]] = []
        self.results = {name: result for name in ("prepare", "execute", "postprocess")}
        self.prepare = _RecordingOperationService(self, "prepare")
        self.execute = _RecordingOperationService(self, "execute")
        self.postprocess = _RecordingOperationService(self, "postprocess")


def _invoke(
    argv: list[str],
    *,
    request_text: str = "",
    services: object | None = None,
    atst_services: object | None = None,
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
        atst_services=atst_services,  # type: ignore[arg-type]
    )
    return code, stdout.getvalue(), stderr.getvalue()


def test_discovery_documents_are_json_safe_and_deterministic() -> None:
    capabilities = capabilities_document()
    schema = request_schema_document("scf", "execute")
    assert json.dumps(capabilities, allow_nan=False, sort_keys=True)
    assert json.dumps(schema, allow_nan=False, sort_keys=True)
    assert capabilities == capabilities_document()
    assert schema == request_schema_document("scf", "execute")


def test_discovery_advertises_all_experimental_capabilities() -> None:
    descriptors = capabilities_document()["capabilities"]
    assert [descriptor["name"] for descriptor in descriptors] == [
        "scf", "relax", "cell-relax", "atst-neb", "md", "band", "dos", "pyatb-band", "export",
    ]
    for descriptor in descriptors[:3]:
        assert descriptor["maturity"] == "experimental"
        assert descriptor["engine"] == "abacus"
        assert descriptor["operations"] == ["prepare", "modify", "execute", "collect"]
        assert descriptor["artifact_roles"] == ["input", "provenance_manifest", "output"]
    assert descriptors[3]["maturity"] == "experimental"
    assert descriptors[3]["engine"] == "atst-tools"
    assert descriptors[3]["operations"] == ["prepare", "execute", "postprocess"]
    assert descriptors[3]["artifact_roles"] == ["input", "output"]
    assert descriptors[4]["maturity"] == "experimental"
    assert descriptors[4]["engine"] == "abacus"
    assert descriptors[4]["operations"] == ["prepare", "modify", "execute", "collect", "postprocess"]
    assert descriptors[4]["artifact_roles"] == ["input", "provenance_manifest", "output"]
    assert descriptors[5:-1] == [
        {
            "schema_version": "forge.capability/v1",
            "name": "band",
            "maturity": "experimental",
            "engine": "abacus",
            "operations": ["postprocess"],
            "inputs": {"postprocess": ["band_files"]},
            "artifact_roles": ["input", "output"],
            "optional_dependencies": [],
        },
        {
            "schema_version": "forge.capability/v1",
            "name": "dos",
            "maturity": "experimental",
            "engine": "abacus",
            "operations": ["postprocess"],
            "inputs": {"postprocess": ["dos_files", "pdos", "tdos"]},
            "artifact_roles": ["input", "output"],
            "optional_dependencies": [],
        },
        {
            "schema_version": "forge.capability/v1",
            "name": "pyatb-band",
            "maturity": "experimental",
            "engine": "pyatb",
            "operations": ["prepare", "execute", "collect"],
            "inputs": {
                "prepare": ["structure", "hr", "sr", "rr", "fermi_energy", "line_kpoints"],
                "execute": ["prepared_workspace"],
                "collect": ["workspace_outputs"],
            },
            "artifact_roles": ["input", "provenance_manifest", "output"],
            "optional_dependencies": ["pyatb"],
        },
    ]
    assert descriptors[-1] == {
        "schema_version": "forge.capability/v1",
        "name": "export",
        "maturity": "experimental",
        "engine": "forge",
        "operations": ["export"],
        "inputs": {"export": ["source_artifact_refs"]},
        "artifact_roles": ["output"],
        "optional_dependencies": [],
    }


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
    [("unknown", "execute"), ("relax", "postprocess"), ("pyatb", "prepare")],
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


@pytest.mark.parametrize(
    ("capability", "request_type", "payload_extra"),
    [
        ("band", BandPostprocessRequest, {"source_paths_rel": ["BANDS_1.dat"]}),
        ("dos", DosPostprocessRequest, {"dos_paths_rel": ["DOS1_smearing.dat"]}),
    ],
)
def test_decode_operation_request_routes_explicit_postprocess_capabilities(
    capability: str, request_type: type[object], payload_extra: dict[str, object]
) -> None:
    payload = {
        "schema_version": "forge.request/v1",
        "capability": capability,
        "operation": "postprocess",
        "operation_id": OPERATION_ID,
        "workspace_rel": ".",
        **payload_extra,
    }
    request = _decode_operation_request("postprocess", payload)
    assert isinstance(request, request_type)
    assert request.to_dict() == payload | {
        "output_dir_rel": "outputs",
        "plot_emin": -10.0,
        "plot_emax": 10.0,
        "save_data": True,
        "save_plot": True,
        **(
            {
                "pdos_path_rel": None,
                "tdos_path_rel": None,
                "include_tdos": True,
                "include_pdos": True,
                "pdos_mode": "species",
                "pdos_atom_indices": [],
                "suffix": None,
            }
            if capability == "dos"
            else {}
        ),
    }


def test_machine_dispatches_explicit_postprocess_to_injected_service() -> None:
    for capability, request_type, extra in (
        ("band", BandPostprocessRequest, {"source_paths_rel": ["BANDS_1.dat"]}),
        ("dos", DosPostprocessRequest, {"dos_paths_rel": ["DOS1_smearing.dat"]}),
    ):
        result = _outcome_for("postprocess", OPERATION_ID)
        services = _AllRecordingPostprocessServices({"postprocess": result})
        payload = {
            "schema_version": "forge.request/v1",
            "capability": capability,
            "operation": "postprocess",
            "operation_id": OPERATION_ID,
            "workspace_rel": ".",
            **extra,
        }
        code, output, diagnostics = _invoke(
            ["operation", "postprocess", "--stdin"],
            request_text=json.dumps(payload),
            services=services,
        )
        assert code == 0
        assert diagnostics == ""
        assert json.loads(output) == result.to_dict()
        assert len(services.calls) == 1
        assert isinstance(services.calls[0][1], request_type)


def test_machine_rejects_postprocess_without_capability_or_with_unsupported_operation_before_service() -> None:
    services = _AllRecordingPostprocessServices({"postprocess": _outcome_for("postprocess", OPERATION_ID)})
    capabilityless = {
        "schema_version": "forge.request/v1",
        "operation": "postprocess",
        "operation_id": OPERATION_ID,
        "workspace_rel": ".",
        "source_paths_rel": ["BANDS_1.dat"],
    }
    code, output, _ = _invoke(
        ["operation", "postprocess", "--stdin"],
        request_text=json.dumps(capabilityless),
        services=services,
    )
    assert code == 2
    assert json.loads(output)["error"]["class"] == "request.invalid"
    unsupported = {
        "schema_version": "forge.request/v1",
        "operation": "export",
        "operation_id": OPERATION_ID,
        "workspace_rel": ".",
        "source_artifact_refs": [{"operation_id": OPERATION_ID, "artifact_id": "artifact"}],
        "destination_path_rel": "exports/result.json",
    }
    code, output, _ = _invoke(
        ["operation", "export", "--stdin"],
        request_text=json.dumps(unsupported),
        services=services,
    )
    assert code == 2
    assert json.loads(output)["error"]["class"] == "request.invalid"
    assert services.calls == []
@pytest.mark.parametrize(
    ("operation", "request_type"),
    [("prepare", AtstNebPrepareRequest), ("execute", AtstNebExecuteRequest), ("postprocess", AtstNebPostprocessRequest)],
)
def test_machine_routes_atst_neb_capability_to_injected_typed_service(
    operation: str, request_type: type[object]
) -> None:
    services = _AllRecordingAtstServices(_outcome_for(operation, OPERATION_ID))
    code, output, diagnostics = _invoke(
        ["operation", operation, "--stdin"], request_text=json.dumps(_atst_payload(operation)), atst_services=services
    )
    # The test helper passes ATST services through the dedicated injection point.
    assert code == 0
    assert diagnostics == ""
    assert services.calls[0][0] == operation
    assert isinstance(services.calls[0][1], request_type)
    assert json.loads(output)["envelope"]["operation"] == operation


def test_machine_rejects_unknown_capability_and_capabilityless_postprocess() -> None:
    unknown = {**_atst_payload("prepare"), "capability": "unknown"}
    code, output, _ = _invoke(["operation", "prepare", "--stdin"], request_text=json.dumps(unknown))
    assert code == 2
    assert json.loads(output)["error"]["class"] == "request.invalid"
    code, output, _ = _invoke(
        ["operation", "postprocess", "--stdin"], request_text=json.dumps(_request())
    )
    assert code == 2
    assert json.loads(output)["error"]["class"] == "request.invalid"


def test_decode_atst_neb_request_requires_explicit_capability() -> None:
    with pytest.raises(ForgeRequestError):
        decode_atst_neb_request("prepare", _atst_payload("prepare", OPERATION_ID) | {"capability": "scf"})


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
        ({"capability": "unknown"}, ForgeRequestError),
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


def _pyatb_prepare_payload() -> dict[str, object]:
    return {
        "schema_version": "forge.request/v1",
        "capability": "pyatb-band",
        "operation": "prepare",
        "operation_id": OPERATION_ID,
        "workspace_rel": "job",
        "structure_path_rel": "inputs/STRU",
        "hr_paths_rel": ["inputs/HR.dat"],
        "sr_path_rel": "inputs/SR.dat",
        "rr_path_rel": "inputs/rR.dat",
        "fermi_energy": 1.25,
        "line_kpoints": [
            {"coords": [0, 0, 0], "label": "G"},
            {"coords": [0.5, 0, 0], "label": "X"},
        ],
    }


@pytest.mark.parametrize(
    ("operation", "request_type", "payload"),
    [
        ("prepare", PyatbBandPrepareRequest, _pyatb_prepare_payload()),
        (
            "execute",
            PyatbBandExecuteRequest,
            {
                "schema_version": "forge.request/v1",
                "capability": "pyatb-band",
                "operation": "execute",
                "operation_id": OPERATION_ID,
                "workspace_rel": "job",
            },
        ),
        (
            "collect",
            PyatbBandCollectRequest,
            {
                "schema_version": "forge.request/v1",
                "capability": "pyatb-band",
                "operation": "collect",
                "operation_id": OPERATION_ID,
                "workspace_rel": "job",
            },
        ),
    ],
)
def test_decode_operation_request_routes_typed_pyatb_band_requests(
    operation: str, request_type: type[object], payload: dict[str, object]
) -> None:
    request = _decode_operation_request(operation, payload)
    assert isinstance(request, request_type)
    assert request.to_dict()["capability"] == "pyatb-band"  # type: ignore[union-attr]


def test_machine_pyatb_band_unknown_selectors_are_invalid_without_service() -> None:
    payload = _pyatb_prepare_payload()
    with pytest.raises(ForgeRequestError):
        _decode_operation_request("prepare", {**payload, "capability": "pyatb"})
    with pytest.raises(ForgeRequestError):
        _decode_operation_request("modify", payload)


def test_pyatb_band_discovery_descriptor_and_schemas_match_wire_fields() -> None:
    descriptors = capabilities_document()["capabilities"]
    descriptor = next(item for item in descriptors if item["name"] == "pyatb-band")
    assert descriptor["maturity"] == "experimental"
    assert descriptor["engine"] == "pyatb"
    assert descriptor["operations"] == ["prepare", "execute", "collect"]
    assert descriptor["artifact_roles"] == ["input", "provenance_manifest", "output"]
    for operation, request_type, payload in (
        ("prepare", PyatbBandPrepareRequest, _pyatb_prepare_payload()),
        ("execute", PyatbBandExecuteRequest, {"operation_id": OPERATION_ID, "workspace_rel": "job"}),
        ("collect", PyatbBandCollectRequest, {"operation_id": OPERATION_ID, "workspace_rel": "job"}),
    ):
        request_values = {key: value for key, value in payload.items() if key not in {"schema_version", "capability", "operation"}}
        request = request_type(**request_values)
        schema = request_schema_document("pyatb-band", operation)["request_schema"]
        assert schema["additionalProperties"] is False
        assert set(schema["properties"]) == set(request.to_dict())
        assert set(schema["required"]) == (
            {"schema_version", "capability", "operation", "operation_id", "workspace_rel"}
            | ({"structure_path_rel", "hr_paths_rel", "sr_path_rel", "rr_path_rel", "fermi_energy", "line_kpoints"} if operation == "prepare" else set())
        )
        assert schema["properties"]["schema_version"]["const"] == "forge.request/v1"


def test_machine_process_pyatb_schema_and_capability_discovery_are_single_documents() -> None:
    for argv in (("capabilities",), ("schema", "pyatb-band", "prepare"), ("schema", "pyatb-band", "collect")):
        code, output, diagnostics = _invoke(list(argv))
        assert code == 0
        assert diagnostics == ""
        assert isinstance(json.loads(output), dict)


@pytest.mark.parametrize(
    ("operation", "request_type", "payload"),
    [
        ("prepare", PyatbBandPrepareRequest, _pyatb_prepare_payload()),
        (
            "execute",
            PyatbBandExecuteRequest,
            {
                "schema_version": "forge.request/v1",
                "capability": "pyatb-band",
                "operation": "execute",
                "operation_id": OPERATION_ID,
                "workspace_rel": "job",
            },
        ),
        (
            "collect",
            PyatbBandCollectRequest,
            {
                "schema_version": "forge.request/v1",
                "capability": "pyatb-band",
                "operation": "collect",
                "operation_id": OPERATION_ID,
                "workspace_rel": "job",
            },
        ),
    ],
)
def test_machine_dispatches_typed_pyatb_band_to_injected_operation_service(
    operation: str, request_type: type[object], payload: dict[str, object]
) -> None:
    result = _outcome_for(operation, OPERATION_ID)
    services = _AllRecordingServices({operation: result})
    code, output, diagnostics = _invoke(
        ["operation", operation, "--stdin"],
        request_text=json.dumps(payload),
        services=services,
    )
    assert code == 0
    assert diagnostics == ""
    assert json.loads(output) == result.to_dict()
    assert len(services.calls) == 1
    assert isinstance(services.calls[0][1], request_type)
