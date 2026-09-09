# Task 3 implementation report — typed PyATB band services

Plan: `docs/superpowers/plans/2026-09-10-forge-typed-pyatb-band.md`

Implementation commit: `3ef68db` (`feat: add typed PyATB band services`)

## RED

Before the service module and package export existed, the new owning service
tests failed during collection:

```text
ImportError: cannot import name 'PyatbBandServiceSet' from 'abacus_forge'
```

## GREEN / acceptance

The brief's selected acceptance command completed successfully at
`3ef68db`:

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_pyatb_typed.py tests/test_machine_cli.py tests/test_cli_process.py tests/test_contracts.py tests/test_workspace.py
........................................................................ [ 15%]
.................................................................... [ 30%]
........................................................................ [ 46%]
........................................................................ [ 61%]
........................................................................ [ 76%]
........................................................................ [ 92%]
.....................................                                    [100%]
469 passed in 39.91s
```

The focused typed PyATB/service/machine suites also completed with `146 passed
in 39.04s`. `git diff --check` passed for the implementation commit.

## Delivered boundary

- Added `PyatbBandServiceSet` with shared context and runner factory plus
  prepare/execute/collect protocols and concrete services.
- Prepare admits before source preconditions, calls the explicit Task 2
  handoff helper, writes the `band`/`pyatb`/`pyatb` unit manifest, and lets
  `ServiceContext.persist` inject artifact refs exactly once.
- Execute validates generated `Input`, `STRU`, `KPT_band`, and the declared
  PyATB routes, runs one local runner with only typed request fields, preserves
  runtime/process facts, and maps pre-start missing executables to the
  existing precondition error while returning started-process failures as a
  failed outcome.
- Collect is independent of prior events and task files, delegates to the
  explicit output collector, and persists one append-only event with factual
  collection status.
- Wired typed requests into the default machine CLI service selection and
  exported the service set/protocols from the package facade.
- Added direct service, fake-process, admission, dry-run, failure/timeout,
  collection, dispatch, and API/CLI parity regressions.

## Boundary and remaining risk

Legacy `prepare_pyatb_band`, `run_pyatb`, `collect_pyatb`,
`run_band_sequence`, their legacy CLI paths, and their existing tests were not
changed. No scheduler, workflow orchestration, scientific acceptance, or
external PyATB Python dependency was added. Real ABACUS/PyATB smoke and later
property operations remain Stage 5/later evidence as required by the plan.
