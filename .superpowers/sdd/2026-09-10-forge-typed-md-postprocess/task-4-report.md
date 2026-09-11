# Task 4 report — typed MD postprocess

## Scope

Task 4 closes the documentation, verification, and whole-branch review for
the experimental `md.postprocess` slice. Production implementation is on
`forge-core-fidelity` at `HEAD=1457ee1`; the documentation/evidence close-out
is included in the closing commit. This report records the exact offline
evidence and keeps real ABACUS/scientific promotion as a later gate.

## Documentation

- `README.md` documents the fifth typed MD operation, explicit trajectory
  request-file/Python API usage, five canonical modes, deterministic outputs,
  status facts, and the upper-adapter alias boundary.
- `ROADMAP.md` records the delivered experimental slice and its external
  boundaries.
- `docs/superpowers/specs/2026-09-10-forge-typed-md-postprocess-design.html`
  and its implementation plan are aligned with the approved 2026-09-01 and
  2026-09-02 Forge specifications.

The documents explicitly defer `MD_dump`/PDB conversion, trajectory discovery,
workflow/orchestration, monitoring, scheduling, retry/resume, export and
scientific acceptance to humans, Agents or an upper adapter. Forge remains a
facts-producing ABACUS unit-operation layer.

## Verification evidence

```text
Focused architecture/MD contract/algorithm/service/process suites:
110 passed

Full offline pytest gate:
1132 passed, 3 skipped in 94.69s

git diff --check:
passed
```

The three skipped tests are existing real/external-environment gates. No
real ABACUS run, Paimon v1.3 benchmark, or scientific acceptance claim is
made by this slice.

## Review

An independent whole-branch review covered `73be1f4..1457ee1`, the current
implementation, and the uncommitted documentation before this closing
commit. The reviewer reported no Critical or Important findings. The only
Minor item was documentation commit hygiene; it is resolved by the closing
documentation commit.

## Remaining release evidence

The later collection-metadata record covers Forge's clean-package/install
gate. Complete Paimon benchmark parity and a real ABACUS
trajectory-to-postprocess smoke remain separate release evidence; this report
does not claim either one. Scientific interpretation and workflow/orchestration
remain caller-owned boundaries, not missing Forge implementation work.
