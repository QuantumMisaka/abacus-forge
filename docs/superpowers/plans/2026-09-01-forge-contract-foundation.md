# ABACUS-Forge Contract Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the versioned, protocol-neutral request/result/workspace contract foundation required before Forge services, CLI, and Paimon v1.3 adapters can migrate.

**Spec:** `docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html` (approved 2026-09-01; implement R1, R2, R3, R5 and the Phase 1 portion of the rollout section)

**Architecture:** Keep the current `prepare`, `modify`, `execute`, `collect`, `export`, `RunResult`, `CollectionResult`, workspace layout, and `forge-result.json` behavior compatible. Add a small `contracts.py` module and append-only workspace records under `reports/`; existing services expose v1 envelopes in parallel rather than changing their legacy `to_dict()` payloads. A later plan will introduce typed per-operation requests, service extraction, status policy, CLI request-file support, and the ATP adapter.

**Tech Stack:** Python 3.10+, standard-library dataclasses/json/hashlib/tempfile/uuid, existing pytest suite, Hatchling package layout.

## Global Constraints

- Keep Forge free of AiiDA, ATP/MCP, scheduler, platform, `abacus-agent-tools`, and `abacustest` runtime dependencies (SPEC R1).
- Preserve current public API signatures, legacy `to_dict()` key sets, workspace `inputs/outputs/reports` layout, and `forge-result.json` writes until a separately approved deprecation plan exists.
- All v1 contract payloads must be JSON-safe with `allow_nan=False`; all portable artifact paths must be canonical POSIX paths relative to the workspace root.
- Write new manifest/event JSON atomically and reject relative paths that are empty, absolute, contain `.`/`..`, or resolve outside the workspace root.
- Default tests stay offline and deterministic; do not require ABACUS, PyATB, network, scheduler, sibling repositories, or user work directories.
- Do not push, publish, or merge as part of this plan. Make one reviewable local commit per completed task.

---

## File map

| Path | Responsibility |
| --- | --- |
| `src/abacus_forge/contracts.py` | JSON-safe v1 request, artifact, metric, check, status, and result-envelope dataclasses plus validation helpers. |
| `src/abacus_forge/workspace.py` | Safe workspace-relative path resolution, atomic JSON writes, `forge-workspace.json`, and append-only operation event persistence. |
| `src/abacus_forge/result.py` | Non-breaking adapters from existing `RunResult`/`CollectionResult`/`TaskResult` to `ForgeResultEnvelope`. |
| `src/abacus_forge/api.py` | Persist a v1 operation event after successful prepare/modify/execute/collect while retaining existing output files. |
| `src/abacus_forge/__init__.py` | Export only the new stable contract types required by Python callers. |
| `tests/test_contracts.py` | Own pure v1 contract validation and JSON round-trip behavior. |
| `tests/test_workspace.py` | Own path-containment, atomic-write, manifest, and event-history behavior. |
| `tests/test_result_contract.py` | Preserve legacy serialization and assert parallel v1 envelope projections. |
| `tests/test_units.py` | Assert prepare/modify/execute/collect append independent events without breaking the legacy result snapshot. |
| `README.md`, `AGENTS.md`, `tests/README.md` | Describe the new additive manifest/event contract and its verification boundary without claiming a completed CLI migration. |

### Task 1: Define JSON-safe v1 contract records

**Files:**
- Create: `src/abacus_forge/contracts.py`
- Create: `tests/test_contracts.py`
- Modify: `src/abacus_forge/__init__.py:3-63`

**Test strategy:**
- Behavior boundary: a caller can construct and serialize a request and result envelope; invalid schema versions, unsafe artifact paths, duplicate artifact ids, non-finite values, and invalid status combinations are rejected before any filesystem side effect.
- Existing suite to extend: `tests/test_result_contract.py` remains the owner of legacy result behavior.
- New test file justification: v1 contracts are a new pure public boundary and do not belong to API, CLI, or parser tests.
- Temporary probes: none.

**Interfaces:**
- Consumes: no Forge runtime module other than standard-library `Path` values converted at the public boundary.
- Produces: `ForgeRequest`, `ArtifactRecord`, `MetricRecord`, `CheckRecord`, `OperationStatus`, and `ForgeResultEnvelope`; all expose `to_dict()` and `from_dict()`.

