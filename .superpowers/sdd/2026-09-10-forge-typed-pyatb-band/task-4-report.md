# Task 4 report — typed PyATB documentation and final offline verification

## Scope and source coverage

This task updated the current-state documentation and verification ledger for
the typed experimental `pyatb-band` capability. It was checked against:

- `docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html`:
  Forge's facts-only unit-operation boundary, explicit PyATB engine adapter,
  caller-owned workflow/scheduling/scientific decisions, and thin TUI/legacy
  compatibility boundaries.
- `docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html`:
  typed request/result and discovery surfaces, workspace-relative artifacts,
  execution/collection status semantics, and the rule that scientific
  validation, task orchestration and platform scheduling remain with the
  human/Agent caller.
- `docs/superpowers/plans/2026-09-10-forge-typed-pyatb-band.md` and the Task 1–3
  reports: the implemented `pyatb-band` request fields, explicit handoff,
  service routing, and experimental maturity.
- Current implementation in `src/abacus_forge/pyatb_contracts.py`,
  `pyatb.py`, `pyatb_services.py`, `discovery.py` and `machine_cli.py`, plus
  `tests/test_pyatb_typed.py`, `tests/test_machine_cli.py` and
  `tests/test_architecture.py`.

## Changes

- `README.md` now documents the typed `pyatb-band` prepare/execute/collect
  requests, explicit workspace-local STRU/HR/SR/rR and Fermi handoff, relative
  link default and explicit copy mode, generated `inputs/Input` and
  `inputs/KPT_band`, output collection facts, the reported-only `band_gap`
  metric, and the separation from legacy SCF-discovery helpers.
- `README.md` and `ROADMAP.md` now list `pyatb-band` as implemented but
  experimental. They retain PyATB properties, nspin 4, typed export, SCF
  sequence orchestration, scheduler/platform integration, scientific
  acceptance and real-smoke promotion as deferred or caller-owned.
- `tests/test_architecture.py` now asserts the eighth discovered capability
  (`pyatb-band`) and its exact maturity, engine, operation and artifact-role
  contract. This fixes a stale capability-list gate; it does not change
  production behavior.
- `docs/superpowers/plans/2026-09-10-forge-typed-pyatb-band.md` records the
  Task 4 documentation scope and the resolved architecture-gate accounting.

## Verification evidence

All commands below were run in
`/home/james/work/sidereus/workplace/abacus-forge/.worktrees/forge-core-fidelity`
with the fixed Paimon interpreter. The implementation baseline before this
documentation/test-accounting commit was `36d87fe`; the only source/test
behavior change in this task is the discovery assertion described above.

### Full offline suite

Command:

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider
```

Raw result:

```text
sss..................................................................... [  8%]
....................................................... [ 16%]
........................................................................ [ 24%]
........................................................................ [ 32%]
........................................................................ [ 40%]
........................................................................ [ 48%]
........................................................................ [ 56%]
........................................................................ [ 64%]
........................................................................ [ 72%]
............................................. [ 80%]
........................................................................ [ 88%]
........................................................................ [ 96%]
...............................                                          [100%]
892 passed, 3 skipped in 70.51s (0:01:10)
```

Exit code: `0`.

### Architecture and forbidden-import gates

Command:

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture.py
```

Raw result:

```text
........                                                                 [100%]
8 passed in 4.93s
```

Exit code: `0`.

Command:

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture.py -k 'forbidden or dependency'
```

Raw result:

```text
...                                                                      [100%]
3 passed, 5 deselected in 0.22s
```

Exit code: `0`; no forbidden production imports were reported.

### Typed discovery assertions

Command:

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_machine_cli.py -k 'pyatb_band or discovery'
```

Raw result:

```text
...........                                                              [100%]
11 passed, 64 deselected in 0.56s
```

Exit code: `0`.

