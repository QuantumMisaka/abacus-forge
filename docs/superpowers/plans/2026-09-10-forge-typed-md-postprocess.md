# Forge typed MD postprocess Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an experimental, explicit `md.postprocess` operation that computes the five already-used Paimon MD trajectory analyses through the same Python/API and Agent-first CLI facts boundary, without adding workflow, scheduler, trajectory discovery or scientific acceptance semantics.

**Spec:** `docs/superpowers/specs/2026-09-10-forge-typed-md-postprocess-design.html`, together with the approved 2026-09-01 and 2026-09-02 Forge SPECs.

**Architecture:** Add a focused `MdPostprocessRequest` contract and a pure `md_postprocess` algorithm module. A dedicated `MdPostprocessServiceSet` owns workspace admission, exact trajectory validation, deterministic output files, artifact/hash construction, status/observation projection and one append-only event. The machine CLI only decodes/routes/renders; existing four typed MD operations, generic band/DOS postprocess and all legacy task APIs remain separate.

**Tech Stack:** Python 3.10+, frozen dataclasses, pathlib, existing Forge `Workspace`/`ServiceContext`/`OperationOutcome` contracts, ASE, NumPy, Matplotlib, pytest.

## Global Constraints

- Capability is exactly `md`, maturity remains `experimental`, and advertised operations become `prepare`, `modify`, `execute`, `collect`, `postprocess`.
- Request/result/error schema versions, seven error classes, operation admission/event/artifact-ref semantics and generic `ArtifactRecord` fields remain unchanged.
- `trajectory_path_rel` is a caller-supplied canonical workspace-relative exact file; no latest lookup, directory scan, external absolute path, MD_dump auto-conversion, PDB conversion, runner, collect chaining or workflow edge is allowed.
- Canonical analysis names are `rdf`, `msd_diffusion`, `vacf_vdos`, `bond_length`, and `bond_angle`; Paimon compatibility aliases are mapped by the upper adapter and are not accepted by the Forge typed contract.
- Top-level request fields are limited to trajectory, analysis, output directory, start/end/stride and JSON-safe `parameters`; initial parameter keys are `timestep`, `selection`, `elements`, `rmax`, `nbins`, `save_data`, and `save_plot`. Unknown parameter keys are preserved and reported as ignored without changing current behavior.
- Pure postprocess returns `execution="not_run"`, `scientific="unassessed"`, and collection `complete|partial|missing_output`; it reports parser/numeric facts only and never an accepted/rejected scientific result.
- All output paths are deterministic and contained. `trajectory` is an input artifact, `trajectory_source.json` is a provenance artifact, analysis/data/plot/report files are output artifacts. Artifact refs are injected only by `ServiceContext.persist()`.
- API and machine CLI must produce equivalent envelopes, diagnostics, observations, artifact refs, events and output bytes in isolated workspaces. Existing legacy and four-operation MD tests must remain green.
- Every task follows RED → GREEN → focused regression → commit; real ABACUS/MD and Paimon benchmark evidence is a later gate and must not be claimed here.

## File Map

- Create `src/abacus_forge/md_postprocess_contracts.py`: immutable request, mode/path/sampling validation and JSON-safe parameter storage.
- Create `src/abacus_forge/md_postprocess.py`: pure trajectory reader, sampling, RDF/MSD/VACF/geometry kernels and deterministic output writer; no Forge workspace/event imports.
- Create `src/abacus_forge/md_postprocess_services.py`: narrow service protocol/set, containment/admission, artifact/report persistence and factual envelope projection.
- Modify `src/abacus_forge/discovery.py`: register the fifth `md` operation, descriptor input and request schema.
- Modify `src/abacus_forge/machine_cli.py`: decode and route `MdPostprocessRequest` to its dedicated service set; keep legacy parser untouched.
- Modify `src/abacus_forge/__init__.py`: export the new request and service set.
- Create `tests/test_md_postprocess_contracts.py`, `tests/test_md_postprocess_algorithms.py`, `tests/test_md_postprocess_services.py`, and `tests/test_md_postprocess_machine_cli.py`; update existing capability-list/MD rejection assertions only where the new operation changes the approved registry.
- Modify `README.md`, `ROADMAP.md`, and this plan with experimental status, explicit-path usage and deferred conversion/coordination boundaries.

