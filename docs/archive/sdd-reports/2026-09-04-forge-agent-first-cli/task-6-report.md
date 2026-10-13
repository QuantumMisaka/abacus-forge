# Stage 3 Task 6 report

## Scope and diagnosis

Task 6 closes the source-boundary and documentation debt left after Tasks 1–5.
The production tree already contained the frozen machine adapter, so no
production implementation change was needed. The missing integration contracts
were an AST gate, marker ownership, and current README coverage for the three
machine commands and their request transport.

## TDD evidence

### RED

Added `tests/test_architecture.py` before documentation edits and ran:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_architecture.py tests/test_cli_process.py
```

Observed `1 failed, 15 passed`. The failure was the documentation contract:
the expected `## Agent-first CLI` section was absent. The AST boundary and
existing process contracts passed, confirming the RED state was caused by the
missing Task 6 documentation rather than a malformed test.

### GREEN and refactor

Added the concise Agent-first CLI section, marker registration, explicit test
ownership documentation, and an AST helper that parses only `src/abacus_forge`
and handles both `ast.Import` and `ast.ImportFrom`. The helper emits sorted
`path:line:module` violations. The owning gate then passed:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_architecture.py tests/test_cli_process.py
17 passed
```

The architecture tests also invoke the real subprocess CLI for both README
request payloads, verify the three machine help surfaces, and assert discovery
contains only experimental SCF.

## Changed files

- `tests/test_architecture.py`: AST import-boundary, help/discovery, and README
  request-process contracts.
- `tests/conftest.py`: registers `test_architecture.py` as `core`.
- `tests/README.md`: assigns machine unit/process parity and AST boundary
  ownership explicitly.
- `README.md`: documents `operation`, `schema`, and `capabilities`, request
  file/stdin examples, SCF experimental maturity, JSON/error/exit behavior,
  cwd workspace root, and caller-owned scientific/orchestration/scheduling.

## Verification

Required focused gate:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_architecture.py tests/test_contracts.py tests/test_service_status.py tests/test_machine_cli.py tests/test_cli_process.py tests/test_cli.py
207 passed
```

Complete deterministic suite:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
344 passed, 2 skipped
```

The skips are the existing opt-in real-smoke and benchmark tests. Command
smoke checks also passed in the `paimon` environment: `capabilities` returned
one JSON document with only `scf` at `experimental` maturity, and
`operation --help` showed mutually exclusive `--request`/`--stdin` plus all
six frozen operation names.

## Self-review

- Source scanning is limited to production Python under `src/abacus_forge`;
  tests and documentation are not treated as runtime dependencies.
- Matching is by root module and covers direct and submodule imports for the
  forbidden upper-layer roots, including AiiDA, legacy ABACUS tool packages,
  ATP/MCP, Bohrium/DPDispatcher, and scheduler bindings.
- Documentation does not add orchestration, scientific policy, scheduling,
  TUI, Stage 4 operations, or adapter behavior.
- README request examples are executable against the real CLI and use explicit
  dry-run requests, so the contract test remains deterministic and offline.
- Legacy top-level help remains untouched; the new command help is documented
  separately as required.

## Review fix

The task-scoped review identified an imprecise README sentence that could be
read as placing the operation outcome/error envelope on stderr. The adapter
behavior was already correct and was not changed. README now states that
machine stdout always contains exactly one JSON document, that operation output
is the complete outcome/error envelope including message and result
diagnostics, and that stderr is reserved for controlled diagnostics and is
empty on currently covered paths. The architecture documentation test asserts
these two channel rules, while the existing real subprocess examples continue
to assert JSON stdout and empty stderr.

Post-fix verification:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_architecture.py tests/test_contracts.py tests/test_service_status.py tests/test_machine_cli.py tests/test_cli_process.py tests/test_cli.py
207 passed

conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
344 passed, 2 skipped
```

The final wording pass made the `operation` qualification explicit: its
stdout document is the single complete JSON outcome/error envelope, while
`capabilities` and `schema` remain single JSON discovery documents.
