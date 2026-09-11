# Task 1 report — core capability migration fact matrix

## Result

The Forge-owned native Relax fixture, workspace-copy helper, and opt-in
SCF/Relax/cell-relax/MD fact matrix are implemented. No file under
`src/abacus_forge` was changed, and no Paimon, AiiDA, or `abacustest` module is
imported at runtime by the new helper or benchmark.

## TDD evidence

### RED

Command:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q tests/benchmark/test_core_capability_facts.py --run-benchmark
```

Before the fixture/helper wiring existed, collection failed with the expected
missing test-support boundary:

```text
ImportError: cannot import name 'copy_native_relax_workspace'
from 'tests.support.reference_workspaces'
```

The failure occurred during test collection and did not involve production
code.

### GREEN

The same focused command passed after the minimal fixture/helper wiring:

```text
4 passed in 1.18s
```

The matrix uses four isolated workspace copies, UUIDv4 operation IDs, the
matching typed collect service for each capability, recursive factual metric
comparison, and workspace-contained artifact path comparison. Relax/cell-relax
also checks the checked-in `-4.2`/`3` log facts, final-structure bytes and
selected native filenames. MD checks the known native fixture values and
requires both legacy and typed values to be finite.

## Owning gates

Benchmark migration gate:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q tests/benchmark/test_core_capability_facts.py tests/benchmark/test_abacustest_compatibility.py --run-benchmark
6 passed in 2.03s
```

Owning offline gate:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q tests/test_collect_abacus_reference.py tests/test_service_status.py tests/test_md_services.py tests/test_architecture.py
198 passed in 20.69s
```

Additional checks:

```text
git diff --check
fixture STRU/STRU_FINAL: byte-identical
```

No new warning or unknown-marker output appeared in the owning gates.

## Changed files

- `tests/fixtures/abacus-native-relax/INPUT`
- `tests/fixtures/abacus-native-relax/KPT`
- `tests/fixtures/abacus-native-relax/STRU`
- `tests/fixtures/abacus-native-relax/OUT.ABACUS/running_relax.log`
- `tests/fixtures/abacus-native-relax/OUT.ABACUS/STRU_FINAL`
- `tests/support/reference_workspaces.py`
- `tests/benchmark/test_core_capability_facts.py`

The report itself is the Task 1 evidence record under the SDD ledger.

## Intentional deviations / concerns

The brief's literal SCF shared tuple included `scf_steps`, but the existing
checked-in `abacustest-abacus-scf` fixture exposes `total_energy`, `natom`, and
`total_time` rather than a parsed `scf_steps` fact. The matrix therefore uses
`("total_energy", "natom", "total_time")`; the existing compatibility
benchmark continues to cover SCF force/stress/pressure facts.

The brief's literal `legacy.status == "completed"` assertion does not hold
for the existing native MD fixture: the legacy collector reports
`unfinished` because that fixture has no legacy SCF convergence prerequisite,
while the typed MD projection reports collection `complete` from its complete
native thermodynamic block. The matrix makes this boundary explicit with a
capability status map (`completed` for SCF/Relax/cell-relax, `unfinished` for
legacy MD) and retains the required typed status and unassessed scientific
status assertions. This is a projection/status compatibility fact, not a
scientific conclusion, and no production status logic was changed.
