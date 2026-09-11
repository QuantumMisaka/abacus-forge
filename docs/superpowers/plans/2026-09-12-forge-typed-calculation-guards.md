# Forge Typed Calculation Guards Implementation Plan

**Goal:** Make every typed ABACUS capability keep its declared `calculation` profile consistent across prepare, modify, execute, and collect, without changing legacy API/CLI behavior.
**Spec:** [`2026-09-01-forge-contract-first-rearchitecture-design.html`](../specs/2026-09-01-forge-contract-first-rearchitecture-design.html) and [`2026-09-02-forge-service-status-migration-design.html`](../specs/2026-09-02-forge-service-status-migration-design.html), especially the responsibility boundary, request/error mapping, and Stage 4 capability rules.
**Authorization:** User-confirmed continuation of the approved Forge implementation plan; the current architecture audit identified a concrete typed capability/profile mismatch.
**Architecture:** Reuse the existing service context and typed discovery registry. Validate explicit request overrides before admission, validate the existing `INPUT` before any typed modify/execute/collect domain action, and keep `ForgeServices` as an opt-out compatibility shim. No new operation, status, scientific policy, scheduler, workflow, or runtime dependency is introduced.
**Verification:** TDD regressions for request/schema, service/API, and machine-CLI paths; owning contract/service/CLI/architecture suites; full offline gate and diff hygiene.

## Scope and boundaries

- Expected ABACUS calculation profiles are `scf`, `relax`, `cell-relax`, and `md`.
- Typed prepare accepts an omitted `parameters.calculation` and supplies the existing profile default; an explicitly conflicting value is a class-2 request/schema error before admission or domain writes.
- Typed modify may repeat the current profile value, but may not change it or remove it. The existing workspace calculation is checked before the input mutation.
- Typed execute/collect check an existing `inputs/INPUT` calculation against the typed capability. A collect of an external output-only workspace with no `INPUT` remains allowed; an existing malformed/mismatched `INPUT` is a precondition error.
- The current `ForgeServices` compatibility facade continues to preserve its historical permissiveness. Legacy `prepare`, `modify`, `execute`, `collect`, task packs, and their files/output remain unchanged.
- `scientific` remains `unassessed`; matching `calculation` is an input/process precondition, not scientific validation.

## Work packages

### Task 1: Add typed profile guards and discovery parity

**Files:** `src/abacus_forge/services.py`, `src/abacus_forge/discovery.py`, `src/abacus_forge/contracts.py`, nearest contract/service tests.

Add one shared expected-profile check in the typed service path. Reject conflicting prepare overrides and modify calculation rewrites/removals with the existing `request.schema` error class; perform the check before operation admission. Enable existing `INPUT` matching for the typed `ScfServiceSet`, while retaining the facade's compatibility opt-out. Make discovery schemas describe the same `calculation` const and prohibit removal for SCF as already done for Relax/MD. Do not widen the public request fields or alter legacy adapters.

**Verification:** RED tests for SCF prepare/modify/execute/collect mismatch cases and schema properties; GREEN focused contract/service/machine tests; confirm no event or domain file is written for request/schema rejection and output-only collect remains valid.

### Task 2: Record the corrected boundary and run release gates

**Files:** `README.md`, `ROADMAP.md`, this plan.

Add a concise statement that typed capability requests and existing `INPUT` profiles must agree, while legacy compatibility remains separate. Record exact focused, owning, architecture, and full offline results; explicitly state that the guard does not perform scientific acceptance or orchestration. Keep all capability maturities experimental until the independent stable-release evidence decision.

**Verification:** Markdown/HTML/diff checks, capability/schema discovery smoke, owning test suites, benchmark opt-in, and full default offline suite. A clean review package must show no runtime dependency or legacy behavior expansion.

## Acceptance checklist

- [ ] All typed ABACUS capabilities reject conflicting calculation profiles at the request/service boundary.
- [ ] Typed modify cannot delete or rewrite `calculation`; same-profile no-op remains accepted.
- [ ] Typed execute/collect reject mismatched existing `INPUT`, while output-only collect remains available.
- [ ] Discovery schemas and runtime behavior agree for SCF, Relax, cell-relax, and MD.
- [ ] Legacy facade/API/CLI behavior remains covered and unchanged.
- [ ] No scientific status, task orchestration, platform scheduling, or dependency boundary changes.
- [ ] Focused and full offline evidence plus independent review are recorded below.

## Verification record

Pending implementation.
