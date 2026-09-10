# Forge legacy property artifact manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Proposed implementation plan; execution requires explicit approval of the companion Draft SPEC.

**Goal:** Add a facts-only `forge.property-manifest/v1` projection to the legacy `charge-density`, `spin-density`, and `charge-diff` post operations without changing the generic result contract, property CLI syntax, or Forge's scientific/workflow boundary.

**Spec:** `docs/superpowers/specs/2026-09-10-forge-property-manifest-design.html` (Draft for review; this plan must not be executed until that SPEC is approved).

**Architecture:** A focused `property_manifest.py` module owns immutable manifest records, strict JSON validation, and an explicit-path builder. Legacy property post functions keep their existing compatibility selection and cube arithmetic, then attach the manifest as `TaskResult.diagnostics["property_manifest"]`. The builder consumes the same `ArtifactRecord` projection as the returned result, so manifest IDs, hashes, sizes, and paths cannot diverge; it never scans directories, chooses latest files, or creates cross-operation provenance.

**Tech Stack:** Python 3.10+, frozen/slotted dataclasses, existing `ArtifactRecord`, `TaskResult`, `Workspace` path containment, `pathlib`, `hashlib` through the existing artifact projection, JSON-safe records, and pytest in the `paimon` environment.

## Global Constraints

- Implement only `forge.property-manifest/v1` diagnostics for the three approved legacy post packs (SPEC R1); keep all other property packs experimental and untouched.
- Do not modify `forge.result/v1`, `ArtifactRecord`, `TaskResult` field names, operation events, admission, legacy `prepare|run|post` syntax, or machine discovery descriptors (SPEC R1/R7).
- Present entries use only `cube|report|text|other`, `input|output`, `source|derived`, and `shared|up|down|unknown` (SPEC R2/R3); derived data cubes require same-result source artifact IDs, while fact reports may omit them (SPEC R5).
- Canonical missing paths are the exact table in SPEC §architecture (R6): ABACUS output is under each subtask's `inputs/OUT.<suffix>/`; missing or empty suffix expands to `ABACUS`; an unsafe suffix never becomes an escaped manifest path.
- Manifest paths are workspace-relative and contained (SPEC R7). A missing path has only `path_rel`, semantic fields, and `reason=missing|escaped|unavailable` (SPEC R4); it never has artifact identity, hash, or size.
- Legacy parser exceptions remain legacy exceptions. This slice does not introduce a malformed-file downgrade; `parse_status="malformed"` is accepted only as a value vocabulary for a separately designed future path.
- Manifest projection failure is best-effort: preserve the original `TaskResult`, status, summary, artifacts, and CLI exit, and append a JSON-safe warning instead of retrying or fabricating a manifest.
- Scientific validation, acceptance, orchestration, retry/resume, scheduler/platform selection, and real ABACUS evidence remain caller-owned; default verification is offline.

---

### Task 1: Define the facts-only manifest value objects

**Files:**
- Create: `src/abacus_forge/property_manifest.py`
- Modify: `src/abacus_forge/__init__.py` to re-export `PROPERTY_MANIFEST_SCHEMA_VERSION`, `PropertyManifest`, and `PropertyManifestEntry` only.
- Modify: `tests/conftest.py` to register `test_property_manifest.py` as `experimental`.
- Create: `tests/test_property_manifest.py`

**Test strategy:**
- Behavior boundary: pure JSON contract and enum/path validation; no workspace writes, engine invocation, or directory discovery.
- Existing suite to extend: none; this file owns the new capability-specific value contract.
- Temporary probes: none.

