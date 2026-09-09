# Forge ATST-NEB Adapter Implementation Plan

> For agentic workers: use the subagent-driven-development or executing-plans workflow for each task, with a failing test before implementation and a focused verification command after each change.

Goal: Add an experimental, optional ATST-NEB capability to abacus-forge. The capability must expose typed prepare/execute/postprocess operations through the same machine CLI envelope used by SCF, while leaving task orchestration, site scheduling, and scientific assessment to the human or Agent caller.

Spec basis: docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html, docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html, and docs/superpowers/plans/2026-09-09-forge-default-pbe-and-atst-neb-boundary.md. The user authorized implementation of this optional ATST-based prepare/execute/post path; this plan freezes only the smallest adapter contract needed for that slice.

Architecture: typed request records and a capability descriptor are added to the existing contract/discovery layer. The adapter calls an external atst executable in a contained Forge workspace and records factual process/artifact information. It does not import atst_tools, mirror the full ATST YAML schema, submit to Slurm, launch site-specific resources, orchestrate image tasks outside the ATST command, or judge scientific correctness.

Tech stack: Python dataclasses, subprocess, existing workspace/result/error helpers, JSON-safe envelopes, and pytest. atst-tools remains an optional external installation; it is not a required dependency or a version-pinned extra in this slice.

## Global constraints

1. Preserve the existing SCF operations, legacy CLI, frozen seven error classes, result envelope versions, and _OPERATIONS set. Typed postprocess remains a machine operation but is only valid for the atst-neb capability in this slice.
2. Keep the request surface portable: workspace-relative paths, explicit operation/capability, no launcher, scheduler, shell, arbitrary environment, retry, or restart injection fields.
3. Keep ATST YAML opaque. Forge validates path containment and process preconditions, but ATST remains the authority for YAML syntax and workflow semantics.
4. Use one JSON document on stdout, diagnostics on stderr, no prompt/TTY branch, and the existing exit mapping: request errors 2, missing preconditions 3, process failure/timeout 4, internal failure 5.
5. Capability maturity is experimental; discovery must describe only behavior implemented and tested in this slice. Existing SCF discovery retains the roles input, provenance_manifest, and output; the ATST-NEB adapter currently emits only input and output artifacts.
6. All operations use the existing workspace admission/operation guard and persist the returned factual outcome. Scientific status remains unassessed.
7. Do not add a top-level legacy post command, Slurm integration, a required ATST Python import, or a scientific validation gate.

## Rulings frozen by this plan

- The capability name is atst-neb; its engine is atst-tools; its optional dependency is advertised in discovery only.
- Requests use explicit capability plus operation. SCF requests remain unchanged and continue to route without a capability field.
- Prepare creates an NEB chain with atst neb make; execute runs an opaque YAML with atst run; postprocess first obtains JSON summary data with atst neb summary and then invokes atst neb post for requested derived artifacts.
- The adapter owns only the local command invocation and factual result capture. ATST owns NEB image/chain semantics; the caller owns outer orchestration, scheduling, and scientific interpretation.
- `atst-neb.prepare` binds specifically to `atst neb make` (endpoint-to-chain generation); it is not the top-level `atst prepare` reverse-config operation that generates a workflow YAML from an ABACUS run directory. This slice exposes only the structured, non-interactive, path-controlled CLI subset needed by the adapter; omitted ATST flags are not passed through as arbitrary argv.
- The ATST backend and model choice (including DeePMD or other calculator implementations) remain owned by atst-tools and the caller's opaque workflow configuration; Forge does not select, install, configure, or scientifically assess those backends.
- The optional dependency/version and clean-environment real-smoke test are release evidence, not a required-dependency change in this implementation slice.

## Task 1: Add typed ATST-NEB request contracts and discovery

Files: src/abacus_forge/contracts.py, src/abacus_forge/discovery.py, src/abacus_forge/__init__.py, tests/test_contracts.py, tests/test_machine_cli.py, tests/test_architecture.py.

