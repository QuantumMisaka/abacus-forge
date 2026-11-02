# Typed concurrent unit-workspace contract — evidence

Status: **offline concurrency contract implemented and independently reviewed;
no real ABACUS/SAI/GPU parity is claimed.** This slice adds a fail-closed typed-service regression proving
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

## Independent closeout

Independent same-family review of
`bdf249bbafde9f5f850b058265f892af9e2c88c2..ac0efd02fdf2785c196d4d264dcf1e40bb8477ba`
returned `READY_FOR_TYPED_CONCURRENT_UNIT_CONTRACTS_CLOSEOUT`. It confirmed the
diff was limited to the regression and evidence, with no production protocol,
service, workspace or runner behavior change.

The reviewer confirmed that the `Barrier(2)` exists inside both runner
invocations, so same-workspace serialization would prevent the second runner
from arriving and fail synchronization rather than merely observing two threads.
It also confirmed exactly one runner call per workspace, two successful
`OperationOutcome` carriers with distinct UUIDv4 operation IDs, and per-workspace
manifest event isolation. The new contract complements the existing
different-ID same-workspace serialization and concurrent same-ID conflict tests
without duplicating them.

Independent reruns at `ac0efd02fdf2785c196d4d264dcf1e40bb8477ba` produced:

```text
new contract: 1 passed in 0.70s
focused owning suite: 606 passed, 5 warnings in 17.99s
full offline suite: 1659 passed, 35 skipped, 176 warnings in 117.34s
```

The evidence correctly limits its claim to offline concurrency and excludes real
ABACUS/SAI/GPU behavior, HPC scheduling correctness, GPU allocation, SAI or
benchmark parity, release, push and MR.
