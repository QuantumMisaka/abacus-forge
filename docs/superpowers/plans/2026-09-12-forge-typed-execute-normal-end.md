# Forge typed execute normal-end observation plan

**Goal:** Make typed ABACUS `execute` outcomes preserve an independently
observable `normal_end` fact when the just-completed process output contains a
confirmed ABACUS normal-termination marker.

**Spec:**
`docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html`
and
`docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html`,
especially R3/R5/R6/R7, the execute fact table, and the rule that
`normal_end` is an observation rather than an execution or scientific status.

**Authorization:** Continued implementation of the approved Forge line was
confirmed in this session. A read-only audit of the current candidate found
that typed `execute` preserves return code, termination, timeout and log
artifacts but drops the explicit `normal_end` observation required by the
approved status SPEC.

**Architecture:** Detect only positive, grammar-confirmed normal-termination
markers in output attributable to the current `LocalRunner` invocation:
captured `outputs/stdout.log` first, then a newly created or changed contained
`OUT.ABACUS/running_*.log` under the workspace. Never inspect an unchanged
pre-existing log as execute evidence; never infer `normal_end=False` from a
missing marker. For an existing log that grows without changing its prefix,
only the appended bytes may establish a marker; a truncated or same-size log
that already had a marker is ambiguous and is omitted. Carry the result through
a non-serialized runner sidecar and add it only at the typed ABACUS execute
envelope/observation boundary. Legacy `RunResult`/`run()` serialization, the
result schema key set, status values, collection, scientific state, workflow,
scheduling and retry behavior remain unchanged.

**Verification:** TDD regressions for stdout marker, changed running-log
marker, absent marker, stale marker, escaped/symlink log, nonzero process with
marker, and direct API/machine CLI parity; owning service/runner/contract
suites, full offline gate, independent review, and diff hygiene.

## Scope and boundaries

- Report `normal_end=true` only when a current, contained output has an exact
  `NORMAL END` or ABACUS `Total  Time  :` marker. Preserve the source as a
  workspace-relative diagnostic pointing at the existing output artifact.
- Missing, unreadable, unchanged, ambiguous, or escaped logs leave the
  observation unavailable (omitted); they do not change `execution` or
  `scientific` status.
- A changed existing log is accepted only when its marker can be attributed to
  the changed content: append-only updates are scanned after the unchanged
  prefix, while stale markers surviving truncation or same-size rewrites are
  treated as ambiguous.
- A nonzero/timeout/signal process may still carry a positive marker if the
  marker was actually observed; `returncode`, `termination`, and
  `normal_end` remain independent facts.
- Do not run `collect`, parse energies/convergence, inspect arbitrary files,
  add a policy or threshold, or turn `normal_end` into a check or scientific
  acceptance result.

## Task 1: Capture current-process normal-end provenance

**Files:** `src/abacus_forge/runner.py`, `src/abacus_forge/result.py`.

- Add a trailing, defaulted, non-serialized `RunResult` sidecar for optional
  normal-end value/source so existing positional construction and legacy
  `to_dict()`/`to_envelope()` remain compatible.
- Snapshot only contained `OUT.ABACUS/running_*.log` candidates before launch;
  after launch, inspect current stdout and changed/new candidates in stable
  order. Reject resolved paths outside the workspace and ignore unchanged
  stale files.
- Recognize only the confirmed positive markers; keep absence as `None`.

## Task 2: Project the fact at the typed ABACUS execute boundary

**Files:** `src/abacus_forge/services.py`,
`src/abacus_forge/service_support.py`, and nearest tests.

- When the runner sidecar reports a positive fact, add
  `normal_end=true` and its workspace-relative source to the typed execute
  diagnostics before `ServiceContext.persist`; otherwise leave diagnostics
  unchanged.
- Extend observation source classification so this execute fact is sourced as
  a log observation. Do not change the embedded legacy result envelope when
  callers use `abacus_forge.run()`/`RunResult.to_envelope()` directly.
- Preserve event payload equality and existing artifact references; the source
  must correspond to an existing contained execute artifact.

## Task 3: Regression and parity gate

**Files:** `tests/test_service_status.py`, `tests/test_cli_process.py`,
`tests/test_result_contract.py` if needed.

- Cover stdout `NORMAL END`, native `Total  Time  :`, changed running-log
  fallback, absent/stale/escaped markers, and marker-plus-nonzero execution.
- Assert the typed API and `operation execute --stdin` produce equivalent
  outcomes, including `normal_end` and source, while legacy `run()` output
  remains unchanged and no stale log is used.
- Assert event payloads retain the observation and all current status and
  artifact invariants.

## Acceptance checklist

- [x] Typed ABACUS execute exposes positive current `normal_end` with source.
- [x] Missing/stale/escaped marker is omitted, never inferred false; mtime-only
  touches of an old log are also ignored.
- [x] Legacy RunResult/result serialization and status/scientific semantics are
  unchanged.
- [x] Owning/full verification after the attribution hardening passes.
- [ ] Independent follow-up review of the exact post-fix range is still pending.

## Verification record

Implementation and review were completed in the candidate worktree:

- `98c2502` added the non-serialized runner sidecar, current stdout/running-log
  detection, typed diagnostics and observation projection, plus API/CLI parity.
- `ec411f3` replaced whole-file snapshots with stat fingerprints and streaming
  marker scans; it also made running-log artifacts auditable and reused the
  existing stdout artifact.
- `8d9bf4c` made source validation and artifact hashing failure-tolerant, so a
  disappearing, unreadable, escaped, directory, or symlink source only omits
  the observation and cannot turn a completed execute into an internal error.
- `14c69ff` added boundary regressions for ambiguous logs, invalid sources,
  nonzero-plus-marker, legacy key sets and artifact de-duplication.
- `eb1b004` made attribution conservative for mtime/ctime-only changes and
  added the touch-only stale-log regression.
- `ad1e167` added a streaming pre/post content fingerprint so same-inode,
  same-size rewrites are detected while touch-only stale logs remain ignored;
  `db3b3c2` made the private fingerprint type explicit and its regression uses
  equal-size before/after content.
- `68f690f` added a streaming unchanged-prefix check so an old marker is not
  reused when a later invocation only appends non-marker text. `cea1afc` also
  snapshots prior marker presence and fails closed for truncated or same-size
  rewrites that could retain that old marker. `0c9dcba` added a regression for
  a growing log whose old marker survives a changed-prefix rewrite; `5e56e93`
  makes that rewrite fail closed, while `9c21f51` keeps the positive case where
  the previous log had no marker and the new log supplies one. The regressions
  cover stale append, truncation, and changed-prefix rewrite.
- `a0718ce` documents the typed `normal_end` observation and its attribution
  boundary in `README.md` and `ROADMAP.md` without changing legacy usage.
- Owning service/result/CLI suite after the final attribution hardening: `306
  passed in 71.69s`.
- Focused normal-end regression suite after the final hardening: `13 passed`.
- Full offline gate after the final attribution hardening: `1346 passed, 10
  skipped in 112.66s`.
- Independent review first found stale append attribution and then a changed-
  prefix rewrite attribution bug; RED regressions and the hardening commits
  `68f690f`, `cea1afc`, and `5e56e93` close those cases. A second RED regression
  covers truncation. The final follow-up review is still required against the
  exact post-fix range before integration.
- `git diff --check` is clean for the post-fix code/test range.
