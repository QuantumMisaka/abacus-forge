# Forge typed ABACUS postprocess operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose a narrow, typed and auditable `postprocess` machine/API surface for single-workspace ABACUS band and DOS facts while preserving all legacy unit and task-pack behavior.

**Spec:** `docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html` (`#boundary`, `#requirements`, `#architecture`) and `docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html` (`#status`, `#decisions`, `#architecture`, `#errors`, `#testing`, `#rollout`). The approved SPEC already includes `postprocess` as an independent operation and requires its own typed request registry; this plan does not change the SPEC boundary.

**Authorization:** The user authorized continued Forge implementation and asked to keep the design aligned with Paimon v1.2, `abacustest`, `abacuslab`, and `abacuscopilot`. The 2026-09-10 read-only boundary audit selected this lower-risk next slice: typed ABACUS `band`/`dos` postprocess first; PyATB engine-specific typed handoff and typed `export` remain separate follow-up plans.

**Architecture:** Add concrete `BandPostprocessRequest` and `DosPostprocessRequest` records under a separate postprocess request registry. Each request names its source files explicitly relative to one workspace and carries only the currently supported rendering/selection options; no directory scan, implicit `collect`, implicit `export`, workflow sequence, scientific policy, or external source path is introduced. A dedicated postprocess service reuses the existing band/DOS parsers and writers, converts every result path to a contained workspace-relative `ArtifactRecord`, persists one `OperationOutcome` and event through the existing admission path, and leaves legacy helpers as compatibility wrappers.

**Tech Stack:** Existing Python 3.10 dataclasses, pathlib, NumPy/matplotlib, ASE-independent band/DOS parsers, pytest and the current `paimon` environment. No new runtime dependency and no reference-repository import.

## Global Constraints

- Preserve `forge.request/v1`, `forge.result/v1`, `forge.operation-outcome/v1`, seven error classes, exit classes 0/2/3/4/5, operation identity and append-only event semantics.
- `postprocess` is a distinct typed operation; never silently perform `collect -> postprocess -> export`, and never change legacy `collect_unit()`'s implicit compatibility postprocess or `api.export()` behavior.
- Typed postprocess accepts one workspace and explicit contained source paths. It must reject missing/non-file/escaped/symlink-outside sources before parser reads and reject output paths that overlap Forge audit files or source files.
- Return parser observations, diagnostics and artifacts only. `scientific` is always `unassessed`; Forge does not calculate band-gap acceptance, topology, convergence acceptance or any other scientific conclusion.
- Advertise only actual operations: experimental `band.postprocess` and `dos.postprocess`; do not advertise `export`, PyATB, property packs or sequence APIs in this batch.
- Preserve legacy absolute-path/diagnostics behavior at compatibility entry points; only the typed path normalizes paths and uses contained artifact records.
- No ABACUS/PyATB process, scheduler, Slurm, workflow, retry/resume or real-science validation is part of this batch.

## Boundary evidence and design rulings

- `src/abacus_forge/unit_postprocess.py` already owns deterministic ABACUS band and DOS generation, while `src/abacus_forge/band_data.py`, `dos_data.py`, and `dos_postprocess.py` own reusable parsing/formatting primitives.
- The current legacy `_postprocess_unit_before_collect()` call in `api.py` is compatibility behavior and must not become the typed service's control flow.
- The current `api.export()` accepts an arbitrary destination and has no operation identity, admission, artifact refs or audit event; typed export therefore stays deferred.
- PyATB currently depends on implicit SCF directory discovery and mixed legacy `CollectionResult`; its explicit artifact-handoff adapter is a separate batch.
- `DosPostprocessRequest.suffix` is constrained to one safe filename component because the legacy helper's string concatenation otherwise permits path traversal on a typed path.

### Task 1: Typed postprocess request contracts and discovery registry

**Files:**
- Create: `src/abacus_forge/postprocess_contracts.py`
- Modify: `src/abacus_forge/discovery.py`, `src/abacus_forge/machine_cli.py`, `src/abacus_forge/__init__.py`
- Modify: `tests/test_contracts.py`, `tests/test_machine_cli.py`, `tests/test_cli_process.py`, `tests/test_architecture.py`

