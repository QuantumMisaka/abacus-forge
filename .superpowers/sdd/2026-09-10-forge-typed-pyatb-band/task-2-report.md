# Task 2 report — explicit PyATB handoff and collection algorithms

Base revision: `84adfcc` (`docs: plan typed PyATB band handoff`)

## RED

Command:

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_pyatb_typed.py
```

Raw result before implementation:

```text
ImportError while importing test module ...
ImportError: cannot import name 'collect_typed_pyatb_band' from 'abacus_forge.pyatb'
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

## GREEN

The owning suite and unchanged legacy PyATB suite pass:

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_pyatb_typed.py tests/test_pyatb.py
....................                                                     [100%]
20 passed in 1.01s
```

`git diff --check` also passed.

## Implementation

- Added explicit `prepare_typed_pyatb_band` and `collect_typed_pyatb_band` helpers
  to `src/abacus_forge/pyatb.py`; legacy helper bodies and signatures were not
  changed.
- Typed preparation validates all contained source files and destination
  conflicts before writing, stages relative links or independent `copy2`
  snapshots, emits source/destination SHA-256 provenance, and renders explicit
  PyATB `Input` and `KPT_band` files for spin-1 and spin-2 routes.
- Typed collection only indexes declared contained output files, reports
  missing/malformed/escaped paths, and exposes a parseable textual `band_gap`
  only as a `reported` metric with `scientific=unassessed`.
- Added temporary-workspace tests for link/copy provenance, containment,
  collisions/no-partial-write, STRU parsing, spin routes, generated files,
  explicit output collection and facts-only behavior.

## Remaining scope

No real PyATB execution, service/CLI dispatch, scheduler integration or
scientific acceptance logic was added; those belong to later tasks/stages.