- [ ] **Step 1: Write the failing pure-contract tests**

Create `tests/test_contracts.py` with these exact behavior checks:

```python
from __future__ import annotations

import json

import pytest

from abacus_forge.contracts import ArtifactRecord, ForgeRequest, ForgeResultEnvelope, MetricRecord, OperationStatus


def test_result_envelope_round_trips_with_relative_artifacts() -> None:
    result = ForgeResultEnvelope(
        operation="collect",
        workspace_rel=".",
        status=OperationStatus(execution="completed", scientific="accepted", collection="complete"),
        artifacts=[ArtifactRecord(id="runtime_log", path_rel="outputs/stdout.log", role="runtime_log", stage="abacus")],
        metrics=[MetricRecord(name="total_energy", value=-5.0, unit="eV", kind="reported", source_artifact_id="runtime_log")],
    )
    payload = result.to_dict()
    assert payload["schema_version"] == "forge.result/v1"
    assert ForgeResultEnvelope.from_dict(json.loads(json.dumps(payload, allow_nan=False))).to_dict() == payload


@pytest.mark.parametrize("path_rel", ["../outside", "/tmp/out", "outputs/../stdout.log", "", "./stdout.log"])
def test_artifact_record_rejects_noncanonical_paths(path_rel: str) -> None:
    with pytest.raises(ValueError, match="path_rel"):
        ArtifactRecord(id="bad", path_rel=path_rel, role="runtime_log", stage="abacus")


def test_request_rejects_non_json_payload() -> None:
    with pytest.raises(ValueError, match="JSON-safe"):
        ForgeRequest(operation="prepare", workspace_rel=".", payload={"value": float("nan")})
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_contracts.py
```

Expected: collection fails because `abacus_forge.contracts` does not exist.

- [ ] **Step 3: Implement the contract module**

Create `src/abacus_forge/contracts.py` with the following stable rules:

```python
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Literal, Mapping, Sequence, TypeAlias

JSONValue: TypeAlias = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]

REQUEST_SCHEMA_VERSION = "forge.request/v1"
RESULT_SCHEMA_VERSION = "forge.result/v1"
WORKSPACE_SCHEMA_VERSION = "forge.workspace/v1"


def canonical_relative_path(value: str) -> str:
    # Accept only "." for a workspace root; all artifact paths must be non-root.
    # Reject absolute paths, backslashes, empty segments, ".", and ".." components.
    path = PurePosixPath(value)
    if value == ".":
        return value
    if not value or path.is_absolute() or "\\" in value or "" in value.split("/") or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("path_rel must be a canonical relative POSIX path")
    return path.as_posix()


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    id: str
    path_rel: str
    role: str
    stage: str
    availability: str = "available"
    media_type: str = "application/octet-stream"
    sha256: str | None = None
    size_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class MetricRecord:
    name: str
    value: JSONValue
    unit: str | None
    kind: Literal["reported", "derived", "runtime"]
    source_artifact_id: str | None = None


@dataclass(frozen=True, slots=True)
class CheckRecord:
    name: str
    status: Literal["passed", "failed", "warning", "unavailable"]
    message: str | None = None


@dataclass(frozen=True, slots=True)
class OperationStatus:
    execution: Literal["not_run", "completed", "failed", "skipped"]
    scientific: Literal["unassessed", "accepted", "guarded", "rejected"]
    collection: Literal["not_collected", "complete", "partial", "missing_output"]


@dataclass(frozen=True, slots=True)
class ForgeRequest:
    operation: Literal["prepare", "modify", "execute", "collect", "export"]
    workspace_rel: str
    payload: Mapping[str, JSONValue]
    schema_version: str = REQUEST_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class ForgeResultEnvelope:
    operation: str
    workspace_rel: str
    status: OperationStatus
    artifacts: Sequence[ArtifactRecord] = ()
    metrics: Sequence[MetricRecord] = ()
    checks: Sequence[CheckRecord] = ()
    warnings: Sequence[str] = ()
    diagnostics: Mapping[str, JSONValue] = field(default_factory=dict)
    schema_version: str = RESULT_SCHEMA_VERSION
```

