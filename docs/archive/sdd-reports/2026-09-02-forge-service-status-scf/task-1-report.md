# Task 1 implementation report

## Implementation

- Added immutable, slot-based `OperationRef` and the four typed SCF request variants: `ScfPrepareRequest`, `ScfModifyRequest`, `ScfExecuteRequest`, and `ScfCollectRequest`.
- Each request exposes a fixed operation discriminator, canonical lowercase UUIDv4 operation identity, workspace-relative scope, required non-empty `policy_id`, schema version, and strict JSON round-trip methods.
- Kept the new request boundary narrow: no legacy `UnitSpec` or untyped payload was introduced. `ForgeRequest` was not changed.
- Exported all five identity/request records from `abacus_forge`.
- Made `ForgeErrorEnvelope.affected_fields` required and made both its envelope and nested `error` object reject unknown serialized fields.
- Added coverage for request variants, UUID validation, policy requirements, operation discriminators, unknown fields, error strictness, and malformed error construction.

## Verification

The new tests initially produced the expected RED collection failure because `OperationRef` was not yet defined:

```text
ImportError: cannot import name 'OperationRef' from 'abacus_forge.contracts'
```

Focused and related contract tests:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider \
  tests/test_contracts.py tests/test_result_contract.py
38 passed in 0.60s
```

Full suite:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider
176 passed, 2 skipped in 12.56s
```

Public export/dataclass introspection also passed for all five records (`frozen`, `slots`, and root-package exports).

## Commit

`0e84940 fix: complete typed forge service contracts`

## Self-review and limitations

- `git diff --check` passed before commit.
- The request variants intentionally contain only common operation identity/workspace/policy fields at this contract stage, per the task boundary; operation-specific service inputs remain for the typed service layer in Task 4.
- The pre-existing generic records retain their historical construction behavior; strict unknown-field decoding was applied to the new public request/error boundary required by this task.

## Scoped re-review fix round 2

- Added lowercase, canonically formatted UUIDv1 and UUIDv3 request IDs as explicit negative cases, proving rejection is based on UUID version rather than formatting alone.
- Added a `ForgeErrorEnvelope.from_dict()` regression case for a nested `error` object missing `affected_fields`.

Verification:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider \
  tests/test_contracts.py tests/test_result_contract.py
40 passed in 0.62s
```

`git diff --check` passed. Self-review confirmed that only the scoped test file changed and both re-review findings are covered without changing production behavior.

Commit: `011de8d6a02c0d9ef09eeac896c90d0f1e008337` (`test: cover strict SCF contract validation`)
