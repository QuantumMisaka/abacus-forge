from __future__ import annotations

import json
from pathlib import Path

import pytest

from abacus_forge.workspace import Workspace


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