**Interfaces:**
- Produce `PROPERTY_MANIFEST_SCHEMA_VERSION = "forge.property-manifest/v1"`.
- Produce frozen `PropertyManifestEntry(path_rel, kind, role, origin, spin, artifact_id=None, sha256=None, size_bytes=None, media_type=None, parse_status=None, source_artifact_ids=(), reason=None)`.
- Produce frozen `PropertyManifest(task, inputs=(), outputs=(), missing=())` with strict `to_dict()`/`from_dict()` using root keys `schema_version`, `task`, `inputs`, `outputs`, and `missing`.
- Produce implementation-facing frozen `PropertyArtifactSpec(path, kind, role, origin, spin="unknown", parse_status=None, source_paths=())`; its `path` may be an absolute `Path` selected by legacy post or a canonical workspace-relative string. It is not re-exported as a stable top-level API.

- [ ] **Step 1: Write the failing pure-contract tests.** Cover every allowed kind, role, origin, and spin (SPEC R2/R3); lowercase SHA-256 and non-negative size; canonical path rejection; strict unknown/root-field rejection; present/missing mutual exclusion; parse-status literals; derived-cube non-empty source-ref rule (SPEC R5); report-derived entries without refs; and round-trip JSON (SPEC R1/R4).

```python
def test_property_manifest_round_trip_and_derived_cube_refs() -> None:
    manifest = PropertyManifest(
        task="spin-density",
        inputs=(PropertyManifestEntry(
            path_rel="spin-density/scf/inputs/OUT.ABACUS/SPIN1_CHG.cube",
            kind="cube", role="input", origin="source", spin="up",
            artifact_id="artifact-up", sha256="a" * 64, size_bytes=12,
            media_type="application/octet-stream", parse_status="ok",
        ),),
        outputs=(PropertyManifestEntry(
            path_rel="reports/spin_density.cube",
            kind="cube", role="output", origin="derived", spin="shared",
            artifact_id="artifact-diff", sha256="b" * 64, size_bytes=12,
            media_type="application/octet-stream", parse_status="ok",
            source_artifact_ids=("artifact-up", "artifact-down"),
        ),),
        missing=(),
    )
    assert PropertyManifest.from_dict(manifest.to_dict()) == manifest


def test_report_derived_entry_may_omit_source_refs() -> None:
    entry = PropertyManifestEntry(
        path_rel="reports/metrics_spin_density.json",
        kind="report", role="output", origin="derived", spin="unknown",
        artifact_id="artifact-report", sha256="c" * 64, size_bytes=2,
        media_type="application/json",
    )
    assert entry.to_dict()["kind"] == "report"
```

- [ ] **Step 2: Run the pure tests to verify RED.**

Run:

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_property_manifest.py
```

Expected: collection fails because `abacus_forge.property_manifest` and its value objects do not yet exist.

- [ ] **Step 3: Implement the minimal value-object module.** Reuse `canonical_relative_path`, `_construct_strict`, `_mapping_payload`, and `_require_nonempty_string` from `contracts.py`; use a lowercase-hex SHA-256 regex; normalize all sequence fields to tuples; omit `None` optionals in `to_dict()`; require exactly the three root arrays in `from_dict()`. Enforce that a missing entry has `reason` and no artifact facts, that a present entry has no `reason`, and that only a `kind="cube"`, `origin="derived"` entry requires non-empty `source_artifact_ids`.

```python
PROPERTY_MANIFEST_SCHEMA_VERSION = "forge.property-manifest/v1"
_KINDS = frozenset({"cube", "report", "text", "other"})
_ROLES = frozenset({"input", "output"})
_ORIGINS = frozenset({"source", "derived"})
_SPINS = frozenset({"shared", "up", "down", "unknown"})
_REASONS = frozenset({"missing", "escaped", "unavailable"})
_PARSE_STATUSES = frozenset({"ok", "malformed"})


@dataclass(frozen=True, slots=True)
class PropertyManifestEntry:
    path_rel: str
    kind: str
    role: str
    origin: str
    spin: str = "unknown"
    artifact_id: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    media_type: str | None = None
    parse_status: str | None = None
    source_artifact_ids: tuple[str, ...] = ()
    reason: str | None = None
