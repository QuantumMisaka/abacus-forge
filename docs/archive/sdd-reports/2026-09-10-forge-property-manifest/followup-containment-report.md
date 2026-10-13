# Property manifest containment follow-up

This follow-up records a narrow safety correction after the provisional
property-manifest slice. It does not change the companion SPEC status or
promote the legacy property packs.

## Revision and scope

- Branch: `forge-core-fidelity`
- Revision: `7344b60`
- Change: legacy property `_find_first` now resolves and contains candidates
  before any cube arithmetic, planar averaging, or external Bader invocation.
- An external symlink candidate is retained only as an explicit `escaped`
  manifest fact; it is never passed to a parser or process.
- Normal contained selection and all generic result/CLI fields remain
  unchanged.

## Regression evidence

Focused property/composite gate:

```text
50 passed in 2.93s
```

The new regression `test_property_post_does_not_read_escaped_cube_symlinks`
proves that escaped spin-density sources produce no derived cube while the
manifest retains an `escaped` reason.

Complete deterministic offline gate:

```text
1173 passed, 3 skipped in 89.43s (0:01:29)
```

The three skips are pre-existing opt-in real-smoke/benchmark tests. This is
not scientific validation and contains no real ABACUS execution.

Diff hygiene:

```text
git diff --check
```

Result: clean.

## Boundary conclusion

The correction closes the identified “manifest rejects but legacy post reads”
gap without adding a typed property capability, discovery entry, workflow,
scientific judgement, retry/resume, scheduler, or external dependency.
