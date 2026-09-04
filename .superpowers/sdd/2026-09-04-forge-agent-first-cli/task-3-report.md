# Stage 3 Task 3 Report

## Result

Implemented static, side-effect-free capability and request-schema discovery for
the typed SCF slice. The public registry advertises only experimental `scf`
with `prepare`, `modify`, `execute`, and `collect`; its artifact roles are
exactly `input`, `provenance_manifest`, and `output`. Unsupported discovery
selectors raise `ForgeRequestError` for Task 4 to map to `request.invalid`.

## TDD evidence

### RED

Added descriptor/discovery tests before implementation and ran:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider tests/test_contracts.py tests/test_machine_cli.py
```

Expected baseline failure occurred during collection: `CapabilityDescriptor`
was absent from `abacus_forge.contracts`, and `abacus_forge.discovery` did not
exist.

### GREEN

After implementation, the same focused command passed:

```text
78 passed
```

The implementation derives schema property-key expectations from
`dataclasses.fields()` plus the computed `operation` key, and cross-checks
those keys against a representative request's actual `to_dict()` output.
Required fields and semantic constraints remain explicit, including the
non-empty prepare structure path and execute numeric bounds/defaults.

## Verification

Contract/workspace/result/service regression gate:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider tests/test_contracts.py \
  tests/test_workspace.py tests/test_result_contract.py tests/test_units.py \
  tests/test_service_status.py
```

Result: `186 passed`.

Full offline suite:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider
```

Result: `299 passed, 2 skipped`.

`git diff --check` passed.

## Changed files

- `src/abacus_forge/contracts.py`: added frozen, strictly decoded
  `CapabilityDescriptor` and capability schema version constant.
- `src/abacus_forge/discovery.py`: added deterministic capability registry,
  request schema documents for all four typed SCF requests, field/wire-key
  drift checks, and fresh JSON-safe return values.
- `src/abacus_forge/__init__.py`: re-exported the descriptor and discovery
  functions.
- `tests/test_contracts.py`: added descriptor validation/round-trip,
  discovery shape, schema drift, required/constant/bounds, and unknown-selector
  coverage.
- `tests/test_machine_cli.py`: added discovery JSON-safety/determinism coverage
  as the CLI-owned discovery test home.
- `tests/conftest.py`: registered `test_machine_cli.py` with the `cli` marker.

## Self-review

- Descriptor lists and input mappings are frozen internally; serialization
  returns detached lists/mappings.
- Discovery does not import legacy task registries or optional dependencies and
  performs no filesystem or service work.
- `additionalProperties` is false for every request schema, while typed request
  constructors remain the runtime validation authority.
- The execute schema includes Task 1 fields (`executable`, `mpi_ranks`,
  `omp_threads`, `timeout_seconds`, `dry_run`) and their defaults/constraints.
- No machine CLI routing, postprocess/export capability, or Task 4 behavior was
  introduced.

## Concerns / remaining uncertainty

Task 4 still owns converting discovery `ForgeRequestError` instances into a
`forge.error/v1` envelope and exit code 2; this task intentionally leaves that
adapter behavior untouched. JSON Schema is descriptive only and is not used as
the runtime validator.
