# Task 6 report: operation admission integrity

## RED

Command:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_workspace.py tests/test_service_status.py
```

Key output:

```text
ModuleNotFoundError: No module named 'abacus_forge.errors'
```

The newly added integrity tests therefore failed at collection before the
implementation existed.

## Implementation and GREEN

The workspace now has a keyed in-process lock plus an exclusive filesystem
lock. `operation_guard` holds that lock from admission through domain action
and event/manifest commit. Admission uses an exclusive create and an opaque
random owner token. Existing claim/event markers always conflict; PID liveness
and age are not inspected. Admission is removed only after the event and
manifest are durably written by the matching owner. Failures leave a
tombstone. Service error classification uses typed exceptions rather than
matching conflict/persistence messages.

Focused GREEN command:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_workspace.py tests/test_service_status.py
```

Output: `72 passed in 2.98s`.

Compatibility GREEN command:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_contracts.py tests/test_result_contract.py tests/test_units.py
```

Output: `53 passed in 2.76s`.

Broader regression command:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
```

Output: `237 passed, 2 skipped in 16.10s`.

## Files

- `src/abacus_forge/errors.py`: typed request, conflict, precondition,
  persistence, and internal failure classes.
- `src/abacus_forge/workspace.py`: workspace lock, atomic admission,
  owner-token verification, tombstone retention, and typed persistence
  boundaries.
- `src/abacus_forge/services.py`: service guard integration, typed owner
  commit, and stable error-class mapping.
- `tests/test_workspace.py`: stale-claim, owner-token, and persistence
  tombstone regressions.
- `tests/test_service_status.py`: stale admission, same-workspace
  serialization, duplicate conflict, and class-5 persistence regressions.

## Self-review

- No rollback, recovery, retry, scheduler, or orchestration behavior was
  added.
- `append_v1_operation_event` keeps its legacy unclaimed behavior; typed
  services exclusively use the guarded owner-token path.
- A failed event/manifest commit intentionally leaves the immutable event (if
  written) and admission marker for reconciliation/safety; the same ID is
  never replayable.
- Task 7 concerns (`OperationOutcome`, `Observation`, and policy removal) were
  not implemented.
- `git diff --check` passed.

## Commit

`0efb2b0 fix: prevent typed operation replay`

## Review fix round 1

The review identified two missing regression scenarios. The pre-fix test
command for the new tests was run against `0efb2b0`; both cases passed because
the implementation already provided the required behavior. This is recorded
as a GREEN-before-test-expansion result rather than claiming a production
failure that was not observed.

Focused command and output:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py -k 'concurrent_same_id or event_failure'
2 passed, 41 deselected in 0.76s
```

Added regressions:

- A first same-ID service call blocks inside the supplied runner sentinel;
  the concurrently entered second call cannot reach the runner or write a
  domain result, and returns `operation.conflict` after the first commits.
- Event-file write injection (separate from manifest injection) returns
  `persistence.failure`, leaves the admission tombstone, and makes a second
  same-ID call return `operation.conflict`.

Post-fix focused/compatibility output:

```text
127 passed in 5.26s
```

The new test-only fix is committed in the follow-up commit recorded below.