```

- [ ] **Step 4: Run the pure tests to verify GREEN.**

Run the same command from Step 2. Expected: all tests in `tests/test_property_manifest.py` pass and serialization emits only JSON values.

- [ ] **Step 5: Refactor duplicate validation only inside the new module, run `git diff --check`, and confirm `git diff -- src/abacus_forge/contracts.py src/abacus_forge/result.py` is empty.**

- [ ] **Step 6: Commit Task 1.**

```bash
git add src/abacus_forge/property_manifest.py src/abacus_forge/__init__.py tests/conftest.py tests/test_property_manifest.py
git commit -m "feat: add legacy property manifest contract"
```

---

### Task 2: Build explicit property facts from the same artifact projection

**Files:**
- Modify: `src/abacus_forge/property_manifest.py` with `build_property_manifest(...)` and explicit path classification.
- Modify: `src/abacus_forge/composite/properties.py` with suffix expansion, manifest attachment, and three post-call projections.
- Modify: `tests/test_property_manifest.py` for builder path/containment/ref cases.
- Modify: `tests/test_maturation_packs.py` for charge/spin/charge-diff diagnostics.

**Test strategy:**
- Behavior boundary: selected files, canonical missing files, derived source refs, symlink containment, file disappearance, and projection-failure isolation; valid legacy arithmetic remains unchanged.
- Existing suite to extend: `tests/test_maturation_packs.py` owns legacy property fixture behavior; pure builder cases stay in `tests/test_property_manifest.py`.
- Temporary probes: none; use existing `_prepared_workspace` and `_write_cube` fixtures.

**Interfaces:**
- Consume `Workspace`/workspace root, `PropertyArtifactSpec` sequences, and the tuple of `ArtifactRecord` values produced by `TaskResult.to_envelope().artifacts`.
- Produce `build_property_manifest(workspace: Path, *, task: str, inputs: Sequence[PropertyArtifactSpec], outputs: Sequence[PropertyArtifactSpec], artifacts: Sequence[ArtifactRecord]) -> PropertyManifest`.
- Produce `_attach_property_manifest(result: TaskResult, *, inputs: Sequence[PropertyArtifactSpec], outputs: Sequence[PropertyArtifactSpec]) -> TaskResult`, which catches projection exceptions and appends a string warning without changing the legacy result.

- [ ] **Step 1: Write RED builder tests.** Use one contained present file and an `ArtifactRecord` with the expected ID/hash/size; assert present entries copy those facts verbatim (SPEC R2). Use a non-existent canonical path for `missing`, an external resolved symlink for `escaped`, a directory or artifact-less path for `unavailable` (SPEC R4/R7), and a derived cube with two `source_paths` to assert same-result source IDs (SPEC R5). Assert a report with `origin="derived"` does not require refs.

```python
def test_build_property_manifest_classifies_explicit_paths_and_missing(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path).ensure_layout()
    cube = workspace.root / "charge-density/scf/inputs/OUT.ABACUS/SPIN1_CHG.cube"
    cube.parent.mkdir(parents=True)
    cube.write_text("cube", encoding="utf-8")
    artifact = ArtifactRecord(
        id="artifact-source", path_rel=cube.relative_to(workspace.root).as_posix(),
        role="output", stage="collect", sha256="a" * 64, size_bytes=4,
    )
    manifest = build_property_manifest(
        workspace.root,
        task="charge-density",
        inputs=(PropertyArtifactSpec(cube, "cube", "input", "source", "unknown"),
                PropertyArtifactSpec(
                    workspace.root / "charge-density/scf/inputs/OUT.ABACUS/MISSING.cube",
                    "cube", "input", "source", "unknown",
                )),
        outputs=(),
        artifacts=(artifact,),
    )
    assert [entry.path_rel for entry in manifest.inputs] == [artifact.path_rel]
    assert manifest.missing[0].reason == "missing"
    assert "artifact_id" not in manifest.missing[0].to_dict()
```

- [ ] **Step 2: Run the focused builder tests to verify RED.**

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_property_manifest.py -k build
```

