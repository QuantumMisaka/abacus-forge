# Forge contract foundation integration fixes

Base reviewed: `38e5218` (findings in `final-review.md`); focused fix commit follows.

## RED evidence

Before implementation, the new regression tests failed for all four behavioral areas: owned writes accepted `"./x"`, `"a/../x"`, empty and absolute paths; a simulated manifest replacement failure removed the event and recovery was absent; malformed `from_dict()` inputs leaked `TypeError`; and duplicate stdout aliases caused duplicate artifact IDs. The initial environment lacked `ase`; rerunning in the project `paimon` environment produced the expected RED failures.

## Changes

- Validate raw owned-write path spelling before resolution, retaining root containment and symlink checks.
- Keep atomic JSON replacement while restoring the legacy `json.dumps(indent=2, sort_keys=True)` bytes (no trailing newline).
- Treat immutable event files as authoritative and reconcile valid unindexed events under the manifest lock on `ensure_manifest()` and append access. This is recovery for the cross-file crash window, not a claim of multi-file atomicity.
- Normalize malformed mapping, missing-field, unknown-field, and enum shapes to `ValueError`.
- Disambiguate repeated reserved stdout/stderr aliases as `stdout_log__2`, etc.; first canonical IDs remain unchanged.
- Document the event/index recovery boundary in `README.md`.

## Verification

Focused:

```text
34 passed in 1.49s
```

Full suite:

```text
156 passed, 2 skipped in 14.21s
```

`git diff --check` passed.

## Compatibility risks

The legacy JSON byte format is restored, including removal of the newly introduced trailing newline, while preserving atomic replacement. Existing event indexes may gain deterministically discovered valid event references after recovery. Only duplicate reserved aliases receive suffixed IDs; normal single-path IDs and legacy result dictionaries remain unchanged. The recovery design intentionally leaves a crash window between two atomic replacements, with immutable event files preserving the audit fact.
