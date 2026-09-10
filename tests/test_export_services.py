from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from abacus_forge import ExportRequest
from abacus_forge.contracts import (
    ArtifactRecord,
    ArtifactRef,
    ForgeErrorEnvelope,
    ForgeResultEnvelope,
    OperationOutcome,
    OperationStatus,
)
from abacus_forge.errors import ForgePersistenceError
from abacus_forge.export_services import ExportServiceSet
from abacus_forge.workspace import Workspace


SOURCE_ID = "123e4567-e89b-42d3-a456-426614174101"
EXPORT_ID = "123e4567-e89b-42d3-a456-426614174102"
OTHER_EXPORT_ID = "123e4567-e89b-42d3-a456-426614174103"


def _source_outcome(*, operation_id: str = SOURCE_ID, path_rel: str = "outputs/energy.dat") -> OperationOutcome:
    envelope = ForgeResultEnvelope(
        operation="collect",
        workspace_rel=".",
        status=OperationStatus(
            execution="completed",
            scientific="unassessed",
            collection="complete",
        ),
        artifacts=(
            ArtifactRecord(
                id="energy",
                path_rel=path_rel,
                role="output",
                stage="collect",
                media_type="text/plain",
                sha256="a" * 64,
                size_bytes=4,
            ),
        ),
        diagnostics={"source_fact": "preserved"},
    )
    return OperationOutcome(operation_id=operation_id, envelope=envelope)


def _request(
    *,
    operation_id: str = EXPORT_ID,
    source_operation_id: str = SOURCE_ID,
    destination_path_rel: str = "exports/result.json",
) -> ExportRequest:
    return ExportRequest(
        operation_id=operation_id,
        workspace_rel=".",
        source_artifact_refs=(ArtifactRef(source_operation_id, "energy"),),
        destination_path_rel=destination_path_rel,
    )


def _write_source(workspace: Workspace, *, outcome: OperationOutcome | None = None) -> Path:
    outcome = outcome or _source_outcome()
    workspace.ensure_layout()
    return workspace.append_v1_operation_event(
        outcome.operation_id,
        outcome.envelope.operation,
        outcome.to_dict(),
    )


def _export_events(workspace: Workspace) -> list[dict[str, object]]:
    manifest = json.loads((workspace.root / "reports/forge-workspace.json").read_text(encoding="utf-8"))
    return [event for event in manifest["events"] if event["operation"] == "export"]


def test_export_service_writes_exact_document_and_one_audited_output(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path)
    source = _source_outcome()
    source_event = _write_source(workspace, outcome=source)
    source_bytes = source_event.read_bytes()

    result = ExportServiceSet.default(workspace_root=tmp_path).export.export(_request())

    assert isinstance(result, OperationOutcome)
    destination = workspace.root / "exports/result.json"
    document = json.loads(destination.read_text(encoding="utf-8"))
    assert document == {
        "schema_version": "forge.export/v1",
        "source_operation_id": SOURCE_ID,
        "source_artifact_refs": [{"operation_id": SOURCE_ID, "artifact_id": "energy"}],
        "source_outcome": source.to_dict(),
    }
    assert source_event.read_bytes() == source_bytes
    assert result.envelope.operation == "export"
    assert result.status.execution == "completed"
    assert result.status.collection == "complete"
    assert result.status.scientific == "unassessed"
    assert len(result.envelope.artifacts) == 1
    artifact = result.envelope.artifacts[0]
    assert artifact.path_rel == "exports/result.json"
    assert artifact.role == "output"
    assert artifact.stage == "export"
    assert artifact.media_type == "application/json"
    assert artifact.sha256 == hashlib.sha256(destination.read_bytes()).hexdigest()
    assert artifact.size_bytes == destination.stat().st_size
    assert result.envelope.to_dict()["diagnostics"] == {
        "artifact_refs": [{"operation_id": EXPORT_ID, "artifact_id": artifact.id}],
        "source_artifact_refs": [{"operation_id": SOURCE_ID, "artifact_id": "energy"}],
        "source_operation_id": SOURCE_ID,
        "destination_path_rel": "exports/result.json",
        "format": "json",
        "overwrite_policy": "fail",
    }
    assert len(_export_events(workspace)) == 1


def test_export_service_rejects_wrong_type_without_admission(tmp_path: Path) -> None:
    service = ExportServiceSet.default(workspace_root=tmp_path).export

    result = service.export(object())  # type: ignore[arg-type]

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.invalid"
    assert not (tmp_path / "reports/claims").exists()


