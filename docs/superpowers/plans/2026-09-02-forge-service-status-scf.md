# ABACUS-Forge Service/Status SCF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Deliver typed service contracts and one end-to-end SCF slice whose execution/collection facts, observations, event identity, and legacy compatibility meet the approved design.

**Spec:** `docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html` and `docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html` (approved; review convergence confirmed 2026-09-04).

**Architecture:** Retain parsers, UnitSpec, legacy API/CLI, layout, and compatibility files. New typed services adapt to the existing primitives exactly once and return execution facts, collection state, observations, metrics, and artifact references. Scientific judgment, task composition, retry/continuation, and platform scheduling remain caller-owned.

**Tech Stack:** Python 3.10+, standard-library dataclasses/json/uuid/pathlib, existing ASE-backed code, pytest.

## Global Constraints

- No AiiDA, ATP/MCP, scheduler, platform, `abacus-agent-tools`, or `abacustest` runtime dependencies.
- Preserve legacy signatures, `to_dict()` key sets, CLI defaults, `forge-unit.json`, `forge-result.json`, and layout.
- A typed request has a lowercase UUIDv4 `operation_id`; it correlates the request, admission, event, and artifacts and provides one-time admission conflict detection. Before any domain write or runner start, an atomic admission tombstone consumes the ID. It does not provide cached/idempotent results, retry, recovery, or workflow semantics, and a stale admission is never automatically reclaimed.
- New typed results expose execution/collection state and raw observations. If a legacy projection still has `scientific`, Forge writes only `unassessed`; acceptance/interpretation is produced outside Forge.
- New service success uses a serializable `OperationOutcome` carrying `operation_id`, the unchanged `ForgeResultEnvelope`, and observations. The embedded `forge.result/v1` key set remains frozen.
- No typed request, service, result, or diagnostic accepts `policy_id`; no scientific policy registry participates in Forge service execution.
- Default tests are offline/deterministic. No new v1 CLI command, TUI, or Paimon adapter is implemented here; a future TUI is an optional thin shell over the stable API/structured CLI envelope.

## File map

| Path | Responsibility |
| --- | --- |
| `src/abacus_forge/contracts.py` | Typed requests, operation/artifact references, status observations, and `forge.error/v1`. |
| `src/abacus_forge/workspace.py` | Append audit events with caller-owned operation IDs. |
| `src/abacus_forge/errors.py` | Typed internal failures and stable public error-class mapping. |
| `src/abacus_forge/services.py` | Typed SCF prepare/modify/execute/collect adapters. |
| `src/abacus_forge/result.py` | Preserve legacy projections without inferring scientific acceptance. |
| `tests/test_contracts.py`, `tests/test_workspace.py` | Pure contract and persistence boundaries. |
| `tests/test_service_status.py` | New owner for service/observation behavior. |
| `tests/test_result_contract.py`, `tests/test_units.py` | Legacy compatibility regression. |
| `src/abacus_forge/__init__.py` | Re-export typed contracts and service entry points (Tasks 1/4). |
| `tests/conftest.py`, `tests/README.md` | Marker registration for new test files and test-layering documentation (Tasks 3/5). |

### Task 1: Add immutable typed service and error contracts

**Files:**
- Modify: `src/abacus_forge/contracts.py`
- Modify: `src/abacus_forge/__init__.py`
- Modify: `tests/test_contracts.py`

**Test strategy:** Reject malformed UUIDs, unknown schema versions, malformed artifact references, and malformed requests before filesystem access. Round-trip typed SCF requests and error envelopes, asserting `schema_version` presence. Verify that no new request requires a scientific policy field.

