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

The `3 passed`/`13 passed` marker-run counts below are transcribed from the
Task 3 service review and its scoped re-review for fix commit `ac74d55`; they
are test-run counts, not collection counts. Task 4 reran the corresponding
strict marker collection gates in the repository worktree:

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest --strict-markers --collect-only -q -p no:cacheprovider -m cli tests/test_export_services.py tests/test_export_machine_cli.py
tests/test_export_machine_cli.py::test_machine_cli_routes_explicit_export_to_injected_service
tests/test_export_machine_cli.py::test_machine_cli_process_stdin_and_request_file_have_same_typed_export_result
tests/test_export_machine_cli.py::test_capabilityless_machine_export_still_rejects_before_service

3/16 tests collected (13 deselected) in 0.60s
Exit code: 0
```

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest --strict-markers --collect-only -q -p no:cacheprovider -m integration tests/test_export_services.py tests/test_export_machine_cli.py
tests/test_export_services.py::test_export_service_writes_exact_document_and_one_audited_output
tests/test_export_services.py::test_export_service_rejects_wrong_type_without_admission
tests/test_export_services.py::test_export_service_rejects_invalid_destination_before_admission[reports/events/new.json-request.path]
tests/test_export_services.py::test_export_service_rejects_invalid_destination_before_admission[reports/claims/new.json-request.path]
tests/test_export_services.py::test_export_service_rejects_invalid_destination_before_admission[../outside.json-request.schema]
tests/test_export_services.py::test_export_service_existing_destination_is_invalid_without_admission
tests/test_export_services.py::test_export_service_source_overlap_is_request_invalid_after_admission
tests/test_export_services.py::test_export_service_missing_source_is_precondition_after_admission
tests/test_export_services.py::test_export_service_duplicate_operation_id_is_conflict
tests/test_export_services.py::test_export_service_uses_unique_artifact_id_when_source_already_uses_base_id
tests/test_export_services.py::test_export_service_write_failure_has_no_fabricated_artifact
tests/test_export_services.py::test_export_service_persist_failure_does_not_return_artifact_or_event
tests/test_export_services.py::test_export_service_does_not_call_legacy_runtime_operations

13/16 tests collected (3 deselected) in 0.56s
Exit code: 0
```

The same Task 3 review reported the marker runs as `cli: 3 passed` and
`integration: 13 passed`; the Task 3 review also reported `git diff --check`
clean for `ac74d55`. The collection outputs above only establish discovery
counts; they do not claim that the collected tests ran in this Task 4 gate.
The final documentation work also passes `git diff --check` below.

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
