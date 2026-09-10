# Forge Typed MD Operations Implementation Plan

> **Scope note (2026-09-10):** This completed plan covers the original four-operation typed MD slice. The standalone `md.postprocess` operation is now specified and implemented separately by `docs/superpowers/specs/2026-09-10-forge-typed-md-postprocess-design.html` and `docs/superpowers/plans/2026-09-10-forge-typed-md-postprocess.md`; the historical deferral below does not describe the current capability registry.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose an experimental `md` capability through the existing typed `prepare`/`modify`/`execute`/`collect` Python and machine-CLI surfaces without adding workflow, scheduler, restart, monitoring, or scientific-acceptance semantics.

**Spec:** `docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html` — especially `#boundary`, `#status`, `#architecture`, `#testing`, and the Stage 4 rollout paragraphs in `#rollout`.

**Architecture:** Add four MD request subclasses that reuse the existing SCF request fields and asset materialization rules, but carry an explicit `capability="md"` and enforce `calculation=md`. Route them through the existing per-operation service implementations, workspace admission/event persistence, runner, collector, discovery registry, and machine CLI. The first slice deliberately uses the existing factual ABACUS collector; `MD_dump` parsing, trajectory conversion, monitoring, restart orchestration, and postprocess/export remain separate future work.

**Tech Stack:** Python 3.10+, frozen dataclasses, existing Forge `Workspace`/service/envelope contracts, `pytest`, JSON machine CLI.

## Global Constraints

- Keep `md` maturity `experimental`; do not promote it to a stable Paimon v1.3 surface (`#rollout`, Stage 4).
- Preserve the existing `forge.request/v1`, `forge.result/v1`, error classes, operation identity, admission/tombstone, artifact and event semantics (`#requirements`, R1–R8).
- Reuse `ScfPrepareRequest`/`ScfModifyRequest`/`ScfExecuteRequest`/`ScfCollectRequest` fields; MD-specific controls remain in the JSON-safe `parameters` map and are not re-frozen as a second parameter table.
- The Forge default MD profile remains PBE/NVE with the existing defaults in `src/abacus_forge/prepare_profiles.py`; caller-supplied parameters may override them.
- `execute` only starts one configured local runner; no Slurm, Bohrium, DPDispatcher, MPI launcher, platform job ID, retry/resume, or workflow graph enters the request or service.
- `collect` returns logs, metrics, `MD_dump` observations and artifact references as facts; it must not state that a trajectory, simulation, or physical result is scientifically acceptable.
- Legacy `run_md`, legacy CLI, `UnitSpec`, result dictionaries and file layouts remain unchanged.
- Every behavior change follows RED → GREEN → focused regression → commit; final claims require the exact test command and diff evidence.

## File Map

- Create `src/abacus_forge/md_contracts.py`: the four immutable MD request types and calculation/capability validation only.
- Modify `src/abacus_forge/services.py`: recognize MD requests, prevent SCF fall-through, and expose `MdServiceSet` through the same private context and narrow protocols.
- Modify `src/abacus_forge/discovery.py`: register `md`, its four request schemas, descriptor and representative request.
- Modify `src/abacus_forge/machine_cli.py`: decode and route `md` requests; no second CLI implementation.
- Modify `src/abacus_forge/__init__.py`: export the typed MD request classes and service set without changing legacy exports.
- Create `tests/test_md_contracts.py`, `tests/test_md_services.py`, and `tests/test_md_machine_cli.py`: keep contract, service/collection-fact, and machine/API parity coverage in independently reviewable suites; extend `tests/test_machine_cli.py` only for registry-level assertions if shared fixtures are clearer.
- Modify `README.md` and `ROADMAP.md`: describe the experimental typed MD surface and explicitly defer MD postprocess, monitoring, restart and scheduling.
- Modify `docs/superpowers/plans/2026-09-10-forge-typed-md-operations.md`: check off completed tasks and append verification/review evidence; do not duplicate the SPEC.

## Task 1: Freeze MD request contracts

**Files:**
- Create: `src/abacus_forge/md_contracts.py`
- Create: `tests/test_md_contracts.py`

**Test strategy:** Contract round-trip and rejection tests own this new public boundary. Use the existing `tests/test_contracts.py` patterns and the approved Relax contract shape as references. No temporary probes.