Command:

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m abacus_forge.cli capabilities
```

Raw result:

```json
{"capabilities": [{"artifact_roles": ["input", "provenance_manifest", "output"], "engine": "abacus", "inputs": {"collect": ["workspace_outputs"], "execute": ["prepared_workspace"], "modify": ["prepared_workspace"], "prepare": ["structure"]}, "maturity": "experimental", "name": "scf", "operations": ["prepare", "modify", "execute", "collect"], "optional_dependencies": [], "schema_version": "forge.capability/v1"}, {"artifact_roles": ["input", "provenance_manifest", "output"], "engine": "abacus", "inputs": {"collect": ["workspace_outputs"], "execute": ["prepared_workspace"], "modify": ["prepared_workspace"], "prepare": ["structure"]}, "maturity": "experimental", "name": "relax", "operations": ["prepare", "modify", "execute", "collect"], "optional_dependencies": [], "schema_version": "forge.capability/v1"}, {"artifact_roles": ["input", "provenance_manifest", "output"], "engine": "abacus", "inputs": {"collect": ["workspace_outputs"], "execute": ["prepared_workspace"], "modify": ["prepared_workspace"], "prepare": ["structure"]}, "maturity": "experimental", "name": "cell-relax", "operations": ["prepare", "modify", "execute", "collect"], "optional_dependencies": [], "schema_version": "forge.capability/v1"}, {"artifact_roles": ["input", "output"], "engine": "atst-tools", "inputs": {"execute": ["workflow_config"], "postprocess": ["trajectory"], "prepare": ["initial_structure", "final_structure"]}, "maturity": "experimental", "name": "atst-neb", "operations": ["prepare", "execute", "postprocess"], "optional_dependencies": ["atst-tools"], "schema_version": "forge.capability/v1"}, {"artifact_roles": ["input", "provenance_manifest", "output"], "engine": "abacus", "inputs": {"collect": ["workspace_outputs"], "execute": ["prepared_workspace"], "modify": ["prepared_workspace"], "prepare": ["structure"]}, "maturity": "experimental", "name": "md", "operations": ["prepare", "modify", "execute", "collect"], "optional_dependencies": [], "schema_version": "forge.capability/v1"}, {"artifact_roles": ["input", "output"], "engine": "abacus", "inputs": {"postprocess": ["band_files"]}, "maturity": "experimental", "name": "band", "operations": ["postprocess"], "optional_dependencies": [], "schema_version": "forge.capability/v1"}, {"artifact_roles": ["input", "output"], "engine": "abacus", "inputs": {"postprocess": ["dos_files", "pdos", "tdos"]}, "maturity": "experimental", "name": "dos", "operations": ["postprocess"], "optional_dependencies": [], "schema_version": "forge.capability/v1"}, {"artifact_roles": ["input", "provenance_manifest", "output"], "engine": "pyatb", "inputs": {"collect": ["workspace_outputs"], "execute": ["prepared_workspace"], "prepare": ["structure", "hr", "sr", "rr", "fermi_energy", "line_kpoints"]}, "maturity": "experimental", "name": "pyatb-band", "operations": ["prepare", "execute", "collect"], "optional_dependencies": ["pyatb"], "schema_version": "forge.capability/v1"}], "schema_version": "forge.capabilities/v1"}
```

Exit code: `0`.

Command:

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m abacus_forge.cli schema pyatb-band prepare
```

Raw result:

```json
{"capability": "pyatb-band", "operation": "prepare", "request_schema": {"$schema": "https://json-schema.org/draft/2020-12/schema", "additionalProperties": false, "properties": {"capability": {"const": "pyatb-band", "type": "string"}, "fermi_energy": {"type": "number"}, "handoff_mode": {"default": "link", "enum": ["link", "copy"], "type": "string"}, "hr_paths_rel": {"items": {"minLength": 1, "pattern": "^(?:(?!\\.{1,2}(?:/|$))[^/\\\\]+)(?:/(?!\\.{1,2}(?:/|$))[^/\\\\]+)*$", "type": "string"}, "maxItems": 2, "minItems": 1, "type": "array"}, "line_kpoints": {"items": {"additionalProperties": false, "properties": {"coords": {"items": {"type": "number"}, "maxItems": 3, "minItems": 3, "type": "array"}, "label": {"minLength": 1, "type": "string"}}, "required": ["coords"], "type": "object"}, "minItems": 2, "type": "array"}, "line_segments": {"default": 20, "minimum": 1, "type": "integer"}, "max_kpoint_num": {"default": 4000, "minimum": 1, "type": "integer"}, "nspin": {"default": 1, "enum": [1, 2], "type": "integer"}, "operation": {"const": "prepare", "type": "string"}, "operation_id": {"format": "uuid", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", "type": "string"}, "rr_path_rel": {"minLength": 1, "pattern": "^(?:(?!\\.{1,2}(?:/|$))[^/\\\\]+)(?:/(?!\\.{1,2}(?:/|$))[^/\\\\]+)*$", "type": "string"}, "schema_version": {"const": "forge.request/v1", "type": "string"}, "sr_path_rel": {"minLength": 1, "pattern": "^(?:(?!\\.{1,2}(?:/|$))[^/\\\\]+)(?:/(?!\\.{1,2}(?:/|$))[^/\\\\]+)*$", "type": "string"}, "structure_path_rel": {"minLength": 1, "pattern": "^(?:(?!\\.{1,2}(?:/|$))[^/\\\\]+)(?:/(?!\\.{1,2}(?:/|$))[^/\\\\]+)*$", "type": "string"}, "workspace_rel": {"minLength": 1, "pattern": "^(?:\\.(?=$)|(?!(?:\\.{1,2})(?:/|$))[^/\\\\]+(?:/(?!\\.{1,2}(?:/|$))[^/\\\\]+)*)$", "type": "string"}}, "required": ["schema_version", "operation", "operation_id", "workspace_rel", "structure_path_rel", "capability", "hr_paths_rel", "sr_path_rel", "rr_path_rel", "fermi_energy", "line_kpoints"], "title": "PyatbBandPrepareRequest", "type": "object"}, "schema_version": "forge.schema-discovery/v1"}
```

