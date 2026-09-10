# Forge typed export Implementation Plan

> **Status:** Approved. The linked SPEC and PLAN passed independent design
> review; use
> `superpowers:subagent-driven-development` with one implementer and one
> independent reviewer per task.

**Goal:** Add a capability-specific, facts-only typed `export` operation that
serializes one explicitly referenced prior operation outcome to a contained JSON
document, while keeping all legacy export behavior unchanged.

**Spec:** `docs/superpowers/specs/2026-09-10-forge-typed-export-design.html`
(Approved under the current thread's continued Forge implementation
authorization), together with the approved 2026-09-01 and 2026-09-02 Forge SPECs.

**Architecture:** `ExportRequest` is a separate typed request registered under
`capability="export"`, `operation="export"`. A small event/ref resolver reads the
explicit source operation from the workspace event index and validates each
`ArtifactRef` against that immutable outcome. The export service atomically writes
one `forge.export/v1` JSON document, constructs one output `ArtifactRecord`, and
uses the existing `ServiceContext.persist()` boundary for artifact refs and one
append-only event. The machine CLI only decodes/routes/renders; legacy
`api.export()` and the legacy `export` command remain untouched.

## Global constraints

- Do not change `forge.result/v1`, `forge.operation-outcome/v1`,
  `ArtifactRecord`, `ArtifactRef`, the seven error classes, or legacy request/API/
  CLI behavior.
- The typed request must contain a non-empty `source_artifact_refs` list. All
  refs must have the same `operation_id`; that source operation is resolved only
  in the current workspace. No latest-result lookup, directory discovery,
  implicit collect/postprocess, or cross-workspace reference is allowed.
- The only file format in this plan is `json`; the only overwrite policy is
  `fail`. Binary copy/archive, replace/merge, multi-operation aggregation and
  publication are separate future designs.
- Every destination and event path is canonical and contained. Never overwrite
  source artifacts, workspace manifest, event/claim/lock files, compatibility
  audit files, or their reserved directories.
- A successful export is an `OperationOutcome` with
  `execution="completed"`, `collection="complete"`, and
  `scientific="unassessed"`; it contains only the new JSON output artifact.
- API and machine CLI call the same service. CLI stdout remains one JSON
  outcome/error document; `--pretty` and text format affect rendering only.
- Source event/artifact facts are read-only. No science, scheduling,
  orchestration, retries, resume, or external process is introduced.

---

## Task 1: Typed request/document contracts and discovery

**Ownership:** `src/abacus_forge/export_contracts.py`,
`src/abacus_forge/discovery.py`, `src/abacus_forge/machine_cli.py`,
`src/abacus_forge/__init__.py`, and contract/discovery tests. Do not modify
legacy `api.py` or `cli.py`.

**Interfaces:**

- Add frozen `ExportRequest` based on `OperationRef` with fields
  `schema_version`, `capability="export"`, `operation="export"`,
  `operation_id`, `workspace_rel`, `source_artifact_refs`,
  `destination_path_rel`, `format="json"`, `pretty=False`, and
  `overwrite_policy="fail"`.
- `source_artifact_refs` decodes through `ArtifactRef.from_dict`; it is a
  non-empty tuple, rejects duplicate refs and mixed operation IDs, and does not
  add workspace/task fields to `ArtifactRef`.
- Add immutable `ExportDocument` (or an equivalently strict value object) with
  `schema_version="forge.export/v1"`, `source_operation_id`,
  `source_artifact_refs`, and `source_outcome`. Its wire shape is strict and
  JSON-safe; `source_outcome` is an unchanged `forge.operation-outcome/v1`
  payload.
- Register only explicit `capability="export"` in the typed decoder and
  discovery registry. Add an experimental `export` descriptor with engine
  `forge`, operation `export`, input/source-ref and output artifact roles. The
  existing capability-less machine `export` request remains `request.invalid` /
  exit 2 until this explicit capability is supplied.
- Static schema properties must be checked against dataclass fields and real
  `to_dict()` keys; `additionalProperties=false`, required identity/source/
  destination fields, canonical relative path pattern and enum values are
  frozen in discovery.

**Tests (RED → GREEN):**

1. Add contract tests for round-trip, strict unknown fields, missing/empty refs,
   duplicate/mixed operation IDs, invalid UUIDs, path traversal/absolute paths,
   unsupported format/overwrite values, and strict export-document decoding.
