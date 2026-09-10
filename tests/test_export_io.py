from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from abacus_forge.contracts import (
    ArtifactRecord,
    ArtifactRef,
    ForgeResultEnvelope,
    OperationOutcome,
    OperationStatus,
)
from abacus_forge.errors import (
    ForgePathError,
    ForgePersistenceError,
    ForgePreconditionError,
    ForgeRequestError,
)
from abacus_forge.export_contracts import ExportDocument
from abacus_forge.export_io import (
    ResolvedExportSource,
    WrittenExportDocument,
    resolve_export_source,
    write_export_document,
)
from abacus_forge.workspace import Workspace


SOURCE_ID = "123e4567-e89b-42d3-a456-426614174001"
OTHER_SOURCE_ID = "123e4567-e89b-42d3-a456-426614174002"
EXPORT_ID = "123e4567-e89b-42d3-a456-426614174003"


def _outcome(
    operation_id: str = SOURCE_ID,
    *,
    artifacts: tuple[ArtifactRecord, ...] | None = None,
) -> OperationOutcome:
    if artifacts is None:
        artifacts = (
            ArtifactRecord(
                id="energy",
                path_rel="outputs/energy.dat",
                role="output",
                stage="collect",
                media_type="text/plain",
                sha256="a" * 64,
                size_bytes=4,
            ),
            ArtifactRecord(
                id="stdout",
                path_rel="outputs/stdout.log",
                role="output",
                stage="collect",
                media_type="text/plain",
                size_bytes=8,
            ),
        )
    envelope = ForgeResultEnvelope(
        operation="collect",
        workspace_rel=".",
        status=OperationStatus(
            execution="completed",
            scientific="unassessed",
            collection="complete",
        ),
        artifacts=artifacts,
        diagnostics={"fact": "preserved"},
    )
    return OperationOutcome(operation_id=operation_id, envelope=envelope)


def _refs(*artifact_ids: str, operation_id: str = SOURCE_ID) -> tuple[ArtifactRef, ...]:
    return tuple(ArtifactRef(operation_id, artifact_id) for artifact_id in artifact_ids)


def _source_event(workspace: Workspace, *, outcome: OperationOutcome | None = None) -> Path:
    outcome = outcome or _outcome()
    workspace.ensure_layout()
    return workspace.append_v1_operation_event(
        outcome.operation_id,
        outcome.envelope.operation,
        outcome.to_dict(),
    )


def _document(
    outcome: OperationOutcome | None = None,
    *,
    refs: tuple[ArtifactRef, ...] | None = None,
) -> ExportDocument:
    outcome = outcome or _outcome()
    refs = refs or _refs("energy", operation_id=outcome.operation_id)
    return ExportDocument(
        schema_version="forge.export/v1",
        source_operation_id=outcome.operation_id,
        source_artifact_refs=refs,
        source_outcome=outcome.to_dict(),
    )


