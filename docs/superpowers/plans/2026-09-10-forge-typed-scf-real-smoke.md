# Typed SCF Real-Smoke Evidence Plan

**Goal:** Add an opt-in real-environment gate that proves the typed SCF
machine path, without treating the existing legacy smoke or parser facts as
scientific acceptance.
**Spec:** `docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html` and `docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html`, especially the typed API/CLI parity, status separation, and Stage 5 real-smoke release-gate clauses.
**Authorization:** Continued Forge development confirmed in this session;
the review of the current branch identified the missing typed SCF release
harness as the next in-scope closure item.
**Architecture:** Keep the legacy SCF smoke unchanged. Copy a caller-supplied
prepared workspace into a temporary directory, invoke the existing typed
`operation execute` and `operation collect` machine commands with distinct
operation IDs, and assert only serialized execution/collection, artifact and
audit facts. The gate remains opt-in and skipped when its external inputs are
not supplied.
**Verification:** Default offline tests still skip real-smoke tests; the
explicit real-smoke selection validates the supplied executable/workspace and
fails on malformed supplied inputs. Run the focused real-smoke collection
check, the machine/CLI owning suites, `git diff --check`, and the full offline
suite. No stable-maturity promotion is made by this plan.

## Scope and boundaries

- Change only `tests/real_smoke/test_abacus_smoke.py`, `tests/conftest.py`,
  `tests/real_smoke/README.md`, `tests/README.md`, and this plan.
- Reuse `ABACUS_FORGE_REAL_SMOKE_WORKSPACE` and
  `ABACUS_FORGE_ABACUS_EXECUTABLE`; register the typed test explicitly in the
  real-smoke environment map.
- Copy the prepared workspace with `symlinks=False`; never execute against or
  mutate the caller's source directory.
- Use the existing `run_cli` helper and typed machine request schema. Require
  `execution=completed`, `collection=complete`, a reported finite
  `total_energy`, `scientific=unassessed`, one event for each operation, and
  contained relative artifact/event paths.
- Do not assert convergence thresholds, physical correctness, scheduler
  behavior, workflow orchestration, retry/resume, or any result interpretation.
- If the executable or source workspace is absent, the test is skipped by the
  existing real-smoke gate. If a supplied value is invalid, the test fails
  clearly; it must never turn an invalid environment into a passing result.

## Task 1: Add typed SCF machine-path real smoke

**Files:** `tests/real_smoke/test_abacus_smoke.py`, `tests/conftest.py`.

Implement one test beside the legacy SCF smoke. It must:

1. validate the supplied workspace directory and executable using the same
   conventions as the existing smoke tests;
2. copy the workspace into `tmp_path` and send typed `execute` and `collect`
   requests through `run_cli`, with distinct valid UUIDv4 operation IDs;
3. assert one JSON stdout document, empty stderr, completed execution,
   complete factual collection, finite reported energy and unassessed
   scientific status;
4. verify each operation event payload equals its machine result and that the
   workspace manifest records both events with relative contained paths;
5. verify returned artifact paths are relative and resolve inside the copied
   workspace.

Add the test name to `_REAL_SMOKE_ENV_BY_TEST` with the shared two variables.
Run the test without `--run-real-smoke` to establish the expected skip; no
real ABACUS executable is assumed to be available locally.

## Task 2: Document the evidence distinction

**Files:** `tests/real_smoke/README.md`, `tests/README.md`, `README.md`,
`ROADMAP.md`, this plan.

Document that the existing legacy SCF smoke and the new typed SCF machine
smoke are separate evidence surfaces; only the latter proves the typed
operation path. Record the actual local result as skipped when no external
workspace/executable is supplied. Keep all current capabilities experimental
until the real gate and other Stage 4 gates have their own evidence.

## Acceptance record

- [x] Typed SCF machine smoke is implemented without modifying legacy API or
  runtime source.
- [x] Default real-smoke selection skips cleanly when environment values are
  absent; supplied invalid values fail.
- [ ] Focused machine/CLI suites and full offline suite pass; real evidence is
  reported only when an external workspace and executable are actually
  supplied.
- [ ] `git diff --check` passes and the branch remains unmerged/unpublished.

## Implementation record (2026-09-10)

- Added `test_typed_scf_machine_execute_and_collect` beside the unchanged
  legacy SCF smoke. It reuses the legacy SCF environment values, materializes
  the supplied workspace with `copytree(..., symlinks=False)`, invokes typed
  machine `execute` and `collect` requests with fresh UUIDv4 IDs, and checks
  factual status, finite energy, operation events, manifest entries, artifact
  references, and path containment.
- Registered the typed test in the existing real-smoke environment map. A
  focused default run without external values produced `1 skipped, 2
  deselected`; a run with supplied invalid paths failed clearly at workspace
  validation. Neither run is real ABACUS evidence.
- Updated both test READMEs to distinguish legacy SCF compatibility evidence
  from typed SCF machine-path evidence. Scientific validation, scheduling,
  orchestration, and maturity promotion remain outside this gate.

**Ruling:** This plan closes a release-evidence harness gap only. It does not
promote SCF maturity, add typed MD/PyATB/NEB real smoke, or alter the approved
Forge responsibility boundary; those remain separate evidence batches.