### Task 1: Typed contract, discovery and machine decoder

**Files:**
- Create: `src/abacus_forge/md_postprocess_contracts.py`
- Modify: `src/abacus_forge/discovery.py`
- Modify: `src/abacus_forge/machine_cli.py`
- Modify: `src/abacus_forge/__init__.py`
- Create/modify: `tests/test_md_postprocess_contracts.py`, `tests/test_md_machine_cli.py`, `tests/test_machine_cli.py`, `tests/test_contracts.py`, `tests/test_architecture.py`

**Interfaces:**
- `MdPostprocessRequest(operation_id, workspace_rel, trajectory_path_rel, analysis, output_dir_rel="outputs/md-postprocess", start=0, end=None, stride=1, parameters={})` is frozen and serializes as `forge.request/v1` with `capability="md"`, `operation="postprocess"`.
- `analysis` is a non-empty tuple of unique canonical strings. `trajectory_path_rel` is a non-root canonical file; `output_dir_rel` is a canonical directory. `start` is non-negative, `stride` positive, and `end` is `None` or a positive integer. `parameters` is detached/frozen JSON-safe mapping.
- `from_dict()` rejects unknown fields, missing identity/trajectory/analysis, aliases, non-canonical paths, invalid sampling, non-JSON values and non-object parameters. `to_dict()` returns fresh lists/maps.
- Register `MD_REQUEST_TYPES["postprocess"]`, update `_MD_DESCRIPTOR` inputs and operation order, and make discovery schema properties/required fields derive-check against dataclass/wire keys. The representative request uses `outputs/md.traj` and `analysis=("rdf",)`.
- Add `MdPostprocessRequest.from_dict` to `_MD_DECODERS`; no capability-less path is introduced.

**Test strategy:** Contract tests own strict wire behavior and discovery tests own descriptor/schema parity. Existing assertions that MD postprocess/export are rejected must be changed so only export remains rejected; a valid MD postprocess request must decode to the new type. No algorithm or filesystem access is used in this task.

- [x] **Step 1: Write failing tests** for round-trip/defaults/immutability, all invalid fields and mode aliases, discovery exact operation list/schema, decoder selection and capability-less export rejection.
- [x] **Step 2: Run RED:** `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_md_postprocess_contracts.py tests/test_md_machine_cli.py tests/test_contracts.py tests/test_architecture.py`; expected new import/assertion failures.
- [x] **Step 3: Implement** the contract and registry/decoder/export wiring exactly as above; keep `md_contracts.py` four-operation classes unchanged.
- [x] **Step 4: Run GREEN** with the same command; expected all selected tests pass.
- [x] **Step 5: Run focused regression** `conda run -n paimon python -m pytest -q tests/test_md_contracts.py tests/test_md_machine_cli.py tests/test_machine_cli.py` and `git diff --check`.
- [x] **Step 6: Commit** `git add src/abacus_forge/md_postprocess_contracts.py src/abacus_forge/discovery.py src/abacus_forge/machine_cli.py src/abacus_forge/__init__.py tests/test_md_postprocess_contracts.py tests/test_md_machine_cli.py tests/test_machine_cli.py tests/test_contracts.py tests/test_architecture.py && git commit -m "feat: add typed MD postprocess contract"` (follow-up fixes in `c175855` and `1489c72`).

### Task 2: Pure trajectory algorithms and deterministic files

**Files:**
- Create: `src/abacus_forge/md_postprocess.py`
- Create: `tests/test_md_postprocess_algorithms.py`

