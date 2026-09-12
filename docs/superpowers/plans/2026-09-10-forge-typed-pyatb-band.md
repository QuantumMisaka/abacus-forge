# Forge typed PyATB band handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose one explicit, experimental typed PyATB band capability that materializes declared ABACUS matrix artifacts, runs one local PyATB process, and collects factual band outputs without inheriting legacy workflow or scientific policy.

**Spec:** `docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html` (R1/R4/R5/R6/R7/R8, lines 209–258, 283–291, 326–359, 411–417); `docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html` (R1/R7/R8 and the experimental PyATB boundary).

**Decision source:** User authorized continued Forge implementation and reference alignment on 2026-09-10. The read-only audit is retained at `.superpowers/sdd/2026-09-10-forge-typed-pyatb-band/pyatb-surface-audit.md`; it checked Forge legacy `pyatb.py`, local PyATB revision `80f7c2d`, `abacus-agent-tools`, `abacuslab`, and the approved SPECs. No new product decision is pending within this deliberately narrow slice.

**Architecture:** Add a dedicated `pyatb_contracts.py` request module, explicit handoff helpers in the PyATB engine adapter, and a `PyatbBandServiceSet` using the existing `ServiceContext`/`LocalRunner`/workspace admission path. Typed preparation consumes only workspace-relative source paths, stages them under the destination workspace, writes the PyATB `Input` and line-mode KPT, and records source/destination/hash provenance. Typed collection consumes declared standard output paths and emits artifacts plus parser/runtime facts. Existing `prepare_pyatb_band`, `run_pyatb`, `collect_pyatb`, and `run_band_sequence` remain compatibility-only code paths.

**Tech Stack:** Existing Python dataclasses, pathlib, hashlib, shutil/os, ASE-backed `AbacusStructure`, `input_io`, `LocalRunner`, `Workspace`, and pytest. PyATB remains an optional executable; no Python import or sibling-repository runtime dependency is added.

## Global Constraints

- Keep `forge.request/v1`, `forge.result/v1`, `forge.operation-outcome/v1`, error classes and exit mapping unchanged; all typed operations use the existing UUIDv4 admission/event/artifact-ref path.
- Capability name is exactly `pyatb-band`; maturity is `experimental`; advertised operations are exactly `prepare`, `execute`, and `collect`.
- Typed preparation accepts only explicit workspace-relative paths; resolved sources and all generated/staged artifacts must remain under the destination workspace. Cross-workspace or absolute sources are rejected; an upper layer must materialize/link them before calling Forge.
- The typed handoff supports `nspin` 1, 2 and 4. Spin-2 HR requires two explicit HR paths; nspin-1/4 require one. SR remains one shared explicit path, matching PyATB's current ABACUS reader; rR is optional and is staged/rendered only when supplied. Other PyATB functions require later evidence and plans.
- Handoff mode defaults to `link` and creates relative symlinks only for sources inside the same workspace; `copy` is explicit and uses `copy2`. Existing conflicting destinations are rejected without unlinking or overwriting.
- Typed preparation performs no SCF directory scan and never derives Fermi energy from logs. It does not run ABACUS, PyATB, a workflow sequence, a scheduler, or a scientific acceptance check.
- Typed execute runs exactly one local process through `LocalRunner`; launcher policy, retries, monitoring, resume/restart, Slurm/site scheduling and upper-layer task IDs remain outside Forge.
- Typed collect reads only the requested/default standard PyATB band paths, keeps `band_gap` as a reported parser fact if present, and never emits an accepted/rejected scientific conclusion. Legacy helpers retain their current behavior and signatures.
- Default tests remain offline and deterministic. Real PyATB/ABACUS smoke is a later release gate, not evidence claimed by this batch.

## Task 1: Typed PyATB request contracts and discovery

**Files:**
- Create: `src/abacus_forge/pyatb_contracts.py`
- Modify: `src/abacus_forge/discovery.py`
- Modify: `src/abacus_forge/machine_cli.py`
- Modify: `src/abacus_forge/__init__.py`
- Modify: `tests/test_contracts.py`, `tests/test_machine_cli.py`, `tests/test_cli_process.py`

