from __future__ import annotations

import json
import fcntl
import multiprocessing
import threading
import time
import uuid
from pathlib import Path

import pytest

from abacus_forge.errors import OperationConflictError, ForgePersistenceError
from abacus_forge.workspace import Workspace


def _append_events(root: str, count: int, operation: str) -> None:
    workspace = Workspace(Path(root))
    for index in range(count):
        workspace.append_operation_event(operation, {"index": index})


def _hold_manifest_lock(root: str, ready: multiprocessing.Event, release: multiprocessing.Event) -> None:
    workspace = Workspace(Path(root))
    with workspace._manifest_lock():
        ready.set()
        release.wait(timeout=10)


def _ensure_manifest(root: str) -> None:
    Workspace(Path(root)).ensure_manifest()


def test_workspace_rejects_escape_paths(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "safe")
    with pytest.raises(ValueError, match="workspace root"):
        workspace.write_json("../outside.json", {"value": 1})
    assert not (tmp_path / "outside.json").exists()


@pytest.mark.parametrize("path", ["", ".", "./x.json", "a/../x.json", "/tmp/x.json"])
def test_workspace_rejects_noncanonical_owned_write_paths(tmp_path: Path, path: str) -> None:
    workspace = Workspace(tmp_path / "safe")
    with pytest.raises(ValueError):
        workspace.write_json(path, {"value": 1})


def test_workspace_rejects_absolute_path_inside_root_and_preserves_legacy_json_bytes(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "safe")
    absolute = workspace.root / "inside.json"
    with pytest.raises(ValueError):
        workspace.write_json(absolute, {"value": 1})
    workspace.write_json("legacy.json", {"b": 2, "a": 1})
    assert (workspace.root / "legacy.json").read_bytes() == b'{\n  "a": 1,\n  "b": 2\n}'


def test_workspace_reconciles_event_left_by_manifest_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = Workspace(tmp_path / "recovery")
    original = Workspace._write_json_atomic
    calls = 0

    def fail_manifest(path: Path, payload: dict) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("simulated manifest failure")
        original(path, payload)

    monkeypatch.setattr(Workspace, "_write_json_atomic", staticmethod(fail_manifest))
    with pytest.raises(OSError, match="simulated"):
        workspace.append_operation_event("prepare", {"status": "prepared"})
    events = list((workspace.root / "reports" / "events").glob("*.json"))
    assert len(events) == 1
    monkeypatch.setattr(Workspace, "_write_json_atomic", staticmethod(original))
    workspace.ensure_manifest()
    manifest = json.loads((workspace.reports_dir / "forge-workspace.json").read_text())
    assert len(manifest["events"]) == 1
    assert manifest["events"][0]["path_rel"] == events[0].relative_to(workspace.root).as_posix()


def test_workspace_reconciles_events_through_a_symlink_root(tmp_path: Path) -> None:
    real_root = tmp_path / "workspace"
    real_workspace = Workspace(real_root)
    event_path = real_workspace.append_operation_event("prepare", {"status": "prepared"})
    manifest_path = real_workspace.ensure_manifest()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["events"] = []
    real_workspace.write_json("reports/forge-workspace.json", manifest)

    alias_root = tmp_path / "workspace-alias"
    alias_root.symlink_to(real_root, target_is_directory=True)
    Workspace(alias_root).ensure_manifest()

    reconciled = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert reconciled["events"] == [
        {
            "id": json.loads(event_path.read_text(encoding="utf-8"))["id"],
            "operation": "prepare",
            "path_rel": "reports/events/" + event_path.name,
        }
    ]


def test_workspace_events_are_append_only(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "events")
    first = workspace.append_operation_event("prepare", {"status": "prepared"})
    second = workspace.append_operation_event("collect", {"status": "completed"})
    manifest = json.loads((workspace.reports_dir / "forge-workspace.json").read_text(encoding="utf-8"))
    assert first != second
    assert [event["operation"] for event in manifest["events"]] == ["prepare", "collect"]
    assert all((workspace.root / event["path_rel"]).exists() for event in manifest["events"])


def test_v1_event_uses_request_operation_id(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "v1-event")
    operation_id = "123e4567-e89b-42d3-a456-426614174000"

    event_path = workspace.append_v1_operation_event(operation_id, "collect", {"status": "complete"})
    manifest = json.loads((workspace.reports_dir / "forge-workspace.json").read_text(encoding="utf-8"))

    assert manifest["events"][-1]["id"] == operation_id
    assert event_path.name == f"{operation_id}-collect.json"


