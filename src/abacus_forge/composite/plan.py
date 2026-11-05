"""File-backed unit handoff for local task packs; scheduling belongs to callers."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any, Callable, Iterable

from abacus_forge.api import collect
from abacus_forge.contracts import ArtifactRecord, ForgeResultEnvelope, OperationOutcome, OperationStatus, canonical_relative_path
from abacus_forge.input_io import read_input
from abacus_forge.result import CollectionResult, TaskResult
from abacus_forge.runner import LocalRunner
from abacus_forge.workspace import Workspace


def _root(workspace: str | Path | Workspace) -> Workspace:
    return Workspace((workspace.root if isinstance(workspace, Workspace) else Path(workspace)).resolve())


def _plan_path(root: Workspace, task: str) -> Path:
    if not isinstance(task, str) or re.fullmatch(r"[a-z][a-z0-9_-]*", task) is None:
        raise ValueError("task must be a path-safe name")
    return root.resolve_relative(f"reports/{task}_plan.json")


def _unit_path(root: Workspace, relative: str) -> Path:
    canonical_relative_path(relative)
    if relative == ".":
        raise ValueError("unit workspace must be a child of the task workspace")
    return root.resolve_relative(relative)


def input_digest(workspace: str | Path | Workspace) -> str:
    """Bind generated INPUT/STRU/KPT bytes, not the runtime environment."""
    root = _root(workspace)
    parameters = read_input(root.inputs_dir / "INPUT")
    digest = hashlib.sha256()
    for role, name in (("INPUT", "INPUT"), ("STRU", parameters.get("stru_file", "STRU")), ("KPT", parameters.get("kpoint_file", "KPT"))):
        path = root.resolve_relative(Path("inputs") / name)
        if role != "KPT" and not path.is_file():
            raise ValueError(f"unit input is missing: {name}")
        payload = path.read_bytes() if path.is_file() else None
        digest.update(role.encode() + b"\0" + name.encode() + b"\0")
        digest.update(b"absent\0" if payload is None else str(len(payload)).encode() + b"\0" + payload)
    return digest.hexdigest()


def save_plan(root: Workspace, task: str, subtasks: list[dict[str, Any]], **metadata: Any) -> Path:
    """Publish generated units without embedding their current absolute root."""
    root = _root(root)
    path = _plan_path(root, task)
    if path.exists():
        raise ValueError("task plan already exists; use a new workspace for changed inputs")
    if not subtasks:
        raise ValueError("a task plan requires at least one unit")
    entries = []
    for item in subtasks:
        entry = dict(item)
        raw_workspace = entry.pop("workspace", None)
        relative = entry.get("workspace_rel")
        if relative is None:
            if raw_workspace is None:
                raise ValueError("unit requires workspace_rel or workspace")
            relative = Path(raw_workspace).resolve().relative_to(root.root).as_posix()
        workspace = _unit_path(root, relative)
        entry.update(unit_id=entry.get("unit_id", relative), workspace_rel=relative, input_digest=input_digest(workspace))
        entries.append(entry)
    payload = {**metadata, "kind": "abacus-forge.task-plan", "schema_version": 1, "task": task, "subtasks": entries}
    _validate_entries(root, entries)
    path = root.write_json(path.relative_to(root.root), payload)
    result = TaskResult(task, root.root, "prepared", artifacts={path.relative_to(root.root).as_posix(): str(path)})
    root.append_operation_event("prepare", result.to_envelope().to_dict())
    return path


def _validate_entries(root: Workspace, entries: Any) -> None:
    if not isinstance(entries, list) or not entries:
        raise ValueError("task plan must contain a non-empty subtasks array")
    ids: set[str] = set()
    paths: set[Path] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("task plan units must be objects")
        unit_id = entry.get("unit_id")
        if not isinstance(unit_id, str) or not unit_id or unit_id in ids:
            raise ValueError("task plan has an invalid or duplicate unit_id")
        relative = entry.get("workspace_rel")
        if not isinstance(relative, str):
            raise ValueError("unit workspace_rel must be a relative path")
        path = _unit_path(root, relative)
        if path in paths:
            raise ValueError("task plan has duplicate unit workspaces")
        if not isinstance(entry.get("input_digest"), str) or re.fullmatch(r"[0-9a-f]{64}", entry["input_digest"]) is None:
            raise ValueError("task plan unit has no valid input_digest")
        ids.add(unit_id)
        paths.add(path)


def load_plan(workspace: str | Path | Workspace, task: str) -> dict[str, Any]:
    """Reload a plan and bind its relative unit paths under the supplied root."""
    root = _root(workspace)
    payload = json.loads(_plan_path(root, task).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("task") != task:
        raise ValueError("task plan does not match the requested task")
    if "schema_version" not in payload and "kind" not in payload:
        # Older unversioned pack plans remain consumable at their original
        # root. They did not freeze input bytes; do not claim historical binding.
        entries = payload.get("subtasks")
        if not isinstance(entries, list) or not entries:
            raise ValueError("legacy task plan has no units")
        normalized = []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("workspace"), str):
                raise ValueError("legacy task plan unit has no workspace")
            path = Path(entry["workspace"]).resolve()
            try:
                relative = path.relative_to(root.root).as_posix()
            except ValueError as error:
                raise ValueError("legacy absolute unit paths require the original workspace; prepare a new plan to relocate") from error
            normalized.append({**entry, "unit_id": relative, "workspace_rel": relative, "input_digest": input_digest(path)})
        payload = {**payload, "subtasks": normalized, "legacy_input_binding": "current_inputs"}
        if task == "vibration":
            payload["atom_indices"] = sorted({entry["atom_index"] for entry in entries if "atom_index" in entry})
    elif payload.get("schema_version") != 1 or payload.get("kind") != "abacus-forge.task-plan":
        raise ValueError("unsupported task plan schema")
    _validate_entries(root, payload.get("subtasks"))
    payload["subtasks"] = [{**entry, "workspace": str(_unit_path(root, entry["workspace_rel"]))} for entry in payload["subtasks"]]
    return payload


def list_subtasks(workspace: str | Path | Workspace, task: str) -> TaskResult:
    root = _root(workspace)
    plan = load_plan(root, task)
    path = _plan_path(root, task)
    return TaskResult(task, root.root, "prepared", subtasks=plan["subtasks"], summary={"count": len(plan["subtasks"])}, artifacts={path.relative_to(root.root).as_posix(): str(path)})


def _selected(root: Workspace, task: str, unit_id: str) -> dict[str, Any]:
    for unit in load_plan(root, task)["subtasks"]:
        if unit["unit_id"] == unit_id:
            return unit
    raise ValueError(f"unknown unit_id: {unit_id}")


def _check_inputs(unit: dict[str, Any]) -> None:
    if input_digest(unit["workspace"]) != unit["input_digest"]:
        raise ValueError(f"unit inputs changed since prepare: {unit['unit_id']}")


def _persist_unit_record(root: Workspace, unit: dict[str, Any], record: dict[str, Any], envelope: ForgeResultEnvelope, token: str) -> dict[str, Any]:
    workspace = Workspace(Path(unit["workspace"]))
    relative = f"reports/subtask-results/{record['operation_id']}.json"
    record["record_path_rel"] = f"{unit['workspace_rel']}/{relative}"
    workspace.write_json(relative, record)
    artifact = ArtifactRecord(id="subtask_result", path_rel=relative, role="result", stage=record["phase"])
    payload = envelope.to_dict()
    payload["artifacts"].append(artifact.to_dict())
    envelope = ForgeResultEnvelope.from_dict(payload)
    outcome = OperationOutcome(operation_id=record["operation_id"], envelope=envelope)
    workspace.append_claimed_v1_operation_event(record["operation_id"], record["phase"], outcome.to_dict(), owner_token=token)
    return {**record, "outcome": outcome.to_dict()}


def _operate(workspace: str | Path | Workspace, task: str, unit_id: str, *, phase: str, operation: Callable[[Workspace], Any]) -> dict[str, Any]:
    root = _root(workspace)
    unit = _selected(root, task, unit_id)
    child = Workspace(Path(unit["workspace"]))
    operation_id = str(uuid.uuid4())
    with child.operation_guard(operation_id, phase) as token:
        record = {"task": task, "unit_id": unit_id, "workspace_rel": unit["workspace_rel"], "input_digest": unit["input_digest"], "operation_id": operation_id, "phase": phase}
        # Input disagreement is a caller error, not a retriable engine failure.
        _check_inputs(unit)
        try:
            result = operation(child)
            record.update(status=result.status, diagnostics=dict(result.diagnostics))
            if phase == "collect":
                record["metrics"] = result.metrics
            else:
                record["run"] = result.to_dict()
            envelope = result.to_envelope()
        except Exception as error:
            record.update(status="failed", diagnostics={"exception_type": type(error).__name__, "message": str(error)})
            if phase == "collect":
                record["metrics"] = {}
            envelope = ForgeResultEnvelope(operation=phase, workspace_rel=".", status=OperationStatus(execution="failed" if phase == "execute" else "not_run", collection="partial" if phase == "collect" else "not_collected", scientific="unassessed"), diagnostics=record["diagnostics"])
        return _persist_unit_record(root, unit, record, envelope, token)


def execute_subtask(workspace: str | Path | Workspace, task: str, unit_id: str, *, runner: LocalRunner | None = None) -> dict[str, Any]:
    """Execute exactly one unit, without collecting or executing its siblings."""
    return _operate(workspace, task, unit_id, phase="execute", operation=(runner or LocalRunner()).run)


def collect_subtask(workspace: str | Path | Workspace, task: str, unit_id: str, *, collector: Callable[[Workspace], CollectionResult] | None = None) -> dict[str, Any]:
    """Collect exactly one unit and durably retain its success or failure facts."""
    return _operate(workspace, task, unit_id, phase="collect", operation=collector or collect)


def gather_subtasks(workspace: str | Path | Workspace, task: str, results: Iterable[dict[str, Any]]) -> TaskResult:
    """Join explicit collection records by unit ID; never run or collect units."""
    root = _root(workspace)
    plan = load_plan(root, task)
    units = {entry["unit_id"]: entry for entry in plan["subtasks"]}
    records: dict[str, dict[str, Any]] = {}
    for row in results:
        if not isinstance(row, dict):
            raise ValueError("collection records must be objects")
        unit_id = row.get("unit_id")
        if not isinstance(unit_id, str) or unit_id not in units:
            raise ValueError(f"unknown unit_id in collection: {unit_id}")
        if unit_id in records:
            raise ValueError(f"duplicate collection for unit_id: {unit_id}")
        unit = units[unit_id]
        if row.get("task", task) != task or row.get("phase", "collect") != "collect":
            raise ValueError("gather requires collect records for the same task")
        if row.get("input_digest") != unit["input_digest"]:
            raise ValueError(f"collection input mismatch: {unit_id}")
        if not isinstance(row.get("status"), str) or not isinstance(row.get("metrics"), dict):
            raise ValueError("collection record requires status and metrics")
        # Canonical unit metadata wins over arbitrary or pre-relocation paths.
        records[unit_id] = {**row, **unit, "task": task, "phase": "collect"}
    ordered = [records[unit_id] for unit_id in units if unit_id in records]
    missing = [unit_id for unit_id in units if unit_id not in records]
    failed = [row["unit_id"] for row in ordered if row["status"] != "completed"]
    summary = {"count": len(units), "collected": len(ordered), "missing_units": missing, "failed_units": failed}
    result = TaskResult(task, root.root, "degraded" if missing or failed else "completed", subtasks=ordered, summary=summary)
    # Each gather is a snapshot; previous partial and complete joins survive.
    relative = f"reports/{task}-collections/{uuid.uuid4()}.json"
    path = root.write_json(relative, result.to_dict())
    result.artifacts[relative] = str(path)
    root.append_operation_event("collect", result.to_envelope().to_dict())
    return result
