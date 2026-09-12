# Forge typed PyATB artifact manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a capability-specific, facts-only forge.pyatb-manifest/v1 projection to typed pyatb-band prepare/collect results without changing the generic result contract or legacy PyATB helpers.

**Spec:** docs/superpowers/specs/2026-09-10-forge-typed-pyatb-artifact-manifest-design.html (Approved), under the approved 2026-09-01 and 2026-09-02 Forge SPECs.

**Status:** Implemented and reviewed. Tasks 1–4 below are complete; the historical
RED/GREEN instructions are retained as execution evidence, not as outstanding work.

**Architecture:** A small src/abacus_forge/pyatb_manifest.py module owns immutable manifest value objects, enum validation and deterministic path/kind mapping. Existing typed PyATB services build the manifest only after their real ArtifactRecord list exists, so every present entry points to an artifact in the same envelope. The machine CLI remains a decoder/router/renderer and legacy helpers are untouched.

**Tech Stack:** Existing frozen dataclasses, typing.Literal, pathlib, explicit MIME constants, current ArtifactRecord/ForgeResultEnvelope/ServiceContext, and pytest with the fixed Paimon interpreter.

## Global Constraints

- Implement only the approved pyatb_manifest/v1 diagnostics projection; do not change forge.result/v1, forge.operation-outcome/v1, ArtifactRecord, request fields or capability operations.
- Successful typed prepare and typed collect result envelopes contain diagnostics["pyatb_manifest"]; error envelopes do not fabricate it. Typed execute neither reads nor emits a previous operation's manifest.
- Manifest paths are canonical workspace-relative paths. artifact_id refers only to an ArtifactRecord.id in the same envelope; no cross-operation ArtifactRef, task ID, workflow edge, scheduler or platform field is allowed.
- Use only prepare handoff records and collect request paths. Never scan sibling SCF directories, infer Fermi/matrices, or discover undeclared output files.
- Preserve existing execution, collection, scientific, error-class and exit mappings. Existing malformed files remain real artifacts; missing/escaped/unavailable paths go to missing without fabricated artifacts.
- Preserve the distinction between parser-malformed files and unreadable files: the typed collector records hash/read failures in unavailable_output_paths_rel, and only that fact maps to manifest missing.reason="unavailable".
- Keep prepare_pyatb_band, run_pyatb, collect_pyatb, run_band_sequence and all legacy CLI behavior unchanged. Do not add nspin 4, PyATB properties, typed export, real-smoke, retry/resume or scientific acceptance.
- Default verification is offline and deterministic. Real PyATB/ABACUS execution remains a later independent gate.

---

### Task 1: Define typed manifest value objects and mapping vocabulary ✅

**Files:**
- Create: src/abacus_forge/pyatb_manifest.py
- Modify: src/abacus_forge/__init__.py to export the public manifest types and schema constant.
- Create: tests/test_pyatb_manifest.py

**Test strategy:**
- Behavior boundary: pure JSON-safe serialization, strict kind/spin/path validation, and deterministic MIME/kind classification; no filesystem writes or service admission.
- Existing suite to extend: none; this new typed value boundary owns its focused pure-contract tests.
- Temporary probes: none.

**Interfaces:**
- Produce PYATB_MANIFEST_SCHEMA_VERSION = "forge.pyatb-manifest/v1".
- Produce PyatbManifestEntry with frozen fields path_rel, kind, spin, optional artifact_id, sha256, size_bytes, media_type, source_path_rel, handoff_mode, source_sha256 and reason.
- Produce PyatbManifest with frozen tuples inputs, outputs and missing, plus to_dict()/from_dict().
- Produce classify_pyatb_output(path_rel) -> tuple[str, str, str] returning kind, spin and deterministic media_type.
- The value object accepts a sparse entry shape for missing records, but prepare/collect builders must require artifact_id/sha256/size_bytes on present entries and forbid those fields on missing entries. Classification is basename-only and deterministic; directory names add no inferred semantics.

- [x] Step 1: Write the failing pure-contract tests. Cover every approved kind (structure, matrix_hr, matrix_sr, matrix_rr, pyatb_input, kpoint_path, band_info, band_data, band_plot, run_input, other), every spin value including total, invalid canonical paths, unknown fields, missing root arrays, round-trip and known output names. Test that reason is reserved for missing-array entries and that present entries require complete artifact facts in the builders.

