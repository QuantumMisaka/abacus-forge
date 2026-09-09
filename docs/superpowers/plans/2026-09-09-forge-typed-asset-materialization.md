# Forge typed prepare asset materialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit, provenance-carrying PP/ORB asset closure to typed prepare while preserving legacy directory-based prepare behavior.

**Spec:** `docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html` (workspace/artifact boundary, typed prepare asset closure and stable error mapping); `docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html` (core/service/compatibility boundaries).

**Decision source:** User authorized continuation on 2026-09-09 after reference audit of Paimon v1.2, abacustest, abacuslab and abacuscopilot. The settled design is explicit element→source maps, default copy, workspace-relative destination, fail-closed missing/collision handling and source/destination/hash provenance. No new product decision is pending.

**Architecture:** Add optional typed request fields without changing `forge.request/v1` or legacy signatures. A small asset materialization core validates maps, resolves source paths, checks containment and collisions, writes `inputs/` files, and returns serializable provenance. Typed prepare calls this core; legacy `pseudo_path`/`orbital_path` continues using its existing inference and `link` default. Typed outcome diagnostics and the compatibility manifest include provenance only when explicit typed maps are supplied.

**Tech Stack:** Existing Python, dataclasses, pathlib, hashlib, shutil/os, ASE/STRU writer and pytest. No reference repository becomes a runtime dependency.

## Global Constraints

- Preserve operation IDs, admission/events, stable error classes/exit mapping, CLI grammar and existing `forge.result/v1` keys.
- Scientific validation, task/workflow orchestration, platform scheduling and asset selection policy remain outside Forge; `dft_functional=pbe` remains the overrideable input default.
- Typed fields remain optional for backward compatibility; no automatic directory scan or filename-based selection on the typed path.
- Absolute sources are allowed only as explicit inputs; default `copy` produces workspace-contained files, while `link` is restricted to workspace-contained sources and uses relative links.
- Missing explicit sources, unsupported families, unknown species, invalid modes, basename collisions and unsafe destinations fail closed; no silent overwrite.
- Preserve source-relative and destination-relative provenance with SHA-256; do not claim unprovided assets are complete.
- No ABACUS/cluster execution, merge or push in this batch. Deterministic tests are the acceptance scope.

## Reference and scope record

The read-only evidence is in `docs/superpowers/plans/2026-09-09-forge-core-fidelity-references.md` and the asset audit report. Adopt Paimon’s two-stage final-STRU closure, copy/hash provenance and fail-closed missing assets. Adopt abacustest’s explicit map precedence only; do not copy its basename overwrite, absolute-link default, nondeterministic inference or warning-only missing behavior. Existing Forge legacy helpers remain unchanged except for safe code reuse where tests prove behavior parity.

## Task 1: Typed request and discovery contract

**Files:**
- Modify: `src/abacus_forge/contracts.py` (`ScfPrepareRequest` serialization/validation)
- Modify: `src/abacus_forge/discovery.py` (prepare schema properties)
- Modify: `tests/test_contracts.py`, `tests/test_cli_process.py`, `tests/test_service_status.py`

**Interfaces:**
- Produces optional `pseudo_sources: Mapping[str, str]`, `orbital_sources: Mapping[str, str]`, and `asset_mode: Literal["copy", "link"]` on `ScfPrepareRequest`; inherited automatically by `RelaxPrepareRequest`.
- `to_dict()`/`from_dict()` round-trip these fields under unchanged `forge.request/v1`; discovery schema properties must be derived/checked against dataclass fields and use object string values plus `asset_mode` enum/default.

**Behavior:** Map keys and values are non-empty strings; maps are JSON-safe and immutable after construction. `asset_mode` accepts only `copy` or `link` and defaults to `copy`. Existing payloads without the fields round-trip to empty maps/copy. Unknown fields remain rejected. No source filesystem access occurs in constructors.

**Test strategy:** Extend contract round-trip and invalid-field cases; assert static `schema` contains the three fields, `additionalProperties=false`, object value types, and default copy. Add machine CLI decode regression for valid/invalid asset fields and stable request.schema/exit 2.

- [x] Write RED tests for round-trip, defaults, invalid map types/empty entries and schema exposure.
- [x] Implement fields and static schema.
- [x] Run `env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_contracts.py tests/test_cli_process.py`; expect pass.
- [x] Commit and report exact output/revision; independent task review follows.

## Task 2: Safe asset materialization core

**Files:**
- Modify: `src/abacus_forge/assets.py`
- Create: `tests/test_assets.py` (new core owner; no existing suite currently owns source-path/collision/materialization behavior)

**Interfaces:**
- Produces a narrow `materialize_assets(target_inputs, workspace_root, pseudo_sources, orbital_sources, mode) -> tuple[AssetMaterialization, ...]` or equivalent typed records, plus serializable provenance conversion.
- Retains `collect_assets` and `stage_assets` legacy semantics for callers outside the typed path unless an owning regression proves behavior-equivalent reuse.

