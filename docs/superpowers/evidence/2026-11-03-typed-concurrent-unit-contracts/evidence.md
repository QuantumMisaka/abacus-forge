# Typed concurrent unit-workspace contract — evidence

Status: **offline concurrency contract complete; no real ABACUS/SAI/GPU parity
is claimed.** This slice adds a fail-closed typed-service regression proving
that distinct Forge unit workspaces can execute concurrently while retaining
per-workspace event isolation. It intentionally does not change the typed
protocol or add another orchestration framework.

## Contract under test

`test_typed_execute_distinct_unit_workspaces_run_concurrently` prepares two
independent unit workspaces (`unit-a`, `unit-b`) and issues two typed
`ScfExecuteRequest` operations with distinct UUIDv4 operation IDs.

A `threading.Barrier(2)` inside both runner calls requires the two executions to
overlap. If Forge serialized distinct unit workspaces, the barrier would time out
and the regression would fail.

The test verifies:

- both runners were invoked for `unit-a` and `unit-b`;
- both calls passed the concurrency barrier;
- both returns are `OperationOutcome`;
- operation IDs remain exactly bound to their requests;
- each workspace manifest contains only its own operation event.

Together with the existing same-workspace serialization test, this pins the
intended boundary: operations in one workspace serialize to protect manifest and
artifact ownership, while independent unit workspaces remain concurrent.

## Validation

Focused owning suite:

```bash
PYTHONPATH= /tmp/forge-release-candidate-venv/bin/python -m pytest \
  tests/test_contracts.py \
  tests/test_workspace.py \
  tests/test_result_contract.py \
  tests/test_units.py \
  tests/test_service_status.py \
  -q --tb=short -p no:cacheprovider
```

Result:

```text
606 passed, 5 warnings in 22.26s
```

New contract alone:

```text
1 passed in 0.90s
```

Full offline suite:

```bash
PYTHONPATH= /tmp/forge-release-candidate-venv/bin/python \
  -m pytest tests -q --tb=short -p no:cacheprovider
```

Result:

```text
1659 passed, 35 skipped, 176 warnings in 129.08s
```

## Boundary

This is offline concurrency behavior only. It does not prove real ABACUS
execution, HPC scheduling correctness, GPU allocation behavior, SAI parity, or
benchmark parity. No release, push, or MR is authorized or claimed.