**Interfaces:**
- `BandPostprocessRequest` serializes `schema_version`, `capability="band"`, `operation="postprocess"`, `operation_id`, `workspace_rel`, `source_paths_rel`, `output_dir_rel`, `plot_emin`, `plot_emax`, `save_data`, and `save_plot`.
- `DosPostprocessRequest` serializes the same identity fields plus `dos_paths_rel`, nullable `pdos_path_rel`, nullable `tdos_path_rel`, `output_dir_rel`, `include_tdos`, `include_pdos`, `pdos_mode`, `pdos_atom_indices`, `plot_emin`, `plot_emax`, `save_data`, `save_plot`, and nullable safe `suffix`.
- Both records are immutable, strict on unknown fields, require at least one explicit source path relevant to the enabled family at service time, and validate all relative paths canonically. `source_paths_rel`/`dos_paths_rel` are non-empty path lists; `pdos_atom_indices` is a tuple of non-negative integers; numeric plot bounds are finite; `plot_emin < plot_emax`; `pdos_mode` is one of the existing `PDOSMode` values; `suffix` contains no slash, backslash, dot path component, or empty value.
- `POSTPROCESS_REQUEST_TYPES` is a separate registry. `REQUEST_TYPES_BY_CAPABILITY` and `decode_operation_request()` select these classes only for explicit `band`/`dos`; missing capability remains the existing SCF path. `ForgeRequest._OPERATIONS` and legacy decoders are unchanged.
- Discovery descriptors for `band` and `dos` each advertise only `postprocess`, `engine="abacus"`, `maturity="experimental"`, actual input names and artifact roles `input`/`output`. Their schema documents reflect dataclass `to_dict()` keys and reject `additionalProperties`.

**Test strategy:** Extend existing contract/machine suites; no new test file because the current registry and process tests own request and discovery behavior. Assert round trips, strict unknown fields, invalid paths/types/bounds/suffix, deterministic descriptors, explicit capability routing, `schema <band|dos> postprocess`, and request-invalid/exit-2 for unsupported operations or missing capability. Verify no service call occurs on invalid input.

- [ ] **Step 1: Write failing contract/discovery/decoder tests.**
- [ ] **Step 2: Run the focused RED gate:**
  `env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_contracts.py tests/test_machine_cli.py tests/test_cli_process.py tests/test_architecture.py`.
- [ ] **Step 3: Implement the separate request module and registry dispatch without widening legacy `ForgeRequest`.**
- [ ] **Step 4: Run the focused GREEN gate and `git diff --check`.**
- [ ] **Step 5: Commit:** `git add src/abacus_forge/postprocess_contracts.py src/abacus_forge/discovery.py src/abacus_forge/machine_cli.py src/abacus_forge/__init__.py tests/test_contracts.py tests/test_machine_cli.py tests/test_cli_process.py tests/test_architecture.py && git commit -m "feat: add typed band dos postprocess requests"`.

### Task 2: Explicit-input algorithm seam and contained artifact projection

**Files:**
- Create or modify only the algorithm owner justified by tests: `src/abacus_forge/postprocess_algorithms.py` and/or `src/abacus_forge/unit_postprocess.py`, `src/abacus_forge/dos_postprocess.py`
- Modify: `tests/test_dos_postprocess.py`, `tests/test_units.py`, and add `tests/test_postprocess_algorithms.py` only if no existing suite can own the explicit-input seam

**Interfaces:**
- Provide event-free functions accepting already validated `Path` inputs and a contained output directory, returning serializable parser summaries plus the exact generated output paths. Band accepts an ordered sequence of `BANDS_*.dat`-compatible files; DOS accepts explicit total-DOS paths and optional PDOS/TDOS paths. Neither function scans a workspace or writes outside the passed output directory.
- Keep the existing public `postprocess_abacus_band`, `postprocess_abacus_dos`, and `postprocess_dos_family` signatures and implicit discovery/absolute diagnostic behavior for legacy callers. Their implementation may delegate to the new seam only where existing tests demonstrate behavior equivalence.
- Typed algorithm results must not emit `accepted`/`rejected` facts. A parser with no numeric rows raises a typed precondition/parse exception for the service to map, while optional DOS family absence is represented as a factual missing-family diagnostic.

**Test strategy:** Use existing sample band/DOS fixtures and hand-created temporary files. Assert explicit file ordering, no directory discovery, safe output names, DOS suffix traversal rejection at the request boundary, deterministic data/plot generation, malformed input handling, and unchanged legacy helper tests. Avoid tests that infer science conclusions from generated plots.

- [ ] **Step 1: Add RED tests for explicit paths and output containment.**
- [ ] **Step 2: Run the owning RED gate:** `env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_dos_postprocess.py tests/test_units.py tests/test_postprocess_algorithms.py` (omit the new file until it exists).
- [ ] **Step 3: Extract/reuse the smallest event-free algorithm seam; leave legacy wrappers behaviorally intact.**
- [ ] **Step 4: Run GREEN and `git diff --check`; inspect generated files for absolute-path leakage in typed results.**
- [ ] **Step 5: Commit:** `git add src/abacus_forge/postprocess_algorithms.py src/abacus_forge/unit_postprocess.py src/abacus_forge/dos_postprocess.py tests/test_dos_postprocess.py tests/test_units.py tests/test_postprocess_algorithms.py && git commit -m "refactor: expose explicit postprocess algorithms"`.

### Task 3: Typed band/DOS services, API/CLI parity and durable audit

**Files:**
- Create: `src/abacus_forge/postprocess_services.py`
- Modify: `src/abacus_forge/machine_cli.py` only for service-set typing/routing if Task 1 did not finish it; modify `src/abacus_forge/__init__.py` only for public service exports
- Create: `tests/test_postprocess_services.py`, `tests/test_postprocess_machine_cli.py` (new independently owned service and subprocess boundaries)

