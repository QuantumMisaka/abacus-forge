# Final whole-branch fix report

## Findings

1. **Critical — duplicate operation reservation:** addressed. `Workspace.claim_v1_operation()` creates an atomic, process-visible reservation before typed prepare/modify/execute/collect work. Claimed event commit is performed before release; duplicate callers receive `persistence.conflict`, do not invoke the runner, and do not overwrite `forge-result.json`. Stale reservations from dead processes are reclaimable.
2. **Critical — collect execution contamination:** addressed. Typed collect always supplies `execution="not_run"`; it no longer reads service-instance state or `forge-result.json`. Upstream execution remains available only as its own operation event/result.
3. **Important — cross-operation artifact references:** addressed. Added immutable strict `ArtifactRef(operation_id, artifact_id)` and typed service diagnostics now expose references for emitted artifacts.
4. **Important — prepare/modify provenance:** addressed. Prepare envelopes enumerate input files and `forge-unit.json`; modify envelopes retain `changes`, modified files, and before/after input snapshots.
5. **Important — policy registry:** addressed. Typed prepare/modify/execute accept only `abacus.scf/v1` or explicit `none`; collect accepts only `abacus.scf/v1`.
6. **Important — error taxonomy:** addressed for the typed boundary. Duplicate/persistence conflicts map to `persistence.conflict`; missing files to `precondition.environment`; schema/path/policy request failures use distinct request classes; unexpected failures map to `internal.error`. Runner nonzero/timeout/missing executable remain structured failed execution envelopes with runtime artifacts.
7. **Important — legacy signatures:** addressed. `prepare_unit` and `modify_unit` no longer expose `record_event`; a private context variable suppresses legacy events only while typed adapters invoke the public primitives.
8. **Important — failure/event coverage:** addressed in the implementation and regression coverage. Typed operations claim before mutation; exceptions release claims without appending caller events; runner failure outputs remain represented by stdout/stderr artifacts and failed status.

## Verification

Focused:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_contracts.py tests/test_service_status.py tests/test_workspace.py tests/test_units.py
```

Result: `100 passed in 2.15s`.

Full deterministic suite:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
```

Result: `231 passed, 2 skipped in 13.12s`.

Additional syntax check: `python -m py_compile src/abacus_forge/*.py` passed.
`git diff --check` passed.

## Self-review

- Legacy event-producing calls retain their historical default behavior.
- Typed operations use caller-owned UUIDv4 event identities and release claims on all exception paths.
- No ATP, MCP, AiiDA, scheduler, `abacus-agent-tools`, or `abacustest` dependency was introduced.
- Remaining limitation: the claim is a filesystem reservation and cannot roll back arbitrary user-visible input mutations if a process crashes after mutation but before event commit; normal exceptions clean the reservation and never publish an error event. Full crash recovery/transactional workspace snapshots should be a later persistence milestone.