Use a private JSON round-trip helper based on `json.dumps(value, allow_nan=False)` followed by `json.loads(serialized)` to validate every `payload`, `diagnostics`, metric value, and serialized result. `ArtifactRecord.__post_init__` must reject the workspace-root path `"."`; `ForgeResultEnvelope.__post_init__` must reject duplicate artifact IDs and metrics whose `source_artifact_id` is absent from the artifact list.

- [ ] **Step 4: Export only the v1 contract types**

Add these names to `src/abacus_forge/__init__.py` and `__all__`:

```python
from abacus_forge.contracts import ArtifactRecord, CheckRecord, ForgeRequest, ForgeResultEnvelope, MetricRecord, OperationStatus
```

Do not move existing imports or remove old exports in this task.

- [ ] **Step 5: Run the owning suites and refactor tests**

Run:

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_contracts.py tests/test_result_contract.py
```

Expected: all tests pass. Keep legacy `to_dict()` exact-key assertions untouched; they are the compatibility boundary.

- [ ] **Step 6: Commit the contract foundation**

```bash
git add src/abacus_forge/contracts.py src/abacus_forge/__init__.py tests/test_contracts.py
git commit -m "feat: add forge v1 contract records"
```

### Task 2: Make workspace writes safe and append operation history

**Files:**
- Modify: `src/abacus_forge/workspace.py:11-55`
- Create: `tests/test_workspace.py`

**Test strategy:**
- Behavior boundary: workspace-owned writes cannot escape root; a manifest and per-operation events are atomically created under `reports/` without replacing prior events.
- Existing suite to extend: `tests/test_units.py` will consume event behavior in Task 4.
- New test file justification: `Workspace` has no owning test file and its path/atomicity contract is independent of ABACUS parsing.
- Temporary probes: none.

**Interfaces:**
- Consumes: `WORKSPACE_SCHEMA_VERSION`, `canonical_relative_path`, and JSON validation from `abacus_forge.contracts`.
- Produces: `Workspace.resolve_relative()`, `Workspace.write_json_atomic()`, `Workspace.ensure_manifest()`, and `Workspace.append_operation_event()`.

- [ ] **Step 1: Write the failing workspace tests**

Create `tests/test_workspace.py`:

```python
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
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_workspace.py
```

Expected: the test fails because `append_operation_event` is not defined and `write_json` permits `..`.

- [ ] **Step 3: Implement safe, atomic workspace persistence**

In `workspace.py`, use `Path.resolve()` plus `relative_to(self.root.resolve())` for a new private `_resolve_owned_path(relative_path)` helper. Route both `write_text` and `write_json` through it. Replace direct JSON writes with a temporary file created in the destination directory, `flush()`/`os.fsync()`, then `os.replace()`.

Implement these methods exactly:

```python
def ensure_manifest(self) -> Path:
    """Create reports/forge-workspace.json once and return it."""

def append_operation_event(self, operation: str, payload: Mapping[str, JSONValue]) -> Path:
    """Atomically write reports/events/<uuid>-<operation>.json and append its relative reference."""
```

The manifest must have `schema_version == "forge.workspace/v1"`, `workspace_rel == "."`, and an `events` array. Each event reference must contain `id`, `operation`, and canonical `path_rel`; append a new event rather than editing an existing event JSON. `append_operation_event` may atomically rewrite the manifest itself, but never any already-written event file.

- [ ] **Step 4: Run workspace and core regression suites**

Run:

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_workspace.py tests/test_api.py tests/test_units.py
```

Expected: all pass; existing files remain under `inputs/`, `outputs/`, and `reports/`.

- [ ] **Step 5: Commit workspace persistence**

```bash
git add src/abacus_forge/workspace.py tests/test_workspace.py
git commit -m "feat: persist forge workspace events safely"
```

### Task 3: Project legacy results into v1 envelopes without breaking callers

**Files:**
- Modify: `src/abacus_forge/result.py:10-80`
- Modify: `tests/test_result_contract.py:10-58`
- Modify: `src/abacus_forge/api.py:248-481`
- Modify: `tests/test_units.py:16-136`