def _manifest_with_event(workspace: Workspace, *, source_id: str, path_rel: str, operation: str = "collect") -> None:
    workspace.reports_dir.mkdir(parents=True, exist_ok=True)
    (workspace.reports_dir / "forge-workspace.json").write_text(
        json.dumps(
            {
                "schema_version": "forge.workspace/v1",
                "workspace_rel": ".",
                "events": [{"id": source_id, "operation": operation, "path_rel": path_rel}],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def test_resolve_export_source_uses_exact_manifest_event_and_validates_refs(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "workspace")
    outcome = _outcome()
    event_path = _source_event(workspace, outcome=outcome)

    resolved = resolve_export_source(workspace, _refs("energy"))

    assert isinstance(resolved, ResolvedExportSource)
    assert resolved.operation_id == SOURCE_ID
    assert resolved.artifact_refs == _refs("energy")
    assert resolved.outcome == outcome
    assert resolved.event_path_rel == event_path.relative_to(workspace.root.resolve()).as_posix()


@pytest.mark.parametrize(
    "setup",
    [
        "missing_event",
        "malformed_event",
        "missing_artifact",
        "mismatched_outcome_id",
        "mismatched_event_id",
        "duplicate_manifest_id",
    ],
)
def test_resolve_export_source_rejects_missing_or_inconsistent_history(
    tmp_path: Path, setup: str
) -> None:
    workspace = Workspace(tmp_path / setup)
    if setup == "missing_event":
        _manifest_with_event(workspace, source_id=SOURCE_ID, path_rel="reports/events/missing.json")
    elif setup == "malformed_event":
        event = workspace.root / "reports" / "events" / "source.json"
        event.parent.mkdir(parents=True)
        event.write_text("not json", encoding="utf-8")
        _manifest_with_event(
            workspace,
            source_id=SOURCE_ID,
            path_rel="reports/events/source.json",
        )
    elif setup == "missing_artifact":
        _source_event(workspace)
    elif setup == "mismatched_outcome_id":
        outcome = _outcome(operation_id=OTHER_SOURCE_ID)
        event = workspace.root / "reports" / "events" / f"{SOURCE_ID}-collect.json"
        event.parent.mkdir(parents=True)
        event.write_text(
            json.dumps({"id": SOURCE_ID, "operation": "collect", "payload": outcome.to_dict()}),
            encoding="utf-8",
        )
        _manifest_with_event(
            workspace,
            source_id=SOURCE_ID,
            path_rel=f"reports/events/{SOURCE_ID}-collect.json",
        )
    elif setup == "mismatched_event_id":
        event = workspace.root / "reports" / "events" / "event.json"
        event.parent.mkdir(parents=True)
        event.write_text(
            json.dumps({"id": OTHER_SOURCE_ID, "operation": "collect", "payload": _outcome().to_dict()}),
            encoding="utf-8",
        )
        _manifest_with_event(workspace, source_id=SOURCE_ID, path_rel="reports/events/event.json")
    else:
        event = _source_event(workspace)
        manifest = json.loads((workspace.reports_dir / "forge-workspace.json").read_text(encoding="utf-8"))
        manifest["events"].append(manifest["events"][0])
        (workspace.reports_dir / "forge-workspace.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

    refs = _refs("missing") if setup == "missing_artifact" else _refs("energy")
    with pytest.raises(ForgePreconditionError):
        resolve_export_source(workspace, refs)


def test_resolve_export_source_rejects_mixed_or_duplicate_refs(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "mixed")
    _source_event(workspace)

    with pytest.raises(ForgePreconditionError):
        resolve_export_source(workspace, _refs("energy", "energy"))
    with pytest.raises(ForgePreconditionError):
        resolve_export_source(
            workspace,
            _refs("energy") + (ArtifactRef(OTHER_SOURCE_ID, "energy"),),
        )


@pytest.mark.parametrize(
    "manifest_path",
    [
        "../outside.json",
        "/tmp/outside.json",
        "reports/events/../event.json",
        "reports/events//event.json",
        "reports\\events\\event.json",
    ],
)
def test_resolve_export_source_rejects_noncanonical_or_outside_event_mapping(
    tmp_path: Path, manifest_path: str
) -> None:
    workspace = Workspace(tmp_path / "path")
    _manifest_with_event(workspace, source_id=SOURCE_ID, path_rel=manifest_path)

    with pytest.raises(ForgePathError):
        resolve_export_source(workspace, _refs("energy"))


def test_resolve_export_source_rejects_malformed_manifest(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "bad-manifest")
    workspace.reports_dir.mkdir(parents=True)
    (workspace.reports_dir / "forge-workspace.json").write_text("{", encoding="utf-8")

    with pytest.raises(ForgePreconditionError):
        resolve_export_source(workspace, _refs("energy"))


def test_resolve_export_source_validates_recorded_artifact_path_without_reading_current_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = Workspace(tmp_path / "historical")
    source = workspace.root / "outputs" / "energy.dat"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"original")
    _source_event(workspace)

    original_read_bytes = Path.read_bytes

    def fail_if_source_is_read(path: Path) -> bytes:
        if path == source:
            raise AssertionError("source artifact bytes must not be read")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fail_if_source_is_read)
    source.unlink()

    resolved = resolve_export_source(workspace, _refs("energy"))

    assert resolved.outcome.envelope.artifacts[0].path_rel == "outputs/energy.dat"
    assert not source.exists()


def test_resolve_export_source_does_not_reinterpret_replaced_source_file(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "replaced")
    source = workspace.root / "outputs" / "energy.dat"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"original")
    _source_event(workspace)
    source.write_bytes(b"replacement")

    resolved = resolve_export_source(workspace, _refs("energy"))

    assert source.read_bytes() == b"replacement"
    assert resolved.outcome.envelope.artifacts[0].sha256 == "a" * 64


def test_write_export_document_creates_contained_parent_and_returns_digest(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "writer")
    document = _document()

    written = write_export_document(workspace, "exports/nested/result.json", document, pretty=False)

    assert isinstance(written, WrittenExportDocument)
    assert written.path == workspace.root / "exports/nested/result.json"
    assert written.path_rel == "exports/nested/result.json"
    assert written.path.is_file()
    assert written.size_bytes == written.path.stat().st_size
    assert written.sha256 == hashlib.sha256(written.path.read_bytes()).hexdigest()
    assert json.loads(written.path.read_text(encoding="utf-8")) == document.to_dict()


@pytest.mark.parametrize(
    "destination",
    ["", ".", "./result.json", "../result.json", "reports/../result.json", "/tmp/result.json", "result\\.json"],
)
def test_write_export_document_rejects_noncanonical_destination(tmp_path: Path, destination: str) -> None:
    workspace = Workspace(tmp_path / "destination-path")

    with pytest.raises(ForgePathError):
        write_export_document(workspace, destination, _document(), pretty=False)


@pytest.mark.parametrize(
    "destination",
    [
        "reports/forge-workspace.json",
        "reports/.forge-workspace.lock",
        "reports/.forge-operation.lock",
        "reports/events/source.json",
        "reports/claims/source.json",
        "forge-unit.json",
        "forge-result.json",
        "outputs/energy.dat",
    ],
)
def test_write_export_document_rejects_reserved_audit_paths(tmp_path: Path, destination: str) -> None:
    workspace = Workspace(tmp_path / "reserved")

    with pytest.raises(ForgePathError):
        write_export_document(workspace, destination, _document(), pretty=False)


def test_write_export_document_rejects_symlink_escape_without_creating_outside_file(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "symlink")
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace.root / "exports").mkdir(parents=True)
    (workspace.root / "exports" / "link").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ForgePathError):
        write_export_document(workspace, "exports/link/result.json", _document(), pretty=False)
    assert not (outside / "result.json").exists()


