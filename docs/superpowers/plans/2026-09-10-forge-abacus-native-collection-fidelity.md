# ABACUS-native collection fidelity implementation plan

**Goal:** Make Forge collection facts follow the native ABACUS SCF and MD
output formats before adding more real-smoke gates. The change is limited to
parsing and operation-specific collection completeness; it does not turn Forge
into a scientific validator or workflow engine.

**Specs:**
`docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html`
and
`docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html`,
especially the facts-only collection rules, operation status separation,
compatibility clauses and Stage 2/4 release evidence boundaries.

**Authorization:** Continued Forge implementation was confirmed in this
session. A read-only boundary audit of the current branch identified a native
ABACUS parser gap that would make the existing typed SCF/MD real-smoke gates
misleading unless fixed first.

**Reference evidence:**

- ABACUS `abacus-develop` revision `94576a801`: `source/source_esolver/esolver_fp.cpp:279`
  writes `!FINAL_ETOT_IS <value> eV`; `source/source_md/md_base.cpp:209-231`
  writes MD `Energy/Potential/Kinetic (Ry)`, `Temperature (K)` and optional
  `Pressure (kbar)` blocks; `source/source_md/md_func.cpp:385-435` writes
  `MDSTEP`/lattice/atom records without thermodynamic values.
- `abacus-test` revision `1c9acbc`: `abacustest/lib_collectdata/abacus/abacus.py`
  reads the final energy marker as eV.
- `abacuscopilot` revision `91b9456`: `postprocessing/md_tasks.py` parses
  `MDSTEP` frames and `preprocessing/system_tasks.py` recognizes native MD
  energy blocks. These are reference evidence only, not runtime dependencies.

## Design decisions

- Add `!FINAL_ETOT_IS` as an additive `total_energy` parser path. Keep the
  existing `TOTAL ENERGY =` parser for compatibility; when both occur, the
  native final marker wins and the last native marker is used.
- Parse native MD thermodynamic rows from the unique, contained
  `running_md.log`, converting the three Ry energy columns with ABACUS's
  `Ry_to_eV = 13.605698`; keep temperature in K and pressure in kbar.
  `MD_dump` contributes native frame/step and artifact facts only on the typed
  MD projection. Its old synthetic `STEP ... TEMP ... ETOT ...` fallback
  remains readable on the legacy `collect()` path for compatibility; it does
  not populate typed MD thermodynamic fields when a typed request is served.
  If both native log and synthetic dump facts exist, native log values win and
  dump values never overwrite them. A dump-only typed collection may expose
  explicitly sourced compatibility observations, but remains `partial`.
- Keep the generic `total_energy` name for the electronic `!FINAL_ETOT_IS`
  value. MD's total/potential/kinetic values use capability-specific
  `md_last_*` fields (and any series/diagnostic fields) so ionic kinetic energy
  can never overwrite the electronic total.
- Route `MdCollectRequest` through a narrow `md_results.py` projection. A
  complete MD collection requires exactly one readable, contained
  `running_md.log` with at least one complete native thermodynamic block; a
  missing log with facts in `stdout.log` or `MD_dump`, or a readable log/dump
  with missing or malformed native facts, is `partial`; no readable domain log
  or dump is `missing_output`. Multiple/ambiguous `running_md.log` candidates
  are always `partial`, even if one candidate parses. A native block without a
  `Pressure (kbar)` column is complete (pressure is optional); a declared
  pressure column with a missing or non-numeric pressure row makes that block
  malformed. `MD_dump` is optional for Forge's minimum fact set (the
  trajectory is an extra artifact), not an assertion about ABACUS's
  `md_dumpfreq` output behavior. Normal-end and convergence remain
  observations/checks.
- Keep the generic `forge.result/v1` envelope, operation events, artifact
  containment and `scientific=unassessed` unchanged. No request fields,
  scheduler hooks, restart behavior or trajectory conversion are introduced.

