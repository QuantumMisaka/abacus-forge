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

- [x] All typed ABACUS capabilities reject conflicting calculation profiles at the request/service boundary.
- [x] Typed modify cannot delete or rewrite `calculation`; same-profile no-op remains accepted.
- [x] Typed execute/collect reject mismatched existing `INPUT`, while output-only collect remains available.
- [x] Discovery schemas and runtime behavior agree for SCF, Relax, cell-relax, and MD.
- [x] Legacy facade/API/CLI behavior remains covered and unchanged.
- [x] No scientific status, task orchestration, platform scheduling, or dependency boundary changes.
- [x] Focused and full offline evidence plus independent review are recorded below.

## Verification record

- Task 1 implementation: `3d5d6f2`, `97e591f`, `e49de5a`, `9012e8e`, `2210a66`, `371e4ef`; typed SCF guards are
  strict on the public `ScfServiceSet`, while the private compatibility path used by `ForgeServices`
  remains permissive. The final hardening checks the actual flat `INPUT` serialization, including
  whitespace/comment keys, line-break injection, and duplicate existing `calculation` directives.
- Focused/owning controller gate after final hardening: `603 passed` across
  `tests/test_typed_calculation_guards.py`, contract, service, machine CLI, process CLI, and MD service
  suites. The implementation agent independently reported `517 passed` for its final owning command.
- Independent Task 1 review: passed after two repair rounds; no Critical or Important findings remain.
  The earlier non-blocking no-admission/same-profile test suggestion was closed by `90f3c8d`.
- `tests/conftest.py` registers the guard suite as `integration`; process CLI regression verifies mismatch →
  one JSON `request.schema` envelope, empty stderr, and exit `2`.
- Discovery smoke: the complete registry exposed 9 capabilities and 26 request schemas; the four typed
  ABACUS calculation profiles covered by this plan account for 17 of those schemas. The guard suite is
  selected by `-m integration` with 9 collected tests.
- Architecture gate: `8 passed`. Full default offline gate: `1327 passed, 10 skipped` (the skips are the
  repository's opt-in real-smoke/benchmark cases). Opt-in core capability benchmark: `6 passed`.
- Documentation gate: 7 Forge SPEC HTML files parsed successfully; changed-doc placeholder scan is clean.
- `git diff --check`: passed for the implementation, test refinement, and documentation range. The final
  whole-plan review passed with no Critical or Important findings; remaining schema/runtime equivalence
  nuances were recorded as non-blocking Minor follow-up. All capability descriptors remain `experimental`;
  no claim of scientific validation or stable release is made.
