# ABACUS-Forge Baseline Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the standalone `abacus-forge` repository the sole development baseline while preserving the reviewed code evolution through historical commit `e3d41a4`.

**Spec:** none - requirements supplied directly（repository comparison evidence + 2026-09-01 user approval: standalone repository is canonical, migrate `a003c55` and `e3d41a4`, exclude `db37bf1`）

**Architecture:** Preserve the two historical implementation commits in the standalone repository, then make the resulting checkout self-contained and aligned with the current PAIMON v1.3/standalone CLI product boundary. Historical PAIMON and `abacus-test` remain evidence sources, not runtime or test-time repository dependencies.

**Tech Stack:** Git, Python 3.10+, pytest, ASE, ABACUS text fixtures.

## Global Constraints

- The standalone `abacus-forge` repository is the only normative development repository.
- Migrate implementation commits `a003c55` and `e3d41a4`; do not migrate the stale plan-only commit `db37bf1`.
- Forge remains protocol-, scheduler-, UI-, and AiiDA-neutral.
- Tests must not contain machine-specific absolute paths or require sibling repository checkouts.
- Property packs remain experimental until real ABACUS validation supplies stronger evidence.
- Do not push or publish changes as part of this plan.

---

### Task 1: Preserve the reviewed historical implementation

**Files:**
- Modify through Git history: `README.md`, `ROADMAP.md`, `src/abacus_forge/**`, `tests/**`

**Test strategy:**
- Behavior boundary: the standalone checkout contains exactly the implementation delta through `e3d41a4`, without the plan-only `db37bf1` document.
- Existing suite to extend: none; verify with Git ancestry and tree comparison.
- New test file justification: none.
- Temporary probes: none.

**Interfaces:**
- Consumes: historical commits `a003c55` and `e3d41a4` from `../paimon/deps/abacus-forge`.
- Produces: unit primitives, flat collection, CubeData, and experimental property-pack APIs in the standalone repository.

- [x] **Step 1:** Fetch commit `e3d41a4` and its ancestors from the local historical repository.
- [x] **Step 2:** Cherry-pick `a003c55` followed by `e3d41a4`, preserving their order and commit identities.
- [x] **Step 3:** Verify `docs/abacus-forge-enhance.md` is absent and the source/test tree matches historical `e3d41a4` for the migrated paths.
- [x] **Step 4:** Run the full pytest suite in the existing `paimon` Conda environment and record the known absolute-fixture-path failure before fixing it.

### Task 2: Make the ABACUSTest reference regression self-contained

**Files:**
- Create: `.gitattributes`
- Modify: `tests/test_collect_abacus_reference.py`
- Create: `tests/fixtures/abacustest-abacus-scf/README.md`
- Create: `tests/fixtures/abacustest-abacus-scf/abacus.json`
- Create: `tests/fixtures/abacustest-abacus-scf/INPUT`
- Create: `tests/fixtures/abacustest-abacus-scf/out.log`
- Create: `tests/fixtures/abacustest-abacus-scf/time.json`
- Create: `tests/fixtures/abacustest-abacus-scf/OUT.ABACUS/INPUT`
- Create: `tests/fixtures/abacustest-abacus-scf/OUT.ABACUS/running_scf.log`
- Create: `tests/fixtures/abacustest-abacus-scf/LICENCE`

**Test strategy:**
- Behavior boundary: the collector comparison test runs from any checkout path without a sibling `abacus-test` repository.
- Existing suite to extend: `tests/test_collect_abacus_reference.py`.
- New test file justification: none; the existing regression already exposes the portability defect.
- Temporary probes: none.

**Interfaces:**
- Consumes: the minimal textual fixture subset currently read by `test_collect_matches_abacustest_reference_for_force_stress_and_pressure`.
- Produces: a repository-local fixture path resolved from `Path(__file__).parent`.

- [x] **Step 1 (RED):** Run the focused collector reference test and confirm it fails on the old machine-specific absolute path.
- [x] **Step 2:** Copy only the seven source files required by the regression into `tests/fixtures/abacustest-abacus-scf/`, include the source LGPL-3.0 license, record provenance, and exempt the verbatim fixed-width outputs from trailing-whitespace diagnostics through `.gitattributes`.
- [x] **Step 3 (GREEN):** Replace the absolute `fixture_root` with `Path(__file__).parent / "fixtures" / "abacustest-abacus-scf"`.
- [x] **Step 4:** Run the focused test and then the full suite; expect all tests to pass.

### Task 3: Align the standalone development entry and maturity claims

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `ROADMAP.md`

**Test strategy:**
- Behavior boundary: development commands resolve from the standalone repository root; no active documentation declares AiiDA as the PAIMON v1.3 mainline; experimental property packs are not presented as production-validated capabilities.
- Existing suite to extend: CLI help and full pytest suite.
- New test file justification: none; this task changes governance and documentation, not runtime behavior.
- Temporary probes: none.

**Interfaces:**
- Consumes: workspace-level `../AGENTS.md` product boundary and the migrated CLI/API implementation.
- Produces: a standalone-repository development entry, accurate commands, and explicit maturity labels.

- [x] **Step 1:** Rewrite stale `deps/abacus-forge` commands and PAIMON/AiiDA-mainline references for the standalone repository.
- [x] **Step 2:** Mark convergence/density/ELF/Bader/work-function/vacancy/BEC packs as experimental or fixture-tested until real ABACUS evidence exists.
- [x] **Step 3:** Run CLI `--help`, documentation/path searches, `git diff --check`, and the full pytest suite.
- [x] **Step 4:** Commit the portability, documentation, fixture, and plan changes without pushing.

### Task 4: Verify the unified baseline

**Files:**
- Verify only: repository history and worktree.

**Test strategy:**
- Behavior boundary: the unified branch contains the intended commits, excludes `db37bf1`, has no unexpected changes, and passes its complete test suite.
- Existing suite to extend: none.
- New test file justification: none.
- Temporary probes: none.

**Interfaces:**
- Consumes: completed Tasks 1-3.
- Produces: evidence that the branch is suitable as the next development baseline.

- [x] **Step 1:** Verify history contains `a003c55` and `e3d41a4` equivalents in order and excludes `db37bf1`.
- [x] **Step 2:** Run `git diff --check`, CLI help, and the full pytest suite fresh.
- [x] **Step 3:** Inspect `git status`, changed-file inventory, and final diff summary.
