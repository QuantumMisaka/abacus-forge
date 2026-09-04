# Final fix v2 report

Date: 2026-09-04
Base: `b244c1c`
Commit: `2591cd1` (`fix: close final forge contract review findings`)

## Scope and diagnosis

This was the single concentrated fix wave from the amended-plan whole-branch
review. The branch already contained the approved `OperationOutcome`, frozen
`forge.result/v1` envelope, operation admission/owner-token/tombstone model,
legacy API/CLI compatibility, and upper-layer boundary. Those interfaces were
preserved.

The remaining findings were:

- `ForgeErrorEnvelope` accepted arbitrary error classes and typed services
  classified every untyped `TypeError`/`ValueError` as a request error.
- `LocalRunner` collapsed signal termination into generic nonzero exit and did
  not expose a termination fact for successful, timeout, or failed processes.
- prepare artifact enumeration and modify input snapshots followed symlinks
  without checking their resolved target against the workspace.
- entry documentation still described typed SCF as a policy path.
- `ForgeServices._execution` was unused state.

## TDD evidence

RED was established with new regressions for:

- the frozen seven-value error class set;
- unexpected collector/parser `ValueError` mapping to `internal.failure`;
- real local subprocess zero exit, nonzero exit, timeout, and signal cases,
  including outcome, event, artifact, returncode, failure class, and
  termination facts;
- prepare and modify symlinks whose resolved target escapes the workspace.

GREEN after implementation:

- focused contract/workspace/result/typed-service suite: `112 passed`;
- full suite: `234 passed, 2 skipped`.

## Changes

- Added the frozen seven-value `ERROR_CLASSES` contract validation.
- Changed wrong typed request objects to `request.invalid`; only explicit
  `ForgeRequestError` subclasses map to request errors. Unexpected runner,
  collector, parser, or internal `TypeError`/`ValueError` now maps to
  `internal.failure`.
- Added LocalRunner `termination` facts: `exited`, `timeout`, `signal`, and
  `not_started` for missing executable; signal returncodes retain the native
  negative subprocess value.
- Added resolved-target containment checks for prepare artifacts and modify
  snapshots. Escaping symlinks raise `ForgePathError` before exposure or
  hashing.
- Removed unused `_execution` state.
- Reworded `README.md`, `AGENTS.md`, and `tests/README.md` so typed SCF is a
  factual execution/collection and observation surface; compatibility
  `scientific` is written only as `unassessed`.

## Verification and scans

Executed in `conda` environment `paimon`:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider \
  tests/test_contracts.py tests/test_workspace.py tests/test_result_contract.py tests/test_units.py
92 passed in 3.66s

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
234 passed, 2 skipped in 15.96s
```

Static checks passed:

- `git diff --check`;
- no `request.type`, `policy_id`, `evaluate_abacus_scf`, or `_execution` in
  production/entry documentation scan;
- compatibility wording scan confirms only `scientific`/`unassessed` factual
  boundary language remains;
- worktree clean after commit.

## Remaining uncertainty

No known finding from the final-fix-v2 brief remains open. This report does
not claim real ABACUS physics validation, scheduler validation, scientific
acceptance, orchestration, retry/recovery, or a new CLI; those remain outside
this Forge slice and its approved boundary.
