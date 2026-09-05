# Forge Relax Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver experimental relax/cell-relax prepare, modify, execute and collect through the same typed Python services and machine CLI, with factual collection and portable artifacts.

**Spec:** `docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html` and `docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html#stage4-relax` (the latter governs detailed status/CLI semantics).

**Authorization:** 2026-09-06 thread goal explicitly authorizes SPEC reconciliation, inventory, writing-plans and SDD implementation following the proposed Stage 4 first batch (relax/cell-relax). This plan delivers that batch, not all of Stage 4 or a stable release. MD, independent postprocess/export, PyATB and the Stage 5 Paimon repository remain distinct subsequent deliverables.

**Architecture:** Four new Relax request classes carry an explicit capability selector and share existing phase-specific validation. Common ABACUS operation mechanics are factored once behind SCF and Relax service sets; a small compatibility bridge may still call existing prepare_unit/modify_unit primitives, but no new request exposes UnitSpec. The machine adapter chooses a typed decoder/service set from the explicit selector; collection returns parsed arrays and final structure through outer observations without changing forge.result/v1.

**Tech Stack:** Python 3.10+, dataclasses, typing.Protocol, pathlib, existing ABACUS parser/LocalRunner/Workspace, pytest; existing paimon conda environment.

## Global Constraints

- Preserve existing SCF constructors and wire serialization, legacy CLI/parser/API/files, forge.result/v1 keys, seven error classes and exit 0/2/3/4/5.
- Each request causes one operation, guarded by existing workspace admission/event persistence; no multi-operation runner, retry, recovery, scheduler or scientific acceptance logic.
- New Relax requests use forge.request/v1 and explicit capability `relax` or `cell-relax`. Missing selector in machine input remains the existing SCF path; unknown selectors are request.invalid/2, invalid known request fields request.schema/2.
- Artifacts remain inside workspace, with workspace-relative paths and operation-scoped refs. New services share a single artifact-ref construction point.
- Relax calculation consistency is input validation: prepare/modify reject contradictory calculation and modify removal; execute validates existing INPUT before launching; collect may use an externally prepared directory without prior Forge events.
- Keep all advertised capabilities experimental until capability-specific real operation evidence exists. Offline tests never launch a cluster or real ABACUS.
- Scientific validation, task orchestration and platform scheduling belong to humans/Agents. Report convergence observations without inventing missing values or using them as collection completeness.

## Inventory and batch boundaries

Baseline: `c6b7dbf`; isolated branch `forge-stage4-relax`. Fresh offline gate returned exit 0, `348 passed, 2 skipped`.

| Area | Existing evidence | Work required / batch |
| --- | --- | --- |
| SCF machine/API | contracts.py Scf*Request; services.py ScfServiceSet; machine_cli.py; Stage 3 merge a800b64 | Preserve bytes/semantics; broaden service internals only where required here. |
| relax/cell-relax input | api.py prepare_unit/modify_unit; prepare_profiles.py task defaults; tests/test_units.py cell-relax tests | New phase requests, explicit calculation consistency and narrow services, this batch. |
| relax collection | api.py collect/_final_structure_snapshot; collectors/abacus.py forces/stress/relax metrics; tests/test_api.py flat cell-relax fixture | Reuse parsing, project arrays/final structure as observations; test completeness independent of convergence, this batch. |
| MD | tasks.py run_md; prepare_profiles.py MD profile; collectors/abacus.py MD_dump parser | Subsequent typed MD batch with its own request fields and trajectory evidence. |
| postprocess/export | api.py _postprocess_unit_before_collect/export; machine_cli.py currently rejects both verbs | Subsequent independent operation contracts; do not wrap implicit collect+export as one new operation. |
| PyATB | pyatb.py prepare_pyatb_band/run_pyatb/collect_pyatb; tests/test_pyatb.py fixtures | Subsequent engine-specific batch with explicit matrix/artifact inputs. |
| real evidence | tests/real_smoke/test_abacus_smoke.py currently only legacy SCF | Add opt-in typed Relax path; no supplied real Relax environment at planning time, no stable claim. |

Stage 3 maintenance carried into touched areas: successful narrow prepare/modify calls, injected runner precedence regression (Task 2); path-specific process parity normalization (Task 3). Workspace claim alias cleanup stays at its previously documented admission-change trigger.

## File map