~~~python
def test_manifest_round_trip_and_known_output_mapping() -> None:
    kind, spin, media_type = classify_pyatb_output(
        "inputs/Out/Band_Structure/band_up.dat"
    )
    assert (kind, spin, media_type) == ("band_data", "up", "text/plain")
    manifest = PyatbManifest(
        inputs=(PyatbManifestEntry(
            path_rel="inputs/Input", kind="pyatb_input", spin="shared",
            artifact_id="input-input", sha256="a" * 64,
        ),),
        outputs=(),
        missing=(PyatbManifestEntry(
            path_rel="inputs/Out/Band_Structure/band.dat",
            kind="band_data", spin="unknown", reason="missing",
        ),),
    )
    assert PyatbManifest.from_dict(manifest.to_dict()) == manifest
~~~

- [x] Step 2: Run the pure tests to verify RED.

Run:

~~~bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_pyatb_manifest.py
~~~

Expected: failure because pyatb_manifest and its value objects/classifier do not yet exist.

- [x] Step 3: Implement the minimal manifest module. Reuse canonical_relative_path and JSON helpers from contracts; validate literals, hashes and sizes in __post_init__; make from_dict strict about unknown keys and require all three root arrays on the wire. Keep the value object permissive enough for a sparse missing record, while builders later enforce that present entries carry artifact_id/sha256/size_bytes, missing entries carry reason without fabricated artifact fields, and reason appears only in the missing array. Classification is basename-only; directory names do not add inferred semantics. Use explicit media mapping before fallback:

~~~python
if name == "band_info.dat": return "band_info", "unknown", "text/plain"
if name == "band_up.dat": return "band_data", "up", "text/plain"
if name in {"band_dn.dat", "band_down.dat"}: return "band_data", "down", "text/plain"
if name == "band.dat": return "band_data", "unknown", "text/plain"
if name == "band.png": return "band_plot", "unknown", "image/png"
if name == "band.pdf": return "band_plot", "unknown", "application/pdf"
if name == "input.json": return "run_input", "unknown", "application/json"
return "other", "unknown", "application/octet-stream"
~~~

- [x] Step 4: Run the pure tests to verify GREEN.

Run:

~~~bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_pyatb_manifest.py
~~~

Expected: all tests in the new file pass with exit code 0; manifest root contains only schema_version, inputs, outputs and missing.

- [x] Step 5: Refactor only duplicate validation in the new module, run git diff --check, and inspect that no generic contract changed.

- [x] Step 6: Commit Task 1.

~~~bash
git add src/abacus_forge/pyatb_manifest.py src/abacus_forge/__init__.py tests/test_pyatb_manifest.py
git commit -m "feat: add typed PyATB manifest contract"
~~~

---

### Task 2: Project explicit prepare handoff and generated inputs ✅

**Files:**
- Modify: src/abacus_forge/pyatb_manifest.py with build_prepare_pyatb_manifest(...).
- Modify: src/abacus_forge/pyatb_services.py only in PyatbBandPrepareService.prepare to assemble the manifest after _prepare_artifacts(workspace) returns.
- Modify: tests/test_pyatb_typed.py for prepare diagnostics/API/CLI assertions.

**Test strategy:**
- Behavior boundary: every physically staged/generated typed prepare input has a semantic entry and same-envelope artifact id; legacy helper output is unchanged.
- Existing suite to extend: tests/test_pyatb_typed.py already owns typed PyATB handoff hashes, nspin and persistence.
- Temporary probes: none; use existing _sources, _prepare_request and isolated tmp_path fixtures.

**Interfaces:**
- Consume PyatbBandPrepareRequest, the handoff tuple returned by prepare_typed_pyatb_band and the tuple[ArtifactRecord, ...] returned by _prepare_artifacts.
- Produce build_prepare_pyatb_manifest(request, handoff, artifacts) -> PyatbManifest.
- The service adds manifest.to_dict() under diagnostics["pyatb_manifest"] before existing ServiceContext.persist; persist remains the only artifact-ref injection point.

- [x] Step 1: Write RED prepare integration tests. Assert manifest version, entries for inputs/STRU, all matrix destinations, inputs/Input and inputs/KPT_band; every present entry id is in the envelope artifact ids; source/destination hashes match pyatb_handoff; nspin 2 maps HR by request order to up/down and SR/rR to shared.

