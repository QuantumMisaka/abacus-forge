# Final fix v4 implementation report

## Scope and diagnosis

This wave addressed only the three findings in `final-fix-v4-brief.md`:

1. Typed `modify_scf` and non-dry-run `execute_scf` admitted operation IDs but did not check the required prepared SCF files before invoking the primitive/runner.
2. Direct public-v1 audit writes re-raised raw `OSError` for event-file and manifest replacement failures when no claim token was supplied.
3. Wrong request objects were passed to error-context extraction, allowing arbitrary `operation_id`/`workspace_rel` attributes to break `ForgeErrorEnvelope` construction.

The existing operation guard, claim tombstones, event reconciliation, dry-run branch, legacy event writer, and exception classification were preserved.

## TDD RED

Added regression coverage in `tests/test_service_status.py` for all three typed-service contracts and in `tests/test_workspace.py` for direct-v1 event and manifest write failures. The focused RED command was:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_workspace.py::test_v1_event_reconciles_after_manifest_write_failure tests/test_workspace.py::test_v1_event_file_failure_is_typed_and_leaves_no_event tests/test_service_status.py::test_typed_scf_services_do_not_copy_context_from_wrong_request_type tests/test_service_status.py::test_typed_scf_missing_inputs_are_admitted_preconditions
```

Observed RED result:

```text
10 failed in 1.20s
```

The failures demonstrated raw `OSError`, invalid foreign context validation, and missing-input execution reaching internal-failure/sentinel paths.

## Implementation

- `src/abacus_forge/services.py`
  - Wrong-type service branches now construct `request.invalid` with a `None` context object, yielding `operation_id=None` and `workspace_rel=None`.
  - `modify_scf` now requires `inputs/INPUT` inside the admitted operation, before snapshots and `modify_unit`.
  - Non-dry-run `execute_scf` now requires `inputs/INPUT`, `inputs/STRU`, and `inputs/KPT` inside the admitted operation, before runner preflight/start.
  - Dry-run execution remains unchanged and does not require prepared assets.
- `src/abacus_forge/workspace.py`
  - Direct and claimed v1 event-file and manifest-write `OSError` paths now consistently raise `ForgePersistenceError`.
  - Legacy `append_operation_event()` behavior was not changed.
- `tests/test_service_status.py`
  - Added parameterized wrong-request context tests.
  - Added parameterized missing-input tests covering modify and each required execute asset, including claim retention, no event, primitive/runner non-invocation, and same-ID conflict.
  - Updated runner-path fixtures to provide the now-required prepared assets.
- `tests/test_workspace.py`
  - Updated direct-v1 manifest-failure expectation to `ForgePersistenceError` while retaining reconciliation assertions.
  - Added direct-v1 event-file failure coverage.

## TDD GREEN and verification

Focused exact verification:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_workspace.py tests/test_service_status.py
........................................................................ [ 83%]
..............                                                           [100%]
86 passed in 5.28s
```

Broader exact verification:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_contracts.py tests/test_result_contract.py tests/test_units.py
.............................................................            [100%]
61 passed in 2.43s
```

Working-tree whitespace check before commit:

```text
git diff --check
```

Result: clean, with no output.

## Self-review

- Admission precedes all new file checks. A missing-input failure therefore leaves its claim tombstone, writes no success event, does not invoke the primitive/runner, and causes same-ID reuse to return `operation.conflict`.
- The dry-run branch still only ensures the layout and writes its skipped result; it does not inspect prepared assets or start a runner.
- Direct-v1 event evidence remains append-only. If manifest replacement fails after the event file is written, the typed persistence error leaves the event available for the existing locked reconciliation path.
- No changes were made to the legacy random-ID event writer, raw primitive/runner exception classification, workflow/retry/recovery/rollback/scientific policy, or specs/plans/docs.
- No remaining implementation uncertainty was found within the declared scope.
