# Stage 3 Task 5 Report

## Result

Exposed the v1 machine adapter through the public `abacus_forge.cli` entrypoint
for only the first argv tokens `operation`, `schema`, and `capabilities`.
All other argv paths still use the existing legacy parser and dispatch. The
subprocess test helper now accepts optional `input_text`; its default remains
`stdin=subprocess.DEVNULL`.

The process tests exercise request-file and stdin transport, discovery,
single-document JSON output, diagnostics-only stderr, non-interactive stdin,
direct typed-service parity, and stable exit classes. Execute parity uses the
typed executable/rank/thread/timeout fields. Started nonzero, timeout, and
signal outcomes are verified as exit class 4; schema, precondition, and a
deterministic persistence failure cover classes 2, 3, and 5.

## TDD evidence

### RED

Added the focused subprocess contracts to `tests/test_cli_process.py` and ran:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider tests/test_cli_process.py
```

The expected baseline failure occurred because `cli.main` sent `operation`
and `capabilities` into the legacy parser (`invalid choice`), while the new
stdin tests initially also exposed the helper's missing input transport.

### GREEN

Added the top-level three-token route and the optional stdin-input branch.
The owning process suite then passed:

```text
12 passed
```

The brief's combined regression gate passed:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider tests/test_machine_cli.py \
  tests/test_cli_process.py tests/test_cli.py tests/test_service_status.py
```

Result: `116 passed`.

## Broader verification

Required full suite before commit:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider
```

Result: `339 passed, 2 skipped`.

Additional checks:

- `git diff --check` passed.
- `PYTHONPATH=src python -m abacus_forge.cli capabilities` returned one
  parseable JSON document with exit 0.

## Changed files

- `src/abacus_forge/cli.py`: added an early first-token route to
  `run_machine_cli`, passing the complete argv and process streams/cwd.
- `tests/support/process.py`: added `input_text`; uses `input=` when supplied
  and retains `DEVNULL` when omitted.
- `tests/test_cli_process.py`: added real subprocess transport, discovery,
  parity, non-interactive, and exit-class contracts.

## Integration decisions and self-review

- `build_parser()` is unchanged, and legacy parser error/output tests remain
  green. The route is evaluated before parser construction and examines only
  the first command token for admission.
- Machine behavior remains wholly owned by `run_machine_cli`; no adapter,
  service, discovery, or result schema code was duplicated or redesigned.
- Direct/API parity runs in separate `api` and `cli` roots. The comparison
  normalizes only workspace-absolute diagnostic paths and random admission
  claim digests (owner tokens), while comparing the serialized result envelope,
  statuses, artifacts, metrics, checks, warnings, and diagnostics.
- The class-5 scenario intentionally makes `reports` a regular file so the
  typed service returns `persistence.failure`; this is deterministic and
  preserves the frozen exit mapping without injecting test-only service code.
- Process stderr stayed empty for machine responses; captured executable
  stdout/stderr are represented in the operation result artifacts.

## Remaining uncertainty

No known task-boundary gaps remain. The test helper's dynamic subprocess
keyword dictionary uses a narrow typing ignore because `subprocess.run` has
overloaded keyword signatures; runtime behavior is covered by both input and
DEVNULL paths.
