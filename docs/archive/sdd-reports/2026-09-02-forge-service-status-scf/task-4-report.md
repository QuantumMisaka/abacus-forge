# Task 4 implementation report

## Evidence before editing

The approved typed SCF request variants currently carry only operation identity,
workspace-relative scope, policy id, and schema version. They intentionally do
not expose a UnitSpec-shaped payload. The legacy primitives remain the only
source of SCF input preparation, modification, execution, and collection.

## RED

Command:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py tests/test_result_contract.py
```

Result: failed during collection with `ImportError: cannot import name
'ForgeServices' from 'abacus_forge'`, proving the typed service boundary was
absent. The new legacy projection assertion also had no implementation yet.

## Implementation

- Added `ForgeServices.default()` with workspace-root containment and injected
  `LocalRunner` support.
- Added typed `prepare_scf`, `modify_scf`, `execute_scf`, and `collect_scf`
  adapters. Each invokes its existing legacy primitive once, converts expected
  exceptions to `ForgeErrorEnvelope`, and appends a caller-owned v1 event only
  after creating a result envelope.
- Collection service alone applies `abacus.scf/v1`, using collected normal-end,
  convergence, parser, and workspace-output evidence. Execution is sourced from
  the operation result / persisted execute record, never inferred from logs.
- Changed policy-free `CollectionResult.to_envelope()` to keep scientific status
  `unassessed`; its convergence check remains informational. `to_dict()` was not
  changed.
- Exported `ForgeServices` from the package boundary.

The request contract does not yet provide operation-specific prepare/modify/
execute fields. This slice therefore uses the established SCF defaults and an
injected runner. Adding those fields belongs to a subsequent contract plan;
they were not smuggled into a broad public payload here.

## Verification

Focused and requested regression command:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py tests/test_contracts.py tests/test_workspace.py tests/test_result_contract.py tests/test_units.py tests/test_cli_process.py
```

Result: `115 passed in 8.03s`.

Full deterministic suite:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
```

Result: `220 passed, 2 skipped in 13.01s`.

`git diff --check` passed.

## Fix round 2

The scoped review found only a missing negative test for a valid typed request
that fails inside the service. Added a test with an injected failing runner;
the pre-existing legacy event manifest remains unchanged and contains no
caller-owned v1 event for the failed request. Production code already returned
the required `ForgeErrorEnvelope`, so no production change was necessary.

Focused verification command:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py tests/test_result_contract.py tests/test_contracts.py tests/test_workspace.py tests/test_units.py tests/test_cli_process.py
```

Result: `118 passed in 8.28s`; `git diff --check` passed.

## Fix round 1

### Diagnosis

The first implementation let `prepare_unit` and `modify_unit` append their
legacy random operation event before the service appended the caller-owned v1
event.  It also prepared an SCF workspace without a structure, translated no
typed modification inputs, and reported modification as executed even though
no runner was called.

### Changes

- Added the keyword-only `record_event=True` compatibility switch to
  `prepare_unit` and `modify_unit`; typed services pass `False`, leaving all
  existing callers unchanged.
- Added required-at-validation `structure_path_rel`, optional
  `structure_format`, and JSON-safe `parameters` to `ScfPrepareRequest`.
  Services resolve the structure only inside the target workspace and map it
  once into the existing `UnitSpec`.
- Added JSON-safe `input_updates` and `remove_parameters` to
  `ScfModifyRequest`, mapping them once to `UnitModifySpec`.
- Typed modification envelopes now report `execution="not_run"`; the
  primitive still writes its legacy result record for compatibility.
- Added tests for narrow request round trips, legacy event preservation,
  exactly one primitive call per typed service, and exactly the four supplied
  v1 event IDs.

### Fix verification

Focused command:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py tests/test_contracts.py tests/test_workspace.py tests/test_result_contract.py tests/test_units.py tests/test_cli_process.py
```

Result: `117 passed in 7.89s`.

Full deterministic command:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
```

Result: `222 passed, 2 skipped in 12.74s`.

`git diff --check` passed.  No runner or legacy CLI signatures were changed.
