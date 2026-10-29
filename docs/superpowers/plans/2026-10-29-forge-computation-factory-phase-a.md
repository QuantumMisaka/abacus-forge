# Forge Computation Factory Phase A — contract-only foundation

- Owner: ABACUS-Forge
- Status: Implemented and verified
- Date: 2026-10-29
- Requirement source: `docs/superpowers/specs/2026-10-29-forge-computation-factory-target-architecture-design.md`
- Authorization: owner asked to continue the confirmed architecture work on 2026-10-29.

## Goal

Land the Phase A contract-only foundation from the “算筹工场” target architecture:
a Python source-of-truth registry for capability/output/maturity contracts, plus
strict schemas for workspace planning, resource specification, execution identity,
diagnostics, and Paimon tool projection.

This phase must not change prepare/modify/execute/collect runtime behavior. It adds
versioned contracts, validation, deterministic documents, and discovery/read-only
CLI access only.

## Non-goals

- No scheduler, Slurm, SAI, platform protocol, or workflow orchestration.
- No automatic retry or scientific acceptance decision.
- No change to existing `forge.request/v1`, `forge.result/v1`, or workspace event
  payloads.
- No claim that all capabilities have complete contracts. The initial registry
  seeds SCF as the reference capability.

## Deliverables

### Task 1: Contract record types

- [x] Add strict record types and deterministic serialization.

Add `src/abacus_forge/capability_registry.py` with frozen, JSON-safe record types:

- `WorkspacePlan` — `forge.workspace-plan/v1`
- `ResourceSpec` — `forge.resource-spec/v1`
- `ExecutionIdentity` — `forge.execution-identity/v1`
- `DiagnosticRecord` — `forge.diagnostic/v1`
- `CapabilityOutputContract`
- `CapabilityMetricContract`
- `CapabilityMaturityEvidence`
- `CapabilityContract` — `forge.capability-contract/v1`
- `ToolProjection` — `forge.tool-projection/v1`
- `CapabilityRegistry`

Requirements:

- frozen dataclasses with slots;
- strict unknown-field rejection;
- UUIDv4 validation for `DiagnosticRecord.operation_id`;
- workspace-relative path validation using the existing canonical path helper;
- positive integer validation for ranks/threads/gpus where present;
- positive timeout validation consistent with `ScfExecuteRequest`;
- JSON-safe `to_dict()` and strict `from_dict()` for every public record;
- deterministic mapping ordering in serialized documents.

Check with `tests/test_capability_registry.py`:

- wire round-trip for every record;
- unknown fields fail;
- wrong schema versions fail;
- escaped workspace paths fail;
- non-positive resource values fail;
- non-UUIDv4 diagnostic operation IDs fail;
- serialized key order is deterministic.

### Task 2: Initial SCF capability contract

- [x] Seed the registry and typed missing-capability lookup.

Seed the registry with a reference `scf` capability contract covering:

- engine `abacus`;
- operations `prepare`, `modify`, `execute`, `collect`;
- maturity `experimental`;
- canonical output contracts for `work_dir`, `running_log_file`,
  `raw_artifacts_manifest_file`, and `result_evidence_file`;
- representative metrics `total_energy`, `fermi_energy`, and `scf_steps`;
- diagnostic classes already used by Forge: `missing_output`,
  `unparseable_output`, `engine_nonzero_exit`, `resource_oom`,
  `resource_timeout`, and `identity_mismatch`;
- maturity evidence currently limited to offline tests.

The registry must expose:

- `capability_contract(name)`;
- `capability_contracts()`;
- `capability_contracts_document()` returning
  `forge.capability-contracts/v1`;
- `export_capability_contracts()` returning deterministic UTF-8 JSON text.

Missing capability lookup must raise a typed `ForgeSchemaError`, not `KeyError`.

### Task 3: Read-only machine access

- [x] Add `capability-contracts` machine access and CLI routing.

Add a machine CLI subcommand:

```bash
abacus-forge capability-contracts [CAPABILITY]
```

Behavior:

- no argument: return `forge.capability-contracts/v1`;
- one capability: return `forge.capability-contract/v1`;
- unknown capability: `request.schema` / exit 2;
- JSON output formatting obeys existing machine CLI `--pretty` behavior;
- no filesystem writes.

Update machine help and add API/CLI parity tests. Extend `capabilities` docs to
point to this read-only contract view without claiming complete registry coverage.

### Task 4: Documentation and SPEC status

- [x] Document registry scope, incompleteness, and module ownership.

Update:

- `docs/reference.md`: Phase A registry scope and explicit incompleteness;
- `docs/architecture.md`: registry ownership and no-runtime-change boundary;
- the target architecture SPEC: mark Phase A implemented only after checks pass.

## Verification

Run from the repository root:

```bash
conda run -n abacus-env pytest tests/test_capability_registry.py tests/test_machine_cli.py tests/test_documentation_links.py tests/test_architecture.py -q
conda run -n abacus-env pytest -q
```

Additional focused checks:

```bash
git diff --check
conda run -n abacus-env python -m abacus_forge.cli capability-contracts > /tmp/capability-contracts.json
conda run -n abacus-env python -m abacus_forge.cli capability-contracts scf > /tmp/scf-contract.json
python -m json.tool /tmp/capability-contracts.json >/dev/null
python -m json.tool /tmp/scf-contract.json >/dev/null
```

Acceptance requires zero failures in the focused and full offline suites, valid
CLI JSON output, and no runtime imports or workspace behavior changes.