| File | Responsibility |
| --- | --- |
| src/abacus_forge/relax_contracts.py | Four Relax requests, explicit capability and calculation validation, sharing existing phase validators. |
| src/abacus_forge/services.py | Shared ABACUS operation implementation, retained SCF public services, RelaxServiceSet and narrow typed protocols. |
| src/abacus_forge/relax_results.py | Factual Relax collection projection and outer observations. |
| src/abacus_forge/discovery.py | Capability/request registry and schema for new requests. |
| src/abacus_forge/machine_cli.py | Selector decoding and one-service dispatch. |
| src/abacus_forge/__init__.py | Public Relax requests/service set exports. |
| tests/test_contracts.py, tests/test_service_status.py | Extend existing request and service behavior suites. |
| tests/test_machine_cli.py, tests/test_cli_process.py, tests/test_architecture.py | Discovery, dispatch, process parity, current advertised capability assertions. |
| tests/real_smoke/test_abacus_smoke.py, tests/real_smoke/README.md | Opt-in typed Relax operation evidence. |
| README.md, tests/README.md, ROADMAP.md | Actual delivered surface and evidence limits. |

### Task 1: Relax typed requests

**Files:** Create `src/abacus_forge/relax_contracts.py`; modify `src/abacus_forge/__init__.py`, `tests/test_contracts.py`.

**Test strategy:** Extend the existing contract suite; no new test file or temporary probes. Parameterize both capability values across all four operations, round trips and negative cases; verify old SCF wire key sets remain unchanged.

**Interfaces:** Produces `RelaxPrepareRequest`, `RelaxModifyRequest`, `RelaxExecuteRequest`, `RelaxCollectRequest`. Each is an immutable dataclass reusing corresponding Scf phase fields and validation, with required keyword-only `capability: Literal['relax', 'cell-relax']`. `to_dict()` includes capability; `from_dict()` requires it. Prepare/modify reject contradictory calculation before any service side effect; remove_parameters cannot include calculation. Execute/collect retain existing phase resource/workspace fields.

- [ ] **Step 1: Add failing round-trip and validation cases.** Use the existing UUID fixture style. Representative test:

```python
@pytest.mark.parametrize('capability', ['relax', 'cell-relax'])
def test_relax_prepare_round_trip(capability):
    request = RelaxPrepareRequest(
        operation_id='123e4567-e89b-42d3-a456-426614174000',
        workspace_rel='job', capability=capability,
        structure_path_rel='source.STRU', parameters={'calculation': capability},
    )
    assert request.to_dict()['capability'] == capability
    assert RelaxPrepareRequest.from_dict(request.to_dict()) == request
    with pytest.raises(ValueError):
        RelaxPrepareRequest(operation_id=request.operation_id, workspace_rel='job',
                            capability=capability, structure_path_rel='source.STRU',
                            parameters={'calculation': 'scf'})
```

Add missing/unknown/non-string capability, unknown fields, operation mismatch, invalid UUID/path, non-JSON parameters, modify calculation removal, invalid execute resources, and strict SCF unchanged-wire checks in the same parameterized families.

- [ ] **Step 2: Run RED:** `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_contracts.py` → missing Relax types or failing new assertions.
- [ ] **Step 3: Implement immutable request extensions.** Reuse Scf phase validation through inheritance; factor selector validation/serialization into one small mixin rather than duplicating four serializers. Required field shape:

```python
@dataclass(frozen=True, slots=True)
class RelaxPrepareRequest(_RelaxCapabilityMixin, ScfPrepareRequest):
    capability: Literal['relax', 'cell-relax'] = field(kw_only=True)
```

The mixin validates literal capability, delegates `__post_init__` and `to_dict` to the phase class, and appends capability. Prepare and modify add calculation consistency validation using exact string values; direct constructor and from_dict must agree. Do not modify legacy SCF wire fields or loosen unknown-field rejection. New service dispatch in Task 2 must distinguish Relax subclasses from SCF instead of relying on broad isinstance alone.

- [ ] **Step 4: Run GREEN:** same contract command plus `tests/test_workspace.py tests/test_result_contract.py tests/test_units.py tests/test_service_status.py` → all pass.
- [ ] **Step 5: Consolidate validation cases by constructor/operation and inspect diff; no duplicate production validators.** Run `git diff --check` → exit 0.
- [ ] **Step 6: Commit:** `git add src/abacus_forge/relax_contracts.py src/abacus_forge/__init__.py tests/test_contracts.py` then `git commit -m "feat: add typed relax operation requests"`.