~~~python
def test_typed_prepare_manifest_aligns_with_same_envelope_artifacts(tmp_path: Path) -> None:
    _sources(tmp_path)
    outcome = PyatbBandServiceSet.default(workspace_root=tmp_path).prepare.prepare(
        _prepare_request(operation_id=_id())
    )
    manifest = outcome.envelope.diagnostics["pyatb_manifest"]
    assert manifest["schema_version"] == "forge.pyatb-manifest/v1"
    by_path = {entry["path_rel"]: entry for entry in manifest["inputs"]}
    artifact_ids = {artifact.id for artifact in outcome.envelope.artifacts}
    assert {"inputs/STRU", "inputs/Input", "inputs/KPT_band"} <= set(by_path)
    assert all(entry["artifact_id"] in artifact_ids for entry in by_path.values())
~~~

- [x] Step 2: Run the focused tests to verify RED.

~~~bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_pyatb_typed.py -k prepare_manifest
~~~

Expected: failure because typed prepare currently contains pyatb_handoff but no pyatb_manifest.

- [x] Step 3: Implement the prepare projection. Build a path-to-artifact index, map handoff roles structure→structure, hr→matrix_hr, sr→matrix_sr and rR→matrix_rr, derive HR spin as shared for nspin 1 and up/down for nspin 2, and add generated Input/KPT entries. Raise ForgeInternalError if a present path is absent from the same artifact tuple; never scan other files or alter persisted handoff metadata.

~~~python
def build_prepare_pyatb_manifest(request, handoff, artifacts) -> PyatbManifest:
    by_path = {artifact.path_rel: artifact for artifact in artifacts}
    # Map each handoff destination and append inputs/Input and inputs/KPT_band
    # from the same ArtifactRecord path/hash/size.
    entries = tuple(_entry_from_handoff(record, by_path, request) for record in handoff)
    entries += tuple(_entry_from_generated_input(path, by_path[path])
                     for path in ("inputs/Input", "inputs/KPT_band"))
    return PyatbManifest(inputs=entries, outputs=(), missing=())
~~~

- [x] Step 4: Run typed prepare, service and legacy tests to verify GREEN.

~~~bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_pyatb_typed.py tests/test_pyatb.py tests/test_service_status.py -k 'pyatb or typed'
~~~

Expected: all selected tests pass with exit code 0; no legacy PyATB assertion changes are required.

- [x] Step 5: Refactor only prepare manifest assembly, run git diff --check, and verify forge-unit.json metadata.pyatb_handoff is unchanged for the same fixture.

- [x] Step 6: Commit Task 2.

~~~bash
git add src/abacus_forge/pyatb_manifest.py src/abacus_forge/pyatb_services.py tests/test_pyatb_typed.py
git commit -m "feat: project typed PyATB prepare manifest"
~~~

---

### Task 3: Project explicit collect artifacts and facts ✅

**Files:**
- Modify: src/abacus_forge/pyatb_manifest.py with build_collect_pyatb_manifest(...).
- Modify: src/abacus_forge/pyatb_services.py only in PyatbBandCollectService.collect to attach the projection after collect_typed_pyatb_band returns its real envelope.
- Modify: tests/test_pyatb_typed.py, tests/test_machine_cli.py and tests/test_cli_process.py for API/CLI parity and mapping.

**Test strategy:**
- Behavior boundary: only requested/default files become output entries; missing/escaped/unavailable paths become missing entries with a reason; malformed files that exist remain real artifacts while diagnostics retain parser incompleteness.
- Existing suite to extend: test_pyatb_typed.py owns direct collection/service behavior; the two CLI files own transport and envelope parity.
- Temporary probes: none; use _write_band_outputs and existing fake executable fixtures.

**Interfaces:**
- Consume PyatbBandCollectRequest, raw collect ForgeResultEnvelope and its ArtifactRecord tuple.
- Produce build_collect_pyatb_manifest(request, envelope) -> PyatbManifest.
- Keep existing status, metrics, artifacts and diagnostics keys, adding only pyatb_manifest before ServiceContext.persist.

- [x] Step 1: Write RED collect/parity tests. Cover band_info.dat, band.dat, band_up.dat, band_dn.dat, PNG, PDF, Out/input.json, unknown explicit files, missing output, escaped symlink, hash/read-unavailable output and malformed band info. Assert fixed media types, proven spin mapping, unknown fallback, no fabricated artifact id in missing, unavailable reason mapping and equal API/CLI manifest JSON.

~~~python
def test_typed_collect_manifest_keeps_malformed_real_artifact(tmp_path: Path) -> None:
    _write_band_outputs(tmp_path, info="Band gap (eV): nan\n", data=False, picture=False)
    result = collect_typed_pyatb_band(
        tmp_path, PyatbBandCollectRequest(operation_id=_id(), workspace_rel=".")
    )
    assert result.artifacts
    assert result.diagnostics["malformed_output_paths_rel"]