**Interfaces:**
- `Frame` and `FrameSelection` hold finite positions, symbols, cell/PBC, masses and optional velocities.
- `load_frames(path, *, start=0, end=None, stride=1) -> FrameSelection` reads an explicit ASE trajectory and falls back to dependency-free XYZ, validates non-empty sampled frames, consistent atom order/count and returns the clamped exclusive source end.
- `validate_analysis(analysis) -> tuple[str, ...]`, `canonical_parameter_values(parameters, modes) -> dict[str, object]`, `analyze_trajectory(frames, modes, *, timestep=None, selection=None, elements=None, rmax=6.0, nbins=100) -> dict[str, object]`, and `run_md_postprocess(trajectory, modes, *, output_dir, start, end, stride, parameters) -> MdPostprocessResult` are pure with respect to Forge state. `MdPostprocessResult` contains JSON-safe `summary`, `diagnostics`, `results`, `sampling`, and generated relative filenames.
- Algorithms must implement the Paimon v1.2 facts: periodic unwrap and mass-weighted Kabsch drift removal for MSD; velocity-preferred or finite-difference VACF plus FFT frequencies; element-pair RDF over explicit periodic cells; minimum-image bond lengths/angles with 1-based selection. RDF must avoid importing Paimon/toolbox modules and use only Forge dependencies.
- The writer always produces `analysis.json` with `schema_version="forge.md-postprocess/v1"`, canonical modes, sampling and finite JSON-safe results; `save_data`/`save_plot` control mode data/PNG files. It never writes outside the supplied output directory and never emits a science policy.

**Test strategy:** Use hand-authored XYZ and ASE fixtures. Assert numerical invariants (rigid drift removal, known right angle, VACF normalization/peak, RDF finite bins), Paimon mode names, sampling semantics, output filenames, JSON round-trip and no imports from `abacus-agent-tools`, `abacustest`, `paimon`, ATP/MCP or schedulers. Keep plots dependency-light and deterministic; when Matplotlib cannot import or render, omit the failed PNG and report the diagnostic so service collection reflects the missing output.

- [x] **Step 1: Write failing tests** for reader/sampling, all five analyses, invalid requirements, finite JSON, output controls and path-safe generated names.
- [x] **Step 2: Run RED:** `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_md_postprocess_algorithms.py`; expected missing-module failures.
- [x] **Step 3: Implement** the pure module, adapting only numerical behavior evidenced by the Paimon toolkit; do not copy ATP wrapper/evidence or introduce a second task/workflow layer.
- [x] **Step 4: Run GREEN** with the same command; expected algorithm tests pass and all result JSON serializes with `allow_nan=False`.
- [x] **Step 5: Run focused regression** `conda run -n paimon python -m pytest -q tests/test_md_postprocess_algorithms.py tests/test_md_services.py tests/test_md_machine_cli.py` after Task 1 integration, then `git diff --check` (algorithm suite `12 passed`; service suites remain a Task 3 gate).
- [x] **Step 6: Commit** `git add src/abacus_forge/md_postprocess.py tests/test_md_postprocess_algorithms.py && git commit -m "feat: add pure MD trajectory postprocess kernels"` (follow-up boundary/numerical/selection fixes in `2f619e6`, `8943ffa`, and `69f5802`).

### Task 3: Service, persistence and API/CLI parity

**Files:**
- Create: `src/abacus_forge/md_postprocess_services.py`
- Modify: `src/abacus_forge/machine_cli.py`, `src/abacus_forge/__init__.py`
- Create: `tests/test_md_postprocess_services.py`, `tests/test_md_postprocess_machine_cli.py`

**Interfaces and behavior:**
- `MdPostprocessServiceProtocol.postprocess(request) -> OperationOutcome | ForgeErrorEnvelope`; `MdPostprocessServiceSet.default(workspace_root=".")` exposes `.postprocess` and accepts optional algorithm injection for deterministic service tests.
- Preflight resolves workspace, exact trajectory and output/report paths, rejects symlink escapes, reserved audit overlap, input/output collision and output target conflicts before `operation_guard`. Under admission it requires the trajectory, calls `run_md_postprocess`, writes `trajectory_source.json` and the algorithm’s `analysis.json`/mode files, hashes all existing files and builds input/provenance/output `ArtifactRecord`s, then calls `ServiceContext.persist()` exactly once.
- Successful envelope has `execution="not_run"`, `collection="complete"` when every requested mode’s declared data requirements exist, otherwise `partial`/`missing_output`, `scientific="unassessed"`; diagnostics include canonical modes, ignored parameter keys, sampling, selected path, generated paths and `analysis_results` summary without absolute paths. Checks are mode facts (`passed`/`warning`), metrics are runtime sampling and reported algorithm values only.
- Missing/invalid trajectory or analysis precondition after admission maps to `precondition.missing`/exit 3 and leaves tombstone; request/path/duplicate/persistence/internal mappings reuse existing `ServiceContext`; no runner, collect, latest lookup or upstream event mutation occurs.
- Machine CLI recognizes the new request and chooses `MdPostprocessServiceSet`; API and CLI use the same service. `--pretty`/text only render the same result.