## Scope

Production changes are limited to `collectors/abacus.py`, the new
`md_results.py`, and `services.py`. Owning tests cover native fixtures,
typed/API/machine parity, status distinctions and the existing legacy paths;
`tests/support/reference_workspaces.py` may add a fixture copier and
`tests/test_architecture.py` receives only the new neutral module root. A
small README/ROADMAP update records the source/units and keeps MD
experimental.

## Task 1: Native SCF final-energy parser

1. Add a regression against the repository-local ABACUSTest SCF fixture for
   `!FINAL_ETOT_IS`, including the exact eV value and last-marker selection.
2. Implement the additive parser path without changing existing metric names,
   legacy fallback behavior or convergence semantics.
3. Extend the benchmark/typed collection assertions to prove the native energy
   is present as a reported factual observation.

## Task 2: Native MD facts and completeness

1. Add a compact fixture copied from the ABACUS-native header/row shape and
   `MD_dump` frame shape, with provenance in the fixture README. The running
   log must contain both a `!FINAL_ETOT_IS` marker and MD thermodynamic rows so
   tests prove the two energy families do not overwrite one another.
2. Add parser tests for multiple MD steps, Ry-to-eV conversion, optional
   pressure (absent pressure column is valid, declared-but-invalid pressure is
   malformed), native frame counting, malformed/missing native rows, and
   multiple running-log ambiguity. Retain a regression proving the historical
   synthetic dump syntax remains readable through legacy `collect()` while
   typed MD fields remain native-log-only.
3. Implement the parser facts and a narrow `md_results.py` status projection;
   do not reuse SCF's unconditional `total_energy` completeness rule for MD.
   Freeze this status matrix:

   | `running_md.log` | native block | `MD_dump` | status |
   | --- | --- | --- | --- |
   | missing | — | missing | `missing_output` |
   | missing | stdout only | present or missing | `partial` |
   | present | missing/malformed | any | `partial` |
   | multiple/ambiguous | any | any | `partial` |
   | present and unique | complete | missing | `complete` |
   | present and unique | complete | present | `complete` |
4. Route only `MdCollectRequest` to that projection. Preserve all other
   capability and legacy collection paths.

## Task 3: Parity, documentation and verification

1. Add typed service and subprocess machine-CLI parity for the native MD
   fixture, checking execution/collection axes, event payloads and contained
   artifact refs without scientific thresholds.
2. Update `README.md`, `ROADMAP.md` and `tests/README.md` concisely: native
   thermodynamic facts come from `running_md.log`; `MD_dump` is trajectory
   evidence; MD remains experimental and real-smoke remains opt-in.
3. Run the focused collector/MD/service/CLI/architecture suites, then the full
   deterministic offline suite and `git diff --check`. Record exact revision
   and unavailable real execution honestly.

## Explicit non-goals

- No MD_dump-to-ASE/PDB conversion, trajectory analysis, latest-directory
  discovery, monitor, restart/resume, orchestration, scheduler/platform code,
  DeePMD support, scientific acceptance or maturity promotion.
- No typed MD real-smoke test is added in this plan merely to produce another
  skip. Once native facts and completeness are correct and a real prepared MD
  workspace/executable is supplied, the existing opt-in gate can be extended
  in a separate evidence batch.

## Acceptance record

- [ ] Native SCF final-energy fixture and parser regression pass.
- [ ] Native MD log/dump facts, units and MD-specific completeness pass with
      legacy synthetic fallback preserved.
- [ ] API/machine parity, architecture boundary and compatibility suites pass.
- [ ] Full offline gate and diff check pass; no real ABACUS or scientific claim
      is made without an external execution environment.

**Ruling:** This plan repairs a concrete Forge operation/collector fidelity
gap. It does not broaden the approved Forge boundary or replace human/Agent
scientific judgment. The next real-smoke evidence batch depends on this one.