**Interfaces:** Produce frozen slot dataclasses `OperationRef`, `ArtifactRef`, `ScfPrepareRequest`, `ScfModifyRequest`, `ScfExecuteRequest`, `ScfCollectRequest`, and `ForgeErrorEnvelope`. Requests expose `schema_version`, operation, operation ID, workspace reference, operation-specific fields, `to_dict()`, and `from_dict()`; `from_dict()` rejects unknown `schema_version` values. Do not change legacy `ForgeRequest`. `OperationRef` carries `{operation_id, workspace_rel}`; `ArtifactRef` carries `{operation_id, artifact_id}`, rejects missing fields, and owns the Stage 1 artifact-ref validator role. Artifact path containment stays enforced where artifacts are produced.

- [x] **Step 1: Write failing tests**

    def test_scf_collect_request_round_trips() -> None:
        request = ScfCollectRequest(
            operation_id="123e4567-e89b-42d3-a456-426614174000",
            workspace_rel=".",
        )
        assert ScfCollectRequest.from_dict(request.to_dict()).to_dict() == request.to_dict()

    def test_scf_collect_request_serializes_schema_version() -> None:
        request = ScfCollectRequest(
            operation_id="123e4567-e89b-42d3-a456-426614174000",
            workspace_rel=".",
        )
        assert "schema_version" in request.to_dict()

    def test_service_request_rejects_unknown_schema_version() -> None:
        with pytest.raises(ValueError, match="schema_version"):
            ScfCollectRequest.from_dict(
                {
                    "schema_version": "forge.unknown/99",
                    "operation_id": "123e4567-e89b-42d3-a456-426614174000",
                    "workspace_rel": ".",
                }
            )

    def test_operation_ref_requires_both_ids() -> None:
        with pytest.raises(ValueError, match="artifact_id"):
            OperationRef.from_dict({"operation_id": "123e4567-e89b-42d3-a456-426614174000"})

    def test_service_request_rejects_noncanonical_uuid4() -> None:
        with pytest.raises(ValueError, match="operation_id"):
            ScfCollectRequest(
                operation_id="123E4567-E89B-42D3-A456-426614174000",
                workspace_rel=".",
            )

- [x] **Step 2: Run RED**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_contracts.py`

Expected: FAIL because typed request/error records do not exist.

- [x] **Step 3: Implement records**

Use frozen, slot-based dataclasses and `uuid.UUID(value).version == 4`; reject noncanonical UUIDs, unknown serialized fields, and non-JSON values. Keep any legacy `scientific` field outside the new request contract.

- [x] **Step 4: Run GREEN**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_contracts.py tests/test_result_contract.py`

Expected: all pass; existing `ForgeRequest` remains unchanged.

- [x] **Step 5: Commit**

    git add src/abacus_forge/contracts.py src/abacus_forge/__init__.py tests/test_contracts.py
    git commit -m "feat: add typed forge service contracts"

### Task 2: Persist request-owned operation events

**Files:**
- Modify: `src/abacus_forge/workspace.py`
- Modify: `tests/test_workspace.py`

**Test strategy:** A new event uses the supplied UUID, is append-only, and is recoverable as an audit record. A duplicated `operation_id` is rejected before service side effects without overwriting or renaming existing evidence. A crash admission remains a conflict. Legacy `append_operation_event()` retains its existing behavior.

**Interfaces:** Produce `Workspace.append_v1_operation_event(operation_id, operation, payload) -> Path`; the service-facing admission/commit interface is hardened in Task 6.

- [x] **Step 1: Write failing test**

    def test_v1_event_uses_request_operation_id(tmp_path: Path) -> None:
        workspace = Workspace(tmp_path / "w")
        event_id = "123e4567-e89b-42d3-a456-426614174000"
        workspace.append_v1_operation_event(event_id, "collect", {"status": "complete"})
        manifest = json.loads((workspace.reports_dir / "forge-workspace.json").read_text())
        assert manifest["events"][-1]["id"] == event_id

    def test_v1_event_rejects_duplicate_operation_id(tmp_path: Path) -> None:
        workspace = Workspace(tmp_path / "w")
        event_id = "123e4567-e89b-42d3-a456-426614174000"
        workspace.append_v1_operation_event(event_id, "collect", {"status": "complete"})
        with pytest.raises(ValueError, match="operation_id"):
            workspace.append_v1_operation_event(event_id, "collect", {"status": "complete"})