**Test strategy:** Service tests cover success, report/source manifest, hashes/refs, status/observations, one event, missing/invalid trajectory, malformed frames, path/symlink/reserved collisions, duplicate IDs, output controls and no-runner/no-collect guarantees. Process tests cover stdin/request-file, JSON stdout/stderr, exit 0/2/3/5, isolated API/CLI parity and legacy MD regression.

- [x] **Step 1: Write failing service/process tests** including fake algorithm injection and real XYZ fixture parity.
- [x] **Step 2: Run RED:** `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_md_postprocess_services.py tests/test_md_postprocess_machine_cli.py`; the initial service/import/routing failures were used to drive the implementation.
- [x] **Step 3: Implement** the dedicated service and route only the new request; keep generic `PostprocessServiceSet` limited to band/DOS.
- [x] **Step 4: Run GREEN** with the focused service/process command; the latest focused architecture/MD service/process/algorithm/contract gate is `109 passed`.
- [x] **Step 5: Run focused regression** with the MD contract, algorithm, service, machine and existing MD suites plus `git diff --check`; follow-up coverage also verifies request-file/API parity, reserved/symlink paths, stale/undeclared output rejection, finite facts and exit 2/3/5.
- [x] **Step 6: Commit** the service route and subsequent boundary hardening in `358a077`, `3f60230`, `3d9b4f7`, `9395207`, and `c454f0b` (the initial implementation commit was followed by review-driven fixes).

### Task 4: Documentation, final verification and branch review

**Files:**
- Modify: `README.md`, `ROADMAP.md`, this plan
- Create: `.superpowers/sdd/2026-09-10-forge-typed-md-postprocess/task-4-report.md`

**Documentation:** Add one typed Python and machine CLI example using an explicit trajectory, explain the five canonical modes and facts-only output, document `parameters` initial keys and `analysis.json`, and plainly defer MD_dump/PDB conversion, aliases (upper adapter), monitoring, workflow, scheduler, export and scientific judgment. Mark only this slice experimental and keep real-smoke/benchmark and stable Paimon v1.3 promotion deferred.

**Verification:**

1. Run focused contract/algorithm/service/process suites with `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src -p no:cacheprovider`.
2. Run discovery/schema, architecture forbidden-import and all existing MD, generic postprocess, API/CLI and legacy task suites.
3. Run the full offline pytest gate and `git diff --check`; record exact HEAD, counts, warnings and intentional skips. Do not claim real ABACUS science evidence.
4. Dispatch an independent task reviewer for each task and a whole-branch reviewer against the exact SPEC/PLAN diff; resolve all Critical/Important findings and rerun affected gates.
5. Commit docs/report only after reviews are clean; do not merge or push in this plan.

- [x] **Step 1:** Update docs and plan completion ledger without changing production behavior.
- [x] **Step 2:** Run focused and full verification commands and save raw summaries to the SDD ledger/report.
- [x] **Step 3:** Obtain task and whole-branch review, resolve findings, run final `git diff --check`.
- [x] **Step 4: Commit** `git add README.md ROADMAP.md docs/superpowers/specs/2026-09-10-forge-typed-md-postprocess-design.html docs/superpowers/plans/2026-09-10-forge-typed-md-postprocess.md .superpowers/sdd/2026-09-10-forge-typed-md-postprocess/task-4-report.md && git commit -m "docs: close typed MD postprocess slice"`.

## Plan self-review and rulings