**Interfaces:**
- `PyatbBandPrepareRequest(operation_id, workspace_rel, structure_path_rel, hr_paths_rel, sr_path_rel, rr_path_rel=None, fermi_energy, line_kpoints, nspin=1, line_segments=20, max_kpoint_num=4000, handoff_mode="link")`; the serialized field is nullable for stable round-trips and may be omitted by callers.
- `PyatbBandExecuteRequest(operation_id, workspace_rel, executable="pyatb", mpi_ranks=1, omp_threads=1, timeout_seconds=None, dry_run=False)`.
- `PyatbBandCollectRequest(operation_id, workspace_rel, band_info_path_rel="inputs/Out/Band_Structure/band_info.dat", band_data_paths_rel=(), band_picture_paths_rel=())`.
- Every request serializes/deserializes under unchanged `forge.request/v1`, carries `capability="pyatb-band"` and the explicit operation, rejects unknown fields, freezes JSON-safe values, and validates canonical workspace-relative paths before any filesystem access.
- `line_kpoints` is a non-empty JSON list of objects with exactly `coords` (three finite numbers) and optional non-empty `label`; at least two points are required for a band path. `hr_paths_rel` length is exactly `nspin`; all output path lists contain canonical relative files.
- Discovery advertises the descriptor and schemas with dataclass/wire/static-property equality checks. Unknown capability/operation returns existing `request.invalid`/exit 2. Schema documents mark only identity plus prepare handoff fields as required; collect optional lists remain optional.

**Test strategy:** Extend the owning contract/machine suites. Cover round-trip/defaults, immutability, nspin/path cardinality, finite numbers and line-point validation, unknown fields/selectors, discovery descriptor/schema exactness, and CLI decoder selection. Do not add a generic PyATB function selector or modify legacy CLI parsing.

- [x] Write RED tests for request round-trips, invalid payloads, schema/discovery and decoder routing.
- [x] Implement the three request classes and registry wiring.
- [x] Run `env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_contracts.py tests/test_machine_cli.py tests/test_cli_process.py`; `396 passed`.
- [x] Commit and report exact output/revision; independent review CLEAN/APPROVED at `d49c515`.

## Task 2: Explicit PyATB handoff and collection algorithms

**Files:**
- Modify: `src/abacus_forge/pyatb.py` only for new explicit helpers; do not change legacy helper bodies or signatures.
- Create: `tests/test_pyatb_typed.py`

**Interfaces:**
- `prepare_typed_pyatb_band(workspace, request) -> tuple[Workspace, tuple[dict[str, JSONValue], ...]]` (the implementation may use a clearer equivalent name, but must return the prepared workspace and serializable handoff records).
- `collect_typed_pyatb_band(workspace, request) -> ForgeResultEnvelope` or an equivalent pure result record consumed by Task 3.
- Handoff records contain role (`structure`/`hr`/`sr` and, when supplied, `rR`), source path relative to workspace, destination path relative to workspace, mode, source SHA-256 and destination SHA-256.

**Behavior:**
- Resolve and validate every declared source beneath the workspace root before writing. Stage the structure as `inputs/STRU`; stage matrix files under `inputs/pyatb_sources/<basename>` with deterministic relative routes in the generated PyATB `Input`. Reject missing/non-file sources, external/symlink-resolved escapes, duplicate destination basenames and conflicting existing destinations before any write.
- Parse the declared STRU with `AbacusStructure`, preserve its lattice vectors, render PyATB `INPUT_PARAMETERS` (`package=ABACUS`, explicit `nspin`, Fermi in eV, HR/SR routes, and a conditional rR route when supplied; `HR_unit=Ry` and conditional `rR_unit=Bohr`) and `BAND_STRUCTURE` from the normalized line points, and write `inputs/Input` plus `inputs/KPT_band`. The algorithm must not read a sibling SCF `INPUT`, output log or Fermi metric.
- Link mode creates relative links only; copy mode creates independent files with `copy2`. A destination that already is the exact requested source may be retained, but any other existing file/link is a hard conflict. No legacy absolute symlink behavior is changed.
- Collection uses the explicit/default `band_info_path_rel` plus optional data/picture paths. It records only contained existing files as output artifacts, parses the existing `Band gap ...` value as a reported `band_gap` metric when parseable, and returns missing/partial/complete collection facts and diagnostics for absent or malformed requested outputs. It does not calculate or classify a band gap.

