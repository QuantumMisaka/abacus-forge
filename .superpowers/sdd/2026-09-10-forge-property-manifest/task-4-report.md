# Forge property manifest Task 4 verification

This is a raw verification record for the provisional implementation on
`forge-core-fidelity`. It does not approve or promote the companion Draft SPEC.

## Revision

- Branch: `forge-core-fidelity`
- HEAD after implementation fixes: `8fe2478`
- Companion SPEC: `docs/superpowers/specs/2026-09-10-forge-property-manifest-design.html`
- SPEC status: `Draft for review`

## Focused gate

Command:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_property_manifest.py tests/test_maturation_packs.py tests/test_cli.py tests/test_result_contract.py tests/test_architecture.py
```

Output:

```text
........................................................................ [ 97%]
..                                                                       [100%]
80 passed in 10.24s
```

The property-only gate after the containment/input hardening added in
`8fe2478` also passed:

```text
22 passed in 0.82s
```

## Complete deterministic offline gate

Command:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
```

Output:

```text
1172 passed, 3 skipped in 87.87s (0:01:27)
```

The three skips are the pre-existing opt-in real-smoke/benchmark tests. This
offline gate is not scientific validation and does not claim a real ABACUS run.

## Diff hygiene

```text
git diff --check
```

Result: clean (no output).

## Scope checks

- `property_manifest` is a neutral-core import-graph root and adds no forbidden
  upper-layer dependency.
- `capabilities` remains unchanged; no typed property capability is advertised.
- Existing `TaskResult` keys, legacy property CLI syntax, arithmetic, status,
  and exit behavior remain covered by regression tests.
- Manifest paths use explicit declarations and workspace containment; they do
  not add directory scanning, latest-file selection, scientific acceptance,
  orchestration, retry/resume, or scheduler behavior.

## Independent review

The task/branch reviewer initially identified three non-blocking gaps: reject
an input/output path overlap, compare the full legacy API/CLI result surface,
and verify ordered references to complete source artifacts. Those were fixed in
`8fe2478` and re-reviewed. The final follow-up reported no Critical,
Important, or new Minor findings.
