from __future__ import annotations

import io
import json
from pathlib import Path

from abacus_forge.contracts import ArtifactRecord, ArtifactRef, ForgeResultEnvelope, OperationOutcome, OperationStatus
from abacus_forge.export_services import ExportServiceSet
from abacus_forge.machine_cli import run_machine_cli
from abacus_forge.workspace import Workspace
from tests.support.process import run_cli


SOURCE_ID = "123e4567-e89b-42d3-a456-426614174111"
EXPORT_ID = "123e4567-e89b-42d3-a456-426614174112"


def _source(workspace: Workspace) -> OperationOutcome:
    outcome = OperationOutcome(
        operation_id=SOURCE_ID,
        envelope=ForgeResultEnvelope(
            operation="collect",
            workspace_rel=".",
            status=OperationStatus(execution="completed", scientific="unassessed", collection="complete"),
            artifacts=(ArtifactRecord(id="energy", path_rel="outputs/energy.dat", role="output", stage="collect"),),
            diagnostics={"fact": "source"},
        ),
    )
    workspace.ensure_layout()
    workspace.append_v1_operation_event(SOURCE_ID, "collect", outcome.to_dict())
    return outcome


def _request() -> dict[str, object]:
    return {
        "schema_version": "forge.request/v1",
        "capability": "export",
        "operation": "export",
        "operation_id": EXPORT_ID,
        "workspace_rel": ".",
        "source_artifact_refs": [{"operation_id": SOURCE_ID, "artifact_id": "energy"}],
        "destination_path_rel": "exports/result.json",
        "format": "json",
        "pretty": False,
        "overwrite_policy": "fail",
    }


class _RecordingExport:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[object] = []

    def export(self, request: object) -> object:
        self.calls.append(request)
        return self.result


class _RecordingExportServices:
    def __init__(self, result: object) -> None:
        self.export = _RecordingExport(result)


def test_machine_cli_routes_explicit_export_to_injected_service() -> None:
    result = OperationOutcome(
        operation_id=EXPORT_ID,
        envelope=ForgeResultEnvelope(
            operation="export",
            workspace_rel=".",
            status=OperationStatus(execution="completed", scientific="unassessed", collection="complete"),
        ),
    )
    services = _RecordingExportServices(result)
    stdout = io.StringIO()
    stderr = io.StringIO()

    code = run_machine_cli(
        ["operation", "export", "--stdin"],
        stdin=io.StringIO(json.dumps(_request())),
        stdout=stdout,
        stderr=stderr,
        cwd=Path("/tmp/forge-export-route"),
        export_services=services,  # type: ignore[arg-type]
    )

    assert code == 0
    assert stderr.getvalue() == ""
    assert json.loads(stdout.getvalue()) == result.to_dict()
    assert len(services.export.calls) == 1


def test_machine_cli_process_stdin_and_request_file_have_same_typed_export_result(tmp_path: Path) -> None:
    stdin_root = tmp_path / "stdin"
    file_root = tmp_path / "request-file"
    direct_root = tmp_path / "direct"
    source_outcome = _source(Workspace(stdin_root))
    _source(Workspace(file_root))
    _source(Workspace(direct_root))

    request = _request()
    direct = ExportServiceSet.default(workspace_root=direct_root).export.export(
        __import__("abacus_forge").ExportRequest.from_dict(request)
    )
    assert isinstance(direct, OperationOutcome)
    stdin_result = run_cli(
        "operation", "export", "--stdin", cwd=stdin_root, input_text=json.dumps(request)
    )
    request_file = file_root / "request.json"
    request_file.write_text(json.dumps(request), encoding="utf-8")
    file_result = run_cli(
        "operation", "export", "--request", request_file, cwd=file_root
    )

    assert stdin_result.returncode == 0
    assert file_result.returncode == 0
    assert stdin_result.stderr == ""
    assert file_result.stderr == ""
    assert json.loads(stdin_result.stdout) == direct.to_dict()
    assert json.loads(file_result.stdout) == direct.to_dict()
    assert json.loads((stdin_root / "exports/result.json").read_text(encoding="utf-8")) == {
        "schema_version": "forge.export/v1",
        "source_operation_id": SOURCE_ID,
        "source_artifact_refs": [{"operation_id": SOURCE_ID, "artifact_id": "energy"}],
        "source_outcome": source_outcome.to_dict(),
    }


def test_capabilityless_machine_export_still_rejects_before_service(tmp_path: Path) -> None:
    request = _request()
    request.pop("capability")
    result = run_cli(
        "operation", "export", "--stdin", cwd=tmp_path, input_text=json.dumps(request)
    )

    assert result.returncode == 2
    assert result.stderr == ""
    assert json.loads(result.stdout)["error"]["class"] == "request.invalid"