Expected: failures because the builder and `PropertyArtifactSpec` are not implemented.

- [ ] **Step 3: Implement explicit builder resolution.** Canonicalize each spec path against the workspace root; resolve strict symlinks; classify failures as `missing`, `escaped`, or `unavailable` (SPEC R4/R6/R7); never walk a directory or glob. For a present path, look up the already-projected `ArtifactRecord` by canonical `path_rel` and copy its ID/hash/size (SPEC R2). Map MIME from the explicit kind (`cube`/`other` → `application/octet-stream`, `report` → `application/json`, `text` → `text/plain`). For a present derived cube, canonicalize every `source_paths` item and require all source IDs in the same `artifacts` tuple (SPEC R5); raise `ForgeInternalError` if that invariant is impossible. Deduplicate repeated declarations in declaration order and reject a path appearing in both present arrays.

```python
def build_property_manifest(
    workspace: Path,
    *,
    task: str,
    inputs: Sequence[PropertyArtifactSpec],
    outputs: Sequence[PropertyArtifactSpec],
    artifacts: Sequence[ArtifactRecord],
) -> PropertyManifest:
    by_path = {artifact.path_rel: artifact for artifact in artifacts}
    present_inputs, missing_inputs = _resolve_specs(workspace, inputs, by_path)
    present_outputs, missing_outputs = _resolve_specs(workspace, outputs, by_path)
    return PropertyManifest(
        task=task,
        inputs=tuple(present_inputs),
        outputs=tuple(present_outputs),
        missing=tuple((*missing_inputs, *missing_outputs)),
    )
```

- [ ] **Step 4: Add legacy post projection without changing selection/arithmetic.** In `properties.py`, derive the safe suffix from each prepared subtask `inputs/INPUT` (`ABACUS` when missing/empty); construct only the canonical paths listed in SPEC R6. Pass the actual path returned by existing `_find_first` when it exists, otherwise pass its canonical path. Attach the metrics report for every call. For spin and charge-diff always declare the derived report/cube expected paths; a missing derived cube becomes a missing manifest fact, while a present derived cube references only the source cubes that were present in the same result (SPEC R5). Keep the existing summary, status, artifacts, diagnostics keys, and exceptions unchanged apart from the additive manifest/warning (SPEC R1/R7).

```python
def _attach_property_manifest(result: TaskResult, *, inputs, outputs) -> TaskResult:
    try:
        artifacts = result.to_envelope().artifacts
        result.diagnostics["property_manifest"] = build_property_manifest(
            Path(result.workspace), task=result.task,
            inputs=tuple(inputs), outputs=tuple(outputs), artifacts=artifacts,
        ).to_dict()
    except Exception as error:
        result.diagnostics.setdefault("warnings", []).append(
            f"property manifest projection unavailable: {type(error).__name__}: {error}"
        )
    return result
```

