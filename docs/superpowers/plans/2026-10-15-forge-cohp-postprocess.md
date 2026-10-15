# Forge COHP postprocess implementation plan

Spec: [2026-10-15-forge-cohp-postprocess-design.md](../specs/2026-10-15-forge-cohp-postprocess-design.md)

## Task 1: Add typed cohp postprocess contract

- Add `CohpPostprocessRequest` to `postprocess_contracts.py`.
- Register `{"postprocess": CohpPostprocessRequest}` under capability `cohp`
  in `request_registry.py`.
- Validate canonical directory paths, positive 1-based atom indices, the
  `iao` method, and the default `all` orbital selectors.
- Contract tests cover strict round trip, immutability, unknown fields,
  invalid paths/indices/method, discovery schema, and registry isolation.

## Task 2: Migrate the IAO kernel behind Forge modules

- Move the Paimon v1.2 pure-Python IAO implementation into Forge as
  `cohp_iao.py`, `cohp_iao_reader.py`, and `cohp_iao_shells.py`.
- Preserve algorithms, constants, guards, warning codes, output formats, and
  public numeric behavior; only change package imports.
- Copy the small real Si fixture used by the Paimon kernel tests.
- Add focused kernel tests for shell rules, reader identities, explicit
  projector reference, Fermi-shift invariance, selector validation, missing
  overlap-R, gamma-only rejection, and artifact writing.

## Task 3: Add service, discovery and machine adapter

- Add `CohpPostprocessService` and include it in `PostprocessServiceSet`.
- Reuse operation guard, workspace path admission, changed-output admission,
  artifact records, outcome persistence, and error classification.
- Advertise `cohp` as experimental with operation `postprocess`; schema
  discovery must round-trip the typed request.
- Extend machine CLI routing so direct service and `operation postprocess`
  runs produce equivalent envelopes.

## Task 4: Own regression and evidence

- Run owning suites plus default offline regression in `abacus-env`.
- Record branch, commit, candidate identity, commands, and boundaries in
  `docs/superpowers/evidence/2026-10-15-forge-cohp-postprocess.md`.
- Explicitly state that legacy bridge, Paimon migration, parity, clean-install,
  benchmark, and release are not accepted by this slice.
