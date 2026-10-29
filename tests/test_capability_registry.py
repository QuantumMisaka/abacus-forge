from __future__ import annotations

import json
from pathlib import Path

import pytest

from abacus_forge.capability_registry import (
    CapabilityContract,
    CapabilityMaturityEvidence,
    CapabilityOutputContract,
    DiagnosticRecord,
    ExecutionIdentity,
    ResourceSpec,
    ToolProjection,
    WorkspacePlan,
    capability_contract,
    capability_contracts,
    capability_contracts_document,
    export_capability_contracts,
)
from abacus_forge.errors import ForgeSchemaError


OPERATION_ID = "123e4567-e89b-42d3-a456-426614174000"


def _workspace_plan(**changes):
    values: dict[str, object] = {
        "schema_version": "forge.workspace-plan/v1",
        "project_root": "GaN",
        "workspace_rel": "runs/prime",
        "role": "run",
        "strategy": "explicit",
        "contained_paths": True,
        "allow_existing": False,
    }
    values.update(changes)
    return values


def _resource_spec(**changes):
    values: dict[str, object] = {
        "schema_version": "forge.resource-spec/v1",
        "mpi_ranks": 4,
        "omp_threads": 4,
        "gpu_count": 1,
        "gpu_shape": "1gpu",
        "expected_locality": "single-node",
        "environment_ref": "reports/environment.json",
        "timeout_seconds": 3600,
        "dry_run": False,
    }
    values.update(changes)
    return values


def _execution_identity(**changes):
    values: dict[str, object] = {
        "schema_version": "forge.execution-identity/v1",
        "engine": "abacus",
        "engine_version": "v3.10.1",
        "engine_build": "LTS3.10.1",
        "executable_sha256": "a" * 64,
        "container_image": "abacus:1.1.1",
        "container_digest": "sha256:" + "b" * 64,
        "forge_version": "0.1.0",
        "forge_commit": "c" * 40,
        "parser_backend": "native",
        "python_lock_ref": "reports/python-lock.json",
        "resource_spec_ref": "reports/resource-spec.json",
    }
    values.update(changes)
    return values


def _diagnostic(**changes):
    values: dict[str, object] = {
        "schema_version": "forge.diagnostic/v1",
        "operation_id": OPERATION_ID,
        "stage": "collect",
        "error_class": "resource_oom",
        "severity": "error",
        "message": "host memory was exhausted",
        "observed_facts": {"oom_kind": "host_memory"},
        "workdir_ref": "runs/prime",
        "artifact_refs": ["running_log"],
        "resource_evidence_ref": "reports/resource-evidence.json",
        "safe_next_actions": ["inspect_resource_evidence"],
        "scientific_interpretation": "unassessed",
    }
    values.update(changes)
    return values


def _tool_projection(**changes):
    values: dict[str, object] = {
        "schema_version": "forge.tool-projection/v1",
        "capability": "scf",
        "operation": "collect",
        "target": "paimon.tool/v1",
        "tool_name": "abacus_worker_scf",
        "declared_outputs": {
            "work_dir": "canonical_output:work_dir",
            "result_evidence_file": "artifact:result_evidence",
        },
        "diagnostic_mapping": {"missing_output": "platform.output.missing"},
    }
    values.update(changes)
    return values


@pytest.mark.parametrize("factory", [WorkspacePlan, ResourceSpec, ExecutionIdentity, DiagnosticRecord, ToolProjection])
def test_phase_a_records_round_trip(factory):
    if factory is WorkspacePlan:
        values = _workspace_plan()
    elif factory is ResourceSpec:
        values = _resource_spec()
    elif factory is ExecutionIdentity:
        values = _execution_identity()
    elif factory is DiagnosticRecord:
        values = _diagnostic()
    else:
        values = _tool_projection()
    record = factory.from_dict(values)
    assert record.to_dict() == values
    assert factory.from_dict(record.to_dict()) == record