def test_v1_event_rejects_duplicate_operation_id(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "duplicate-v1-event")
    operation_id = "123e4567-e89b-42d3-a456-426614174000"
    workspace.append_v1_operation_event(operation_id, "collect", {"status": "complete"})

    with pytest.raises(ValueError, match="operation_id"):
        workspace.append_v1_operation_event(operation_id, "collect", {"status": "complete"})


@pytest.mark.parametrize(
    "operation_id",
    [
        "123E4567-E89B-42D3-A456-426614174000",
        "c232dad3-7f13-11f0-8000-426614174000",
        "123e4567e89b42d3a456426614174000",
    ],
)
def test_v1_event_rejects_noncanonical_uuid4(tmp_path: Path, operation_id: str) -> None:
    workspace = Workspace(tmp_path / "invalid-v1-id")

    with pytest.raises(ValueError, match="operation_id"):
        workspace.append_v1_operation_event(operation_id, "collect", {"status": "complete"})


@pytest.mark.parametrize("operation", ["", "Collect", "collect-status", "collect/status", "collect\\status"])
def test_v1_event_rejects_unsafe_operation_tokens(tmp_path: Path, operation: str) -> None:
    workspace = Workspace(tmp_path / "invalid-v1-operation")

    with pytest.raises(ValueError, match="operation"):
        workspace.append_v1_operation_event(
            "123e4567-e89b-42d3-a456-426614174000", operation, {"status": "complete"}
        )


@pytest.mark.parametrize(
    "payload",
    [
        {1: "non-string key"},
        {"nested": {1: "non-string key"}},
        {"nested": ("tuple is not JSONValue",)},
        {"nested": float("nan")},
        {"nested": object()},
    ],
)
def test_v1_event_rejects_non_json_mapping_payload(tmp_path: Path, payload: dict) -> None:
    workspace = Workspace(tmp_path / "invalid-v1-payload")

    with pytest.raises(ValueError, match="payload"):
        workspace.append_v1_operation_event(
            "123e4567-e89b-42d3-a456-426614174000", "collect", payload
        )
    assert not (workspace.reports_dir / "events").exists()


def test_v1_event_reconciles_after_manifest_write_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = Workspace(tmp_path / "v1-recovery")
    original = Workspace._write_json_atomic
    calls = 0

    def fail_manifest(path: Path, payload: dict) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("simulated manifest failure")
        original(path, payload)

    monkeypatch.setattr(Workspace, "_write_json_atomic", staticmethod(fail_manifest))
    with pytest.raises(ForgePersistenceError, match="unable to persist workspace manifest"):
        workspace.append_v1_operation_event(
            "123e4567-e89b-42d3-a456-426614174000", "collect", {"status": "complete"}
        )
    events = list((workspace.root / "reports" / "events").glob("*.json"))
    assert len(events) == 1
    monkeypatch.setattr(Workspace, "_write_json_atomic", staticmethod(original))
    workspace.ensure_manifest()
    manifest = json.loads((workspace.reports_dir / "forge-workspace.json").read_text())
    assert manifest["events"][-1]["id"] == "123e4567-e89b-42d3-a456-426614174000"
    assert manifest["events"][-1]["path_rel"] == events[0].relative_to(workspace.root).as_posix()


def test_v1_event_file_failure_is_typed_and_leaves_no_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = Workspace(tmp_path / "v1-event-failure")
    original = Workspace._write_json_atomic

    def fail_event(path: Path, payload: dict) -> None:
        if path.parent.name == "events":
            raise OSError("simulated event failure")
        original(path, payload)

    monkeypatch.setattr(Workspace, "_write_json_atomic", staticmethod(fail_event))
    with pytest.raises(ForgePersistenceError, match="unable to persist operation event"):
        workspace.append_v1_operation_event(
            "123e4567-e89b-42d3-a456-426614174000", "collect", {"status": "complete"}
        )
    assert not list((workspace.reports_dir / "events").glob("*.json"))


def test_legacy_event_ids_remain_random_uuid4(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "legacy-event-id")
    first = workspace.append_operation_event("legacy-operation", {"status": "complete"})
    second = workspace.append_operation_event("legacy-operation", {"status": "complete"})

    first_id = json.loads(first.read_text(encoding="utf-8"))["id"]
    second_id = json.loads(second.read_text(encoding="utf-8"))["id"]
    assert first_id != second_id
    assert uuid.UUID(first_id).version == 4
    assert uuid.UUID(second_id).version == 4