2. Add discovery/schema tests for `capabilities`, `schema export export`, exact
   descriptor maturity/engine/operations and static/dataclass parity.
3. Preserve tests proving no-capability `operation export` still returns one
   `request.invalid` envelope until the explicit export request is used.
4. Run the owning RED gate before implementation, then the GREEN gate and
   `git diff --check`.

**Commit:**

```bash
git add src/abacus_forge/export_contracts.py src/abacus_forge/discovery.py \
  src/abacus_forge/machine_cli.py src/abacus_forge/__init__.py \
  tests/test_export_contracts.py tests/test_machine_cli.py \
  tests/test_cli_process.py tests/test_architecture.py
git commit -m "feat: add typed export request contract"
```

---

## Task 2: Explicit source-event resolver and atomic document writer

**Ownership:** create `src/abacus_forge/export_io.py` and its focused tests;
keep service dispatch and legacy APIs out of this task.

**Interfaces and algorithm:**

- `resolve_export_source(workspace, refs)` must ensure the workspace manifest is
  readable, locate the exact event index entry for the single operation ID, and
  resolve its contained event path. It may reconcile the existing event index,
  but must not scan for “latest” or infer an event from filenames.
- Parse the event as `OperationOutcome`; reject an invalid/missing source event
  or missing artifact ID as `ForgePreconditionError`. Verify every ref's
  `artifact_id` exists in the source envelope and that the source event's
  operation ID agrees with the ref list.
- `write_export_document(workspace, destination_path_rel, document, pretty)`
  must validate the canonical destination again, reject reserved audit/source
  paths, create only contained parent directories, write a same-directory
  temporary file plus fsync, and publish it with an atomic **no-replace** step
  (for example, a hard-link from the temporary file followed by cleanup). A
  target that appears after the initial existence check must fail rather than
  be overwritten. Return the final path, SHA-256 and byte size. The `pretty`
  flag only selects deterministic JSON indentation; it must not alter the
  document object.
- Source artifacts are historical records: after the event payload and
  `artifact_id` membership are validated, do not read, stat, resolve symlinks
  for, or compare the current source file. Validate only that the recorded
  `ArtifactRecord.path_rel` is canonical and contained; a deleted or changed
  source file does not invalidate export.
- Do not add a generic “read event” public protocol, modify event payloads, or
  mutate source files. Reuse existing workspace containment and JSON helpers
  where their byte behavior is compatible; otherwise keep the atomic writer
  private to this module.

**Tests (RED → GREEN):**

- Resolve one known event and exact refs; reject missing event, malformed event,
  missing/duplicate/mixed refs, outside event path and source artifact mismatch.
- Confirm source event bytes are unchanged and that export succeeds even when a
  recorded source artifact has been deleted or replaced; export must not read or
  mutate that source path.
- Confirm destination parent creation, canonical containment, symlink escape,
  reserved audit paths, source overlap, existing destination with `fail`,
  deterministic pretty/compact JSON, atomic no-replace publication (including a
  destination-created-after-check race), temporary cleanup and returned
  hash/size.
- Simulate write/stat failures and map them to the existing persistence/internal
  boundary without fabricating an output artifact.

**Commit:**

```bash
git add src/abacus_forge/export_io.py tests/test_export_io.py
git commit -m "feat: add explicit typed export source resolver"
```

---

## Task 3: Export service, API/CLI routing, event and artifact parity

**Ownership:** create `src/abacus_forge/export_services.py`; modify only the
typed registries/routing and public exports needed by tests. Add
`tests/test_export_services.py` and `tests/test_export_machine_cli.py`.

**Service contract:**

- `ExportService.export(request) -> OperationOutcome | ForgeErrorEnvelope` and
  `ExportServiceSet.default(workspace_root=".")` expose one concrete service;
  no compatibility facade is introduced.
- Validate request identity, destination containment and reserved paths before
  admission. Under the existing `operation_guard`, resolve the source event and
  refs, check the destination still does not exist, write the document, build
  one `ArtifactRecord` with `role="output"`, `stage="export"`,
  `media_type="application/json"`, hash and size, then call
  `ServiceContext.persist()` exactly once.
- The returned envelope diagnostics contain only factual source refs,
  source operation ID, destination, format and overwrite policy. The exported
  file contains the exact source `OperationOutcome` plus the source refs; no
  metrics/status/scientific values are recomputed or changed.