- [x] **Step 2: Run RED**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_workspace.py`

Expected: FAIL because `append_v1_operation_event` is absent.

- [x] **Step 3: Implement additive persistence**

Under the existing manifest lock, validate the UUID, reject an `operation_id` already present in the manifest event index (no overwrite, rename, or silent append), atomically write the event file, and append the manifest reference. This additive primitive alone is not the service-side duplicate guard: Task 6 adds admission before side effects. The duplicate rejection does not give the ID idempotency semantics. Do not use persistence to return cached results, infer recovery, or manage workflow state; do not edit legacy event files.

- [x] **Step 4: Run GREEN**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_workspace.py tests/test_units.py`

Expected: all pass, including legacy concurrent event coverage.

- [x] **Step 5: Commit**

    git add src/abacus_forge/workspace.py tests/test_workspace.py
    git commit -m "feat: persist v1 operation identities"

### Task 3: Define factual operation/observation status

**Files:**
- Create: `tests/test_service_status.py`
- Modify: `src/abacus_forge/contracts.py` as needed
- Modify: `tests/conftest.py` (register the new test file in the marker map)
- Modify: `tests/support/` (shared service-test helpers)

**Test strategy:** No policy registry and no scientific acceptance matrix. Cover execution, collection, normal-end, convergence, parser completeness, required artifacts, dry-run, missing output, and parser partial as independently sourced observations.

**Interfaces:** `OperationStatus` exposes execution and collection states. `CheckRecord`/metric records retain source and value. `Observation` is a frozen record `(name, value, source)` with `source ∈ {log, file, parser, runtime}`; observations are returned on the service surface and never serialized into the `forge.result/v1` envelope (the envelope key set stays frozen); write them into an operation event payload when audit persistence is needed. A collector may report `normal_end=False` or `convergence=unavailable`; it must not map these observations to accepted/guarded/rejected.

- [x] **Step 1: Write failing observation tests**

    def test_nonconverged_observation_does_not_change_execution_status() -> None:
        result = collect_fixture(convergence=False)
        assert result.status.execution == "not_run"
        assert result.observations["convergence"].value is False

    def test_missing_output_is_collection_state() -> None:
        result = collect_fixture(missing_output=True)
        assert result.status.collection == "missing_output"

- [x] **Step 2: Run RED**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py`

Expected: FAIL until observations and collection mapping are exposed.

- [x] **Step 3: Implement narrow factual mapping**

Keep returncode, termination, normal-end, convergence, parser, metrics, and artifact presence as separate records. If a legacy envelope still serializes `scientific`, set it to `unassessed` and never derive it from any check. Register `tests/test_service_status.py` in `tests/conftest.py`'s marker map. Shared helpers used by the example tests (`collect_fixture`, `prepared_scf_workspace_with_log`, `fake_abacus`, and the service scenario helpers) live under `tests/support/` or shared fixtures; do not redefine them per task.

- [x] **Step 4: Run GREEN**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py tests/test_collect_abacus_reference.py`

Expected: all pass.

- [x] **Step 5: Commit**

    git add src/abacus_forge/contracts.py tests/test_service_status.py tests/conftest.py tests/support
    git commit -m "feat: expose factual operation observations"

### Task 4: Build typed SCF services and legacy projection

**Files:**
- Create: `src/abacus_forge/services.py`
- Modify: `src/abacus_forge/result.py`
- Modify: `src/abacus_forge/__init__.py`
- Modify: `tests/test_service_status.py`, `tests/test_result_contract.py`, `tests/test_units.py`

**Test strategy:** A fake ABACUS prepare → modify → execute → collect returns factual envelopes and persists the supplied IDs. Existing collection `to_dict()` remains byte-compatible; its compatibility projection never infers scientific acceptance.

