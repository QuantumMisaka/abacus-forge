# Forge COHP postprocess W1 evidence

Date: 2026-10-15

Status: **offline W1 implementation and regression passed.** This evidence does
not run ABACUS, publish a package, transfer a production kit, claim legacy
COHP parity, claim Paimon target-path migration, or close W3/W4.

## Candidate identity

- Repository: `/home/james/work/sidereus/workplace/abacus-forge`
- Branch: `feature/cohp-postprocess`
- Implementation commit: `fc1fdc56d2e83c5621c005307f34534815f3edda`
- Base Forge: `main@5c978b0c88b0654dc0a03e43f93eee4e42a72441`
- Numeric implementation provenance: Paimon v2 `origin/main@52798406d`
  feature/abacus/cohp-iao; imported from
  `app-tools-forge/toolbox/ABACUS/toolkits/cohp_iao*.py`.
- Fixture SHA-256:
  `46960167c998d4a387bdee8c80f3d713819fe9847309d81ea9c7bfa1df20fead`
  (`tests/fixtures/cohp-iao/si_prim_4k.tar.gz`).

## Implemented boundary

`cohp` is advertised as an experimental `postprocess` capability with request
`CohpPostprocessRequest`, method `iao`, explicit `scf_dir_rel`, optional
`out_dir_rel`, 1-based atom indices, orbital selectors, and
`output_dir_rel`.  The typed service writes:

- `outputs/cohp/cohp.meta.json`
- `outputs/cohp/cohp_EminusEf.dat`
- `outputs/cohp/cohp.png`
- `outputs/cohp/cohp_bond_images.json`
- `reports/postprocess/<operation_id>.json`

Machine CLI discovery, schema, decoder, direct-service/API parity, operation
guard, durable report/events, and output-artifact admission are covered by
tests.  No legacy `abacus-cohp-lcao` subprocess bridge is implemented in W1.

## Verification

Environment: Python 3.12 `abacus-env`; commands run from the Forge root.

1. Focused owning regression:

```bash
conda run --no-capture-output -n abacus-env pytest \
  tests/test_cohp_iao.py tests/test_postprocess_services.py \
  tests/test_postprocess_machine_cli.py tests/test_contracts.py \
  tests/test_imports.py tests/test_machine_cli.py \
  tests/test_architecture.py -q
```

Result after the final export-order change: **451 passed**.

2. Default offline regression:

```bash
conda run --no-capture-output -n abacus-env pytest -q
```

Result: **1468 passed / 34 skipped**, with third-party warnings retained.

3. `git diff --check` on this implementation had no whitespace errors before
commit.  Raw ABACUS fixture bytes are preserved and are not reformatted.

## Boundary / excluded claims

This proves offline typed API/CLI/kernel behavior on the checked-in cut real
SCF fixture only.  It does not prove:

- legacy COHP or IAO numeric parity against `abacus-cohp-lcao` beyond the
  inherited Paimon kernel tests;
- Paimon `abacus_worker_cohp` consumption of Forge COHP;
- clean-install, wheel-only production admission, or dependency closure;
- full Agent Benchmark, platform acceptance, scientific acceptance, release,
  or Paimon v1.3 W3/W4 closure.