@pytest.mark.parametrize(
    ("destination", "error_class"),
    [
        ("reports/events/new.json", "request.path"),
        ("reports/claims/new.json", "request.path"),
        ("../outside.json", "request.schema"),
    ],
)
def test_export_service_rejects_invalid_destination_before_admission(
    tmp_path: Path, destination: str, error_class: str
) -> None:
    # The traversal case cannot be represented by ExportRequest because the
    # public contract rejects it.  Exercise that boundary directly below.
    if destination == "../outside.json":
        with pytest.raises(ValueError):
            _request(destination_path_rel=destination)
        return

    service = ExportServiceSet.default(workspace_root=tmp_path).export
    result = service.export(_request(destination_path_rel=destination))

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == error_class
    assert not (tmp_path / "reports/claims" / f"{EXPORT_ID}.json").exists()


def test_export_service_existing_destination_is_invalid_without_admission(tmp_path: Path) -> None:
    destination = tmp_path / "exports/result.json"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"keep")

    result = ExportServiceSet.default(workspace_root=tmp_path).export.export(_request())

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.invalid"
    assert destination.read_bytes() == b"keep"
    assert not (tmp_path / "reports/claims" / f"{EXPORT_ID}.json").exists()


def test_export_service_source_overlap_is_request_invalid_after_admission(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path)
    _write_source(workspace)

    result = ExportServiceSet.default(workspace_root=tmp_path).export.export(
        _request(destination_path_rel="outputs/energy.dat")
    )

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.invalid"
    claim = tmp_path / "reports/claims" / f"{EXPORT_ID}.json"
    assert claim.is_file()


def test_export_service_missing_source_is_precondition_after_admission(tmp_path: Path) -> None:
    result = ExportServiceSet.default(workspace_root=tmp_path).export.export(_request())

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "precondition.missing"
    assert (tmp_path / "reports/claims" / f"{EXPORT_ID}.json").is_file()
    assert not (tmp_path / "exports/result.json").exists()


def test_export_service_duplicate_operation_id_is_conflict(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path)
    _write_source(workspace)
    services = ExportServiceSet.default(workspace_root=tmp_path)

    first = services.export.export(_request())
    second = services.export.export(_request())

    assert isinstance(first, OperationOutcome)
    assert isinstance(second, ForgeErrorEnvelope)
    assert second.error_class == "operation.conflict"
    assert len(_export_events(workspace)) == 1


def test_export_service_uses_unique_artifact_id_when_source_already_uses_base_id(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path)
    source = _source_outcome()
    # The source event is an independent operation and deliberately contains
    # the conventional export artifact ID.
    source = OperationOutcome(
        operation_id=source.operation_id,
        envelope=ForgeResultEnvelope(
            operation="collect",
            workspace_rel=".",
            status=source.status,
            artifacts=(ArtifactRecord(id="export-document", path_rel="outputs/other.json", role="output", stage="collect"),),
        ),
    )
    _write_source(workspace, outcome=source)
    request = ExportRequest(
        operation_id=EXPORT_ID,
        workspace_rel=".",
        source_artifact_refs=(ArtifactRef(SOURCE_ID, "export-document"),),
        destination_path_rel="exports/result.json",
    )

    result = ExportServiceSet.default(workspace_root=tmp_path).export.export(request)

    assert isinstance(result, OperationOutcome)
    assert result.envelope.artifacts[0].id != "export-document"


def test_export_service_write_failure_has_no_fabricated_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = Workspace(tmp_path)
    _write_source(workspace)

    def fail(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise ForgePersistenceError("simulated writer failure")

    monkeypatch.setattr("abacus_forge.export_services.write_export_document", fail)
    result = ExportServiceSet.default(workspace_root=tmp_path).export.export(_request())

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "persistence.failure"
    assert not (tmp_path / "exports/result.json").exists()
    assert _export_events(workspace) == []


def test_export_service_persist_failure_does_not_return_artifact_or_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = Workspace(tmp_path)
    _write_source(workspace)
    services = ExportServiceSet.default(workspace_root=tmp_path)

    def fail(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise ForgePersistenceError("simulated event failure")

    monkeypatch.setattr(services.export._context, "persist", fail)
    result = services.export.export(_request())

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "persistence.failure"
    assert (tmp_path / "exports/result.json").is_file()
    assert _export_events(workspace) == []
    assert not hasattr(result, "envelope")


def test_export_service_does_not_call_legacy_runtime_operations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = Workspace(tmp_path)
    _write_source(workspace)
    called: list[str] = []

    monkeypatch.setattr("abacus_forge.export_services.collect", lambda *args: called.append("collect"), raising=False)
    monkeypatch.setattr("abacus_forge.export_services.postprocess", lambda *args: called.append("postprocess"), raising=False)
    monkeypatch.setattr("abacus_forge.export_services.LocalRunner", lambda *args, **kwargs: called.append("runner"), raising=False)

    result = ExportServiceSet.default(workspace_root=tmp_path).export.export(_request())

    assert isinstance(result, OperationOutcome)
    assert called == []