**Interfaces:**
- Consumes: base request dataclasses and `_require_matching_calculation` pattern from `src/abacus_forge/relax_contracts.py`.
- Produces: `MdPrepareRequest`, `MdModifyRequest`, `MdExecuteRequest`, `MdCollectRequest`, each serializing the base fields plus `capability: "md"` and accepting the same `forge.request/v1` operation fields.

- [x] **Step 1: Write failing tests**
  - Round-trip all four request types through `to_dict()`/`from_dict()`.
  - Assert prepare preserves explicit `pseudo_sources`, `orbital_sources`, `asset_mode`, and arbitrary JSON-safe MD parameters.
  - Assert prepare rejects `parameters={"calculation": "scf"}` and modify rejects an update to another calculation or removal of `calculation`.
  - Assert unknown serialized fields are rejected and `capability != "md"` is rejected.
- [x] **Step 2: Run the owning tests and verify RED**
  - Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_md_contracts.py`
  - Expected: collection/import or assertion failures because the MD request module/types do not exist.
- [x] **Step 3: Implement the minimal contracts**
  - Mirror the Relax mixin, but use a single literal capability `md`.
  - Keep all MD controls in inherited `parameters`; do not add `md_type`, thermostat, pressure, seed, restart, or trajectory fields to the request dataclasses.
  - Enforce `parameters["calculation"] == "md"` when supplied; prohibit changing/removing `calculation` in modify.
- [x] **Step 4: Run the owning tests and verify GREEN**
  - Run the command from Step 2; expected: all MD contract tests pass.
- [x] **Step 5: Run adjacent contract regressions**
  - Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_contracts.py tests/test_structure.py`
  - Expected: existing contract and structure tests remain green.
- [x] **Step 6: Commit**
  - `git add src/abacus_forge/md_contracts.py tests/test_md_contracts.py && git commit -m "feat: add typed MD request contracts"`

## Task 2: Route MD through typed services

**Files:**
- Modify: `src/abacus_forge/services.py`
- Modify: `src/abacus_forge/__init__.py`
- Create: `tests/test_md_services.py`

**Test strategy:** Use the existing fake ABACUS executable and workspace helpers from `tests/support`. Verify only operation mechanics and factual output. Include a negative test that a typed MD request cannot be accepted by `ScfServiceSet`.

**Interfaces:**
- Consumes: the four `Md*Request` types from Task 1 and the existing `_PrepareService`, `_ModifyService`, `_ExecuteService`, `_CollectService` implementations.
- Produces: `MdServiceSet.default(workspace_root, runner_factory)` with `.prepare`, `.modify`, `.execute`, `.collect` members implementing the existing narrow protocols.

- [x] **Step 1: Write failing tests**
  - `MdServiceSet.prepare` writes `inputs/INPUT` with `calculation=md`, retains the PBE/NVE profile defaults, and records the same typed envelope/event/provenance shape as SCF/Relax.
  - `MdServiceSet.modify` refuses a calculation change and otherwise returns before/after snapshots.
  - `MdServiceSet.execute` supports the inherited dry-run and local fake-runner path, returning only execution facts and `scientific=unassessed`.
  - `MdServiceSet.collect` accepts an externally prepared workspace with `calculation=md`, returns existing `md_steps`/`md_dump_summary` parser facts when available, and never adds a scientific acceptance conclusion.
  - `ScfServiceSet` rejects `Md*Request` as `request.invalid`; `MdServiceSet` rejects SCF/Relax request types.
- [x] **Step 2: Run tests and verify RED**
  - Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_md_services.py`; expected: missing service/routing failures.
- [x] **Step 3: Implement minimal routing**
  - Extend `_AbacusServiceContext.task_for` to return `md` for MD requests.
  - Extend `accepts_request` exclusions so SCF never consumes Relax or MD subclasses and each capability set accepts only its own request type.
  - Add `MdServiceSet` using `validate_input_calculation=True`, exactly like Relax, without adding a new service implementation or facade.
  - Export `MdServiceSet` and MD request classes from `abacus_forge.__init__`.
- [x] **Step 4: Run tests and verify GREEN**
  - Run focused `tests/test_md_services.py`; expected: all service tests pass.
- [x] **Step 5: Run service/status regressions**
  - Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py tests/test_result_contract.py tests/test_tasks.py`
  - Expected: existing SCF/Relax/legacy behavior remains green.
- [x] **Step 6: Commit**
  - `git add src/abacus_forge/services.py src/abacus_forge/__init__.py tests/test_md_services.py && git commit -m "feat: expose typed MD services"`