**Interfaces:** `ForgeServices.prepare_scf`, `modify_scf`, `execute_scf`, and `collect_scf` consume Task 1 requests, invoke legacy primitives once, and persist with Task 2. On success they return serializable `OperationOutcome(schema_version, operation_id, envelope, observations)` with a delegating `status` property; on request/environment/persistence failure they return `ForgeErrorEnvelope`. The embedded result keeps its frozen key set (no `operation_id` or observations field). This task-scoped facade is the deviation registered by the 09-02 SPEC "最小接口形态" first-slice approval note; converge to per-operation protocols or re-register before Stage 4.

- [x] **Step 1: Write failing vertical-slice test**

    def test_typed_scf_collect_returns_observations_and_event_id(tmp_path: Path) -> None:
        services = ForgeServices.default()
        workspace = prepare_through_service(services, tmp_path / "scf")
        execute_through_service(services, workspace, fake_abacus)
        collected = collect_through_service(services, workspace)
        assert collected.status.collection in {"complete", "partial", "missing_output"}
        assert "convergence" in collected.observations

- [x] **Step 2: Run RED**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py tests/test_result_contract.py`

Expected: FAIL because `ForgeServices` and the factual typed envelope are absent.

- [x] **Step 3: Implement narrow adapters**

Translate typed requests to the minimum existing `UnitSpec`/`UnitModifySpec`, call the old primitive once, build only workspace-contained artifacts, expose observations, and persist the event. Change compatibility envelope projection to `scientific=unassessed` without altering legacy `to_dict()`. Keep the `ForgeResultEnvelope` key set unchanged: no new serialized field, no `operation_id` on the success envelope.

- [x] **Step 4: Run GREEN and deterministic regression**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py tests/test_contracts.py tests/test_workspace.py tests/test_result_contract.py tests/test_units.py tests/test_cli_process.py`

Expected: all pass.

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider`

Expected: default suite passes without real smoke or benchmark.

- [x] **Step 5: Commit**

    git add src/abacus_forge/services.py src/abacus_forge/result.py src/abacus_forge/__init__.py tests/test_service_status.py tests/test_result_contract.py tests/test_units.py
    git commit -m "feat: add factual scf services"

### Task 5: Make execution control explicit and document the boundary

**Files:**
- Modify: `src/abacus_forge/services.py`
- Modify: `tests/test_service_status.py`
- Modify: `README.md`, `AGENTS.md`, `tests/README.md`

**Test strategy:** Typed execute never infers skip from log text. Only an explicit dry-run/skip request yields `execution=skipped`; deciding to repeat or use a new module remains caller-owned.

- [x] **Step 1: Write failing no-implicit-skip tests**

    def test_typed_execute_does_not_infer_skip_from_normal_end(tmp_path: Path) -> None:
        workspace = prepared_scf_workspace_with_log(tmp_path, "NORMAL END")
        result = ForgeServices.default().execute_scf(request_for(workspace, dry_run=False, executable=fake_abacus))
        assert result.status.execution == "completed"

    def test_typed_execute_dry_run_does_not_start_runner(tmp_path: Path) -> None:
        result = ForgeServices(fake_runner=FailIfCalled()).execute_scf(request_for(tmp_path / "w", dry_run=True))
        assert result.status.execution == "skipped"

- [x] **Step 2: Run RED**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py`

Expected: FAIL until typed execute uses explicit dry-run.

- [x] **Step 3: Implement and document**

Use `LocalRunner.run` directly for non-dry-run service execution and never call `_run_one_for_many`. Preserve `run_many` as legacy. Do not add scheduler, workflow, recovery, or scientific decision branches.