- [ ] **Step 5: Run the maturation/property suites to verify GREEN.**

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_property_manifest.py tests/test_maturation_packs.py
```

Expected: all pure builder and legacy property tests pass; existing cube arithmetic values and legacy statuses remain unchanged.

- [ ] **Step 6: Refactor only local spec construction, run `git diff --check`, and inspect that no import of `abacustest`, `abacusagent`, scheduler, or external workflow package was added.**

- [ ] **Step 7: Commit Task 2.**

```bash
git add src/abacus_forge/property_manifest.py src/abacus_forge/composite/properties.py tests/test_property_manifest.py tests/test_maturation_packs.py
git commit -m "feat: project legacy property artifact facts"
```

---

### Task 3: Freeze API/CLI parity and failure isolation

**Files:**
- Modify: `tests/test_maturation_packs.py` for direct API and legacy CLI parity.
- Modify: `tests/test_cli.py` for JSON output and old-key compatibility.
- Modify: `tests/test_result_contract.py` only for the additive diagnostics assertion if the existing generic result fixture needs an explicit guard.

**Test strategy:**
- Behavior boundary: the same fixture passed through direct property functions and `abacus_forge.cli.main` yields byte-equivalent manifest facts; projection errors never alter legacy status/exit.
- Existing suite to extend: `tests/test_maturation_packs.py` owns property API; `tests/test_cli.py` owns in-process legacy CLI output; `tests/test_result_contract.py` owns generic result key stability.
- Temporary probes: none.

**Interfaces:**
- Consume the three post functions and the additive `diagnostics.property_manifest` object from Task 2.
- Produce regression evidence that `TaskResult.to_dict()` still has exactly `task`, `workspace`, `status`, `subtasks`, `summary`, `artifacts`, and `diagnostics`; only the diagnostics value is additive for the three post operations.

- [ ] **Step 1: Add parity and isolation tests.** Prepare isolated workspaces with the existing cube fixture under `outputs/` and compare the direct result's manifest to the JSON captured from `main(["spin-density", "post", ..., "--json"])` (SPEC R1/R6). Repeat for charge-density and charge-diff. Monkeypatch `build_property_manifest` to raise `RuntimeError` and assert the post result keeps its baseline status/summary/artifacts and contains a JSON-safe warning (SPEC R7).

```python
def test_spin_density_api_and_legacy_cli_share_property_manifest(tmp_path: Path, capsys) -> None:
    workspace = _prepared_workspace(tmp_path / "spin-parity")
    prepared = prepare_spin_density(workspace.root)
    spin_dir = workspace.root / "spin-density" / "scf" / "outputs"
    _write_cube(spin_dir / "SPIN1_CHG.cube", [3.0, 4.0])
    _write_cube(spin_dir / "SPIN2_CHG.cube", [1.0, 1.5])
    direct = post_spin_density(workspace.root)
    assert main(["spin-density", "post", str(workspace.root), "--json"]) == 0
    cli = json.loads(capsys.readouterr().out)
    assert cli["diagnostics"]["property_manifest"] == direct.diagnostics["property_manifest"]
    assert set(direct.to_dict()) == {"task", "workspace", "status", "subtasks", "summary", "artifacts", "diagnostics"}
```

- [ ] **Step 2: Run the focused parity tests against the Task 2 implementation.**

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_maturation_packs.py tests/test_cli.py -k 'property_manifest or spin_density_api'
```

Expected: all selected tests pass. A failure means the Task 2 projection has a parity or best-effort-isolation regression and must be corrected before documentation work; no new public production surface is added by this task.

- [ ] **Step 3: Refactor only test helpers and fixture setup.** Use separate temporary API/CLI roots so no operation result is reused; compare only `property_manifest` for path-independent parity, while retaining exact relative paths, hashes, source IDs, missing reasons, and statuses. Do not change production contracts in this task.

