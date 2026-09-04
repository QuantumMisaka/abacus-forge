# Stage 3 Task 1 Report

## Result

Completed the typed local-runner configuration for `ScfExecuteRequest` while preserving `forge.request/v1`, existing defaults, `dry_run`, strict decoding, and deterministic serialization.

## RED evidence

Command:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_contracts.py
```

Result: expected failure before implementation: `50 passed, 1 failed`; construction rejected the new `executable` keyword.

## GREEN evidence

Command:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_contracts.py tests/test_service_status.py
```

Result: `103 passed`.

Full-suite command:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
```

Result: `269 passed, 2 skipped`.

## Changed files

- `src/abacus_forge/contracts.py`: added `executable`, `mpi_ranks`, `omp_threads`, and `timeout_seconds`; added strict validation and serialization.
- `tests/test_contracts.py`: added round-trip, invalid-value, and unknown-field coverage.

## Self-review

- Minimal construction remains valid with defaults (`abacus`, `1`, `1`, `None`, `False`).
- Boolean values are rejected for integer and timeout fields.
- Counts require positive integers; timeout requires a positive finite number or `None`.
- Existing strict unknown-field decoding remains active; no launcher, argv/extra args, environment, shell, scheduler, or scientific fields were added.
- `git diff --check` passed.

## Concerns

The brief mentions rejecting empty argv entries, but the specified interface explicitly excludes argv/extra args. No argv field was introduced; empty executable values are rejected.

## Review fix evidence

Review identified missing direct coverage for negative values and wrong/non-JSON types in the newly added fields. Added parametrized cases covering negative `mpi_ranks`, `omp_threads`, and `timeout_seconds`, plus list/dict executable values and string/list-like numeric values.

Focused verification after the fix: `112 passed`.

Full-suite verification after the fix: `278 passed, 2 skipped`.
