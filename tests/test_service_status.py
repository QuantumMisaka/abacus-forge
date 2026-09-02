from __future__ import annotations

import pytest
from pathlib import Path
import json
import importlib

import abacus_forge
from abacus_forge import ForgeErrorEnvelope, ForgeResultEnvelope, ForgeServices, LocalRunner
from abacus_forge.contracts import CheckRecord, ScfCollectRequest, ScfExecuteRequest, ScfModifyRequest, ScfPrepareRequest
from tests.support.fake_executables import write_fake_abacus


def _check(name: str, status: str) -> CheckRecord:
    return CheckRecord(name=name, status=status)  # type: ignore[arg-type]


def _evaluate(
    *,
    execution: str = "completed",
    collection: str = "complete",
    normal_end: str = "passed",
    convergence: str = "passed",
    parser_complete: str = "passed",
    required_artifacts_present: bool = True,
):
    return abacus_forge.evaluate_abacus_scf_v1(
        execution=execution,
        collection=collection,
        normal_end=_check("normal_end", normal_end),
        convergence=_check("scf_convergence", convergence),
        parser_complete=_check("parser_complete", parser_complete),
        required_artifacts_present=required_artifacts_present,
    )


def test_scf_policy_accepts_only_complete_positive_evidence() -> None:
    status, checks = abacus_forge.evaluate_abacus_scf_v1(
        execution="completed",
        collection="complete",
        normal_end=_check("normal_end", "passed"),
        convergence=_check("scf_convergence", "passed"),
        parser_complete=_check("parser_complete", "passed"),
        required_artifacts_present=True,
    )

    assert status.to_dict() == {"execution": "completed", "scientific": "accepted", "collection": "complete"}
    assert [check.name for check in checks] == ["normal_end", "scf_convergence", "parser_complete"]


def test_scf_policy_rejects_explicit_nonconvergence() -> None:
    status, _ = abacus_forge.evaluate_abacus_scf_v1(
        execution="completed",
        collection="complete",
        normal_end=_check("normal_end", "passed"),
        convergence=_check("scf_convergence", "failed"),
        parser_complete=_check("parser_complete", "passed"),
        required_artifacts_present=True,
    )

    assert status.scientific == "rejected"


def test_scf_policy_keeps_missing_evidence_unassessed() -> None:
    status, _ = abacus_forge.evaluate_abacus_scf_v1(
        execution="not_run",
        collection="missing_output",
        normal_end=_check("normal_end", "unavailable"),
        convergence=_check("scf_convergence", "unavailable"),
        parser_complete=_check("parser_complete", "unavailable"),
        required_artifacts_present=False,
    )

    assert status.scientific == "unassessed"


@pytest.mark.parametrize("execution", ["completed", "not_run"])
def test_scf_policy_preserves_valid_execution_fact(execution: str) -> None:
    status, _ = _evaluate(execution=execution)

    assert status.execution == execution
    assert status.scientific == "accepted"


@pytest.mark.parametrize("execution", ["not_run", "completed", "failed", "skipped"])
def test_scf_policy_keeps_execution_independent_from_scientific_assessment(execution: str) -> None:
    status, _ = _evaluate(execution=execution)

    assert status.execution == execution
    assert status.scientific == "accepted"


@pytest.mark.parametrize("collection", ["not_collected", "missing_output"])
def test_scf_policy_keeps_absent_collection_unassessed(collection: str) -> None:
    status, _ = _evaluate(collection=collection, required_artifacts_present=False)

    assert status.collection == collection
    assert status.scientific == "unassessed"


def test_scf_policy_guards_partial_collection_with_usable_evidence() -> None:
    status, _ = _evaluate(collection="partial")

    assert status.scientific == "guarded"


def test_scf_policy_keeps_missing_required_artifacts_unassessed() -> None:
    status, _ = _evaluate(required_artifacts_present=False)

    assert status.scientific == "unassessed"


@pytest.mark.parametrize("status_name", ["failed", "warning", "unavailable"])
def test_scf_policy_guards_nonpassing_normal_end(status_name: str) -> None:
    status, _ = _evaluate(normal_end=status_name)

    assert status.scientific == "guarded"


@pytest.mark.parametrize("status_name", ["warning", "unavailable"])
def test_scf_policy_guards_uncertain_convergence(status_name: str) -> None:
    status, _ = _evaluate(convergence=status_name)

    assert status.scientific == "guarded"


@pytest.mark.parametrize("status_name", ["warning", "unavailable"])
def test_scf_policy_guards_degraded_parser_evidence(status_name: str) -> None:
    status, _ = _evaluate(parser_complete=status_name)

    assert status.scientific == "guarded"


def test_scf_policy_keeps_failed_parser_evidence_unassessed() -> None:
    status, _ = _evaluate(parser_complete="failed")

    assert status.scientific == "unassessed"


def test_scf_policy_rejects_explicit_nonconvergence_with_complete_parse() -> None:
    status, _ = _evaluate(convergence="failed")

    assert status.scientific == "rejected"