- [x] **Step 4: Run release-candidate gate**

    git diff --check
    conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
    PYTHONPATH=src python -m abacus_forge.cli --help
    rg -n "abacus-agent-tools|abacustest|aiida|ATP|MCP|Bohrium|DPDispatcher|slurm" src/abacus_forge pyproject.toml

Expected: whitespace and pytest exit 0; legacy help exits 0; scan finds no runtime dependency imports. The scan is text-level: comment/docstring mentions need manual triage, and AST boundary tests are the authoritative dependency gate.

- [x] **Step 5: Commit**

    git add src/abacus_forge/services.py README.md AGENTS.md tests/README.md tests/test_service_status.py
    git commit -m "docs: define factual operation boundary"

### Task 6: Harden operation admission and persistence failures

**Why this task exists:** The first implementation review proved that rejecting a duplicate only when appending the event is too late: prepare/modify/execute may already have changed files or started a process. A PID-based stale-claim cleanup also permits the same ID to replay after a crash. This task replaces that behavior; it does not add workflow recovery.

**Files:**
- Create: `src/abacus_forge/errors.py`
- Modify: `src/abacus_forge/workspace.py`
- Modify: `src/abacus_forge/services.py`
- Modify: `tests/test_workspace.py`, `tests/test_service_status.py`

**Interfaces and invariants:** Add typed internal exceptions for request/schema/path, operation conflict, precondition, persistence, and internal failures. Add a workspace operation guard that (1) holds an exclusive per-workspace operation lock, (2) atomically creates an admission record before domain writes or runner start, and (3) yields an opaque owner token required by event commit. An existing admission or event is always `operation.conflict`; do not inspect PID liveness or age. Delete admission only after the same owner has durably committed the event and manifest. On exception, crash, token mismatch, or persistence failure, retain admission as a tombstone. Do not promise rollback of already-written domain files.

- [x] **Step 1: Write RED integrity tests**

  Cover concurrent same-ID calls (only one reaches its supplied side-effect sentinel), different-ID calls against one workspace (serialized), a pre-created dead/stale admission (no runner and no domain mutation), wrong owner token (cannot commit), and injected event/manifest persistence failure (class 5 and same ID remains blocked).

- [x] **Step 2: Run RED**

  Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_workspace.py tests/test_service_status.py`

  Expected: FAIL because stale claims are reclaimed, ownership is not proved, and the service mutation window is not serialized.

- [x] **Step 3: Implement admission and typed persistence boundary**

  Validate the typed request and resolvable paths before acquiring admission where this is side-effect free. Then hold the operation guard across legacy primitive/runner execution and event commit. Replace exception-message parsing for conflict/persistence with typed exceptions. A controlled error after admission consumes the ID; callers use a new ID.

- [x] **Step 4: Run GREEN**

  Run the RED command, then `tests/test_contracts.py tests/test_result_contract.py tests/test_units.py`. Expected: all pass with no warning noise.

- [x] **Step 5: Commit**

    git add src/abacus_forge/errors.py src/abacus_forge/workspace.py src/abacus_forge/services.py tests/test_workspace.py tests/test_service_status.py
    git commit -m "fix: prevent typed operation replay"

### Task 7: Freeze the factual outcome surface and remove scientific policy

**Why this task exists:** The approved contract requires observations to reach both Python and the future machine CLI, while preserving the existing `forge.result/v1` shape. The reviewed branch also still routes typed services through a scientific policy registry. Both are contract violations.

**Files:**
- Modify: `src/abacus_forge/contracts.py`, `src/abacus_forge/services.py`, `src/abacus_forge/result.py`, `src/abacus_forge/__init__.py`
- Remove from the typed service surface: `src/abacus_forge/policies.py` and policy-only tests/exports if they were introduced solely by this branch
- Modify: `tests/test_contracts.py`, `tests/test_service_status.py`, `tests/test_result_contract.py`, `tests/test_units.py`

**Interfaces and invariants:** `Observation(name, value, source)` is frozen and JSON-safe. `OperationOutcome` has schema `forge.operation-outcome/v1`, `operation_id`, `envelope`, observations, `to_dict()/from_dict()`, and a delegating `status`; it is the success value of every typed SCF service. Its embedded `ForgeResultEnvelope.to_dict()` remains byte-compatible. Remove `policy_id` from all new requests, service validation, diagnostics, exports, and fixtures. Historical `OperationStatus.from_dict()` may read all four legacy `scientific` values, but every new Forge write is `unassessed`.

- [x] **Step 1: Write RED contract and failure-matrix tests**

  Round-trip `OperationOutcome`, assert its observations and operation ID survive serialization, assert the embedded result key set is unchanged, and reject non-JSON observations. Assert typed request schemas contain no `policy_id`. Cover execute nonzero, timeout/signal, missing executable, and an unexpected pre-start runner exception: started failures return outcome with execution facts; recognized missing executable is `precondition.missing`; unexpected pre-start failure is `internal.failure`. Cover collect with false/unavailable convergence without any accepted/guarded/rejected projection.

  The nonzero, timeout, and signal cases must include real `LocalRunner` subprocess coverage; hand-built `RunResult` diagnostics alone are insufficient. Add prepare/modify artifact regressions proving a symlink whose resolved target escapes the workspace is rejected. Freeze `ForgeErrorEnvelope.error_class` to the SPEC enum and prove unexpected parser/collector `ValueError` is `internal.failure`, not a request error.

- [x] **Step 2: Run RED**

  Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_contracts.py tests/test_service_status.py tests/test_result_contract.py`

  Expected: FAIL because the reviewed branch returns bare results, exposes policy fields, and lacks the complete typed failure matrix.