**Interfaces:**
- `PostprocessService` protocol exposes `postprocess(request: BandPostprocessRequest | DosPostprocessRequest) -> OperationOutcome | ForgeErrorEnvelope`.
- `PostprocessServiceSet.default(workspace_root=".")` exposes `.band.postprocess` and `.dos.postprocess`, sharing one `ServiceContext` and one admission/persistence path. A compatibility facade is not added.
- The service resolves and validates every source before opening it, verifies output directory containment and reserved audit paths, then admits the operation ID before domain writes. It calls the explicit algorithm seam, writes only requested data/plot and factual report diagnostics under the workspace, builds input/output `ArtifactRecord`s with relative paths, hashes and sizes, and persists one event. Source records have `role="input"`, generated records have `role="output"`, and report files are included only when actually written.
- Successful parse with at least one requested family yields `execution="completed"`, `collection="complete"`; optional missing DOS family yields `collection="partial"` with diagnostics; no usable source after admission yields `collection="missing_output"` only when the request itself was valid but the expected file has disappeared. Missing request-declared files before parser invocation map to `precondition.missing`/exit 3. Parser failure maps to an admitted outcome with `execution="failed"`, `collection="partial"`, factual `parse_error` diagnostics and exit 4; it never changes a prior ABACUS execute/collect event.
- `scientific="unassessed"` for every outcome. Observations are parser facts such as file counts, row/point counts, spin channels, selected paths and generated artifact names; no band-gap or physical acceptance observation is synthesized.
- Repeated `operation_id` is rejected by existing workspace admission without touching source/output files. A source symlink resolving outside the workspace and an output path overlapping `reports/events`, `reports/claims`, `reports/forge-workspace.json`, locks, or a source file are rejected with the existing path/request classes.

**Test strategy:** New service/process suites use isolated temporary workspaces, explicit files, a fake no-process algorithm seam where useful, and true `run_cli` subprocess calls for parity. Assert API and CLI envelopes match after normalizing only operation IDs/path-bearing diagnostics, input/output artifact roles and refs are relative/contained, one event is written, no implicit collect/export occurs, error/exit mappings are stable, and legacy `collect_unit(postprocess=True)` remains unchanged.

- [ ] **Step 1: Add RED service/API/process tests, including malformed files, missing optional DOS family, repeated IDs, symlink escape and reserved output paths.**
- [ ] **Step 2: Run RED:** `env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_postprocess_services.py tests/test_postprocess_machine_cli.py`.
- [ ] **Step 3: Implement the narrow service set using `ServiceContext.persist()` and the existing operation guard; do not add postprocess logic to `api.py` or the legacy `ForgeServices` facade.**
- [ ] **Step 4: Run GREEN with the service suites plus `tests/test_contracts.py tests/test_machine_cli.py tests/test_cli_process.py tests/test_units.py tests/test_dos_postprocess.py`; run `git diff --check`.**
- [ ] **Step 5: Commit:** `git add src/abacus_forge/postprocess_services.py src/abacus_forge/machine_cli.py src/abacus_forge/__init__.py tests/test_postprocess_services.py tests/test_postprocess_machine_cli.py && git commit -m "feat: expose typed band dos postprocess services"`.

### Task 4: Public documentation, capability evidence and final verification

**Files:**
- Modify: `README.md`, `ROADMAP.md`, this plan and the SDD ledger/report
- Modify only if required by the tests: `tests/README.md`, `tests/conftest.py`

**Behavior:** Document the exact typed request examples and explicit source-path requirement for `band`/`dos` postprocess, workspace-relative artifacts, `experimental` maturity, factual observations and unchanged legacy behavior. State that typed `export`, PyATB engine handoff, property/composite aggregation, scheduling, orchestration and scientific judgment remain separate boundaries. Do not claim a stable capability or real ABACUS evidence.

**Verification:**

- [ ] Run the full offline gate with the repository interpreter and flags: `env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider`.
- [ ] Run actual discovery commands and parse output: `PYTHONPATH=src ... -m abacus_forge.cli capabilities`, `... schema band postprocess`, `... schema dos postprocess`.
- [ ] Run `git diff --check`, forbidden-import scan and clean worktree check. Any pre-existing scan hits must be recorded, not silently reclassified.
- [ ] Obtain independent task reviews and a whole-branch review; close Critical/Important findings with revision-bound reruns.
- [ ] Commit docs and the exact verification evidence; do not merge or push.

## Self-review record

This plan was checked against the approved SPEC's independent postprocess request requirement, one-operation admission/event rule, facts-vs-science boundary, API/CLI parity, artifact containment and legacy compatibility clauses. It deliberately keeps `export` out because its source-result reference and destination/overwrite contract is not yet specified, and keeps PyATB out because the current helper has implicit SCF directory discovery. The only new public capabilities are narrow `band.postprocess` and `dos.postprocess`, each independently testable and still experimental. No unresolved product decision remains within this selected batch; the next PyATB and typed export batches require their own plans.