def test_scf_policy_does_not_turn_missing_collection_into_rejection() -> None:
    status, _ = _evaluate(collection="missing_output", convergence="failed", required_artifacts_present=False)

    assert status.scientific == "unassessed"


@pytest.mark.parametrize(
    ("field", "wrong_name"),
    [("normal_end", "completion"), ("convergence", "converged"), ("parser_complete", "parse")],
)
def test_scf_policy_requires_exact_check_names(field: str, wrong_name: str) -> None:
    checks = {
        "normal_end": _check("normal_end", "passed"),
        "convergence": _check("scf_convergence", "passed"),
        "parser_complete": _check("parser_complete", "passed"),
    }
    checks[field] = _check(wrong_name, "passed")

    with pytest.raises(ValueError, match=field):
        abacus_forge.evaluate_abacus_scf_v1(
            execution="completed",
            collection="complete",
            normal_end=checks["normal_end"],
            convergence=checks["convergence"],
            parser_complete=checks["parser_complete"],
            required_artifacts_present=True,
        )


def test_scf_policy_rejects_invalid_execution() -> None:
    with pytest.raises(ValueError, match="execution"):
        _evaluate(execution="done")


def test_scf_policy_rejects_invalid_collection() -> None:
    with pytest.raises(ValueError, match="collection"):
        _evaluate(collection="unknown")


def _request(request_type, workspace: str, operation_id: str, policy_id: str = "abacus.scf/v1", **kwargs):
    return request_type(operation_id=operation_id, workspace_rel=workspace, policy_id=policy_id, **kwargs)


def test_typed_scf_services_persist_request_ids_and_apply_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    services_module = importlib.import_module("abacus_forge.services")
    calls = {name: 0 for name in ("prepare_unit", "modify_unit", "execute", "collect")}
    for name in calls:
        original = getattr(services_module, name)

        def counted(*args, _name=name, _original=original, **kwargs):
            calls[_name] += 1
            return _original(*args, **kwargs)

        monkeypatch.setattr(services_module, name, counted)

    executable = write_fake_abacus(
        tmp_path / "fake-abacus",
        stdout_lines=["TOTAL ENERGY = -3.2", "SCF CONVERGED", "NORMAL END"],
    )
    services = ForgeServices.default(
        workspace_root=tmp_path,
        runner=LocalRunner(executable=str(executable)),
    )
    prepare_id = "123e4567-e89b-42d3-a456-426614174001"
    modify_id = "123e4567-e89b-42d3-a456-426614174002"
    execute_id = "123e4567-e89b-42d3-a456-426614174003"
    collect_id = "123e4567-e89b-42d3-a456-426614174004"
    structure = tmp_path / "scf" / "source.STRU"
    structure.parent.mkdir()
    structure.write_text(
        "ATOMIC_SPECIES\nSi 28.085500 Si.upf\n\nLATTICE_CONSTANT\n1.0\n"
        "LATTICE_CONSTANT_UNIT\nAngstrom\n\nLATTICE_VECTORS\n"
        "4 0 0\n0 4 0\n0 0 4\n\nATOMIC_POSITIONS\nDirect\nSi\n0\n1\n"
        "0 0 0 m 1 1 1\n",
        encoding="utf-8",
    )

    prepared = services.prepare_scf(
        _request(
            ScfPrepareRequest,
            "scf",
            prepare_id,
            structure_path_rel="source.STRU",
            parameters={"ecutwfc": 80},
        )
    )
    modified = services.modify_scf(
        _request(ScfModifyRequest, "scf", modify_id, input_updates={"ecutwfc": 90})
    )
    executed = services.execute_scf(_request(ScfExecuteRequest, "scf", execute_id))
    collected = services.collect_scf(_request(ScfCollectRequest, "scf", collect_id))

    assert isinstance(prepared, ForgeResultEnvelope)
    assert isinstance(modified, ForgeResultEnvelope)
    assert isinstance(executed, ForgeResultEnvelope)
    assert isinstance(collected, ForgeResultEnvelope)
    assert collected.status.scientific == "accepted"
    manifest = json.loads((tmp_path / "scf" / "reports" / "forge-workspace.json").read_text())
    assert [event["id"] for event in manifest["events"]] == [prepare_id, modify_id, execute_id, collect_id]
    assert [event["operation"] for event in manifest["events"]] == ["prepare", "modify", "execute", "collect"]
    assert isinstance(modified, ForgeResultEnvelope)
    assert modified.status.execution == "not_run"
    assert calls == {"prepare_unit": 1, "modify_unit": 1, "execute": 1, "collect": 1}


def test_typed_scf_service_returns_structured_error_without_event(tmp_path: Path) -> None:
    services = ForgeServices.default(workspace_root=tmp_path)
    result = services.execute_scf(object())
    assert isinstance(result, ForgeErrorEnvelope)
    assert result.operation_id is None
    assert result.workspace_rel is None