- [x] **Step 3: Implement the outcome and factual mappings**

  Translate engine/collector facts directly into observations, checks, metrics, artifacts, and status. Persist the serialized outcome facts in the event payload without nesting a second workflow record. Use the stable typed error classes from Task 6; never classify by matching exception text. If removing a tracked file, follow the repository deletion contract by moving it to `$HOME/scratch` before recording its deletion.

- [x] **Step 4: Run release-candidate gate**

    git diff --check
    conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
    PYTHONPATH=src python -m abacus_forge.cli --help
    rg -n "policy_id|evaluate_abacus_scf|abacus-agent-tools|abacustest|aiida|ATP|MCP|Bohrium|DPDispatcher|slurm" src/abacus_forge pyproject.toml

  Expected: diff and suite pass; legacy help exits 0; no typed-service policy/runtime dependency remains. Text matches in historical compatibility comments require manual triage.

- [x] **Step 5: Commit**

    git add src/abacus_forge tests README.md AGENTS.md
    git commit -m "feat: expose factual operation outcomes"

### Task 8: Close primitive exception classification

**Decision source:** 2026-09-04 final-fix scoped re-review reproduced that `prepare_unit()` and `modify_unit()` internal `ValueError` exceptions are still exposed as `request.invalid`; the user explicitly authorized a new follow-up phase. This task is a bounded correction to the frozen error matrix, not a new final-review fix wave.

**Files:**
- Modify: `src/abacus_forge/services.py`
- Modify: `tests/test_service_status.py`

**Test strategy:** Inject unexpected `TypeError` and `ValueError` independently at the prepare and modify primitive boundaries. Every case must return `ForgeErrorEnvelope(error_class="internal.failure")`, retain the admission tombstone, append no success event, and make the same operation ID conflict on reuse. Existing explicit request type/path/schema tests must continue to return their frozen request classes before primitive invocation.

- [x] **Step 1: Write RED regression tests**

  Add a table-driven regression for prepare/modify × `TypeError`/`ValueError`. Assert error class, no event, retained admission, and same-ID conflict. Do not assert implementation source text.

