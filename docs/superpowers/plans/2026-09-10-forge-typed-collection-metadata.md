# Typed collection metric provenance and smoke-gate integrity plan

**Goal:** Make the typed SCF/Relax/MD collection envelope carry the unit,
kind, and contained artifact provenance that its existing `MetricRecord`
contract already allows, and close two real-smoke gate holes without changing
Forge's operation or scientific boundaries.

**Spec:**
`docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html`
and
`docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html`,
especially R3/R4/R6, the facts-only collection rules, compatibility clauses,
and the explicit separation of execution, collection, and scientific
assessment.

**Authorization:** Continued implementation of the approved Forge plan was
confirmed in this session. The current-branch read-only gap audit found that
typed collection values already have known physical units and source paths,
but serialization drops that metadata; it also found two opt-in real-smoke
assertion/timeout gaps. This plan is the next bounded Forge checkpoint.

**Architecture:** Enrich only the typed collection projection built by
`collection_results.py` (and the Relax/MD projections that reuse it). Keep the
existing `MetricRecord` and `Observation` shapes, `forge.result/v1`, legacy
`CollectionResult`/CLI output, status values, and event persistence unchanged.
The collector may carry parser provenance in a non-serialized internal
sidecar on `CollectionResult`; it must not add provenance keys to the legacy
diagnostics/result dict. Use the already emitted `ArtifactRecord` list to
resolve source artifact IDs; leave a source ID unset when no contained path
can be established. Existing `Observation.source` categories remain as-is in
this checkpoint; the metric's `source_artifact_id` is the precise provenance
link. The real-smoke changes are test-only: validate the typed SCF input
calculation before execution and give typed Relax's parent process the same
long timeout budget as the SCF gate.

**Verification:** Focused typed SCF/Relax/MD collection and contract tests,
real-smoke collection tests in skip-safe mode, full deterministic offline
pytest, clean `git archive` focused tests, clean wheel installation/import and
console-entry-point checks, plus `git diff --check`. No real ABACUS execution,
scientific acceptance, scheduler, orchestration, retry/resume, or new schema
field is introduced by this plan.

## Rulings and boundaries

- **Ruling:** Improve metadata at the typed service boundary, not in
  `CollectionResult.to_envelope()`. The legacy envelope and `to_dict()` are
  compatibility surfaces and must retain their historical `unit=None`,
  generic-kind, and diagnostics key behavior. Parser provenance therefore
  lives in non-serialized `CollectionResult` sidecar fields (origin map plus
  derived-name set) with empty defaults. The collector places the sidecar on
  the constructed result after consuming private parser metadata; `to_dict()`
  and `to_envelope()` explicitly omit those fields, and `relax_results` carries
  them when it reconstructs a projection. The cost if wrong is a reversible
  internal model change rather than a legacy wire-format change.
- **Ruling:** Use an explicit per-metric table. `runtime` is reserved for
  `returncode` and `omp_threads`; `derived` is used only for values explicitly
  computed by the current parser (`energy_per_atom` and stress-trace
  `pressure`); all other parsed scalar facts, including MD dump counts, are
  `reported`. Unknown scalar facts remain `unit=None`, `kind="reported"`.
- **Ruling:** Units are attached only when the producing parser branch has a
  confirmed grammar/semantic source. Native MD energies are `eV`, native MD
  temperature is `K`, native MD pressure is `kbar`, and stress-trace pressure
  is `kbar`; native `!FINAL_ETOT_IS` is `eV`. A computed per-atom value is
  `eV/atom` only when its source total energy is known to be eV. Generic
  unitless regex values (`fermi_energy`, `band_gap`, `volume`,
  `largest_gradient`, generic `PRESSURE`, and output-log timing columns) keep
  `unit=None` until their grammar is verified. Count labels are limited to
  `natom=atoms`, `nelec=electrons`, `scf_steps/relax_steps/md_steps/md_dump_steps=steps`,
  `md_dump_frames=frames`; `time.json`'s `total_time` is `s`.
- **Ruling:** A source origin is recorded at the parser branch that actually
  supplies the final value. Main running log wins for regex/native/stress
  facts; output log supplies only fields added by its fallback parser;
  `time.json` overrides `total_time` when present; `MD_dump` supplies its
  counts and legacy synthetic fallback facts. Typed projections never attach a
  report/final-structure source ID to a scalar metric in this checkpoint;
  nested report/structure observations retain their existing file/parser
  categories. External, escaped, missing, or ambiguous paths yield no source
  ID.