def test_write_export_document_rejects_existing_destination_without_replacing_bytes(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "existing")
    target = workspace.root / "exports" / "result.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"keep")

    with pytest.raises(ForgeRequestError):
        write_export_document(workspace, "exports/result.json", _document(), pretty=False)
    assert target.read_bytes() == b"keep"


def test_write_export_document_race_target_created_after_check_fails_without_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = Workspace(tmp_path / "race")
    target = workspace.root / "exports" / "result.json"
    original_link = os.link

    def create_target_then_link(source: str | os.PathLike[str], destination: str | os.PathLike[str], **kwargs: object) -> None:
        del kwargs
        Path(destination).write_bytes(b"raced")
        original_link(source, destination)

    monkeypatch.setattr("abacus_forge.export_io.os.link", create_target_then_link)
    with pytest.raises(ForgeRequestError):
        write_export_document(workspace, "exports/result.json", _document(), pretty=False)
    assert target.read_bytes() == b"raced"
    assert not list(target.parent.glob(".result.json.*.tmp"))


def test_write_export_document_compact_and_pretty_are_deterministic(tmp_path: Path) -> None:
    compact_workspace = Workspace(tmp_path / "compact")
    pretty_workspace = Workspace(tmp_path / "pretty")
    document = _document()

    compact = write_export_document(compact_workspace, "result.json", document, pretty=False)
    pretty = write_export_document(pretty_workspace, "result.json", document, pretty=True)

    compact_bytes = compact.path.read_bytes()
    pretty_bytes = pretty.path.read_bytes()
    assert compact_bytes == compact.path.read_bytes()
    assert pretty_bytes == pretty.path.read_bytes()
    assert compact_bytes != pretty_bytes
    assert compact_bytes == json.dumps(
        document.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    assert pretty_bytes == json.dumps(
        document.to_dict(), sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False
    ).encode("utf-8")


def test_write_export_document_cleans_temporary_file_after_success(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "cleanup")
    write_export_document(workspace, "result.json", _document(), pretty=False)

    assert not list(workspace.root.glob(".result.json.*.tmp"))


def test_write_export_document_cleans_temporary_file_after_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = Workspace(tmp_path / "write-failure")
    original_fsync = os.fsync

    def fail_fsync(fd: int) -> None:
        original_fsync(fd)
        raise OSError("simulated fsync failure")

    monkeypatch.setattr("abacus_forge.export_io.os.fsync", fail_fsync)
    with pytest.raises(ForgePersistenceError):
        write_export_document(workspace, "result.json", _document(), pretty=False)
    assert not (workspace.root / "result.json").exists()
    assert not list(workspace.root.glob(".result.json.*.tmp"))


def test_write_export_document_maps_stat_failure_to_persistence_and_does_not_return_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = Workspace(tmp_path / "stat-failure")
    original_stat = Path.stat
    target = workspace.root / "result.json"

    def fail_target_stat(path: Path, *args: object, **kwargs: object):
        if path == target:
            raise OSError("simulated stat failure")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", fail_target_stat)
    with pytest.raises(ForgePersistenceError):
        write_export_document(workspace, "result.json", _document(), pretty=False)
    monkeypatch.setattr(Path, "stat", original_stat)
    assert not target.exists()


def test_write_export_document_rejects_non_document_value(tmp_path: Path) -> None:
    with pytest.raises(ForgeRequestError):
        write_export_document(Workspace(tmp_path / "wrong-type"), "result.json", object(), pretty=False)  # type: ignore[arg-type]