def test_typed_collect_service_persists_manifest_diagnostics(tmp_path: Path) -> None:
    _write_band_outputs(tmp_path)
    outcome = PyatbBandServiceSet.default(workspace_root=tmp_path).collect.collect(
        _collect_request(operation_id=_id())
    )
    assert outcome.envelope.diagnostics["pyatb_manifest"]["schema_version"] == \
        "forge.pyatb-manifest/v1"
~~~

- [x] Step 2: Run the focused tests to verify RED.

~~~bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_pyatb_typed.py tests/test_machine_cli.py tests/test_cli_process.py -k 'manifest or pyatb_band'
~~~

Expected: new manifest assertions fail while existing typed collect/API/CLI tests continue to pass.

- [x] Step 3: Implement the collect projection. First update collect_typed_pyatb_band to preserve hash/read failures in unavailable_output_paths_rel (without changing parser-malformed behavior). Then index existing ArtifactRecords by canonical path; classify only requested paths; build missing from missing_output_paths_rel, escaped_output_paths_rel and unavailable_output_paths_rel with reasons missing, escaped or unavailable. Do not move parser-malformed existing files out of outputs and do not infer total from band.dat, pictures or band_info.dat.

~~~python
def build_collect_pyatb_manifest(request, envelope) -> PyatbManifest:
    diagnostics = envelope.to_dict()["diagnostics"]
    present = {artifact.path_rel: artifact for artifact in envelope.artifacts}
    outputs = tuple(_entry_from_artifact(path, present[path])
                    for path in _requested_output_paths(request, present))
    missing = tuple(_missing_entry(path, reason)
                    for path, reason in _requested_failures(request, diagnostics, present))
    return PyatbManifest(inputs=(), outputs=outputs, missing=missing)

# Task 1/3 define these private helpers with typed signatures; they accept only
# canonical workspace-relative paths and existing ArtifactRecord instances.
# Their concrete signatures are:
# _requested_output_paths(request, present) -> tuple[str, ...]
# _requested_failures(request, diagnostics, present) -> tuple[tuple[str, str], ...]
# _entry_from_artifact(path_rel, artifact) -> PyatbManifestEntry
# _missing_entry(path_rel, reason) -> PyatbManifestEntry
~~~

- [x] Step 4: Run typed, CLI and legacy suites to verify GREEN.

~~~bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_pyatb_typed.py tests/test_pyatb.py tests/test_machine_cli.py tests/test_cli_process.py
~~~

Expected: all selected tests pass with exit code 0; isolated equivalent API/CLI fixtures have byte-equivalent pyatb_manifest diagnostics, including unavailable output reasons.

- [x] Step 5: Refactor only duplicate path/classification code, run git diff --check, and confirm no ArtifactRef or previous-operation lookup was added.

- [x] Step 6: Commit Task 3.

~~~bash
git add src/abacus_forge/pyatb_manifest.py src/abacus_forge/pyatb_services.py tests/test_pyatb_typed.py tests/test_machine_cli.py tests/test_cli_process.py
git commit -m "feat: project typed PyATB collect manifest"
~~~

---

### Task 4: Documentation, architecture checks and final branch verification ✅

Progress ledger: Task 1 completed by `7628a76`, `4533462`, `9e1340c` and verified by
the pure manifest suite. Task 2 completed by `e281a84` and `4fde284`, covering
prepare provenance and deterministic MIME. Task 3 completed by `f4e0d5c` and
`3afc132`, with reviewer fixes in `d79bdf1` and legacy-path hygiene in `d7b90fc`;
these close collect availability semantics, malformed-file handling, matrix
classification and subprocess API/CLI parity. Final verification on `d7b90fc`:
focused typed/legacy/machine suites `194 passed in 41.16s`; architecture/discovery
gate `19 passed, 64 deselected in 5.68s`; full offline gate `934 passed, 3 skipped
in 74.31s`; `git diff --check` clean. Whole-branch scoped review of
`10e14e9..d7b90fc` is APPROVED; the three Important findings from the first review
were fixed and rechecked.

**Files:**
- Modify: README.md with manifest shape and one API/CLI example, keeping typed PyATB scope/facts-only language concise.
- Modify: ROADMAP.md to mark manifest closure experimental and keep properties, nspin 4, export and real-smoke deferred.
- Modify: tests/test_architecture.py only if the new module needs explicit forbidden-import/assertion coverage.
- Modify: the companion SPEC and this plan/progress ledger with approved status, exact commits and evidence after review.
- Create: .superpowers/sdd/2026-09-10-forge-typed-pyatb-artifact-manifest/task-4-report.md for raw verification output.