- The plan adds one new public operation but does not alter the five core request verbs or any legacy parser. Task 1 produces the exact request type consumed by Task 3; Task 2 produces the pure result consumed by Task 3; Task 4 touches only docs and evidence.
- No task performs automatic trajectory discovery or MD_dump conversion. The explicit trajectory contract matches the current Paimon `trajectory_file` handoff and keeps cross-workspace materialization outside Forge.
- `parameters` remains open for future analysis controls, but recognized keys are validated and unknown keys are surfaced as ignored facts; silently changing behavior is not allowed.
- Ruling: implement all five canonical analyses in one shared reader rather than five tools because the Paimon v1.2 contract already uses one multi-mode entry and shared sampling. Wrong-scope cost is isolated to one experimental module and can be reverted without touching legacy MD.
- Ruling: keep `MdPostprocessServiceSet` separate from the existing band/DOS set because the MD request and output semantics include trajectory sampling/provenance; forcing a broad generic refactor would enlarge the compatibility surface without user value.

## Follow-up hardening record (2026-09-10)

The pure `Frame` value object now normalizes `symbols` to an owned tuple and
rejects empty or non-string symbol sequences.  This closes a local mutability
gap in the frozen algorithm input without changing the typed request, result,
CLI, or scientific boundary.  Regression coverage lives in
`tests/test_md_postprocess_algorithms.py`; focused MD/CLI/service tests pass on
the `forge-core-fidelity` branch.  This is an internal correctness hardening,
not a new capability or promotion claim.

The pure writer also preflights its deterministic output names and rejects a
symlinked output directory or output file before writing any analysis file.
This mirrors the service containment guarantee for direct algorithm callers;
it does not introduce a new path field or alter the typed service contract.

The dependency-free XYZ fallback now carries the same finite common-element
mass table used by the Paimon v1.2 MD kernel (with the existing `1.0` fallback
for symbols outside that table).  This is an internal numerical-fidelity
alignment only; ASE-provided masses remain authoritative and no new species or
scientific validation contract is introduced.

The 2026-09-11 review-fixes slice supersedes that fallback behavior: it keeps
the complete finite table and rejects unknown symbols instead of assigning a
synthetic mass.  The earlier `84962ee` verification remains historical
evidence for the behavior that existed at that revision.

Verification at `84962ee`: the focused MD/legacy compatibility gate passed
`68 passed`; the stable deterministic gate passed `1138 passed, 42 deselected`,
the experimental gate passed `39 passed, 1141 deselected`, and the full offline
gate passed `1177 passed, 3 skipped`.  The skips remain opt-in real-smoke or
benchmark evidence and are not scientific validation.

After the public-loader fallback review, `58e54eb` adds the `load_frames()`
regression and the latest verification passes `69` focused tests, `1139 passed,
42 deselected` in the stable gate, `39 passed, 1142 deselected` in the
experimental gate, and `1178 passed, 3 skipped` in the full offline gate.

The ASE frame adapter now validates the returned mass array and falls back to
the same finite common-element table when ASE supplies an invalid shape, NaN,
or non-positive mass.  A public `load_frames()` regression covers this path;
it aligns the reader with the Paimon v1.2 fallback without weakening the
finite-positive `Frame` invariant or introducing a new scientific policy.

The latest branch verification after this hardening and the typed collector
migration benchmark is:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
1179 passed, 4 skipped

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider --run-benchmark -m benchmark
2 passed, 1181 deselected

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider -m 'not experimental and not real_smoke and not benchmark'
1140 passed, 43 deselected
```

These are offline compatibility and contract gates.  The four skipped tests
remain opt-in real-smoke/benchmark boundaries; no real ABACUS execution or
scientific acceptance claim is made.

## Current-state boundary clarification (2026-09-11)

The later review-fixes plan
`2026-09-11-forge-md-postprocess-review-fixes.md` supersedes the historical
fallback wording above: current behavior uses a complete finite element-mass
table and rejects unknown symbols. Later clean-package evidence is recorded in
the collection-metadata plan. Complete Paimon benchmark parity and a real
trajectory-to-postprocess smoke remain separate release evidence; scientific
interpretation and workflow/orchestration are caller-owned boundaries, not
missing Forge implementation tasks.