## Task 3: Add discovery and machine-CLI parity

**Files:**
- Modify: `src/abacus_forge/discovery.py`
- Modify: `src/abacus_forge/machine_cli.py`
- Create: `tests/test_md_machine_cli.py`
- Modify: `tests/test_machine_cli.py`

**Test strategy:** Discovery/schema tests verify dataclass-to-wire parity and truthful descriptors. Process tests send the same request through the machine CLI and direct MD service using isolated workspaces/IDs. Unknown capabilities and unsupported MD operations must use existing `request.invalid`/exit 2 semantics.

**Interfaces:**
- Consumes: `Md*Request` and `MdServiceSet` from Tasks 1–2.
- Produces: `capabilities` entry `md` with maturity `experimental`, engine `abacus`, operations `prepare|modify|execute|collect`, inputs and artifact roles matching actual output (`input`, `provenance_manifest`, `output`); `schema md <operation>` documents the inherited request fields.

- [x] **Step 1: Write failing tests**
  - `capabilities_document()` includes exactly the four MD operations and no postprocess/export claim.
  - `request_schema_document("md", op)` round-trips representative requests and rejects schema/property drift.
  - Machine `operation prepare|modify|execute|collect` decodes `capability=md`, routes to `MdServiceSet`, emits one JSON envelope, and has the same status/artifact facts as direct service invocation in an isolated workspace.
  - `schema md postprocess` and `schema md export` return `request.invalid`/2; `operation postprocess|export` with `capability=md` also returns `request.invalid`/2.
- [x] **Step 2: Run tests and verify RED**
  - Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_md_machine_cli.py tests/test_machine_cli.py`
  - Expected: MD is absent from discovery/decoder/routing.
- [x] **Step 3: Implement registry and routing**
  - Add `MD_REQUEST_TYPES`/decoder entries, the descriptor and representative request to discovery.
  - Add `md` to machine capability decoders and route decoded `Md*Request` to `MdServiceSet`.
  - Keep parser operation choices and generic `ForgeRequest` operation set unchanged; do not create a `post` alias or legacy CLI branch.
- [x] **Step 4: Run tests and verify GREEN**
  - Run the command from Step 2; expected: discovery, schema and CLI parity tests pass.
- [x] **Step 5: Run process/architecture gates**
  - Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_cli_process.py tests/test_architecture.py`
  - Expected: stdout/error envelope, exit classes, forbidden-import and CLI architecture gates remain green.
- [x] **Step 6: Commit**
  - `git add src/abacus_forge/discovery.py src/abacus_forge/machine_cli.py tests/test_md_machine_cli.py tests/test_machine_cli.py && git commit -m "feat: expose typed MD machine capability"`

## Task 4: Document the bounded experimental surface

**Files:**
- Modify: `README.md`
- Modify: `ROADMAP.md`
- Modify: `docs/superpowers/plans/2026-09-10-forge-typed-md-operations.md`

**Test strategy:** Documentation must match `capabilities_document()` and the implemented request fields. Verify snippets by invoking discovery and a dry-run machine request; no real ABACUS process is required for this batch.

- [x] **Step 1: Update docs**
  - State that `md` is experimental and supports only typed `prepare/modify/execute/collect`.
  - Show the inherited `parameters` map for `md_type`, `md_nstep`, `md_dt`, temperatures and `md_dumpfreq`, while warning that caller/Agent owns physical parameter selection.
  - State that `MD_dump`/log facts are collected where present; trajectory conversion, monitor, restart/resume, postprocess/export, scheduler and scientific judgment are outside this batch.
  - Keep PBE/NVE defaults explicit and preserve legacy `run_md` documentation.
