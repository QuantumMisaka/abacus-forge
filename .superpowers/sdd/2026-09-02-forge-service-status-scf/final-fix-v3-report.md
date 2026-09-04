# Task 8 final fix wave report

## Scope

Implemented only the four behaviors in `final-fix-v3-brief.md` in the typed
services, local runner, workspace audit persistence, result projection, and
service-status regression tests. No SPEC or PLAN files were changed.

## RED evidence

Added regressions first and ran:

```text
conda run -n abacus-env pytest -q tests/test_service_status.py -k 'missing_prepare_structure or missing_explicit_launcher or missing_generated_mpirun or audit_infrastructure or execute_provenance'
```

Result before implementation: 7 failed, 34 deselected. The failures covered
pre-admission missing-structure checks, launcher/mpirun preflight, untyped audit
I/O failures, and execute artifact/metric/observation provenance.

## Implementation and focused GREEN

- Prepare now validates resolved containment before admission, then checks
  existence/type after admission; missing inputs retain the tombstone and do
  not write an event.
- `LocalRunner.preflight()` checks the engine and the actual explicit launcher
  or generated `mpirun`; typed execute maps missing programs to
  `precondition.missing` before process start.
- Workspace lock, reports, claim, manifest, and reconciliation I/O failures
  are typed as `ForgePersistenceError`; existing identity conflicts remain
  `OperationConflictError`.
- Execute stdout/stderr artifacts are stage `execute`; returncode and OMP
  thread metrics are `runtime`; observation names are unique and returncode is
  not duplicated as a parser check.

Focused verification:

```text
conda run -n abacus-env pytest -q tests/test_service_status.py tests/test_result_contract.py tests/test_workspace.py
82 passed, 8 warnings
```

## Full deterministic suite

```text
conda run -n abacus-env pytest -q
245 passed, 2 skipped, 279 warnings
```

## CLI help

```text
conda run -n abacus-env env PYTHONPATH=src python -m abacus_forge.cli --help
```

Exited 0 and rendered the complete command list, including the typed
`execute` and `collect` entry points.

## Diff and forbidden-boundary scan

```text
git diff --check
```

Passed with no whitespace errors.

Scanned the changed implementation and service-status tests for scheduler,
retry/recovery, workflow, scientific acceptance/policy, and related boundary
terms. No new out-of-scope behavior was introduced; the only matches are
existing legacy comments describing policy-free projections or compatibility
skip behavior.

## Remaining uncertainty

The full suite includes the repository's two intentional skipped tests and
existing deprecation warnings from ASE. No functional failure remains within
this brief's boundary.

## Approved gate evidence on `paimon` (post-commit)

The required clean-HEAD checks were rerun at commit `5e94a4670b1b2df959d93b97fb5301371474cd5e`.

Focused suite:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py tests/test_result_contract.py tests/test_workspace.py
82 passed in 4.17s
```

Full deterministic suite:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
245 passed, 2 skipped in 15.28s
```

The no-cache/no-bytecode runs emitted no warnings.

CLI help command, run exactly as required:

```text
PYTHONPATH=src python -m abacus_forge.cli --help
```

This check failed before argument handling because the workspace system Python
does not have the package dependency `ase` installed:

```text
ModuleNotFoundError: No module named 'ase'
```

The paimon-environment test commands above are green; the exact CLI command
remains an environment/dependency failure and is recorded here without
masking it.

Baseline diff check:

```text
git diff --check 6cc21c3..HEAD
```

Passed with no output.
