# Forge typed real-smoke freshness gate plan

**Goal:** prevent the existing typed SCF, Relax/cell-relax, and MD real-smoke
gates from treating generated files copied from an earlier run as evidence of
the current `execute` call.

**Spec baseline:** `docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html`
real-smoke/testing and boundary clauses, plus the completed typed SCF/Relax/MD
operation plans. This is a test-facility correction; it does not alter a Forge
runtime contract.

**Authorization:** continue the user-authorized Forge implementation stream in
an isolated worktree based on `3f61505`; do not modify `main` or push.

**Architecture:** add one collector-aware freshness helper to the existing
real-smoke test module. Each typed test calls it after copying the supplied
workspace and before `execute`. The helper rejects only generated files that
the corresponding collector can consume and the runner does not reliably
replace; it never deletes the caller's source. Normal Forge `execute` and
`collect` behavior remains unchanged.

## Scope

- `tests/real_smoke/test_abacus_smoke.py`: shared guard and calls from typed SCF,
  Relax/cell-relax, and MD tests.
- `tests/test_real_smoke_freshness.py`: offline positive/negative coverage for
  the guard's collector path and suffix boundaries.
- `tests/real_smoke/README.md`, `tests/README.md`, `README.md`, `ROADMAP.md`:
  state that supplied real-smoke sources must be fresh with respect to
  generated domain outputs.
- This plan and the ignored SDD ledger record evidence and review.

## Non-goals and constraints

- No production `runner`, collector, service, request schema, artifact schema,
  or persistence change.
- No scheduler, retry/resume, workflow, monitor, or scientific validation.
- Do not reject arbitrary `inputs/OUT.*` restart/handoff assets; reject only
  named generated logs/artifacts that can make a typed smoke pass without a
  new run.
- A supplied source with stale generated outputs fails explicitly. The source
  is never modified; callers must provide a fresh prepared copy.
- `/bin/true` plus stale outputs is a required deterministic negative check for
  SCF and Relax; the MD stale-output negative already exists and remains.

## Task 1: shared freshness guard

**Files:** `tests/real_smoke/test_abacus_smoke.py`

- [x] Write a helper that scans the copied workspace for generated files under
  collector-visible Forge areas (including `reports/` running logs), with
  capability-specific names: SCF/Relax running logs and fallback `out.log`;
  Relax final-structure outputs matching the collector suffix set; MD
  `running_md.log` and `MD_dump`.
- [x] Call the helper before each typed execute. Preserve the existing MD
  guard's behavior while moving it to the shared implementation.
- [x] Verify `--run-real-smoke` with no variables still skips all four tests.

## Task 2: deterministic stale-output negatives

**Files:** `tests/real_smoke/test_abacus_smoke.py`,
`tests/test_real_smoke_freshness.py`, optional temporary probe

- [x] With `/bin/true` and a copied stale SCF source (including a
  `reports/running_scf.log` case), verify the typed SCF smoke fails before
  execution.
- [x] With `/bin/true` and stale Relax log/final structure (including the
  ordinary `STRU` and a prefixed filename matching the collector's suffix
  semantics), verify the typed Relax smoke fails before execution.
- [x] Keep the existing stale MD log negative and verify the shared guard also
  rejects stale MD dump output.

## Task 3: documentation, verification, and review

**Files:** four docs above and this plan.

- [x] Document the freshness requirement as an evidence-gate input condition,
  not a Forge runtime rule; keep `scientific=unassessed` and experimental
  maturity explicit.
- [x] Run typed real-smoke skip/fail-fast selections, all typed operation/API
  owning suites, architecture, full offline, benchmark opt-in and diff checks.
- [ ] Obtain an independent task/whole-branch review; fix all Critical and
  Important findings and record justified Minor findings.

## Verification evidence

- `--run-real-smoke -m real_smoke tests/real_smoke/test_abacus_smoke.py` with no
  external variables: `4 skipped`.
- Guard unit tests plus typed operation/API/architecture owning suites:
  `660 passed`.
- Full offline gate (`not real_smoke and not benchmark`): `1222 passed, 6
  deselected`.
- Benchmark opt-in: `2 passed, 1226 deselected`.
- `/bin/true` fail-fast probes reject stale `reports/running_scf.log`, stale
  `reports/running_relax.log` plus `outputs/OUT.ABACUS/STRU`, and stale MD
  `outputs/OUT.ABACUS/MD_dump`; the offline guard positive test allows explicit
  `inputs/OUT.*` handoff files and non-domain report files. A prefixed
  `outputs/OUT.ABACUS/final_STRU` probe also fails, proving suffix matching
  follows the collector rather than exact basenames.
- `git diff --check` passed before commit.

## Rulings

- `Ruling: fix evidence integrity at the test boundary, not by adding lineage
  fields to forge.request/v1 or changing collect semantics.` The service is
  intentionally an independent factual collect primitive; a release smoke
  gate must instead start from a fresh prepared copy.
- `Ruling: reject targeted generated outputs, not all inputs/OUT.*.` Explicit
  restart and artifact handoff assets may be legitimate prepared inputs and
  remain the caller's responsibility; the gate only prevents known collector
  outputs from being reused.
- `Ruling: mirror collector suffix and path boundaries.` Relax freshness uses
  the collector's complete final-structure suffix set while preserving
  `inputs/` handoffs and `reports/` audit files as non-domain structure
  candidates.
