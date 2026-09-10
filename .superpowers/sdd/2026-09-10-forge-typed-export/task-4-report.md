# Task 4 report — typed export documentation and final offline verification

## Scope

Task 4 documents the implemented typed `export` capability and closes the
approved typed-export plan. The capability remains `experimental` and is not
presented as real ABACUS/PyATB or scientific-validation evidence.

The documentation was checked against the approved typed-export SPEC, the
2026-09-01/09-02 Forge contract/status SPECs, and the implementation at
`ac74d55`. It records the explicit source `ArtifactRef` boundary, the
`forge.export/v1` JSON document, the shared API/machine service, legacy
compatibility, and the caller-owned science/orchestration/scheduling boundary.

## Documentation changes

- `README.md` adds a complete experimental typed-export request, request-file
  and stdin CLI examples, Python API example, exact document shape, and the
  explicit historical-outcome/no-binary-copy semantics.
- `README.md` and `ROADMAP.md` distinguish explicit `capability="export"`
  from the unchanged capability-less machine and legacy export paths. They no
  longer describe generic typed export as deferred; MD-specific export,
  binary/archive, replace/merge and multi-operation aggregation remain out of
  scope.
- The typed-export SPEC records implementation status without changing its
  approved contract. The PLAN records the implemented commit set and this
  verification boundary.

## Verification evidence

All commands below ran in
`/home/james/work/sidereus/workplace/abacus-forge/.worktrees/forge-core-fidelity`
with the repository Paimon interpreter.

### Focused typed-export and architecture gate

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture.py tests/test_export_contracts.py tests/test_export_io.py tests/test_export_services.py tests/test_export_machine_cli.py
```

```text
90 passed in 9.49s
```

### Marker-stratified collection gates

The Task 3 review ran the registered marker subsets:

```text
cli: 3 passed
integration: 13 passed
```

The same review reported `git diff --check` clean for the marker/architecture
fix commit `ac74d55`; the final documentation work also passes the command
below.

### Full offline suite

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider
```

```text
1016 passed, 3 skipped in 82.72s (0:01:22)
```

Exit code was `0`. The three skips are the repository's opt-in real-smoke or
benchmark cases; no external ABACUS/PyATB process was started, and no
scientific acceptance claim is made.

```text
git diff --check
```

Exit code was `0` with no output.

## Review status

- Task 1 contract review: APPROVED after strict outcome and artifact-ref
  validation fixes (`bda4597`).
- Task 2 I/O review: APPROVED after directory-FD anchored no-replace
  publication fixes (`015c3b7`).
- Task 3 service review: APPROVED; the marker and AST dependency-root minors
  were addressed by `ac74d55`, with scoped re-review APPROVED and no new
  Critical/Important findings.
- Whole-branch review remains a final parent-agent gate over the exact typed
  export diff; this report does not substitute for that review.

No merge, push, scheduler integration, workflow orchestration, retry/resume,
or scientific validation was performed by this plan.