- [x] **Step 2: Run RED**

  Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py -k 'primitive_internal_error'`

  Expected: FAIL because prepare/modify currently wrap primitive `TypeError`/`ValueError` as `ForgeRequestError`.

- [x] **Step 3: Implement the narrow exception boundary**

  Remove the broad primitive exception wrappers. Only explicit `ForgeRequestError` subclasses created by typed request/path/schema validation may map to request errors; untyped primitive/parser/runner exceptions fall through to `internal.failure`. Do not parse exception messages and do not change success, admission, outcome, legacy API/CLI, or scientific boundaries.

- [x] **Step 4: Run GREEN and regression**

  Run the RED command, then:

    conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py tests/test_contracts.py tests/test_workspace.py tests/test_result_contract.py tests/test_units.py

  Expected: all pass without warning noise.

- [x] **Step 5: Commit**

    git add src/abacus_forge/services.py tests/test_service_status.py
    git commit -m "fix: classify primitive defects as internal"

## Deliberately deferred plans

1. Agent-first CLI: operation, schema, capabilities, and JSON error/exit mapping consume Forge facts without adding scientific policy.
2. Capability migration: relax, MD, postprocess, PyATB, and property packs get individual unit-operation contracts and real-smoke evidence.
3. Paimon adapter/acceptance: create the independent `paimon-v3` repository only after the typed operation output is stable. It owns scientific criteria, interpretation, orchestration, scheduler/platform adapters, benchmark parity, and real ABACUS/PyATB acceptance. The current app-tools toolbox remains the Paimon v1.2 release surface rather than a duplicate v3 source tree.
4. Optional TUI shell: after the Python API and machine CLI are stable, add a VASPKIT/AbacusCopilot-style human shell if needed. It may prompt, navigate, preview parameters, and render results, but must call the same API or structured CLI envelope and must not own operation semantics, scientific judgment, orchestration, or scheduling.

## Plan self-review

- **Spec coverage:** Tasks 1–2 establish typed requests and additive event identity; Task 3 defines factual status/observations; Tasks 4–5 build the SCF slice and explicit execution control; Tasks 6–7 close the post-implementation review gaps in pre-side-effect admission, typed failure mapping, machine observation transport, and scientific-policy removal; Task 8 closes the last reproduced primitive-error classification defect.
- **Scope discipline:** v1 CLI and Paimon adapter are deferred because both must consume, not shape, the stable Forge operation contract.
- **Type consistency:** services consume Task 1 requests, persist via Task 2, and return Task 3 facts without a Forge scientific policy layer.
- **Review revisions (2026-09-04):** the first review/fix wave was not accepted as complete. Tasks 6–7 replace late duplicate rejection and stale-claim reclaim, require owner proof and same-workspace serialization, distinguish persistence failures by type, freeze `OperationOutcome` as the Agent-visible observation carrier, remove typed-service scientific policy, and add the missing failure matrix. These are contract corrections, not new workflow, recovery, scheduling, or scientific responsibilities.
- **Final-review closure (2026-09-04):** before integration, Task 7 also closes strict public error-class validation, explicit request-error conversion, real `LocalRunner` signal/timeout/nonzero evidence, symlink resolved-target containment for prepare/modify evidence, stale policy wording in README/AGENTS/test guidance, and removal of unused facade state. These enforce already-approved contracts; they do not expand Forge's role.
- **Authorized follow-up (2026-09-04):** the Task 7 final-fix re-review left one load-bearing defect at the prepare/modify primitive boundary. The user confirmed a new follow-up phase; Task 8 removes that broad exception wrapper and requires its own task review before a new whole-branch review.
- **Task 8 whole-branch closure (2026-09-04):** the new whole-branch review found four remaining implementation gaps governed by existing requirements: prepare asset existence checks must occur after admission while pure containment remains before it; launcher executables require the same pre-start classification as the engine executable; admission/lock filesystem failures are persistence failures; execute artifacts, metrics, termination, and observations must carry unambiguous runtime/execute provenance. They are handled together by the one permitted final fix wave.
