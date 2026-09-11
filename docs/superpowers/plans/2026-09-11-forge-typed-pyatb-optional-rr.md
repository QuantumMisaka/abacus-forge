# Forge typed PyATB optional-rR correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Correct the experimental `pyatb-band` handoff so that the documented
PyATB Bands module can run with explicit HR/SR inputs alone, while preserving
strict validation and provenance when an optional rR file is supplied.

**Evidence:** The local PyATB repository at revision `80f7c2d` lists only
geometry/optical/transport modules in `need_rR_matrix`; `BAND_STRUCTURE` reads
HR/SR and does not consume rR. A local HR/SR-only run with the existing
installed PyATB executable completed successfully in a temporary workspace.

**Scope:** This is a narrow contract correction to the existing experimental
`pyatb-band` capability. It does not add PyATB properties, a function
selector, workflow sequencing, scheduling, scientific validation, or a new
schema version. Existing requests that provide `rr_path_rel` retain their
wire form and behavior.

## Global constraints

- Keep `forge.request/v1`, `forge.result/v1`, `forge.pyatb-manifest/v1`, event,
  artifact-ref, error-class, exit-code, legacy helper and legacy CLI behavior
  unchanged.
- `structure_path_rel`, HR paths, SR path, Fermi energy and line K points remain
  required. `rr_path_rel` defaults to `null` and may be omitted on decode;
  explicit non-null values remain workspace-relative, contained and hashed.
- Preparation stages and records rR only when supplied, and omits `rR_route`
  when it is absent. Execute requires HR/SR and validates a declared rR route
  if one exists; it must not require an absent optional route, including in
  dry-run mode.
- The manifest keeps `matrix_rr` for supplied rR handoffs. An absent rR file is
  neither an input entry nor a missing entry.
- All tests remain deterministic and offline except the already observed
  temporary local PyATB evidence; no scientific or maturity promotion claim is
  made from it.

## Task 1: Add RED boundary tests

**Files:** `tests/test_contracts.py`, `tests/test_machine_cli.py`,
`tests/test_cli_process.py`, `tests/test_pyatb_typed.py`.

- Add constructor and JSON-decoder cases for omitted and explicit `null`
  `rr_path_rel` across nspin 1, 2 and 4.
- Freeze discovery expectations: rR is a nullable optional property and is not
  in the prepare schema `required` list; the descriptor lists only required
  handoff inputs.
- Add prepare assertions that HR/SR-only input has no `rR_route` and no
  `matrix_rr` manifest entry, while the existing rR case remains unchanged.
- Add execute/preflight and API/CLI parity cases for HR/SR-only prepared
  workspaces, plus a regression that an explicitly declared missing rR remains
  `precondition.missing`.

Run the focused suites before implementation and retain the expected RED
output in the SDD ledger.

## Task 2: Implement the smallest correction

**Files:** `src/abacus_forge/pyatb_contracts.py`,
`src/abacus_forge/pyatb_typed.py`, `src/abacus_forge/pyatb_services.py`,
`src/abacus_forge/discovery.py`.

- Make `rr_path_rel: str | None = None`, accept absent/null values, and keep
  the field in JSON serialization as a nullable value so dataclass/wire/schema
  drift checks remain exact.
- Remove the rR source triple and `rR_route` line when the request is absent;
  retain the existing staging, route and manifest behavior for a supplied rR.
- Change execute preflight to require only HR/SR, with conditional rR file
  validation when the generated input declares a route.
- Derive the static schema property as nullable and remove rR from required;
  remove it from the descriptor's required input tuple.

Run the focused tests until GREEN and commit the implementation separately
from documentation.

## Task 3: Align approved design records and user docs

**Files:**
`docs/superpowers/specs/2026-09-10-forge-typed-pyatb-nspin4-design.html`,
`docs/superpowers/specs/2026-09-10-forge-typed-pyatb-artifact-manifest-design.html`,
`docs/superpowers/plans/2026-09-10-forge-typed-pyatb-band.md`,
`docs/superpowers/plans/2026-09-10-forge-typed-pyatb-nspin4.md`,
`README.md`, `ROADMAP.md`.

State plainly that Bands requires HR/SR and treats rR as optional; supplied rR
remains facts/provenance only. Correct tables and examples without rewriting
historical verification results. Record this follow-up as a contract
correction and retain the separate PyATB-properties deferral.

## Task 4: Verification and review

- Run focused contract/typed/machine suites, then the full offline gate,
  architecture and forbidden-import checks, `git diff --check`, and clean
  wheel/import checks as applicable.
- Re-run the existing temporary local HR/SR-only PyATB smoke only as factual
  compatibility evidence; do not promote `pyatb-band` maturity or make a
  scientific claim.
- Obtain an independent task/whole-branch review of the exact correction diff;
  resolve all Critical/Important findings before considering the candidate
  ready for formal integration. Do not merge or push in this plan.

## Ruling

The current mandatory rR field is an accidental over-constraint contradicted
by the local PyATB Bands input contract. Making it optional is the smallest
faithful correction: it broadens valid handoffs without adding a capability,
new operation, implicit discovery, or scientific policy.

## Execution evidence (2026-09-11)

- Task 1 test commit: `7abbd4a`; Task 2 implementation commit: `8d41e64`;
  documentation alignment and review fixes: `97de6dc`.
- Focused contract/CLI/typed/legacy/workspace suites: `523 passed in 50.59s`.
- Full offline suite: `1294 passed, 6 skipped in 95.84s`.
- Architecture/discovery/forbidden-import selection: `10 passed, 36 deselected
  in 15.45s`; HTML parse, placeholder scan and `git diff --check` passed.
- A clean Python 3.13 wheel/import/console gate passed with declared
  dependencies and no `abacus_agent_tools`, `abacustest`, `aiida` or
  `atst_tools` installed. The wheel SHA-256 was
  `9582cde343f3b38df329ac1ac037be861022dabccd74ff1aa0f465abb774f702`.
- Candidate typed service was run in a temporary workspace with archived
  ABACUS HR/SR matrix inputs and the locally available serial PyATB executable:
  prepare completed, execute returned `execution=completed`, and collect
  returned `collection=complete` with `band_info.dat`, `band_up.dat`,
  `band_dn.dat` and `band.pdf`. This is input/process compatibility evidence
  only, not scientific validation or maturity promotion.
- Independent documentation and whole-branch reviews found no Critical or
  Important findings. Two Minor wording findings were corrected before this
  closeout. The candidate remains isolated; no merge or push was performed.