### Task 2: Shared narrow services and factual Relax collection

**Files:** Modify `src/abacus_forge/services.py`, `src/abacus_forge/__init__.py`, `tests/test_service_status.py`; create `src/abacus_forge/relax_results.py`.

**Test strategy:** Extend the existing service suite using ASE Si structures, existing fake executable helper and parser fixtures. New result module is a distinct projection responsibility, not a new parser. No new test file; no temporary probes. Verify every operation for both capability values through real service calls, identity/events/artifacts, empty exceptions and no side effects on invalid requests.

**Interfaces:** Consumes four Relax requests. Produces `RelaxServiceSet.default(workspace_root='.', runner_factory=LocalRunner)` with `.prepare.prepare`, `.modify.modify`, `.execute.execute`, `.collect.collect`, each returning `OperationOutcome | ForgeErrorEnvelope`. Existing ScfServiceSet/Scf*Service/ForgeServices remain source compatible. `relax_results.collection_envelope(result: CollectionResult, workspace_rel: str) -> ForgeResultEnvelope` and `collection_observations(result: CollectionResult) -> tuple[Observation, ...]` supply Relax projection. Shared persistence accepts optional extra observations and constructs artifact refs exactly once.

- [ ] **Step 1: Add failing operation scenarios.** For each capability prepare a source STRU from `AbacusStructure(Atoms('Si', positions=[[0,0,0]], cell=[4,4,4], pbc=True)).to_stru()`, invoke prepare and read INPUT/profile; modify `ecutwfc` and inspect file and snapshots; execute `write_fake_abacus` with zero/nonzero/timeout and assert outcome/event/exit facts; collect a parser fixture with output energy and final STRU. Each invocation uses a distinct UUID; repeated ID must leave files/events unchanged. Representative dispatch/assertions:

```python
services = RelaxServiceSet.default(workspace_root=tmp_path)
request = RelaxExecuteRequest(operation_id=str(uuid.uuid4()), workspace_rel='job',
                              capability='cell-relax', dry_run=True)
outcome = services.execute.execute(request)
assert outcome.status.execution == 'skipped'
assert outcome.status.scientific == 'unassessed'
assert outcome.operation_id == request.operation_id
```

Also test request/service family mismatch, execute calculation mismatch (no runner start), external collect with no Forge manifest, nested forces/stress and final structure observations, missing-output/partial/complete, and complete data with convergence false/absent. Include electronic convergence present but relax report lacking a converged key: no ionic convergence may be synthesized in either nested diagnostics or observations. Include complete data without optional time/report JSON and genuine final-structure parse failure as distinct cases. Test final structure references are relative and escaped symlink is rejected or excluded with partial diagnostics. Extend SCF successful narrow prepare/modify and conflicting request-vs-injected-runner precedence regressions while this shared boundary is touched.

- [ ] **Step 2: Run RED:** `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py` → missing RelaxServiceSet/new behavior.
- [ ] **Step 3: Factor shared operations and implement Relax projection.** Parameterize private ABACUS operation classes by expected request type and task resolution; preserve public SCF service classes and signatures. Shared mechanics own containment, admission, primitive call, error mapping, persistence. Relax task comes from validated capability; no default SCF fallthrough for a Relax instance. At the narrow compatibility call only, use existing prepare_unit/modify_unit with resolved task, never run_task/execute_unit workflow shortcuts. Verify existing INPUT calculation for execute/collect when INPUT exists; absent collect INPUT is allowed for external output directories. Existing SCF behavior stays compatible.

```python
# Shared persistence shape; extra observations are already factual parser values.
outcome = OperationOutcome(
    operation_id=request.operation_id,
    envelope=_with_artifact_refs(envelope, request.operation_id),
    observations=tuple({o.name: o for o in (*_observations(envelope), *extra_observations)}.values()),
)
```

