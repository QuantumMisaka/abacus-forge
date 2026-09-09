# Task 1 report — typed PyATB band contracts and discovery

## Scope

Implemented only the typed request contracts, capability/schema discovery,
machine decoder registry, public exports, and their owning tests. Legacy
`pyatb.py` helpers, services, algorithms, and legacy CLI parsing were not
modified.

## TDD evidence

### RED

Command:

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_contracts.py -k pyatb_band
```

Result: collection failed with the expected missing-feature error:
`ModuleNotFoundError: No module named 'abacus_forge.pyatb_contracts'`.

### GREEN

Focused commands after implementation:

```text
tests/test_contracts.py -k pyatb_band: 15 passed, 274 deselected
tests/test_machine_cli.py -k pyatb_band: 5 passed, 67 deselected
```

The focused tests cover defaults/round trips, nested immutability, strict
unknown-field decoding, path and cardinality validation, finite numeric and
line-point validation, capability routing, and discovery/schema equality.

### REFACTOR / owning acceptance

Exact command required by the task brief:

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_contracts.py tests/test_machine_cli.py tests/test_cli_process.py
```

Result: `396 passed in 35.81s`.

Additional `git diff --check` and Python compilation checks passed.

## Concerns

- `pyatb` is represented as an optional executable dependency in the
  descriptor; no Python/runtime dependency was added.
- No service or algorithm behavior is included, by design; Task 2/3 own those
  boundaries.
