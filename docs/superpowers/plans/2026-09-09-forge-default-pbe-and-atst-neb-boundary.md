# Forge PBE Default and ATST NEB Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Forge's ABACUS preparation policy explicitly default to PBE and freeze a future, optional atst-tools-backed NEB adapter without moving Slurm, site scheduling, or scientific judgement into Forge.

**Spec:** `docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html`, `docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html`, plus the 2026-09-09 user ruling in this task. ATST integration references the maintained `atst-tools` CLI and Python API documentation: <https://github.com/QuantumMisaka/atst-tools/blob/main/docs/user/CLI_REFERENCE.md> and <https://github.com/QuantumMisaka/atst-tools/blob/main/docs/user/PYTHON_API_REFERENCE.md>.

**Architecture:** `prepare_profiles.build_task_parameters()` emits an explicit lowercase `dft_functional=pbe` default for every ABACUS task profile; caller-supplied parameters and input overrides remain authoritative. A later NEB capability will be an optional engine adapter that delegates workflow/image execution to atst-tools, exposes Forge's existing `prepare`, `execute`, and `postprocess` operation names, and records workspace-relative facts/artifacts. The adapter is not imported by core modules and does not implement Slurm, site launch, retry, or scientific acceptance.

**Tech Stack:** Existing Python/pytest stack; no new required dependency in this plan. Future ATST work must use only documented stable `atst_tools.api` names or the documented API runner, with an explicitly tested optional dependency.

## Global Constraints

- PBE is the default `dft_functional` value; explicit request/profile values override it. This is an input policy, not a scientific conclusion.
- Keep the frozen Forge operation grammar (`prepare`, `modify`, `execute`, `collect`, `postprocess`, `export`); external `atst neb post` maps to Forge `postprocess`, not a new top-level `post` operation.
- atst-tools is a delegated optional engine for a future NEB capability. It may own NEB image/workflow execution, but Forge must not own Slurm, platform scheduling, site launchers, retry/resume policy, or workflow DAG semantics.
- Core Forge imports and required dependencies remain free of `atst_tools`; any future adapter is isolated, lazy/optional, and advertises its dependency and maturity through capability discovery.
- All outcomes preserve operation identity, execution/collection status, observations, diagnostics, artifact refs, and the no-scientific-acceptance boundary from the 09-02 SPEC.
- Default regression stays offline and deterministic; real atst-tools/ABACUS evidence is an explicit future smoke gate.

## Rulings

- **Ruling:** Land the PBE default now as an explicit profile value rather than relying on ABACUS's implicit default. **Why:** this makes Forge's reproducible input policy visible while preserving caller overrides. **Cost if wrong:** generated INPUT snapshots gain one explicit line and any consumer comparing raw text must account for that additive default.
- **Ruling:** Do not add an atst-tools runtime dependency or NEB public request schema in this change. **Why:** the dependency is not installed in the current Forge environment and the exact adapter contract needs a dedicated real-smoke plan. **Cost if wrong:** NEB support starts one planned slice later; adding an unverified adapter now would risk coupling core contracts to an unstable external surface.
- **Ruling:** Treat atst-tools as the NEB image/workflow orchestration engine, not as Forge's site scheduler. **Why:** its documented `atst run`/API handles YAML-driven workflow execution and image-level parallelism, while the outer site launcher and Slurm remain external. **Cost if wrong:** the future adapter boundary would need to be reworked, but the current core remains unaffected.

### Task 1: Record the approved defaults and delegated ATST boundary

**Files:**
- Modify: `docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html`
- Modify: `docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html`
- Modify: `README.md`
- Modify: `ROADMAP.md`

**Test strategy:**
- Behavior boundary: documentation is the normative statement that PBE is Forge's explicit default, Slurm remains out of scope, and a future atst-tools NEB adapter is optional/delegated.
- Existing suite to extend: no new test file; run the documentation grep and full offline suite in Task 3.

**Interfaces:**
- Consumes: frozen operation/status/artifact contracts in the two approved SPECs.
- Produces: a concise decision record and roadmap entry naming the future adapter's prepare/execute/postprocess shape and its optional dependency boundary.

- [x] **Step 1: Add the minimal normative decision text**

  Add one PBE default statement to the architecture/input-policy portion of the 09-01 SPEC, and one short ATST delegation statement to the engine/rollout portion of the 09-02 SPEC. Do not duplicate the full Copilot or ATST feature lists.

- [x] **Step 2: Align user-facing docs**

  State in `README.md` that generated ABACUS INPUT profiles explicitly default to `dft_functional=pbe`, while parameters can override it. Add a ROADMAP item for the optional ATST NEB adapter and retain the existing explicit Slurm exclusion.

- [x] **Step 3: Verify the documentation boundary**

  Run:

  ```bash
  rg -n "dft_functional|PBE|atst-tools|postprocess|Slurm|scheduler" \
    docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html \
    docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html \
    README.md ROADMAP.md
  ```

  Expected: PBE, delegated ATST NEB, Forge `postprocess`, and the Slurm exclusion are each stated without adding a `post` core operation or scheduler implementation claim.