**Behavior:** Resolve relative source paths against workspace root; permit absolute external sources; require regular files and family suffixes (`.upf`/`.vp` for pseudo, `.orb` for orbital). Destination is `target_inputs / basename`. Validate all mappings before writes. Reject unknown/empty source, unsafe basename, duplicate basename from distinct sources, and existing destination with conflicting content/source; never unlink or overwrite a conflicting destination. `copy` uses `shutil.copy2`; `link` only accepts sources resolved under workspace root and creates a relative symlink. Return family/species/source path/destination relative path/mode/source and destination hashes. Same source may be reused for repeated species references without duplicate writes.

**Test strategy:** Hand-created temporary workspace and external source files test copy bytes, relative in-workspace source, external copy, relative internal link, external-link rejection, missing source, invalid suffix, basename collision, existing conflicting destination, same-source dedup and SHA-256. Tests must assert no partial writes after validation failure.

- [x] Write RED tests for each named boundary.
- [x] Implement validation/materialization/provenance with no directory inference.
- [x] Run `env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_assets.py`; expect pass.
- [x] Commit and report raw output/revision; independent task review follows.

## Task 3: Integrate typed prepare and provenance

**Files:**
- Modify: `src/abacus_forge/preparation.py`, `src/abacus_forge/services.py`, `src/abacus_forge/service_support.py` only if a narrow serializer/helper is needed
- Modify: `tests/test_service_status.py`, `tests/test_api.py`, `tests/test_cli_process.py`

**Interfaces:** Typed service passes request maps/mode into preparation; preparation writes final STRU references from materialized basenames and returns/records provenance without changing legacy `prepare(...)` return type or arguments. Typed `OperationOutcome.envelope.diagnostics` contains a JSON-safe `asset_materialization` list; `forge-unit.json` remains byte-compatible when no explicit maps are supplied and carries the same list only for typed explicit maps.

**Behavior:** Validate map keys against final structure species before any asset write; explicit entries override existing species references only for named species. Unmapped species retain source STRU metadata and are not inferred/staged. A missing explicit source is `precondition.missing`/exit3; unknown species, invalid mode, suffix or basename conflict is request/schema or request/invalid per typed error mapping. Default typed mode is copy. External source copy is allowed and recorded; external link is rejected before writes. Typed API and machine CLI produce equivalent STRU, staged artifacts and provenance. Legacy API/path inference and default link behavior remain unchanged.

**Test strategy:** Add service/API/process cases with a structure containing Si/O, external Si.upf/O.upf/Si.orb/O.orb; assert final STRU names, bytes, artifact records, diagnostics, event payload and source/destination hashes. Cover partial map preserving source metadata, unknown element, missing source, collision and external link rejection. Reuse existing operation IDs and isolated workspaces to avoid admission conflicts.

- [x] Write RED integration tests against Task1/2 contracts.
- [x] Integrate typed path and prove legacy regression stays green.
- [x] Run `env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_service_status.py tests/test_api.py tests/test_cli_process.py tests/test_contracts.py tests/test_workspace.py tests/test_assets.py`; exact revision `ec3d84d` passed `492` tests in `46.51s`.
- [x] Commit and report exact raw output/revision; independent task review passed at `ec3d84d`.

## Task 4: Documentation and final verification

**Files:**
- Modify: `README.md`, `ROADMAP.md`, this plan and its SDD ledger
- No compatibility code changes; only document implemented behavior and deferred limits.

**Behavior:** README describes typed map fields, path resolution, default copy, link restriction, fail-closed conflicts/missing sources, provenance and distinction between explicit assets and unprovided STRU references. Legacy `prepare` examples and behavior remain clear. ROADMAP moves typed asset materialization from pending to implemented and records future enhancements only if evidenced.

**Verification:** Run the full offline gate after Task3/Task4 docs with exact interpreter/flags, `git diff --check`, and review packages. No real ABACUS run is required for this file/materialization boundary.

- [x] Update docs concisely after code behavior is fixed.
- [ ] Run full offline pytest and diff check; retain raw output (主代理在文档提交后独立重跑全量 gate)。
- [x] Obtain task reviews and whole-branch review; close all Critical/Important findings before delivery; Task 3 review passed at `ec3d84d`.

**Plan self-review:** Checked against the two SPECs at branch `80d197a`, current contracts/discovery/service seams, Paimon v1.2 asset pipeline, abacustest map behavior and current Forge legacy tests. New fields are optional and preserve request v1. Asset writes are isolated below typed service, explicit and fail-closed. The plan deliberately excludes directory inference for typed requests, science validation, orchestration, scheduler behavior and real execution. No unresolved public behavior decision remains after the user’s “进行推进” authorization.
