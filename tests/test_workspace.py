from __future__ import annotations

import json
import multiprocessing
from pathlib import Path

import pytest

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


def test_workspace_events_are_append_only(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "events")
    first = workspace.append_operation_event("prepare", {"status": "prepared"})
    second = workspace.append_operation_event("collect", {"status": "completed"})
    manifest = json.loads((workspace.reports_dir / "forge-workspace.json").read_text(encoding="utf-8"))
    assert first != second
    assert [event["operation"] for event in manifest["events"]] == ["prepare", "collect"]
    assert all((workspace.root / event["path_rel"]).exists() for event in manifest["events"])


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