- [x] **Step 4: Commit**

  ```bash
  git add docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html \
    docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html \
    README.md ROADMAP.md
  git commit -m "docs: record pbe default and atst neb boundary"
  ```

### Task 2: Make PBE explicit in task preparation

**Files:**
- Modify: `src/abacus_forge/prepare_profiles.py`
- Modify: `tests/test_api.py`

**Test strategy:**
- Behavior boundary: every supported ABACUS task profile gets `dft_functional=pbe` when the caller does not provide one; explicit `parameters` and `input_overrides` remain authoritative.
- Existing suite to extend: `tests/test_api.py` already owns prepare/task profile integration and is marked `integration` by `tests/conftest.py`.

**Interfaces:**
- Consumes: `build_task_parameters()` and `prepare()`'s existing merge order.
- Produces: the same returned workspace and INPUT snapshots, with one explicit default parameter.

- [x] **Step 1: Write the failing regression**

  Add tests that prepare representative `scf`, `relax`, `md`, `band`, and `dos` workspaces and assert `INPUT["dft_functional"] == "pbe"`; add one test proving an explicit `parameters={"dft_functional": "pbesol"}` value survives.

- [x] **Step 2: Run the focused tests to verify the gap**

  ```bash
  conda run -n paimon python -m pytest tests/test_api.py -q
  ```

  Expected before implementation: the new default assertions fail because current profiles omit `dft_functional`.

- [x] **Step 3: Implement the smallest profile change**

  Add the shared explicit `dft_functional: "pbe"` default to the existing task-profile merge without changing the caller override order or legacy execution path.

- [x] **Step 4: Run the focused tests again**

  ```bash
  conda run -n paimon python -m pytest tests/test_api.py -q
  ```

  Expected: PASS, including the explicit PBEsol override case.

- [x] **Step 5: Commit**

  ```bash
  git add src/abacus_forge/prepare_profiles.py tests/test_api.py
  git commit -m "feat: make pbe the explicit forge default"
  ```

### Task 3: Verify the combined change and preserve the deferred ATST scope

**Files:**
- No additional production files.

**Test strategy:**
- Behavior boundary: current Forge behavior remains compatible apart from the intentional explicit PBE input default; no atst_tools import, required dependency, Slurm code, or new `post` operation appears.
- Existing suite to extend: `tests/test_architecture.py`, `tests/test_contracts.py`, `tests/test_api.py`, and the full offline suite.

**Interfaces:**
- Consumes: Tasks 1–2 changes.
- Produces: revision-bound test and boundary evidence for the next dedicated ATST adapter plan.

- [x] **Step 1: Run boundary scans**

  ```bash
  rg -n "from atst_tools|import atst_tools|slurm|DPDispatcher|Bohrium|post\b" src/abacus_forge pyproject.toml
  ```

  Expected: no new core import, required dependency, scheduler integration, or Forge top-level `post` operation.

- [x] **Step 2: Run the complete offline suite**

  ```bash
  conda run -n paimon python -m pytest -q
  ```

  Expected: all existing tests pass, with only the repository's documented skips.

- [x] **Step 3: Check diff hygiene**

  ```bash
  git diff --check
  git status --short --branch
  ```

  Expected: no whitespace errors; only the intended commits are present and the worktree is clean.

- [x] **Step 4: Commit the verification record if needed**

  No source commit is required for a clean verification. The next ATST implementation must start from a dedicated plan that pins a tested atst-tools version, selects documented stable APIs, and supplies real-smoke evidence before discovery promotion.

## Self-review record

- Checked against 09-01 goals/non-goals, R1/R7/R10; 09-02 summary, boundary, R3/R5/R7/R10, operation grammar, and Stage 4 rollout.
- Confirmed current baseline before edits: `conda run -n paimon python -m pytest -q` → `348 passed, 2 skipped`.
- Confirmed atst-tools maintained docs expose `atst_tools.api.run_workflow`, `validate_config`, the API runner, and lightweight `atst neb make/post/summary`; the docs also keep site launch/scheduler concerns outside the package.
- No unresolved public-field decision is needed for this documentation/PBE slice. Exact `AtstNeb*Request` fields remain intentionally outside this plan and must be settled in the dedicated implementation plan described in Task 3.

## Execution evidence (2026-09-09)

- Documentation boundary grep completed; the only `post` matches in `src/abacus_forge/cli.py` are the pre-existing composite/property task-pack commands, not a new core operation.
- RED focused run: `conda run -n paimon python -m pytest tests/test_api.py -q` reported 5 new PBE assertions failing with `KeyError` and 19 existing tests passing.
- GREEN focused run: the same command reported `24 passed`.
- Full offline run: `conda run -n paimon python -m pytest -q` reported `354 passed, 2 skipped`.
- `git diff --check` completed without errors; the implementation is isolated on branch `forge-copilot-neb` and has not been merged to `main`.