- [ ] **Step 4: Run the focused suites to verify GREEN.**

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_property_manifest.py tests/test_maturation_packs.py tests/test_cli.py tests/test_result_contract.py
```

Expected: all selected tests pass; no legacy CLI top-level flags or JSON keys are changed.

- [ ] **Step 5: Commit Task 3.**

```bash
git add tests/test_maturation_packs.py tests/test_cli.py tests/test_result_contract.py
git commit -m "test: lock legacy property manifest parity"
```

---

### Task 4: Documentation, architecture gate, and final offline verification

**Files:**
- Modify: `README.md` with a short property manifest example and explicit facts-only boundary.
- Modify: `ROADMAP.md` to record this as experimental diagnostics support while leaving typed property promotion, nspin 4, workfunc/ELF/Bader manifests, aggregation, and real-smoke deferred.
- Modify: `tests/test_architecture.py` to include `property_manifest` in the neutral import-graph roots and verify it has no legacy API or forbidden upper-layer dependency.
- Modify: `docs/superpowers/specs/2026-09-10-forge-property-manifest-design.html` only after the human approves it: change status to Approved and record the approval date/source.
- Modify: this plan with completed task ledger and exact verification output after implementation.
- Create: `.superpowers/sdd/2026-09-10-forge-property-manifest/task-4-report.md` with raw gate output; force-add it because `.superpowers/` is ignored.

**Test strategy:**
- Behavior boundary: documentation does not advertise a typed property capability, automatic discovery, scheduler, scientific acceptance, or real ABACUS evidence; architecture protects the import boundary.
- Existing suite to extend: `tests/test_architecture.py` owns AST/import checks and discovery; README examples remain covered by its existing machine-CLI parsing tests.
- Temporary probes: none; no real-smoke command belongs in the default gate.

**Interfaces:**
- Consume the completed value objects, builder, and legacy post projection from Tasks 1–3.
- Produce an approved SPEC/PLAN record, current documentation, architecture evidence, and a clean offline branch; no new runtime wire object beyond `diagnostics.property_manifest`.

- [ ] **Step 1: Update README and ROADMAP after behavior is green.** Show one JSON fragment with `schema_version`, `task`, `inputs`, `outputs`, and `missing`; state that actual variant paths are preserved, canonical paths are only missing facts, and scientific validation/orchestration/scheduling remain outside Forge.

- [ ] **Step 2: Add the architecture root and test.** Extend the neutral service roots with `abacus_forge.property_manifest`; assert `dependency_violations` is empty and that the module imports neither `abacus_forge.api` nor any forbidden upper layer. Do not add property to machine discovery because this slice is legacy diagnostics, not a typed capability.

- [ ] **Step 3: Run the architecture and documentation checks.**

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_architecture.py tests/test_property_manifest.py tests/test_maturation_packs.py tests/test_cli.py
git diff --check
```

Expected: zero failures and no diff-check output; discovery continues to list only the already implemented typed capabilities.

- [ ] **Step 4: Run the complete deterministic gate and retain raw output.**

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
git diff --check
```

Expected: pytest exits 0, the only skipped tests are the pre-existing opt-in real-smoke/benchmark tests, and `git diff --check` is clean. Do not represent this offline gate as scientific validation.

- [ ] **Step 5: Self-review the approved SPEC/PLAN against the implementation.** Verify every R1–R7 row has a test or explicit unchanged boundary, canonical paths match `properties.py`, present IDs come from the same envelope artifact tuple, reports do not fabricate refs, and no typed discovery entry was added.

- [ ] **Step 6: Request an independent task-scoped review and whole-branch review.** Bind any finding to the approved SPEC and exact diff, fix Critical/Important findings, record justified Minor deferrals in this plan, and rerun the complete gate after each fix wave. No cross-model review or real-smoke claim is required unless separately requested or supplied.

- [ ] **Step 7: Commit documentation and verification evidence.**

```bash
git add README.md ROADMAP.md tests/test_architecture.py docs/superpowers/specs/2026-09-10-forge-property-manifest-design.html docs/superpowers/plans/2026-09-10-forge-property-manifest.md
git add -f .superpowers/sdd/2026-09-10-forge-property-manifest/task-4-report.md
git commit -m "docs: close legacy property artifact manifest"
```

## Plan self-review

- Spec coverage: R1 is Task 1 plus Task 3; R2–R5 are Tasks 1–2; R6 is Task 2 plus canonical-path tests; R7 is Tasks 2–4 and the unchanged legacy/architecture gates.
- Scope check: one additive diagnostics projection for three existing legacy post packs; no typed property capability, scheduler, workflow, scientific judgement, or cross-operation provenance is introduced.
- Type consistency: Task 1 defines the exact manifest records/spec and Task 2 consumes them; Task 3 compares the same `property_manifest` key; Task 4 documents the same root and entry vocabulary.
- Placeholder scan: no execution step depends on an unnamed file, unbounded discovery rule, or unspecified command; every verification command is offline and deterministic.
- Approval boundary: the companion SPEC remains `Draft for review`; after this plan is reviewed, execution still requires explicit human approval followed by the selected execution mode.