- **Ruling:** The production SCF service remains compatibility-liberal about
  `INPUT calculation`; only the typed SCF real-smoke fixture gate checks that
  the supplied workspace is actually an SCF workspace. The cost if wrong is a
  clearer release gate without changing callers that rely on the service's
  existing acceptance behavior.

## Owned files and responsibilities

- `src/abacus_forge/result.py`: add trailing, defaulted, non-serialized
  `CollectionResult` sidecar fields for per-metric origin and derived names;
  keep them out of `to_dict()` and `to_envelope()` explicitly so existing
  positional constructors and wire keys remain unchanged.
- `src/abacus_forge/collectors/abacus.py` and `src/abacus_forge/collection.py`:
  record parser-branch provenance in private metadata, consume it while
  constructing `CollectionResult`, and never expose it in legacy diagnostics.
- `src/abacus_forge/relax_results.py`: copy the sidecar while rebuilding the
  Relax projection so typed metadata survives final-structure selection.
- `src/abacus_forge/collection_results.py`: build typed collection metric
  records with the finite unit/kind/source map and artifact-ID resolution;
  preserve legacy projection and non-scalar `legacy_metrics`.
- `tests/test_collect_abacus_reference.py`, `tests/test_md_services.py`, and
  the relevant `tests/test_service_status.py` cases: regress SCF/MD/Relax
  units, derived-vs-reported kind, source artifact IDs, existing observation
  categories, and legacy compatibility.
- `tests/real_smoke/test_abacus_smoke.py`: add the SCF calculation preflight
  and pass the long parent-process timeout to typed Relax.
- `README.md`, `ROADMAP.md`, `tests/README.md`: concise documentation of
  machine metric metadata and the smoke-gate preconditions; no new user
  workflow or scientific claim.

## Task 1: Preserve derived-fact provenance

**Files:** `src/abacus_forge/collectors/abacus.py`, `src/abacus_forge/result.py`,
`src/abacus_forge/collection.py`, and collector regression tests.

**Behavior:** When a scalar value is computed from other parsed facts, record
the fact's derived status and actual source origin in the internal
`CollectionResult` sidecar without changing the legacy diagnostics, metrics,
or numeric value. The collector may use a private temporary metadata key in its
internal return, but `collection.py` must consume it into the sidecar before
returning the result. At minimum, distinguish computed versus explicitly
parsed `energy_per_atom` and stress-trace versus explicitly parsed `pressure`;
record the final branch for output-log fallback and `time.json` override
values. The sidecar has empty defaults for callers that construct
`CollectionResult` directly.

**Verification:** Focused collector tests cover explicit and computed
energy-per-atom values, stress-derived pressure, output-log fallback and
`time.json` override. They assert the sidecar facts while comparing the
existing `collect().to_dict()`/legacy envelope keys and values for compatibility.

## Task 2: Enrich typed SCF/Relax/MD metric records

**Files:** `src/abacus_forge/collection_results.py`, nearest typed collection
tests, with no edits to `MetricRecord` or result schema definitions.

**Behavior:** Rebuild only the typed collection envelope's scalar metrics
using existing fields and the following closed table:

- `eV`: `total_energy` only for native `!FINAL_ETOT_IS`, native MD last
  energies; `eV/atom`: computed `energy_per_atom` only when the source total
  energy is known eV; `K`: native `md_last_temperature`; `kbar`:
  native `md_last_pressure` and stress-trace `pressure`;
- count units: `natom=atoms`, `nelec=electrons`,
  `scf_steps/relax_steps/md_steps/md_dump_steps=steps`,
  `md_dump_frames=frames`; `time.json` `total_time=s`;
- all other generic regex scalar values (`fermi_energy`, `band_gap`, `volume`,
  `largest_gradient`, generic `pressure`, output-log timing values), booleans,
  version strings, return codes, and unknown values retain `unit=None`;
- `runtime`: `returncode` and `omp_threads` only; `derived`: only parser-marked
  `energy_per_atom` and stress-trace `pressure`; all other parsed scalar facts
  remain `reported`;