- A source precondition discovered after admission returns
  `precondition.missing` / exit 3 and leaves the admission tombstone according
  to existing rules. Existing destination returns `request.invalid` / exit 2;
  persistence errors return class 5. No error envelope fabricates the export
  manifest/artifact.
- Add the explicit `export` service-set branch to `run_machine_cli`. The
  capability-less legacy machine path and all top-level legacy CLI tests remain
  unchanged. `operation --request/--stdin` and API must produce equivalent
  outcome, diagnostics, output bytes, refs and one event in isolated workspaces.

**Tests (RED → GREEN):**

- Successful API service export: exact document, one output artifact, hash/size,
  same-workspace refs, status and one event; source event unchanged.
- API/CLI process parity for request-file and stdin; stdout is one JSON document,
  text/pretty only changes rendering, stderr remains diagnostic-only.
- Missing source/event/ref, outside/reserved/overlap destination, existing
  destination, repeated operation ID, malformed source payload and write/event
  failure with stable error class/exit mapping.
- Assert no collect/postprocess/runner call, no latest lookup, no cross-workspace
  read, and no legacy `api.export()`/`abacus-forge export` regression.

**Commit:**

```bash
git add src/abacus_forge/export_services.py src/abacus_forge/machine_cli.py \
  src/abacus_forge/__init__.py tests/test_export_services.py \
  tests/test_export_machine_cli.py tests/test_cli_process.py
git commit -m "feat: expose typed export service"
```

---

## Task 4: Documentation, review and final verification

**Ownership:** `README.md`, `ROADMAP.md`, this plan, the companion SPEC status
and `.superpowers/sdd/2026-09-10-forge-typed-export/` report files. No further
production scope is allowed.

**Documentation:**

- Add one explicit typed request/API/CLI example and the exact
  `forge.export/v1` document shape. Label capability `experimental`.
- State plainly that typed export serializes a referenced result outcome; it
  does not copy binary artifacts, discover latest results, execute collection/
  postprocess, publish reports or judge science. Keep legacy export examples
  and behavior documented separately.
- Update ROADMAP to mark only this typed JSON export slice as landed when the
  final gate passes; keep replace/merge, binary/archive export, multi-operation
  aggregation, PyATB properties, real-smoke and Stage 5 deferred.

**Verification and review:**

1. Run focused export contracts/IO/service/process suites with the repository
   Paimon interpreter and `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src
   -p no:cacheprovider`.
2. Run discovery/schema, architecture forbidden-import and all legacy export/API/
   CLI suites.
3. Run the full offline pytest gate and `git diff --check`; record exact output,
   HEAD and intentional skips in the SDD report. No real science evidence is
   claimed.
4. Have an independent task reviewer inspect each task and a whole-branch
   reviewer inspect the exact diff against the approved SPEC. Resolve all
   Critical/Important findings and rerun the relevant gates.
5. Commit docs/report only after the final review is clean. Do not merge or push
   in this plan.

**Commit:**

```bash
git add README.md ROADMAP.md docs/superpowers/specs/2026-09-10-forge-typed-export-design.html \
  docs/superpowers/plans/2026-09-10-forge-typed-export.md
git add -f .superpowers/sdd/2026-09-10-forge-typed-export/task-4-report.md
git commit -m "docs: close typed export slice"
```

## Self-review

- The plan adds one generic typed export capability and no new scheduler,
  workflow, science or external-runtime dependency.
- Source selection is explicit and auditable; no directory/latest inference is
  hidden in the service. Existing `ArtifactRef` remains unchanged.
- The result document preserves the source outcome while the service outcome
  records only the new export artifact, so source and export operation identity
  cannot be confused.
- `overwrite_policy=fail` deliberately protects append-only artifact evidence;
  replacement and binary packaging are deferred rather than silently guessed.
- All behavior changes are isolated behind a new typed capability. Existing
  capability-less machine `export` invalid behavior and legacy export paths are
  explicit regression gates.

## Implementation record (2026-09-10)

Tasks 1–3 are implemented and independently reviewed. The typed export slice
is represented by commits `8e2591b`, `dc6032f`, `52a16d8`, `bda4597`,
`3f1f7d4`, `370a102`, `015c3b7`, `d16c3ac` and `ac74d55`; the last commit
closes the marker and architecture-gate hygiene findings from the Task 3
review. Task 4 documents the shipped experimental capability and records the
final offline verification. No merge or push is part of this plan.