@pytest.mark.parametrize("factory", [WorkspacePlan, ResourceSpec, ExecutionIdentity, DiagnosticRecord, ToolProjection])
def test_phase_a_records_reject_unknown_fields(factory):
    values = _workspace_plan() if factory is WorkspacePlan else _resource_spec()
    if factory is ExecutionIdentity:
        values = _execution_identity()
    elif factory is DiagnosticRecord:
        values = _diagnostic()
    elif factory is ToolProjection:
        values = _tool_projection()
    values["unknown"] = True
    with pytest.raises(ValueError, match="unknown fields"):
        factory.from_dict(values)


def test_workspace_plan_rejects_escaping_path():
    for field in ("project_root", "workspace_rel"):
        with pytest.raises(ValueError, match="canonical relative"):
            WorkspacePlan.from_dict(_workspace_plan(**{field: "../escape"}))


@pytest.mark.parametrize("field", ("mpi_ranks", "omp_threads", "gpu_count"))
def test_resource_spec_rejects_non_positive_counts(field):
    with pytest.raises(ValueError, match=field):
        ResourceSpec.from_dict(_resource_spec(**{field: 0}))


def test_resource_spec_rejects_nonpositive_timeout():
    with pytest.raises(ValueError, match="timeout_seconds"):
        ResourceSpec.from_dict(_resource_spec(timeout_seconds=0))


def test_execution_identity_rejects_bad_digest_and_commit():
    with pytest.raises(ValueError, match="executable_sha256"):
        ExecutionIdentity.from_dict(_execution_identity(executable_sha256="short"))
    with pytest.raises(ValueError, match="forge_commit"):
        ExecutionIdentity.from_dict(_execution_identity(forge_commit="main"))


def test_diagnostic_requires_uuid4_operation_id():
    with pytest.raises(ValueError, match="operation_id"):
        DiagnosticRecord.from_dict(_diagnostic(operation_id="not-a-uuid4"))


def test_tool_projection_rejects_unknown_target():
    with pytest.raises(ValueError, match="target"):
        ToolProjection.from_dict(_tool_projection(target="other.tool/v1"))


def test_scf_capability_contract_is_available_and_strict():
    contract = capability_contract("scf")
    assert contract.capability == "scf"
    assert contract.engine == "abacus"
    assert contract.operations == ("prepare", "modify", "execute", "collect")
    assert contract.maturity == "experimental"
    assert {item.name for item in contract.canonical_outputs} >= {
        "work_dir", "running_log_file", "raw_artifacts_manifest_file", "result_evidence_file",
    }
    assert CapabilityContract.from_dict(contract.to_dict()) == contract


def test_missing_capability_contract_fails_typed():
    with pytest.raises(ForgeSchemaError, match="unknown capability contract"):
        capability_contract("teleport")


def test_capability_documents_are_deterministic():
    contracts = capability_contracts()
    assert [item.capability for item in contracts] == sorted(item.capability for item in contracts)
    first = capability_contracts_document()
    second = capability_contracts_document()
    assert first == second
    assert first["schema_version"] == "forge.capability-contracts/v1"
    text = export_capability_contracts()
    assert text == export_capability_contracts()
    assert json.loads(text) == first
    assert text.endswith("\n")


def test_capability_contract_machine_access(tmp_path: Path):
    from tests.support.process import run_cli

    all_result = run_cli("capability-contracts", cwd=tmp_path)
    assert all_result.returncode == 0
    assert all_result.stderr == ""
    all_payload = json.loads(all_result.stdout)
    assert all_payload["schema_version"] == "forge.capability-contracts/v1"
    assert [item["capability"] for item in all_payload["capabilities"]] == ["scf"]

    one_result = run_cli("capability-contracts", "scf", cwd=tmp_path)
    assert one_result.returncode == 0
    assert one_result.stderr == ""
    one_payload = json.loads(one_result.stdout)
    assert one_payload["schema_version"] == "forge.capability-contract/v1"
    assert one_payload["capability"] == "scf"

    missing = run_cli("capability-contracts", "teleport", cwd=tmp_path)
    assert missing.returncode == 2
    missing_payload = json.loads(missing.stdout)
    assert missing_payload["error"]["class"] == "request.schema"

    pretty = run_cli("capability-contracts", "--pretty", cwd=tmp_path)
    assert pretty.returncode == 0
    assert pretty.stderr == ""
    assert "\n" in pretty.stdout