- [x] **Step 2: Verify docs against code**
  - Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m abacus_forge.cli capabilities`
  - Expected: the documented MD descriptor is present and exactly matches its operation/artifact claims.
- [x] **Step 3: Update this PLAN ledger**
  - Check off completed Tasks 1–4 and append commit IDs, test outputs and reviewer findings.
- [x] **Step 4: Commit**
  - `git add README.md ROADMAP.md docs/superpowers/plans/2026-09-10-forge-typed-md-operations.md && git commit -m "docs: describe typed MD capability boundary"`

## Task 5: Final verification and independent review

**Files:**
- No new production files; update this plan's evidence block only.

- [x] **Step 1: Run the focused gate**
  - `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_md_contracts.py tests/test_md_services.py tests/test_md_machine_cli.py tests/test_machine_cli.py tests/test_service_status.py tests/test_cli_process.py tests/test_contracts.py tests/test_workspace.py tests/test_result_contract.py tests/test_architecture.py`
- [x] **Step 2: Run the full offline suite**
  - `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider`
  - Expected: all existing and new tests pass; any real-smoke skips remain explicit and do not become release evidence.
- [x] **Step 3: Run hygiene checks**
  - `git diff --check`
  - `rg -n "abacus-agent-tools|abacustest|aiida|ATP|MCP|Bohrium|DPDispatcher|slurm" src/abacus_forge pyproject.toml`
  - Expected: no new forbidden runtime dependency/import; only pre-existing documentation/test references remain.
- [x] **Step 4: Request independent task and whole-branch review**
  - Review the frozen diff against this PLAN and the SPEC sections listed above.
  - Reviewer must specifically check: MD cannot fall through to SCF, `calculation` fencing is symmetric, descriptors do not advertise postprocess/export, collection remains factual, and no scheduler/restart/science policy leaked in.
- [x] **Step 5: Record evidence**
  - Add exact HEAD, focused/full test counts, hygiene output and review result here. Do not claim stable maturity or Paimon migration.

## Self-review record

- **Inputs checked:** approved SPEC Stage 4 rollout and open-item rule, existing typed SCF/Relax contracts/services/discovery/machine CLI, Forge MD profile, and current reference evidence from `abacus-agent-tools` MD parameters, `abacuscopilot` v0.1.35, and `atst-tools` v2.2.4.
- **Boundary decisions:** MD is a separate explicit capability; request fields stay inherited and open through `parameters`; existing factual collector is reused; MD parser/trajectory postprocess is a separate future batch; no monitor, restart/resume, scheduler, workflow or scientific acceptance.
- **Compatibility checks:** no changes to generic `ForgeRequest` operation set, legacy `run_md`, legacy CLI, output layout, error classes, status values or artifact roles. `MdServiceSet` is a new typed entry only.
- **Known limitations intentionally retained:** collection completeness still follows the existing factual collector rules and does not claim trajectory completeness; real ABACUS/MD smoke and Paimon v1.3 promotion remain later gates.

## Execution ledger (Tasks 1–5)

- Task 1 contracts: `85babc5`, calculation-fencing fix `574563e`, and contract-strengthening tests `bbd487b`; contract/structure regression: `252 passed`, later MD focused suites: `33 passed`.
- Task 2 services: `6383e97` plus the LocalRunner fact test in `2c7737e`; service/status/result/task regression: `172 passed`.
- Task 3 discovery and machine surface: `97a181c`, type annotation fix `3e70b50`, registry/architecture expectation updates `4ada4d7`, `2836de8`, `ad669eb`; in-process and subprocess/API parity plus fake-runner evidence in `2c7737e` and `7223d0c`.
- Task 4 documentation: `104b759` and boundary-clarification fix `e5461b7`; `capabilities` output verified that `md` is `experimental`, advertises exactly `prepare`/`modify`/`execute`/`collect`, and uses artifact roles `input`/`provenance_manifest`/`output`.
- Task 5 final focused gate: **561 passed**; full offline suite: **760 passed, 3 skipped**. `git diff --check` passed. The forbidden-import scan reported only pre-existing compatibility text (`pyproject.toml:45`) and a path-filter string (`src/abacus_forge/collectors/abacus.py:416`), with no forbidden production import. Independent review by `typed_md_final_review` approved the corrected boundary and parity evidence at `e5461b7`; the final tests-only delta is `bbd487b`. This batch remains experimental and is not real-ABACUS or stable-release evidence.

## Completion evidence

Final code revision under test: `bbd487b` (the evidence update itself is documentation-only). Focused gate: the exact command in Task 5 Step 1, **561 passed**. Full offline gate: the exact command in Task 5 Step 2, **760 passed, 3 skipped**. `git diff --check`: passed. Forbidden-import scan: no new runtime import; only the two pre-existing matches recorded above. Independent reviewer: `typed_md_final_review`, approved after the documentation-boundary and four-operation subprocess/API parity corrections; no blocker or remaining Important finding. `md` remains `experimental`; this is not real-ABACUS validation or Paimon v1.3 stable-maturity evidence.
