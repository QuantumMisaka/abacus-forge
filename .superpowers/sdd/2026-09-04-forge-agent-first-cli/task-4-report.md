# Stage 3 Task 4 Report

## Result

Implemented the isolated v1 machine adapter in `src/abacus_forge/machine_cli.py`.
It accepts the `operation`, `schema`, and `capabilities` machine command forms,
reads exactly one UTF-8 JSON request from either `--request FILE` or `--stdin`,
dispatches one typed SCF request to one narrow service, and emits one structured
stdout document. The legacy CLI was not imported or modified.

Unsupported `postprocess` and `export` operation requests, unknown discovery
selectors, malformed request sources, and parser usage failures are represented
as `ForgeErrorEnvelope` values with the specified stable exit classes. Request
schema, operation, and workspace path checks are separate typed phases; result
classification never examines exception message text.

## TDD evidence

### RED

Added focused adapter tests to `tests/test_machine_cli.py`, then ran:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider tests/test_machine_cli.py
```

The expected baseline failure occurred during collection:
`ModuleNotFoundError: No module named 'abacus_forge.machine_cli'`.

### GREEN

After adding the adapter, the focused command passed:

```text
21 passed
```

The owning adapter/service regression passed:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider tests/test_machine_cli.py tests/test_service_status.py
```

Result: `76 passed`.

Coverage includes request-file/stdin exclusivity, malformed UTF-8 and JSON,
top-level shape, schema/operation/path phase mapping, strict typed decoding,
unsupported operations, unknown schema selectors, injected single-call
dispatch, error/result exit mapping, compact/pretty JSON, text projection,
and `--pretty`/text rejection.

## Broader verification

Full offline suite:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider
```

Result: `328 passed, 2 skipped`.

Additional checks:

- `git diff --check` passed.
- Direct command-local help check returned `0`, wrote through the injected
  stdout stream, and included `--request`.

## Changed files

- `src/abacus_forge/machine_cli.py`: added the isolated machine parser,
  request source/JSON reader, explicit SCF decoder map, typed preflight and
  error conversion, narrow-service dispatch, renderers, and semantic exits.
- `tests/test_machine_cli.py`: retained discovery coverage and added focused
  machine adapter behavior and regression tests.

## Self-review

- The adapter uses `ScfServiceSet` members (`prepare`, `modify`, `execute`,
  `collect`) and does not reproduce domain operation behavior.
- `postprocess`/`export` are recognized only to return `request.invalid`/2;
  discovery remains unchanged and does not advertise them.
- JSON rendering uses `allow_nan=False`, `sort_keys=True`, and one final
  newline. Pretty mode changes JSON whitespace only; text mode reads from the
  same typed object and does not infer scientific conclusions.
- Invalid requests preserve only safely validated UUIDv4 and canonical
  workspace values; unsafe values serialize as null through the error contract.
- No TTY or prompt inspection is performed, and diagnostics are not written to
  stdout.
- The implementation is limited to the two Task 4 files; public CLI routing
  remains Task 5 work.

## Concerns / remaining uncertainty

- `--help` is handled as a normal zero-exit parser response through the supplied
  stdout stream; it is intentionally not an envelope because it is command
  documentation rather than an operation result.
- Text rendering is intentionally a concise projection (operation identity,
  execution/collection facts, artifact paths, and error fields); callers that
  need every field should consume the default JSON document.
- Real subprocess/process-parity checks and top-level `cli.py` routing remain
  Task 5 scope.

## Review fix evidence

Addressed the Task 4 review’s two Important coverage gaps:

- Added a parametrized test for each `prepare`, `modify`, `execute`, and
  `collect` request. Each uses a matching valid typed request, records exactly
  one invocation on the matching narrow service, and asserts no other service
  call occurred.
- Added JSON-reader tests proving a second JSON document is rejected as
  `request.invalid`/exit 2 without dispatch, while trailing whitespace is
  accepted and dispatches once.

Focused adapter suite after the fixes:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider tests/test_machine_cli.py
```

Result: `27 passed`.

Adapter/service regression after the fixes:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider tests/test_machine_cli.py tests/test_service_status.py
```

Result: `82 passed`.

Full offline suite after the fixes:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider
```

Result: `334 passed, 2 skipped`.