For Relax collection, call existing `collect(workspace)` without automatic postprocess. Use its artifact/metric records as the base; override collection completeness from available selected logs, parsed total_energy, final_structure_snapshot and structured parser diagnostics, never result.status/convergence. No nonempty selected log (`log_sources == 0`) → missing_output; absent energy/final structure or ambiguous log/final-structure selection or final_structure_parse_error → partial; otherwise complete. Do not treat the legacy warnings list as a completeness predicate: it includes absent convergence markers and optional time/report files. Retain those warnings as diagnostics only. execution=not_run, scientific=unassessed. Include arrays/dictionaries already parsed as source='parser' observations (forces, stress, relax metrics/summary) and available initial/final structure snapshots as source='file'. Derive electronic convergence observation from existing matched_converged_markers/matched_nonconverged_markers: negative evidence → false, positive only → true, neither → omit or null; remove the legacy default-false converge/converged metric/check from the new Relax projection when no marker exists. Preserve ionic convergence only when an explicit key exists in parsed relax_metrics; do not copy the legacy relax_summary fallback from electronic convergence. Emit final structure ArtifactRecord through the existing contained result conversion. Keep legacy CollectionResult.to_dict/to_envelope unchanged for legacy and SCF callers.

- [ ] **Step 4: Run GREEN:** `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py tests/test_contracts.py tests/test_workspace.py tests/test_result_contract.py tests/test_units.py tests/test_api.py` → all pass.
- [ ] **Step 5: Refactor duplicated operation logic and test setup; run the same gate and `git diff --check`.** Production must have one admission/persistence path per operation, not copied SCF and Relax method bodies.
- [ ] **Step 6: Commit:** `git add src/abacus_forge/services.py src/abacus_forge/relax_results.py src/abacus_forge/__init__.py tests/test_service_status.py` then `git commit -m "feat: expose factual relax operation services"`.

### Task 3: Capability discovery and machine/API parity

**Files:** Modify `src/abacus_forge/discovery.py`, `src/abacus_forge/machine_cli.py`, `tests/test_machine_cli.py`, `tests/test_cli_process.py`, `tests/test_architecture.py`.

**Test strategy:** Extend current discovery/decoder/process suites; no new test files or temporary probes. Existing assertions claiming only SCF must become exact three-capability assertions; preserve unsupported MD/postprocess/PyATB checks with unsupported selectors. Retain old SCF decoding tests.

**Interfaces:** `decode_operation_request(operation: str, payload: object)` selects existing SCF decoder when capability missing and Relax decoder for relax/cell-relax. Keep `decode_scf_request` unchanged for its existing callers. `run_machine_cli` retains signature and injected services compatibility; default service selection follows decoded request type. `request_schema_document` supports all four operations for both new capabilities and includes required capability enum/const appropriate to the requested capability.

- [ ] **Step 1: Add failing discovery, decoder and real process tests.** Example wire payload:

```python
payload = {'schema_version': 'forge.request/v1', 'operation': 'execute',
           'operation_id': str(uuid.uuid4()), 'workspace_rel': 'job',
           'capability': 'cell-relax', 'dry_run': True}
completed = run_cli('operation', 'execute', '--stdin', cwd=tmp_path,
                    input_text=json.dumps(payload))
assert completed.returncode == 0
assert completed.stderr == ''
assert json.loads(completed.stdout)['envelope']['status']['execution'] == 'skipped'
```

Test descriptors in deterministic order scf/relax/cell-relax, actual artifact roles input/provenance_manifest/output, experimental maturity; schema reflection and actual to_dict fields for each new request; unknown/non-string/null selector, conflicting calculation, bad paths, schema/version errors. Real subprocess request-file prepare/modify/collect scenarios for both capabilities must match direct API serialized outcomes from isolated roots and separate IDs, normalizing only operation IDs/refs and explicitly path-bearing diagnostics (not arbitrary strings). Assert error/exit and no service calls for invalid requests. Existing process failure classes remain covered.

- [ ] **Step 2: Run RED:** `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_machine_cli.py tests/test_cli_process.py tests/test_architecture.py` → unsupported Relax selectors/discovery.
- [ ] **Step 3: Implement explicit registry dispatch.** Share common schema property builders; add required capability with per-document const. Maintain dataclass-fields/to_dict drift validation and JSON-safe detached discovery documents. Validate transport first and require selector be a string before dictionary lookup; unknown values raise ForgeRequestError. Use RelaxServiceSet for Relax request instances and ScfServiceSet for existing requests, then existing `_dispatch`/render/exit mapping unchanged.

```python
capability = payload.get('capability', 'scf')
if not isinstance(capability, str) or capability not in {'scf', 'relax', 'cell-relax'}:
    raise ForgeRequestError('unknown capability')
```