**Test strategy:** New owning suite uses temporary workspaces and hand-authored STRU/matrix files. Cover copy/link provenance, source containment, collision/no-partial-write, spin-1/spin-2 routes, generated Input/KPT contents, malformed STRU, explicit output artifacts, parser facts, missing/partial collection and no scientific acceptance. Include a regression that legacy `tests/test_pyatb.py` remains unchanged and passing.

- [x] Write RED algorithm tests for handoff, route rendering, spin handling, collection facts and safety.
- [x] Implement only the explicit helpers; retain legacy path discovery and absolute-link compatibility.
- [x] Run `env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_pyatb_typed.py tests/test_pyatb.py`; `35 passed` after the R1 boundary fixes.
- [x] Commit and report exact output/revision; implementation `940706a`, fix `ec97e35`, report `a487557`; scoped re-review CLEAN/APPROVED.

## Task 3: Typed service set and machine/API parity

**Files:**
- Create: `src/abacus_forge/pyatb_services.py`
- Modify: `src/abacus_forge/machine_cli.py`, `src/abacus_forge/__init__.py`
- Modify: `tests/test_pyatb_typed.py`, `tests/test_machine_cli.py`, `tests/test_cli_process.py`

**Interfaces:**
- `PyatbBandServiceSet.default(workspace_root=".", runner_factory=LocalRunner)` exposes per-operation `.prepare`, `.execute`, and `.collect` protocols and shares one `ServiceContext`/runner factory.
- Prepare returns an `OperationOutcome` with `execution=not_run`, `collection=not_collected`, input/provenance artifacts, and JSON-safe `pyatb_handoff` diagnostics; execute returns the existing runner envelope with `execution=completed|failed|skipped`; collect returns `execution=not_run` and `collection=complete|partial|missing_output`.
- The machine CLI routes all three request types to the same service objects used by the Python API; capability discovery, stdin/request-file decoding, JSON/text rendering and exit classes remain shared infrastructure.

**Behavior:**
- Prepare admits one operation, validates source preconditions after admission, writes `forge-unit.json` with `task=band`, `unit=pyatb`, `engine=pyatb`, persists one outcome/event, and injects artifact refs only through `ServiceContext.persist`. Missing sources map to `precondition.missing`/exit 3; request/path/conflict errors retain existing mappings.
- Execute requires the prepared `inputs/Input` (and generated handoff inputs), honours request-level dry-run without inspecting stale logs, invokes one `LocalRunner` with request fields only, records stdout/stderr and returncode/termination facts, and never forwards an ABACUS return code as a Forge process exit class.
- Collect admits independently, applies the explicit/default paths, persists one outcome/event and never mutates the execute event or infers a previous task. API and CLI envelopes, status values, artifact paths and artifact refs must be equivalent for isolated workspaces.
- Legacy `prepare_pyatb_band`, `run_pyatb`, `collect_pyatb`, `run_band_sequence`, legacy CLI flags and existing `tests/test_pyatb.py` behavior stay unchanged.

**Test strategy:** Add direct service and subprocess parity tests with a fake PyATB executable that writes `Out/Band_Structure/band_info.dat`, `band.dat`, and a picture. Cover missing executable, nonzero exit, timeout, dry-run, missing output, duplicate operation admission, artifact containment, one-event persistence and API/CLI parity. Use unique operation IDs and separate workspaces per invocation.

- [x] Write RED service/machine/API parity tests.
- [x] Implement the service set and registry/dispatch wiring.
- [x] Run `env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_pyatb_typed.py tests/test_machine_cli.py tests/test_cli_process.py tests/test_contracts.py tests/test_workspace.py`; `469 passed`.
- [x] Commit and report exact output/revision; implementation `3ef68db`, report `f06e2c3`; independent review CLEAN/APPROVED.

## Task 4: Documentation, final verification and branch review

