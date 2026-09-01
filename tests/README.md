# Forge test portfolio

The default suite is deterministic and offline. Markers describe evidence,
not implementation ownership:

| Marker | Evidence boundary | Release role |
| --- | --- | --- |
| `core` | INPUT/STRU/KPT, structures, transformations, DOS data | required PR gate |
| `integration` | prepare/execute/collect/unit/task boundaries | required PR gate |
| `cli` | in-process CLI dispatch | required PR gate |
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

Deleting or merging a test requires a named production mutation that the
remaining test still catches. A passing count alone is not evidence.

Evidence limits: `core`, `integration`, `cli`, and `composite` are deterministic
PR gates; `compat` and `benchmark` are migration evidence; `real_smoke` is
release evidence. None of these alone proves physical convergence or HPC
scheduler correctness.
