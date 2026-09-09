# Forge input fidelity and factual collection implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox syntax for tracking.

**Goal:** Close reproducible input/collection defects and remove typed services' reverse dependency on the legacy API.

**Spec:** `../specs/2026-09-01-forge-contract-first-rearchitecture-design.html` (#requirements, #architecture), `../specs/2026-09-02-forge-service-status-migration-design.html` (#status, #architecture, #decisions).

**Decision sources:** User confirmed the 2026-09-09 architecture/algorithm review and authorized continued implementation with Paimon v1.2, abacustest, abacuslab and abacuscopilot references. Execution authorized in this conversation; no additional approval ceremony. Baseline `e7a9cc8`, 593 passed / 3 skipped, same paimon Python environment.

**Architecture:** Keep existing public compatibility adapters while extracting shared input and collection primitives below both adapters and typed services. Preserve ABACUS input semantics; collection completeness concerns data availability, never scientific acceptance.

**Tech Stack:** Existing Python, ASE, NumPy and pytest. Interpreter `/home/james/apps/miniforge3/envs/paimon/bin/python`.

## Global Constraints

- Preserve operation IDs, admission/events, error classes, CLI grammar and `forge.result/v1` keys.
- Scientific validation, orchestration and platform scheduling belong to humans/Agents; PBE remains the overrideable default.
- Reference repositories are read-only evidence, never new runtime dependencies; capabilities remain experimental.
- No external execution, cluster submission, merge or push in this implementation batch.
- Use existing owning tests; retain RED/GREEN output and exact commit in task reports. Do not delete tests without mutation evidence.

## Reference discipline

Reference root is `/home/james/work/sidereus/workplace` (not the worktree parent). Inspect Paimon v1.2 `app-tools/toolbox/ABACUS/utils/abacus_structure_io.py`, `toolkits/structure_prepare_pipeline.py`, result evidence; abacustest `abacustest/lib_prepare/stru.py`; abacuscopilot `abacuscopilot/io/stru_file.py`; and abacuslab input/output helpers. Record exact source symbols and revisions in the closure report. ABACUS's own `source/source_cell/read_atoms_helper.cpp` is authoritative for coordinate units.

## Task 1: Preserve STRU semantics and periodic geometry

**Files:** `src/abacus_forge/structure.py`, `structure_recognition.py`, `modify.py`, `api.py` only where STRU fallback masks parsing errors; `tests/test_structure.py`, `test_modify.py`, `test_api.py`.

**Interfaces:** Existing `AbacusStructure.from_input/to_stru`, `modify_stru`, `prepare`, `detect_vacuum_info`; signatures unchanged.

**Behavior:** Preserve per-species PP/ORB references and supplied masses by default; explicit nonempty map entries override by species, missing map entries retain source metadata. Preserve species association after writer sorting. Set read masses on ASE atoms, so transformations use actual masses. Structure mutation must preserve move flags for retained/repeated atoms instead of falling back to all movable after atom count changes.

Coordinate dispatch must use exact recognized modes: Direct, Cartesian (coordinates multiplied by lattice constant in Angstrom), Cartesian_angstrom, Cartesian_au (Bohr conversion independent of lattice constant). Reject unknown and centered modes explicitly in this batch rather than silently reinterpreting; recognized STRU parser errors must not become successful raw fallback preparation. Prior review incorrectly described Cartesian_au as falling through to Direct; the actual defect is Cartesian scale and prefix acceptance of centered/unknown modes.

Write native ABACUS lattice units: LATTICE_CONSTANT is in Bohr; do not emit the Forge-only LATTICE_CONSTANT_UNIT extension. Keep reading old Forge Angstrom-unit files for compatibility. A consumer-independent assertion must reconstruct geometry using native Bohr semantics, so a Forge read/write round-trip cannot mask wrong units.

Vacuum detection for full periodic cells uses the largest circular fractional gap times the perpendicular interplanar cell height (reciprocal metric), not Cartesian span; preserve return shape and threshold. Check translation/wrapping/rotation invariance, skew cells and the z=.98/.02 in a 20-A cell case (19.2-A gap). Handle empty/degenerate and nonperiodic cells explicitly without NaN or fabricated axes. Axis-swap behavior is not changed in this batch.

**Test strategy:** Extend the three owning suites with hand-derived fixtures; no new test file or runtime reference imports. Tests compare output fields/geometries, not source strings.

- [x] Add regression cases and record RED for metadata loss, nonunit Cartesian scale, unsupported mode, periodic vacuum and move-flag retention.
- [x] Implement bounded fixes, consulting the named source implementations.
- [x] Run `env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_structure.py tests/test_modify.py tests/test_api.py`; 57 passed at `2c9e198`.
- [x] Commit reviewed task changes; report reference evidence, RED/GREEN, revision and remaining limits. Independent task review approved; original intermediate RED patch was not retained as a checkout, while raw output and final GREEN were retained.

## Task 2: Common typed collection projection

**Files:** `src/abacus_forge/relax_results.py`, new `collection_results.py` for shared typed collection/projection, `services.py`; `api.py` only if a shared internal collection hook is needed to avoid duplicate parsing; existing `tests/test_service_status.py`, `test_cli_process.py`, `test_result_contract.py`.

**Interfaces:** SCF typed collect uses factual projection; Relax retains its extra final-structure requirements. Legacy `CollectionResult.to_envelope` and `api.collect` retain compatibility semantics.

**Behavior:** Shared artifact filtering excludes all `reports/events/`, `reports/claims/`, workspace manifest and locks, both lexical and resolved aliases. Retain actual domain artifacts and relative paths. SCF complete requires a selected nonempty contained output log, finite parsed total energy, no relevant parser/report errors or ambiguous selection; no log is missing_output, missing energy/degraded parse is partial. Convergence true/false/missing never controls completeness. Do not require optional time/report JSON. Preserve available arrays and structures as observations; missing convergence must not become a false fact. Reuse common helpers in Relax without weakening its final-output requirement.

Enforce source containment before reading selected logs or parsing artifacts; filtering only the resulting ArtifactRecord cannot undo external-file reads. Share underlying selection/parsing machinery, with the narrow typed seam subsequently moved below api in Task 3.

**Test strategy:** Existing service tests cover output-only directories, marker-only partial, energy with nonconverged complete, missing convergence observation, repeated collect excluding older audit events, symlink aliases; one process parity regression guards machine transport.

- [x] Record RED for false completeness and audit artifact leakage.
- [x] Implement common projection and wire SCF/Relax.
- [x] Run `env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_service_status.py tests/test_cli_process.py tests/test_result_contract.py tests/test_contracts.py tests/test_workspace.py`; 407 passed at `dc2dc8a`.
- [x] Commit and provide revision-bound evidence. Independent task review approved without findings.

## Task 3: Extract neutral operation core

**Files:** `src/abacus_forge/api.py`, `services.py`, `atst_neb.py`; new narrow `preparation.py`, `collection.py`, `service_support.py` as justified by extraction; existing architecture/service/unit/API/ATST tests.

**Interfaces:** Keep legacy public `prepare`, `collect`, `UnitSpec`, `UnitModifySpec`, compatibility files and facade. Both legacy and typed services call shared primitives below `api.py`. Typed service must not construct UnitSpec/UnitModifySpec, call legacy API, or require event suppression. Generic service support must not import capability-specific requests; capability matching belongs in services/adapters. ATST consumes generic support rather than SCF private context.

Extraction seams: move `prepare` and preparation-only helpers into `preparation.py`, `collect` plus log/artifact/snapshot helpers into `collection.py`; both keep event-free primitives. Keep wide task/engine/sequence dispatch in `api.py`. Share `forge-unit.json` and modify compatibility record construction via small helpers if needed, not new wide specs. Current `services.execute` import is unused; remove it while updating the spy test to check runner calls and single-event behavior instead. The private module monkeypatch names are not public compatibility contracts. Preserve legacy callers' public API and file/event behavior.

**Behavior:** Mechanically extract preparation/collection primitives and their helper dependencies, retaining signatures where helpful. INPUT-only typed modification calls existing `modify_input`; share compatibility serialization where duplication would otherwise arise. Keep public wrappers forwarding into primitives and existing public injection behavior where genuinely supported. Do not relocate the entire God Object/API under another name. Keep runner separate and preserve exactly one typed outcome/event per operation.

**Test strategy:** Extend AST import graph gate to reject direct/transitive neutral-core or typed-service dependence on legacy API and forbidden platform modules; retain behavioral unit/service and compatibility tests. New AST gate must fail against baseline. Inspect monkeypatch seams rather than preserving arbitrary private names blindly.

- [x] Add architecture regression and establish RED.
- [x] Extract narrow modules; use prior two tasks' fixed primitives without duplication.
- [x] Run full offline suite with the interpreter/flags above; 631 passed, 3 opt-in skips at `c5c2ce6`; `git diff --check` exit 0.
- [x] Commit and report exact moved responsibilities and verification. Independent task review approved without findings.

## Task 4: Preserve metadata across primitive/conventional standardization

**Evidence:** Parent probe after Task1: `primitive_to_conventional` converts Si2 with custom mass 30 and Si.upf/Si.orb to Si8 with default mass and empty metadata. Pymatgen `keep_site_properties=True` retains mass but can merge distinct site magnetic moments by choosing a representative; blindly enabling it is insufficient.

**Files/interfaces:** `structure.py` existing `primitive_to_conventional` and `conventional_to_primitive`; existing `tests/test_structure.py` and `test_modify.py`. Signatures remain unchanged.

**Behavior:** Preserve species PP/ORB metadata and uniform-per-species supplied masses/magnetic moments through both conversions; use existing pymatgen `keep_site_properties` support and reinstall metadata on returned ASE atoms. Explicitly reject inputs with constrained move flags or different masses/magnetic moments among atoms of one species when this normalization cannot preserve them, using `ForgeRequestError` rather than silently selecting a representative. Flags for unconstrained converted atoms remain all movable. Do not invent magnetic-symmetry or constraint-rotation algorithms.

**Test strategy:** Hand-checked silicon primitive/conventional cells with custom mass/resources; compare geometry, atom count, species-bound references and mass. Test a nonuniform magnetic case and a constrained case both fail explicitly; do not infer expected data using the converter under test.

- [x] Establish RED for standardization metadata loss and silent site-property merging.
- [x] Implement bounded preservation/rejection and run Task1 owning-suite command; 68 passed at `97c4238`.
- [x] Commit with raw RED/GREEN report and obtain independent task review; approved without findings.

## Remaining design work and acceptance scope

Explicit typed PP/ORB asset maps and materialization policy require a dedicated request-schema increment plan after this core extraction; existing legacy asset arguments remain available. This batch restores reference preservation, but does not claim typed prepare stages source-relative external assets or validates an executable-ready complete directory. Document that limit near typed prepare usage. Follow-up must settle explicit map precedence, workspace containment, copy/link semantics, basename collision behavior and absent-asset diagnostics together, using Paimon v1.2 PP/ORB finalization as reference. Typed MD, independent export/PyATB and property algorithm promotion remain separate batches.

## Controller closure

- [x] Update SPEC concisely for corrected input/collection behavior and actual extraction status, without expanding governance prose; sync README/ROADMAP and source reference report.
- [x] Independent task reviews followed by whole-branch review; both Important findings (commented coordinate modes and duplicate log aliases) fixed at `07d5032`, scoped re-review approved without new findings.
- [x] Retain branch and reviewable diff; report actual limitations and next typed-asset task. Branch `forge-core-fidelity` retained; no merge or push.

**Self-review:** Plan checked against two SPECs at e7a9cc8: status/observation separation, one-operation boundary, source compatibility and no old runtime dependency retained. No new schema is introduced. Structural coordinate handling is corrected/rejected within existing inputs, not a new scientific algorithm. Known omitted asset materialization is explicitly recorded above; implementation tasks have disjoint serial ownership.

**Integrated offline evidence:** Source/test revision `97c4238`: full pytest with the interpreter/flags above returned 642 passed, 3 opt-in skips (59.16 s), exit 0. Final fix revision `07d5032`: 24 focused regressions and the six-suite owning gate (structure, modify, API, service status, CLI process, reference collection), 229 passed (45.28 s), exit 0; `git diff --check` exit 0. Whole-branch review plus scoped fix review are closed. These are separate runs; no full-suite642 claim is made for the amended revision, nor any real execution or stable-release claim.