The existing SCF schema does not acquire a capability property: absent selector remains its frozen request; explicit scf is rejected by its existing strict field decoder. Do not add top-level CLI flags or route according to directory names.

- [ ] **Step 4: Run GREEN:** same RED command plus `tests/test_contracts.py tests/test_service_status.py` → all pass.
- [ ] **Step 5: Consolidate scenario matrices and narrow the existing parity root normalizer to actual path-bearing diagnostics/fields.** Verify non-path string content remains observable. Run `git diff --check`.
- [ ] **Step 6: Commit:** stage the five named files and `git commit -m "feat: route relax capabilities through machine CLI"`.

### Task 4: Public usage, opt-in smoke and final acceptance

**Files:** Modify `README.md`, `tests/README.md`, `ROADMAP.md`, `tests/real_smoke/test_abacus_smoke.py`, `tests/real_smoke/README.md`; update this plan's completion record.

**Test strategy:** Add an opt-in typed Relax execute/collect smoke to the existing real_smoke module; no default real process execution, no new marker. Current offline process tests prove the documented commands and requests. Do not add prose substring tests.

**Interfaces:** Environment `ABACUS_FORGE_RELAX_SMOKE_WORKSPACE`, `ABACUS_FORGE_ABACUS_EXECUTABLE`, `ABACUS_FORGE_RELAX_SMOKE_CAPABILITY` (default relax, only relax/cell-relax) feed a copied temporary prepared workspace. Test calls machine CLI execute then collect using distinct IDs and verifies serialized outcome/event/artifact facts; the sequence exists only in the external test harness.

- [ ] **Step 1: Implement the opt-in test using existing real-smoke environment/file validation style.** Missing environment skips with a precise reason; supplied invalid path/capability/executable fails. Copy source into tmp_path, run real machine commands and assert returncode=0, execution completed, collected energy numeric, final structure artifact present and relative, and scientific unassessed. Do not assert a physical convergence threshold or call the legacy execute_unit path for the new evidence.
- [ ] **Step 2: Verify offline opt-out:** `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/real_smoke/test_abacus_smoke.py` → smoke tests skipped. If supplied real inputs exist, run `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider --run-real-smoke tests/real_smoke/test_abacus_smoke.py -k typed_relax` and retain full output; otherwise report real evidence unavailable, capability stays experimental.
- [ ] **Step 3: Document actual API and JSON usage.** Include a RelaxPrepareRequest example and a machine request with explicit capability; record four supported operations, phase boundaries, collection facts, maturity and remaining Stage 4 batches. Update stale SCF-only prose while retaining executable README examples exercised by tests.
- [ ] **Step 4: Final offline gate:** `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider` → no failures; opt-in skips recorded separately. Run `conda run -n paimon env PYTHONPATH=src python -m abacus_forge.cli capabilities` and `conda run -n paimon env PYTHONPATH=src python -m abacus_forge.cli schema cell-relax prepare` → parseable actual discovery; `git diff --check` → exit 0.
- [ ] **Step 5: Record completion with exact commits, raw command output locations, outcomes and unavailable real evidence.** Do not mark all Stage 4 complete or promote maturity.
- [ ] **Step 6: Commit:** stage the named docs/smoke files and `git commit -m "docs: publish experimental relax machine operations"`.

## Review and completion

Each task gets an independent spec/quality review and revision-bound verification evidence. Final review covers the complete branch, both SPECs, this plan and deferred findings. Fix verified gaps via SDD and re-review. No stable-release claim without real evidence; no push or remote publication is included. The first-batch deliverable is complete only when both Relax capabilities work through four typed API/CLI operations with consistent profiles, portable artifacts, factual collection, unchanged SCF/legacy regression and clean review.

## Plan self-review

- SPEC requirements R1–R4: Tasks 1–3; R5–R8 factual projection, runner/admission and compatibility: Task 2 and process coverage in Task 3; R9–R10 upper-layer and dependency boundary remain unchanged and are covered by existing architecture gate.
- Interfaces: Task 1 produces four phase request classes; Task 2 consumes them and produces RelaxServiceSet; Task 3 binds exactly that set and those classes; Task 4 documents and exercises the public machine path.
- Stage 4 remaining batches and Stage 5 release work are explicit in the inventory; this plan implements the authorized first batch. No task introduces an implicit operation sequence into production.
