# Forge Native Fermi Unit Follow-up Plan

**Goal:** Preserve the confirmed unit of native ABACUS `E_Fermi` observations in the typed collection projection.
**Spec:** `docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html` and `docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html`, plus the completed typed collection metadata boundary in `docs/superpowers/plans/2026-09-10-forge-typed-collection-metadata.md`.
**Authorization:** Continued user-authorized Forge maturation; a read-only audit found a concrete parser/projection fidelity gap.
**Architecture:** Mark only the native `E_Fermi <Ry> <eV>` parser branch internally, then map that provenance to `MetricRecord.unit="eV"` at the typed boundary. Keep generic `FERMI ENERGY =` output unitless, preserve all legacy projections, and do not add wire fields or scientific interpretation.
**Verification:** TDD regression for native and generic Fermi paths, typed API/CLI parity, owning collection/service suites, full offline gate, and diff/review hygiene.

## Scope and boundaries

- Native ABACUS `E_Fermi` rows already select the final eV column; typed `fermi_energy` receives `unit="eV"` only when that branch supplies the final value.
- Historical generic `FERMI ENERGY =` rows remain `unit=None` because their unit is not established by the grammar.
- Numeric values, `MetricRecord` schema, `forge.result/v1`, legacy `CollectionResult` serialization, event shape, status, and `scientific="unassessed"` remain unchanged.
- No broad unit inference, workflow, scheduling, execution, or scientific validation is introduced.

## Task 1: Preserve native Fermi provenance

**Files:** `src/abacus_forge/collectors/abacus.py`, `src/abacus_forge/collection_results.py`, nearest collection/API/CLI tests.

- [x] Add a private parser diagnostic/provenance marker only when native `E_Fermi` supplies `fermi_energy`; do not mark the generic legacy regex path.
- [x] Map that marker to typed `fermi_energy.unit="eV"` while retaining `kind="reported"` and source artifact behavior.
- [x] Add regressions for native eV selection, generic unitless fallback, and API/CLI parity; verify legacy envelopes remain unchanged.
- [x] Run owning/full gates, review the diff, and record exact evidence here.

## Acceptance checklist

- [x] Native `E_Fermi` typed metric has unit `eV`.
- [x] Generic `FERMI ENERGY =` typed metric remains unitless.
- [x] Legacy output and scientific/status boundaries are unchanged.
- [x] Full verification and independent review pass.

## Verification record

Implemented on candidate branch `forge-maturity-gates`:

- `0ba5f90` introduced native Fermi unit provenance; `1b09a22` moved that provenance to a private `CollectionResult.metric_units` sidecar so it cannot leak into legacy or typed diagnostics/events.
- `e612740` added a real direct typed-API versus `operation collect --stdin` parity fixture; `ce25c8d` tidied the test boundary without behavior changes.
- Owning regression command (`tests/test_collect_abacus_reference.py`, `tests/test_cli_process.py`, `tests/test_result_contract.py`, `tests/test_service_status.py`, `tests/test_machine_cli.py`): **309 passed in 56.87s**.
- Full offline gate (`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider`): **1329 passed, 10 skipped in 102.29s**.
- `git diff --check e467633..ce25c8d`: clean.
- Independent task review of `e467633..ce25c8d`: no Critical, Important, or Minor findings. Review confirmed native/generic precedence, typed unit projection, Relax sidecar propagation, legacy/event non-leakage, and real process/API parity.

No SPEC, schema, status, scientific, workflow, scheduling, or execution contract changed. The capability remains experimental pending the existing maturity gates.
