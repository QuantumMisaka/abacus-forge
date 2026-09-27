# Unified Forge candidate clean-package evidence (2026-09-27)

## Scope and candidate

Candidate: `unify/mainline-paimon-20260927` at
`a9e9d48b888d2fa6f397e44f18f1292998edd157` (clean worktree).

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