**Test strategy:**
- Behavior boundary: legacy result dictionaries remain byte-for-byte equivalent in shape, while each core operation creates a v1 envelope event whose artifacts are workspace-relative and whose statuses distinguish execution/collection facts.
- Existing suite to extend: `tests/test_result_contract.py` and `tests/test_units.py`.
- New test file justification: none; both boundaries already have focused owners.
- Temporary probes: none.

**Interfaces:**
- Consumes: contract records from Task 1 and `Workspace.append_operation_event()` from Task 2.
- Produces: `RunResult.to_envelope()`, `CollectionResult.to_envelope()`, `TaskResult.to_envelope()`, and private `api._record_operation_event(workspace, envelope)`.

- [ ] **Step 1: Add failing compatibility-and-envelope tests**

Append to `tests/test_result_contract.py`:

```python
def test_collection_result_projects_a_v1_result_envelope(tmp_path: Path) -> None:
    workspace = prepare(tmp_path / "envelope", task="scf")
    workspace.write_text("outputs/stdout.log", "TOTAL ENERGY = -5.0\nSCF CONVERGED\n")
    workspace.write_text("outputs/stderr.log", "")
    envelope = collect(workspace).to_envelope()
    payload = envelope.to_dict()
    assert payload["schema_version"] == "forge.result/v1"
    assert payload["status"]["collection"] == "complete"
    assert any(item["id"] == "stdout_log" and item["path_rel"] == "outputs/stdout.log" for item in payload["artifacts"])
```

Append to `tests/test_units.py`:

```python
def test_unit_operations_append_v1_events_without_replacing_prior_events(tmp_path: Path) -> None:
    workspace = prepare_unit(UnitSpec(task="scf", workdir=tmp_path / "event-unit")).workspace
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["SCF CONVERGED"])
    execute_unit(UnitSpec(task="scf", workdir=workspace.root, executable=str(executable)))
    collect_unit(UnitSpec(task="scf", workdir=workspace.root))
    manifest = json.loads((workspace.reports_dir / "forge-workspace.json").read_text(encoding="utf-8"))
    assert [event["operation"] for event in manifest["events"]] == ["prepare", "execute", "collect"]
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_result_contract.py tests/test_units.py
```

Expected: failure because `to_envelope()` and API event recording do not yet exist.

- [ ] **Step 3: Implement parallel envelope projections**

Add `to_envelope()` methods in `result.py`; do not alter `to_dict()`.

```python
def _collection_state(legacy_status: str) -> str:
    return {
        "completed": "complete",
        "unfinished": "partial",
        "failed": "partial",
        "missing-output": "missing_output",
    }.get(legacy_status, "partial")


def _collection_envelope(self: CollectionResult) -> ForgeResultEnvelope:
    artifacts = _workspace_artifact_records(self.workspace, self.artifacts)
    metrics, legacy_metrics = _scalar_metric_records(self.metrics)
    converged = self.metrics.get("converged") is True
    diagnostics = {**_json_mapping(self.diagnostics), "legacy_metrics": legacy_metrics}
    return ForgeResultEnvelope(
        operation="collect",
        workspace_rel=".",
        status=OperationStatus(
            execution="not_run",
            scientific="accepted" if converged else "guarded",
            collection=_collection_state(self.status),
        ),
        artifacts=artifacts,
        metrics=metrics,
        checks=(CheckRecord(name="converged", status="passed" if converged else "warning"),),
        warnings=tuple(str(item) for item in diagnostics.pop("warnings", [])),
        diagnostics=diagnostics,
    )
```

Bind `_collection_envelope` as `CollectionResult.to_envelope`; implement equivalent `RunResult.to_envelope` and `TaskResult.to_envelope` with the same helper functions. `_workspace_artifact_records(workspace, artifacts)` must use deterministic IDs `stdout_log`, `stderr_log`, and `artifact-<sha256-of-path_rel[:12]>` for unnamed collected files. For an existing artifact path outside the workspace root, omit it and append a warning; do not serialize an absolute path as a portable artifact. `_scalar_metric_records` returns named records only for `None`, bool, int, float, and str values; it retains JSON-safe nested legacy metrics in `diagnostics["legacy_metrics"]` until the later metric-schema migration.