def test_workspace_concurrent_events_preserve_all_manifest_references(tmp_path: Path) -> None:
    root = tmp_path / "concurrent"
    context = multiprocessing.get_context("fork")
    processes = [
        context.Process(target=_append_events, args=(str(root), 8, operation))
        for operation in ("prepare", "collect")
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0

    manifest = json.loads((root / "reports" / "forge-workspace.json").read_text(encoding="utf-8"))
    assert len(manifest["events"]) == 16
    assert {event["operation"] for event in manifest["events"]} == {"prepare", "collect"}


def test_public_manifest_initialization_waits_for_append_lock(tmp_path: Path) -> None:
    root = tmp_path / "ensure-lock"
    context = multiprocessing.get_context("fork")
    ready = context.Event()
    release = context.Event()
    holder = context.Process(target=_hold_manifest_lock, args=(str(root), ready, release))
    holder.start()
    assert ready.wait(timeout=10)

    ensure_process = context.Process(target=_ensure_manifest, args=(str(root),))
    ensure_process.start()
    ensure_process.join(timeout=0.2)
    assert ensure_process.is_alive()
    release.set()
    ensure_process.join(timeout=10)
    holder.join(timeout=10)
    assert ensure_process.exitcode == 0
    assert holder.exitcode == 0

    workspace = Workspace(root)
    workspace.append_operation_event("prepare", {"status": "prepared"})
    manifest = json.loads((root / "reports" / "forge-workspace.json").read_text(encoding="utf-8"))
    assert len(manifest["events"]) == 1


@pytest.mark.parametrize(
    ("lock_name", "message"),
    [
        ("_manifest_lock", "unable to release workspace manifest lock"),
        ("_operation_lock", "unable to release operation lock"),
    ],
)
def test_workspace_lock_unlock_failure_is_persistence_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lock_name: str, message: str
) -> None:
    workspace = Workspace(tmp_path / "unlock-failure")
    original_flock = fcntl.flock

    def fail_unlock(fd: int, operation: int) -> None:
        if operation == fcntl.LOCK_UN:
            raise OSError("injected unlock failure")
        original_flock(fd, operation)

    monkeypatch.setattr(fcntl, "flock", fail_unlock)
    with pytest.raises(ForgePersistenceError, match=message):
        with getattr(workspace, lock_name)():
            pass


def test_v1_admission_does_not_reclaim_dead_claim(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "stale-claim")
    workspace.ensure_layout()
    claims_dir = workspace.reports_dir / "claims"
    claims_dir.mkdir()
    operation_id = "123e4567-e89b-42d3-a456-426614174020"
    (claims_dir / f"{operation_id}.json").write_text(
        json.dumps({"operation_id": operation_id, "operation": "execute", "owner_token": "dead"}),
        encoding="utf-8",
    )

    with pytest.raises(OperationConflictError):
        with workspace.claim_v1_operation(operation_id, "execute"):
            pytest.fail("a stale admission must remain a conflict")

    assert (claims_dir / f"{operation_id}.json").exists()


def test_v1_event_commit_requires_opaque_owner_token(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "owner-token")
    operation_id = "123e4567-e89b-42d3-a456-426614174021"
    with workspace.claim_v1_operation(operation_id, "prepare") as owner_token:
        assert isinstance(owner_token, str)
        assert owner_token != operation_id
        with pytest.raises(OperationConflictError):
            workspace.append_claimed_v1_operation_event(
                operation_id, "prepare", {"status": "prepared"}, owner_token="wrong-token"
            )
        assert (workspace.reports_dir / "claims" / f"{operation_id}.json").exists()


def test_v1_admission_persistence_failure_retains_tombstone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = Workspace(tmp_path / "persist-failure")
    operation_id = "123e4567-e89b-42d3-a456-426614174022"
    original = Workspace._write_json_atomic

    def fail_manifest(path: Path, payload: dict) -> None:
        if path.name == "forge-workspace.json" and isinstance(payload.get("events"), list) and payload["events"]:
            raise OSError("injected manifest failure")
        original(path, payload)

    monkeypatch.setattr(Workspace, "_write_json_atomic", staticmethod(fail_manifest))
    with workspace.claim_v1_operation(operation_id, "prepare") as owner_token:
        with pytest.raises(ForgePersistenceError):
            workspace.append_claimed_v1_operation_event(
                operation_id, "prepare", {"status": "prepared"}, owner_token=owner_token
            )
    assert (workspace.reports_dir / "claims" / f"{operation_id}.json").exists()