- a metric receives `source_artifact_id` from the sidecar's actual producing
  branch: selected main log, output log fallback, `time.json`, or `MD_dump`,
  provided the path resolves to exactly one contained envelope artifact.
  Reports/final structures are not scalar metric sources in this checkpoint;
  missing/ambiguous/external paths leave the ID null rather than inventing
  provenance.

Non-scalar arrays/nested parser facts stay in `diagnostics.legacy_metrics`.
Collection status, checks, warnings, workspace-relative paths, event payloads,
and scientific `unassessed` semantics do not change. API and machine CLI must
remain equivalent in isolated workspaces.

**Verification:** Add assertions for typed SCF (`total_energy`, stress-derived
`pressure`, `total_time`, computed `energy_per_atom`), typed MD (native energies,
temperature, optional pressure, and `MD_dump` step/frame facts), and typed
Relax scalar metrics; confirm nested report facts remain observations. Assert
each source ID names an envelope artifact, that existing observation source
categories remain unchanged, and that legacy
`collect(workspace).to_envelope()` retains its existing generic metadata. Add
same-name fallback/override and external/escaped source cases. Run the owning
suites.

## Task 3: Repair real-smoke gate integrity

**Files:** `tests/real_smoke/test_abacus_smoke.py` and, only if needed,
`tests/support/process.py` call sites.

**Behavior:** Before typed SCF execute, parse the copied `inputs/INPUT` with
the existing input reader (or the nearest existing parser) and fail the smoke
gate if `calculation` is not `scf`; do not change production `ScfServiceSet`
compatibility behavior. Pass `_REAL_SMOKE_PROCESS_TIMEOUT_SECONDS` to typed
Relax's execute and collect `run_cli` calls so the parent process cannot kill a
normal Relax run after 30 seconds.

**Verification:** Run the real-smoke module without environment variables and
confirm the tests skip cleanly; use focused source/test checks to prove the SCF
mismatch assertion occurs before the first execute `run_cli` call and that
both typed Relax execute and collect calls pass
`_REAL_SMOKE_PROCESS_TIMEOUT_SECONDS`. No real-smoke success is claimed
without the externally supplied workspace and executable.

## Task 4: Documentation and release gates

**Files:** `README.md`, `ROADMAP.md`, `tests/README.md`, and this plan.

**Behavior:** State concisely that typed collection metrics expose units,
  reported/derived/runtime kind, and contained source artifact IDs only for
  grammar-confirmed facts; legacy collection remains compatible;
  real-smoke requires a capability-matching prepared workspace and uses a long
  parent timeout. Keep maturity and scientific-validation language unchanged.

**Verification:** Run focused suites, full offline pytest, clean archive focused
tests, clean wheel/install/import/entry-point checks with no legacy package
imports, and `git diff --check`. Record exact revision and test counts here and
in the roadmap only after the commands pass.

## Explicit non-goals

- No new schema version, MetricRecord/Observation field, error class, status
  value, policy, threshold, convergence judgment, or scientific acceptance.
- No changes to legacy `collect()`/`CollectionResult.to_envelope()` metadata,
  legacy CLI defaults, or historical artifact paths.
- No broad unit inference for unknown parser keys, no arbitrary source-path
  scanning, and no external/escaped artifact references.
- No production SCF calculation-mismatch rejection in this checkpoint.
- No ABACUS execution, scheduler/platform integration, workflow orchestration,
  restart/resume, monitor, DeePMD support, or Paimon adapter work.

## Acceptance record

- [ ] Typed SCF/Relax/MD scalar metrics carry the finite unit/kind/source
      metadata and retain legacy compatibility.
- [ ] Existing observation source categories and event shape remain unchanged;
      precise provenance is available through metric artifact IDs.
- [ ] Typed SCF/Relax real-smoke gates reject mismatched input/avoid premature
      parent timeout; absent environment still skips cleanly.
- [ ] Focused, full offline, archive, wheel/import, and diff checks pass.
- [ ] No real execution or scientific acceptance claim is made without an
      external supplied environment.

**Ruling:** This plan closes a concrete facts-envelope fidelity gap and two
release-gate hygiene defects while preserving Forge's narrow role as an
ABACUS unit-operation substrate. Human/Agent layers still own scientific
validation, orchestration, retry/resume, and platform scheduling.