**Test strategy:**
- Behavior boundary: documentation accurately describes the additive diagnostics manifest and does not advertise unimplemented property/export/scheduler behavior.
- Existing suite to extend: tests/test_architecture.py and tests/test_cli_process.py already enforce discovery, dependency and machine-envelope contracts.
- Temporary probes: no committed temporary files; any real-smoke probe is outside this plan and must not enter the default suite.

**Interfaces:**
- Consume completed manifest value objects and typed service output from Tasks 1–3.
- Produce an approved SPEC/PLAN record, current-state documentation and exact offline evidence; no production interface beyond diagnostics["pyatb_manifest"].

- [x] Step 1: Update README/ROADMAP after behavior is green. Document successful typed prepare/collect manifest, finite kinds/spins, same-envelope artifact ids, malformed versus unavailable-file fact behavior and the external scientific boundary. Do not document automatic discovery or export.

- [x] Step 2: Run documentation, architecture and discovery checks.

The discovery request schema and capability descriptor do not change: this slice
adds response diagnostics only, so no discovery.py edit is expected unless an
architecture assertion requires an import-boundary test.

~~~bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture.py tests/test_machine_cli.py -k 'architecture or discovery or pyatb_band'
~~~

Expected: selected gates pass with exit code 0 and no forbidden imports.

- [x] Step 3: Run the complete deterministic gate and retain raw output.

~~~bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider
git diff --check
~~~

Expected: pytest exits 0 with all existing/new tests passing; diff-check produces no output. Record exact HEAD, output and intentional real-smoke skips.

- [x] Step 4: Perform plan/spec self-review before final review. Scan for placeholder text, verify every M1–M7 requirement maps to tests/implementation, confirm no legacy helper changes and confirm the manifest root is the only new wire object. After human approves SPEC/PLAN, change SPEC status to Approved and record approval source.

- [x] Step 5: Request independent task reviews and one whole-branch review. Bind findings to the implementation diff and approved SPEC; resolve Critical/Important findings, record verified Minor deferrals and rerun the complete gate after each fix wave. Real smoke remains unavailable evidence unless separately supplied.

- [x] Step 6: Commit docs and verification record.

~~~bash
git add README.md ROADMAP.md tests/test_architecture.py docs/superpowers/specs/2026-09-10-forge-typed-pyatb-artifact-manifest-design.html docs/superpowers/plans/2026-09-10-forge-typed-pyatb-artifact-manifest.md
git add -f .superpowers/sdd/2026-09-10-forge-typed-pyatb-artifact-manifest/task-4-report.md
git commit -m "docs: close typed PyATB artifact manifest"
~~~

## Plan self-review

- Spec coverage: M1 is Tasks 1/4, M2 is Task 2, M3 is Task 3, M4 is Tasks 1/3, M5/M6 are Tasks 2–3 and global constraints, and M7 is Task 4 plus unchanged legacy suites.
- Scope check: one capability and one diagnostics projection only; typed export, real smoke, properties, nspin 4 and orchestration remain separate future plans.
- Placeholder scan: every implementation step names files, interfaces, tests and commands, with no open-ended template text.
- Type consistency: Task 1 defines PyatbManifest, PyatbManifestEntry and classify_pyatb_output; Tasks 2–3 consume those exact names and Task 4 documents the diagnostics shape.
- Verification boundary: all default commands are offline; no command treats a fake process as scientific or stable-release evidence.

Implementation was executed after the companion SPEC approval with
superpowers:subagent-driven-development, using task-scoped implementer/reviewer
passes followed by a whole-branch review. Future extensions must use a new
approved SPEC/PLAN when they change the manifest vocabulary or capability scope.

## Follow-up contract correction (2026-09-11)

The later typed PyATB nspin=4 handoff work and the optional-rR correction
supersede the historical assumptions above that nspin=4 or rR were deferred or
always present. Current truth is: Bands requires explicit HR/SR, accepts
nspin=1|2|4 with HR cardinality 1|2|1, and records `matrix_rr` only when the
caller supplies rR. The original manifest implementation and its verification
evidence remain historical records; the current contract is defined by the
approved nspin=4 design and `2026-09-11-forge-typed-pyatb-optional-rr.md`.