Exit code: `0`.

Command:

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m abacus_forge.cli schema pyatb-band execute
```

Raw result:

```json
{"capability": "pyatb-band", "operation": "execute", "request_schema": {"$schema": "https://json-schema.org/draft/2020-12/schema", "additionalProperties": false, "properties": {"capability": {"const": "pyatb-band", "type": "string"}, "dry_run": {"default": false, "type": "boolean"}, "executable": {"default": "pyatb", "minLength": 1, "type": "string"}, "mpi_ranks": {"default": 1, "minimum": 1, "type": "integer"}, "omp_threads": {"default": 1, "minimum": 1, "type": "integer"}, "operation": {"const": "execute", "type": "string"}, "operation_id": {"format": "uuid", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", "type": "string"}, "schema_version": {"const": "forge.request/v1", "type": "string"}, "timeout_seconds": {"default": null, "exclusiveMinimum": 0, "type": ["number", "null"]}, "workspace_rel": {"minLength": 1, "pattern": "^(?:\\.(?=$)|(?!(?:\\.{1,2})(?:/|$))[^/\\\\]+(?:/(?!\\.{1,2}(?:/|$))[^/\\\\]+)*)$", "type": "string"}}, "required": ["schema_version", "operation", "operation_id", "workspace_rel", "capability"], "title": "PyatbBandExecuteRequest", "type": "object"}, "schema_version": "forge.schema-discovery/v1"}
```

Exit code: `0`.

Command:

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m abacus_forge.cli schema pyatb-band collect
```

Raw result:

```json
{"capability": "pyatb-band", "operation": "collect", "request_schema": {"$schema": "https://json-schema.org/draft/2020-12/schema", "additionalProperties": false, "properties": {"band_data_paths_rel": {"default": [], "items": {"minLength": 1, "pattern": "^(?:(?!\\.{1,2}(?:/|$))[^/\\\\]+)(?:/(?!\\.{1,2}(?:/|$))[^/\\\\]+)*$", "type": "string"}, "type": "array"}, "band_info_path_rel": {"default": "inputs/Out/Band_Structure/band_info.dat", "minLength": 1, "pattern": "^(?:(?!\\.{1,2}(?:/|$))[^/\\\\]+)(?:/(?!\\.{1,2}(?:/|$))[^/\\\\]+)*$", "type": "string"}, "band_picture_paths_rel": {"default": [], "items": {"minLength": 1, "pattern": "^(?:(?!\\.{1,2}(?:/|$))[^/\\\\]+)(?:/(?!\\.{1,2}(?:/|$))[^/\\\\]+)*$", "type": "string"}, "type": "array"}, "capability": {"const": "pyatb-band", "type": "string"}, "operation": {"const": "collect", "type": "string"}, "operation_id": {"format": "uuid", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", "type": "string"}, "schema_version": {"const": "forge.request/v1", "type": "string"}, "workspace_rel": {"minLength": 1, "pattern": "^(?:\\.(?=$)|(?!(?:\\.{1,2})(?:/|$))[^/\\\\]+(?:/(?!\\.{1,2}(?:/|$))[^/\\\\]+)*)$", "type": "string"}}, "required": ["schema_version", "operation", "operation_id", "workspace_rel", "capability"], "title": "PyatbBandCollectRequest", "type": "object"}, "schema_version": "forge.schema-discovery/v1"}
```

Exit code: `0`.

### Diff hygiene

Command:

```text
git diff --check
```

Raw result: no output; exit code `0`.

## Not performed / remaining uncertainty

- No real PyATB or ABACUS executable was started. The passing suite uses
  offline fixtures and fake processes only; this report makes no scientific or
  stable-release claim.
- No scheduler/platform integration, SCF sequence orchestration, PyATB
  property operation, nspin 4 support, typed export, scientific acceptance,
  retry/resume or monitoring was added.
- The final whole-branch independent review and integration decision remain
  with the parent agent. No merge or push was performed by this task.