In `api.py`, after each successful `prepare_unit`, `modify_unit`, `execute_unit`, and `collect_unit`, call `_record_operation_event()` with the relevant v1 envelope. Preserve the existing `forge-unit.json` and `forge-result.json` writes exactly for compatibility. For `prepare_unit`, construct a prepared envelope with execution `not_run`, scientific `unassessed`, collection `not_collected`; include `forge-unit.json` as a `provenance_manifest` artifact when it exists.

- [ ] **Step 4: Run the owning suites and full deterministic regression**

Run:

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_result_contract.py tests/test_units.py tests/test_api.py
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
```

Expected: focused suites and the full default suite pass; legacy tests that assert the exact old `to_dict()` field sets remain green.

- [ ] **Step 5: Commit the additive service integration**

```bash
git add src/abacus_forge/api.py src/abacus_forge/result.py tests/test_result_contract.py tests/test_units.py
git commit -m "feat: record forge v1 operation envelopes"
```

### Task 4: Document the additive contract and establish its regression gate

**Files:**
- Modify: `README.md:14-25,333-358`
- Modify: `AGENTS.md:13-27,44-58`
- Modify: `tests/README.md:1-34`

**Test strategy:**
- Behavior boundary: users and developers can distinguish legacy snapshots from v1 append-only manifests, locate the owning contract/workspace tests, and run the required offline gate.
- Existing suite to extend: no production suite; documentation is checked by CLI help, link existence, and the tests introduced in Tasks 1-3.
- New test file justification: none.
- Temporary probes: none.

**Interfaces:**
- Consumes: the public behavior completed in Tasks 1-3.
- Produces: accurate user/developer documentation for `reports/forge-workspace.json` and `reports/events/*.json`.

- [ ] **Step 1: Update README without changing user command examples**

State that current legacy `meta.json`, `forge-unit.json`, and `forge-result.json` remain compatibility files; new machine consumers should read the additive v1 workspace manifest and event records. Do not claim request-file CLI support, typed operation requests, ATP adapter availability, or stable property packs.

- [ ] **Step 2: Update AGENTS and test documentation**

Add these requirements:

```markdown
- New Forge artifacts exposed across an operation boundary require a v1 `ArtifactRecord` and a regression asserting a workspace-relative path.
- `reports/forge-workspace.json` and `reports/events/*.json` are append-only audit records; do not replace them with a mutable last-result file.
- Run `tests/test_contracts.py`, `tests/test_workspace.py`, and the owning API/result tests whenever contracts or workspace persistence change.
```

- [ ] **Step 3: Run documentation and regression verification**

Run:

```bash
git diff --check
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m abacus_forge.cli --help
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_contracts.py tests/test_workspace.py tests/test_result_contract.py tests/test_units.py
```

Expected: no whitespace errors, CLI exits 0, and all named tests pass.

- [ ] **Step 4: Commit the documentation gate**

```bash
git add README.md AGENTS.md tests/README.md
git commit -m "docs: describe forge v1 workspace records"
```

## Spec coverage and intentional follow-up plans

This plan covers SPEC requirements R1, R2, R3, R5, R11, and R12 at the contract-foundation level. It deliberately does not implement R4/R6/R7/R8/R9/R10: they depend on the persisted v1 result/workspace records produced here and must remain separate reviewable plans.

After this plan is verified, create the following plans in order:

1. **Service and status migration:** typed per-operation requests; task-aware execution/scientific/collection status policy; runner/engine protocol; legacy `UnitSpec` compatibility shim.
2. **Agent-first CLI migration:** request-file/stdin input, schema discovery, JSON error envelope, stable exit classes, and process tests.
3. **Paimon thin adapter and acceptance:** ATP output/evidence projection, legacy-runtime dependency removal, benchmark parity, and real ABACUS/PyATB smoke matrix.

## Plan self-review

- **SPEC coverage:** the contract foundation implements the prerequisites for the remaining phases without pretending to complete the adapter or physical acceptance work.
- **Placeholder scan:** no task contains a deferred implementation placeholder; follow-up work is explicitly out of scope with named plans and dependencies.
- **Type consistency:** all later tasks consume `ForgeResultEnvelope`, `Workspace.append_operation_event()`, and `to_envelope()` defined by earlier tasks; legacy `to_dict()` remains unchanged throughout this plan.
