# Unified Forge candidate clean-package evidence (2026-09-27)

## Scope and candidate

Code-content commit: `a9e9d48b888d2fa6f397e44f18f1292998edd157` on
`unify/mainline-paimon-20260927`. Later candidate commits in this record are
documentation/evidence-only; rebuilding after those commits produced the same
wheel SHA-256.

This record covers a rebuilt release wheel, wheel metadata gates, and a fresh
Python 3.13 venv install/import/console/schema probe. It does **not** claim a
real ABACUS execution in the fresh venv, full Agent Benchmark parity, SAI or
platform acceptance, scientific acceptance, or stable maturity promotion.

## Build and wheel

Build command:

```bash
python -m build --wheel
```

Result:

```text
abacus_forge-0.1.0-py3-none-any.whl
sha256=d7ab21e15d867324113f6c18cf6e3b5f0c032ff7f6f229ac2f1bb099112caf7e
```

The wheel metadata contract passed against this exact artifact:

```bash
ABACUS_FORGE_WHEEL=<wheel> pytest tests/test_package_contract.py tests/test_package_metadata_drift.py -q
```

Result: `15 passed`.

## Clean venv probe

Created a fresh Python `3.13.13` venv and installed the wheel with its declared
dependencies. The wheel install completed successfully. The clean interpreter
confirmed `abacus_forge` was importable while the forbidden legacy/runtime
packages were absent:

```text
abacusagent: absent
abacustest: absent
aiida: absent
atst_tools: absent
```

Console and machine-boundary probes:

```text
import_ok 0.1.0
capabilities ['scf', 'relax', 'cell-relax', 'atst-neb', 'md', 'band', 'dos', 'pyatb-band', 'export']
cli_ok forge.capabilities/v1 9
schema_ok forge.schema-discovery/v1 scf execute
decode_ok ScfExecuteRequest execute fixture True
```

This proves wheel installation, import boundary, console entry point,
capability discovery, schema discovery, and typed request decoding for the
unified candidate. It does not prove execution because no ABACUS process was
started in this probe.

## Related candidate gates

The same candidate commit also passed the Forge offline suite:
`1423 passed / 32 skipped`.

## Fresh-venv real SCF execution

The same clean venv then executed and collected a real Si LCAO SCF through the
Forge machine CLI. The ABACUS LTS executable and input/pseudopotential bundle
were identical by SHA-256 to the archived 2026-09-15 clean-install slice.

- ABACUS LTS executable SHA-256:
  `51f898a40698200db79bacfdc5a0c799847d712941f7da04773a474022412d8f`
- Input identity: INPUT `c30de3c5...`, KPT `1ad281c0...`, STRU `363e2ff2...`
- Resources: 1 MPI rank, 4 OpenMP threads, 600 s timeout
- Result: execution `completed`, collection `complete`
- Facts: `normal_end=true`, `converged=true`, `total_energy=-229.9415680244328 eV`,
  `fermi_energy=6.7936808644 eV`, `total_time=44.2588 s`
- Fresh-venv isolation remained true after the run: `abacusagent`,
  `abacustest`, `aiida`, and `atst_tools` were all absent.

Raw machine outcomes and the clean-venv dependency freeze are retained beside
this record. This advances fresh-venv real execution from the prior import-only
probe, but remains a one-capability local slice: it does not claim full Agent
Benchmark parity, SAI/platform acceptance, production rollout, or scientific
acceptance.