1. Write failing tests for strict round-trip decoding and rejection of unknown fields, wrong capability, non-contained paths, invalid image counts/methods, execute check-input invariants, and postprocess output options.
2. Add _AtstNebRequest and three dataclass requests:
   - AtstNebPrepareRequest: init/final structure relative paths, `n_images` >= 1 (Forge default `5`, following ATST 2.2.4's top-level prepare/reverse-config convention; `neb make` receives it explicitly), chain output path default, method IDPP or linear, and no_align.
   - AtstNebExecuteRequest: opaque config relative path, dry-run/check-input controls (with positive `check_input_timeout` default `120`, matching ATST 2.2.4), optional ABACUS executable, and optional positive outer Forge subprocess timeout; enforce check_input implies dry_run.
   - AtstNebPostprocessRequest: trajectory and summary/output paths, non-negative n_max, and explicit typed flags for plotting, energy profile, vibration analysis/threshold (`vib_thr` default `0.10`, matching ATST 2.2.4), strict band, latest-chain and init-chain output.
   Every request serializes capability: atst-neb, its operation, schema version, workspace identity, and only portable fields. Required fields use the existing sentinel pattern so inherited dataclasses stay strict.
3. Extend discovery with an experimental atst-neb descriptor and per-operation static schemas. Derive request properties from dataclass fields and assert schema/wire parity; include the capability constant without introducing a JSON Schema runtime dependency.
4. Export the new public request types. Keep _OPERATIONS and all SCF serialization unchanged.
5. Run focused contract/discovery/architecture tests and commit as feat: add typed atst neb contracts.

## Task 2: Implement the isolated external-CLI adapter

Files: src/abacus_forge/atst_neb.py, src/abacus_forge/__init__.py, tests/test_atst_neb.py.

1. Add failing service tests using a temporary fake atst executable. Cover successful prepare, dry-run execute, summary-plus-postprocess, missing input/executable, non-zero process exit, timeout, operation admission, artifact references, and unassessed scientific status.
2. Implement AtstNebPrepareService, AtstNebExecuteService, AtstNebPostprocessService, and AtstNebServiceSet.default(...) without importing atst_tools.
3. Resolve all request paths under the admitted workspace; reject missing inputs as precondition.missing. Resolve an absolute executable or shutil.which; missing executable is the same precondition class.
4. Store stdout/stderr logs below reports/atst/ and construct artifact references once. Preserve the existing operation guard and claimed-operation event behavior.
5. Invoke:
   - prepare: atst neb make INIT FINAL N_IMAGES --method METHOD -o CHAIN, adding --no-align when requested;
   - execute: atst run CONFIG, adding only the typed dry-run/check-input/timeout/executable flags;
   - postprocess: atst neb summary TRAJ --n-max N --format json --output SUMMARY, then atst neb post TRAJ with typed postprocess flags.
   Process non-zero exits and timeouts return failed OperationOutcome values (exit class 4); command/precondition errors return frozen Forge errors. Never synthesize scientific conclusions.
6. Run focused adapter tests and commit as feat: add external atst neb services.

## Task 3: Bind the capability to the machine CLI

Files: src/abacus_forge/machine_cli.py, tests/test_machine_cli.py, tests/test_cli_process.py, README.md.

1. Write failing tests for request-file and stdin execution of ATST prepare/execute/postprocess, capability discovery/schema, unknown capability/operation mapping to request.invalid with exit 2, missing executable exit 3, fake process failure exit 4, and direct-service versus CLI envelope parity.
2. Add ATST decoders and capability-aware routing. SCF requests keep their existing route; an atst-neb capability selects the ATST service set; postprocess without that capability remains invalid.
3. Keep the CLI runner as decode then same service then render. Do not expose a top-level legacy post parser or alter legacy default output. Permit injected ATST services in tests without widening the public legacy facade unnecessarily.
4. Document the experimental machine request entry point and the external atst executable requirement. State that ATST, outer scheduling, and scientific assessment remain caller responsibilities.
5. Run focused machine/process tests and commit as feat: expose atst neb on machine cli.

## Task 4: Final boundary and release-evidence update

Files: ROADMAP.md, relevant SPEC/plan wording only if implementation evidence requires it, and tests as needed.

1. Add the adapter to the roadmap as experimental and record the future release gate: optional ATST installation/version pin, clean-environment import/process verification, and real-smoke evidence.
2. Run architecture/boundary scans proving no atst_tools import, Slurm/DPDispatcher integration, scheduler launch, or scientific validation code entered Forge.
3. Run the full suite in the supported environment, git diff --check, and the repository verification-before-completion checks. Record exact outputs in this plan.
4. Perform an independent review of the final diff for SPEC alignment, strict request/schema parity, envelope/exit parity, and accidental legacy surface changes. Commit as docs: record atst neb adapter boundaries.

## Verification and self-review checklist

- [x] Every new request round-trips and rejects unknown keys.
- [x] Discovery advertises only the implemented experimental ATST operations and truthful artifact roles.
- [x] Direct service and machine CLI produce equivalent envelopes for the same isolated fixture.
- [x] Missing preconditions, process failures, and malformed requests map to the frozen classes/exits.
- [x] No required dependency or import of atst_tools was added.
- [x] No Slurm/site scheduler or scientific judgment entered the Forge boundary.
- [x] Full tests, boundary scan, and diff hygiene are green before claiming completion.

## Task 4 execution evidence

- Roadmap now records `atst-neb` as an implemented but experimental optional adapter. Stable release remains gated on an explicit atst-tools installation/version/API decision, clean-environment import/process verification, and a real NEB smoke run.
- Boundary scan command: `rg -n "from atst_tools|import atst_tools|slurm|DPDispatcher|Bohrium|srun|sbatch|mpirun|scientific.*(valid|accept)|validation.*scientific" src/abacus_forge pyproject.toml`.
  Result: no ATST Python import, scheduler integration, or scientific validation implementation was found; the existing `mpirun` match is the pre-existing SCF runner command construction and is not an ATST/site scheduler integration.
- Full supported-environment test command: `conda run -n paimon python -m pytest -q`.
  Result after default-alignment changes: `396 passed, 2 skipped in 42.26s`.
- Focused adapter/machine/architecture command: `conda run -n paimon python -m pytest -q tests/test_atst_neb.py tests/test_contracts.py tests/test_machine_cli.py tests/test_cli_process.py tests/test_architecture.py`.
  Result after default-alignment changes: `174 passed in 32.17s`.
- Hygiene command: `git diff --check`.
  Result: passed (no output).
- ATST source/version verification: `/home/james/work/deepmodeling/atst-tools` is on `main` at `9318177`, exactly matches `origin/main`, and declares version `2.2.4`; the published PyPI version is also `2.2.4`. The `atst-dev` environment resolves the source tree and reports `atst 2.2.4`.
- Real ATST CLI contract smoke: using that `atst-dev` executable, Forge `prepare` (`atst neb make`), `execute` dry-run (`atst run`), and `postprocess` (`atst neb summary/post`) succeeded against local fixtures, with structured Forge outcomes and artifacts. A full ABACUS/NEB calculation was not run; real workflow execution, version/API locking, and clean-environment evidence remain release gates and are not represented by this CLI smoke.

## Task 4 checklist

- [x] Roadmap records the experimental adapter and future release gates.
- [x] Boundary scan completed; no new platform scheduling or scientific judgment entered Forge.
- [x] Full supported-environment test output recorded after the final implementation revision.
- [x] `git diff --check` recorded after the final implementation revision.
- [x] Independent final diff review completed.

## Final independent review evidence

- Independent review scope: complete implementation change `ed53bdc..8030523`, with a focused re-review of `c9a25df..8030523` and the then-current PLAN wording.
- Independent result: PASS. The review confirmed the resolved-path protections for logs, derived outputs, Forge audit paths, input collisions, and output aliases; SCF descriptor compatibility, ATST 2.2.4 default alignment, discovery/README/marker alignment, and the external-backend boundary were preserved.
- Post-review closure: `999f035..a707e96` contains documentation-only follow-ups clarifying backend/model ownership and correcting the SPEC/README/PLAN evidence wording. The independent review remains scoped to the ATST implementation change; the later cross-stage integration added the Relax capability and a small machine-CLI dispatch adjustment, so the combined-branch evidence is recorded separately below.
- Release boundary retained: real atst-tools smoke and explicit version/API locking remain future release gates, not claims made by this fake-executable test slice.

## Cross-stage integration revalidation (2026-09-09)

- The isolated branch `forge-integrated-stage4-atst` combines the completed `forge-stage4-relax` batch with the ATST-NEB adapter while retaining `atst_neb.py`, its contracts, tests, and optional executable boundary. Discovery order is now `scf`, `relax`, `cell-relax`, `atst-neb`; the first three expose `prepare/modify/execute/collect`, and ATST exposes `prepare/execute/postprocess`.
- During reconciliation, the machine CLI was corrected to reject `postprocess`/`export` only when the selected capability has no decoder. This preserves the frozen invalid request behavior for capability-less `postprocess` and `export`, while allowing the explicitly supported `atst-neb postprocess` operation.
- Combined focused gate after reconciliation: `conda run -n paimon python -m pytest -q tests/test_architecture.py tests/test_contracts.py tests/test_workspace.py tests/test_service_status.py tests/test_machine_cli.py tests/test_cli_process.py tests/test_atst_neb.py` → `462 passed in 44.64s`.
- Combined full offline gate: `conda run -n paimon python -m pytest -q` → `593 passed, 3 skipped in 56.70s`.
- Discovery/process smoke: `capabilities` returns the four descriptors above; `schema atst-neb postprocess` and `schema cell-relax prepare` return JSON documents with capability-specific fields and constants. `git diff --check` and Python compilation pass.
- Clean package/import gate: `python -m pip wheel --no-deps .` built `abacus_forge-0.1.0-py3-none-any.whl`; installing that wheel with its declared dependencies into a fresh Python 3.13 venv succeeded. In that venv, `import abacus_forge`, the four-capability discovery document, `schema atst-neb postprocess`, and the `abacus-forge capabilities` console entry point all succeeded; `abacus_agent_tools`, `abacustest`, `aiida`, and `atst_tools` were absent, so this check does not rely on the legacy Paimon environment.
- Reference recheck: `/home/james/work/deepmodeling/atst-tools` `main` is at `9318177`, exactly equal to `origin/main`, and declares `2.2.4`. Its maintained CLI/API references confirm `atst neb make`, `atst run`, `atst neb summary/post`, opaque YAML configuration, caller-owned calculator/backend configuration (including DeePMD), and caller-owned scheduler/launcher boundaries. Forge therefore keeps the adapter optional, external-CLI based, and factual; no DeePMD, Slurm, or scientific acceptance logic is added.
- The clean package/import gate is now green, but the real ABACUS/NEB calculation gate remains unavailable in this environment: no `abacus` executable is present in the host, `paimon`, `atst-dev`, or `atst` environments, and the opt-in Forge real-smoke module reports `2 skipped` without a supplied workspace/executable. The current evidence is therefore deterministic fake-executable coverage, local ATST CLI contract smoke, and package/import verification; the capability stays `experimental` until the independent version/API and real-workflow gates are satisfied.