**Files:**
- Modify: `README.md`, `ROADMAP.md`, `tests/test_architecture.py`, this plan and `.superpowers/sdd/2026-09-10-forge-typed-pyatb-band/progress.md`
- Create: `.superpowers/sdd/2026-09-10-forge-typed-pyatb-band/task-4-report.md`
- No compatibility code changes in this task.

**Behavior:** README documents the typed `pyatb-band` request examples, explicit workspace-local handoff, default relative link/copy option, generated files, execution/collection facts, reported-vs-scientific boundary and legacy helper separation. This plan records only the experimental band handoff; PyATB properties and stable/real-smoke promotion remain separate follow-up work. The optional rR handoff is documented without making it a required Bands input.

**Verification:** Run the full offline gate with the repository's fixed interpreter and flags, `git diff --check`, discovery assertions and forbidden-import scan. Bind every result to the final code revision. Obtain task reviews and one whole-branch review; fix all Critical/Important findings before marking this plan complete. No merge or push is part of this plan.

- [x] Update docs concisely after code behavior is fixed; do not claim real PyATB evidence.
- [x] Run the full offline suite and diff/discovery/import gates; retain raw output in the ledger.
- [x] Obtain final review, close findings, and record exact commits/evidence.

Task-local verification note: the architecture gate's capability-list assertion
was updated to include the already implemented `pyatb-band` descriptor and its
exact maturity/engine/operation/artifact-role contract. This is a test-accounting
fix only; no production behavior or compatibility surface changed.

## Plan self-review and rulings

- Checked against the two approved SPECs, the local PyATB `80f7c2d` input/output contract, Forge legacy tests, Paimon/abacus-agent-tools band behavior and abacuslab matrix handoff templates. The plan adds no runtime dependency and keeps legacy helpers intact.
- `Ruling: use a named `pyatb-band` capability with prepare/execute/collect — the existing `band` capability is already the ABACUS parser surface and a generic PyATB function selector would freeze unsupported property contracts; if wrong, only the new registry/request names need migration.`
- `Ruling: require explicit Fermi and workspace-relative matrix paths — PyATB consumes HR/SR and, for modules that need it, an optional rR from one SCF handoff, while automatic SCF discovery/metric lookup is exactly the legacy workflow boundary; if wrong, callers can still materialize the same files and a later adapter can add a separate explicit source-reference contract.`
- `Ruling: default relative link, copy as opt-in — matrix files can be large and same-workspace links preserve zero-copy handoff, while relative links satisfy workspace portability; if wrong, a future default change is confined to the new request default and docs.`
- `Ruling: collect standard band outputs without scientific acceptance — `band_gap` may be emitted as a reported parser fact, but Forge does not classify it; this keeps the SPEC's facts-only status model and avoids importing abacus-agent-tools policy.`

## Follow-up correction (2026-09-11)

The local PyATB input contract confirms that `BAND_STRUCTURE` consumes HR/SR and does not require an rR route. The typed request therefore keeps `rr_path_rel` nullable/optional: supplied rR files remain strict workspace-relative handoffs with manifest provenance, while omitted rR produces no route or `matrix_rr` entry. This correction narrows an unnecessary input requirement and does not expand the capability into PyATB properties, orchestration, scheduling or scientific validation.

## Follow-up architecture hardening (2026-09-10)

The typed PyATB helpers were extracted into
`src/abacus_forge/pyatb_typed.py` so `PyatbBandServiceSet` no longer reaches
the legacy `abacus_forge.api` facade through `pyatb.py`.  The historical
`abacus_forge.pyatb.prepare_typed_pyatb_band` and
`collect_typed_pyatb_band` names remain compatibility wrappers, including the
existing private hash-helper test seam; legacy PyATB discovery and sequence
helpers were not changed.  The architecture gate now traverses both
`pyatb_services` and `pyatb_typed` and rejects a direct or transitive legacy
API dependency.

The hardening was delivered as `4778adb` with stale compatibility residue
removed in `2d62f59`; wrapper return annotations and the corresponding
standalone-module comments were restored in `485ec2b`.  The focused
PyATB/architecture/machine/service gate passed `325` tests, and the current
full offline gate passed `1179 passed, 4 skipped`.  These are compatibility
and boundary results only; PyATB and ABACUS real-smoke evidence remains a
separate release gate.
