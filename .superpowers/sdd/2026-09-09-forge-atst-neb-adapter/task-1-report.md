# Task 1 report

## Delivered

- Added strict, JSON-safe `AtstNebPrepareRequest`, `AtstNebExecuteRequest`, and `AtstNebPostprocessRequest` contracts.
- Added capability and operation discriminators (`atst-neb`) and portable workspace-relative path validation.
- Added validation for image count/method, execute dry-run/check-input invariants and timeout values, and postprocess output/analysis flags.
- Added experimental ATST-NEB capability discovery and per-operation static schemas, with dataclass/wire/schema parity checks.
- Exported the request types from the package root.
- Updated discovery tests to account for the newly advertised experimental capability and added contract rejection/round-trip coverage.

## Verification

`conda run -n paimon python -m pytest tests/test_contracts.py tests/test_machine_cli.py tests/test_architecture.py -q`

Result: `122 passed`.

## Scope

No ATST executable invocation, service implementation, or machine CLI routing was added; those remain in later tasks.
