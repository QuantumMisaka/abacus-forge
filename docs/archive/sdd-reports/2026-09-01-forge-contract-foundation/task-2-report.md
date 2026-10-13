# Task 2 report: safe workspace persistence

## Base and head

- Base: `2fafe25` (`fix: freeze forge contract JSON values`)
- Head: `HEAD` (Task 2 implementation commit; final hash recorded at handoff)

## RED evidence

Ran:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_workspace.py
```

Result: 2 failed. The escape-path test did not raise, and `Workspace` had no `append_operation_event` method.

## Implementation

- Added `resolve_relative` and private owned-path resolution using resolved paths and root containment checks.
- Routed text and JSON writes through owned-path resolution.
- Added atomic JSON writes using a destination-directory temporary file, flush, fsync, and replace; JSON NaN/Infinity values are rejected.
- Added one-time `reports/forge-workspace.json` initialization with the versioned workspace schema.
- Added UUID-named operation event writes and append-only manifest references.

## Changed files

- `src/abacus_forge/workspace.py`
- `tests/test_workspace.py`
- `.superpowers/sdd/2026-09-01-forge-contract-foundation/task-2-report.md`

## Tests and results

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_workspace.py tests/test_api.py tests/test_units.py
29 passed in 2.38s
```

## Commit

`feat: persist forge workspace events safely`

## Risks

 The lock uses Unix `fcntl`; the supported runtime is Unix. A process crash
 between event creation and manifest replacement can leave an unreferenced
 event file, but cannot remove an already-recorded reference.

## Fix round 1

- Review finding addressed: `append_operation_event()` now serializes the full
  event creation and manifest read-modify-write with a cross-process Unix
  `fcntl.flock` lock stored under `reports/`.
- Added a two-process regression test that appends 16 events and verifies all
  manifest references are retained.
- Added parent-directory fsync after atomic replacement where supported by the
  Unix filesystem.
- Verification: `30 passed` for `tests/test_workspace.py`,
  `tests/test_api.py`, and `tests/test_units.py`.
- Fix commit: `6cb475e` (`fix: serialize concurrent workspace event appends`).

## Fix round 2

- Public `ensure_manifest()` now acquires the manifest lock and delegates to
  `_ensure_manifest_unlocked()`; append uses that helper inside its existing
  critical section, avoiding nested lock acquisition.
- Added a coordinated cross-process test proving public initialization waits
  for the shared lock and cannot reset event history.
- Manifest-update failures now attempt to remove only the newly-created event,
  preserving the primary exception; a crash can still leave a reconcilable
  orphan.
- Directory fsync is explicitly best-effort: open and fsync errors are
  swallowed after atomic replacement, so unsupported filesystems do not turn a
  successful write into a spurious failure.
- Verification: `31 passed` for `tests/test_workspace.py`,
  `tests/test_api.py`, and `tests/test_units.py`.
- Fix commit: `0822a46` (`fix: serialize public workspace manifest initialization`).
