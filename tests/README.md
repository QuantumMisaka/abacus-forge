# Forge test portfolio

The default suite is deterministic and offline. Markers describe evidence,
not implementation ownership:

| Marker | Evidence boundary | Release role |
| --- | --- | --- |
| `core` | INPUT/STRU/KPT, structures, transformations, DOS data, source import boundaries | required PR gate |
| `integration` | prepare/execute/collect/unit/task boundaries | required PR gate |
| `cli` | CLI dispatch and process contracts | required PR gate |
| `compat` | ABACUS/abacustest output compatibility | required migration gate |
| `pyatb` | PyATB mapping and collection | required when PyATB bridge is enabled |
| `composite` | local composite pack wiring | deterministic regression, not physics proof |
| `experimental` | mock/fixture-only property packs | non-stable evidence |
| `real_smoke` | supplied real ABACUS workspace | opt-in release evidence |
| `benchmark` | normalized migration projections | opt-in migration evidence |

Commands:

```bash
conda run -n paimon python -m pytest -q
conda run -n paimon python -m pytest -q -m 'not experimental and not real_smoke and not benchmark'
conda run -n paimon python -m pytest -q -m experimental
conda run -n paimon python -m pytest -q --run-benchmark -m benchmark
conda run -n paimon python -m pytest -q --run-real-smoke -m real_smoke
```

## Contract and workspace gate

Changes to versioned records, workspace persistence, or operation-boundary
artifacts must run the offline contract gate below, together with any owning
API/result tests:

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_contracts.py tests/test_workspace.py tests/test_result_contract.py tests/test_units.py tests/test_service_status.py
```

`tests/test_contracts.py` owns record validation, `tests/test_workspace.py`
owns the append-only manifest and event paths, and
`tests/test_result_contract.py` plus `tests/test_units.py` own result/API
projections, and `tests/test_service_status.py` owns the typed service's public
error and observation mapping. The v1 workspace manifest and event records are additive; legacy
`forge-unit.json` and `forge-result.json` compatibility outputs remain covered
by the unit tests.

`tests/test_machine_cli.py` owns the in-process machine decoder, discovery,
rendering, and service-dispatch contracts. `tests/test_cli_process.py` owns
subprocess stdout/stderr/exit behavior and API/process parity. The two suites
are the machine-path unit and process gates and should be run together for
transport changes. `tests/test_architecture.py` owns the AST-only production
import boundary and the current machine-surface documentation contracts; it
is registered as `core`.

The typed SCF service tests additionally own the migration boundary:
`ForgeServices` returns execution/collection facts and observations, and any
legacy `scientific` projection remains `unassessed`. `dry_run` is explicit, and
typed execution never infers a skip from an existing `NORMAL END` log.
`run_many(skip_completed=True)` remains covered as a legacy compatibility helper
for composite tasks and is intentionally not part of the typed status protocol.

Deleting or merging a test requires a named production mutation that the
remaining test still catches. A passing count alone is not evidence.

Evidence limits: `core`, `integration`, `cli`, and `composite` are deterministic
PR gates; `compat` and `benchmark` are migration evidence; `real_smoke` is
release evidence. None of these alone proves physical convergence or HPC
scheduler correctness.
