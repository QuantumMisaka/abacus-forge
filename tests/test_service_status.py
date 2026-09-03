from __future__ import annotations

import pytest
from pathlib import Path
import json
import importlib
import threading
import time

import abacus_forge
from abacus_forge import ForgeErrorEnvelope, ForgeResultEnvelope, ForgeServices, LocalRunner, Workspace
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


def _prepared_scf_workspace_with_log(tmp_path: Path, content: str) -> Path:
    workspace = Workspace(tmp_path / "scf")
    workspace.ensure_layout()
    (workspace.outputs_dir / "stdout.log").write_text(content + "\n", encoding="utf-8")
    return workspace.root


class _FailIfCalled:
    def run(self, workspace):
        raise AssertionError("typed dry-run must not start the runner")


def test_typed_execute_does_not_infer_skip_from_normal_end(tmp_path: Path) -> None:
    workspace = _prepared_scf_workspace_with_log(tmp_path, "NORMAL END")
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["NORMAL END"])
    result = ForgeServices.default(
        workspace_root=tmp_path,
        runner=LocalRunner(executable=str(executable)),
    ).execute_scf(
        _request(
            ScfExecuteRequest,
            "scf",
            "123e4567-e89b-42d3-a456-426614174007",
            dry_run=False,
        )
    )

    assert isinstance(result, ForgeResultEnvelope)
    assert result.status.execution == "completed"


def test_typed_execute_dry_run_does_not_start_runner(tmp_path: Path) -> None:
    result = ForgeServices(
        workspace_root=tmp_path,
        runner=_FailIfCalled(),  # type: ignore[arg-type]
    ).execute_scf(
        _request(
            ScfExecuteRequest,
            "scf",
            "123e4567-e89b-42d3-a456-426614174008",
            dry_run=True,
        )
    )

    assert isinstance(result, ForgeResultEnvelope)
    assert result.status.execution == "skipped"


def test_legacy_run_many_skip_completed_remains_available(tmp_path: Path) -> None:
    workspace = _prepared_scf_workspace_with_log(tmp_path, "NORMAL END")
    calls = 0

    class CountingRunner(LocalRunner):
        def run(self, workspace, check=False):
            nonlocal calls
            calls += 1
            return super().run(workspace, check=check)

    from abacus_forge.runner import run_many

    results = run_many([workspace], runner=CountingRunner(executable="missing-abacus"), skip_completed=True)

    assert results[0].status == "skipped"
    assert calls == 0


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
    # Typed execution calls LocalRunner.run directly; the legacy ``execute``
    # API remains imported for compatibility but is not part of this path.
    assert calls == {"prepare_unit": 1, "modify_unit": 1, "execute": 0, "collect": 1}


def test_typed_scf_service_returns_structured_error_without_event(tmp_path: Path) -> None:
    services = ForgeServices.default(workspace_root=tmp_path)
    result = services.execute_scf(object())
    assert isinstance(result, ForgeErrorEnvelope)
    assert result.operation_id is None
    assert result.workspace_rel is None


def test_typed_scf_internal_failure_returns_error_without_caller_event(tmp_path: Path) -> None:
    class FailingRunner:
        def run(self, workspace):
            raise RuntimeError("runner fixture failed")

    workspace = abacus_forge.Workspace(tmp_path / "scf")
    workspace.append_operation_event("legacy", {"status": "completed"})
    operation_id = "123e4567-e89b-42d3-a456-426614174006"
    services = ForgeServices.default(workspace_root=tmp_path, runner=FailingRunner())  # type: ignore[arg-type]

    result = services.execute_scf(_request(ScfExecuteRequest, "scf", operation_id))

    assert isinstance(result, ForgeErrorEnvelope)
    manifest = json.loads((workspace.reports_dir / "forge-workspace.json").read_text())
    assert operation_id not in {event["id"] for event in manifest["events"]}


def test_collect_has_operation_local_not_run_execution_even_after_execute(tmp_path: Path) -> None:
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["SCF CONVERGED", "NORMAL END"])
    services = ForgeServices.default(workspace_root=tmp_path, runner=LocalRunner(executable=str(executable)))
    workspace = Workspace(tmp_path / "scf")
    workspace.ensure_layout()
    (workspace.outputs_dir / "running_scf.log").write_text("SCF CONVERGED\nNORMAL END\n", encoding="utf-8")
    execute_id = "123e4567-e89b-42d3-a456-426614174009"
    collect_id = "123e4567-e89b-42d3-a456-426614174010"
    services.execute_scf(_request(ScfExecuteRequest, "scf", execute_id))
    collected = services.collect_scf(_request(ScfCollectRequest, "scf", collect_id))
    assert isinstance(collected, ForgeResultEnvelope)
    assert collected.status.execution == "not_run"


def test_typed_services_reject_unknown_policy(tmp_path: Path) -> None:
    services = ForgeServices.default(workspace_root=tmp_path)
    result = services.execute_scf(_request(ScfExecuteRequest, "scf", "123e4567-e89b-42d3-a456-426614174011", policy_id="garbage"))
    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.policy"


def test_typed_execute_duplicate_request_id_runs_once_and_returns_conflict(tmp_path: Path) -> None:
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["NORMAL END"])
    calls = 0
    class CountingRunner(LocalRunner):
        def run(self, workspace, check=False):
            nonlocal calls
            calls += 1
            return super().run(workspace, check=check)
    runner = CountingRunner(executable=str(executable))
    services = ForgeServices.default(workspace_root=tmp_path, runner=runner)
    request = _request(ScfExecuteRequest, "scf", "123e4567-e89b-42d3-a456-426614174012")
    first = services.execute_scf(request)
    second = services.execute_scf(request)
    assert isinstance(first, ForgeResultEnvelope)
    assert isinstance(second, ForgeErrorEnvelope)
    assert second.error_class == "operation.conflict"
    assert calls == 1
    manifest = json.loads((tmp_path / "scf" / "reports" / "forge-workspace.json").read_text())
    assert [event["id"] for event in manifest["events"]].count(request.operation_id) == 1


def test_typed_execute_concurrent_same_id_admits_only_first_runner(tmp_path: Path) -> None:
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["NORMAL END"])
    first_started = threading.Event()
    second_invoked = threading.Event()
    release_first = threading.Event()
    calls = 0

    class BlockingRunner(LocalRunner):
        def run(self, workspace, check=False):
            nonlocal calls
            calls += 1
            first_started.set()
            assert release_first.wait(timeout=5)
            return super().run(workspace, check=check)

    services = ForgeServices.default(
        workspace_root=tmp_path,
        runner=BlockingRunner(executable=str(executable)),
    )
    request = _request(ScfExecuteRequest, "scf", "123e4567-e89b-42d3-a456-426614174027")
    results: list[ForgeResultEnvelope | ForgeErrorEnvelope] = []
    first = threading.Thread(target=lambda: results.append(services.execute_scf(request)))

    def invoke_second() -> None:
        second_invoked.set()
        results.append(services.execute_scf(request))

    second = threading.Thread(target=invoke_second)
    first.start()
    assert first_started.wait(timeout=5)
    second.start()
    assert second_invoked.wait(timeout=5)
    assert calls == 1
    assert second.is_alive()

    release_first.set()
    first.join(timeout=5)
    second.join(timeout=5)
    assert not first.is_alive()
    assert not second.is_alive()
    assert calls == 1
    assert len(results) == 2
    assert sum(isinstance(result, ForgeResultEnvelope) for result in results) == 1
    conflicts = [result for result in results if isinstance(result, ForgeErrorEnvelope)]
    assert len(conflicts) == 1
    assert conflicts[0].error_class == "operation.conflict"


def test_typed_execute_stale_admission_blocks_runner_and_domain_writes(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "scf")
    workspace.ensure_layout()
    claims_dir = workspace.reports_dir / "claims"
    claims_dir.mkdir()
    operation_id = "123e4567-e89b-42d3-a456-426614174023"
    (claims_dir / f"{operation_id}.json").write_text(
        json.dumps({"operation_id": operation_id, "operation": "execute", "owner_token": "dead"}),
        encoding="utf-8",
    )

    calls = 0

    class CountingRunner:
        def run(self, workspace):
            nonlocal calls
            calls += 1
            raise AssertionError("stale admission must stop before runner")

    result = ForgeServices.default(workspace_root=tmp_path, runner=CountingRunner()).execute_scf(
        _request(ScfExecuteRequest, "scf", operation_id)
    )

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "operation.conflict"
    assert calls == 0
    assert not (workspace.root / "forge-result.json").exists()


def test_typed_services_serialize_different_ids_for_one_workspace(tmp_path: Path) -> None:
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["NORMAL END"])
    first_started = threading.Event()
    release_first = threading.Event()
    calls: list[str] = []

    class SerialRunner(LocalRunner):
        def run(self, workspace, check=False):
            calls.append("runner")
            if len(calls) == 1:
                first_started.set()
                assert release_first.wait(timeout=5)
            return super().run(workspace, check=check)

    services = ForgeServices.default(
        workspace_root=tmp_path,
        runner=SerialRunner(executable=str(executable)),
    )
    requests = [
        _request(ScfExecuteRequest, "scf", "123e4567-e89b-42d3-a456-426614174024"),
        _request(ScfExecuteRequest, "scf", "123e4567-e89b-42d3-a456-426614174025"),
    ]
    results: list[ForgeResultEnvelope | ForgeErrorEnvelope] = []
    threads = [threading.Thread(target=lambda request=request: results.append(services.execute_scf(request))) for request in requests]
    threads[0].start()
    assert first_started.wait(timeout=5)
    threads[1].start()
    time.sleep(0.1)
    assert len(calls) == 1
    release_first.set()
    for thread in threads:
        thread.join(timeout=5)
        assert not thread.is_alive()

    assert len(results) == 2
    assert all(isinstance(result, ForgeResultEnvelope) for result in results)


def test_typed_service_manifest_failure_is_class_5_and_keeps_id_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["NORMAL END"])
    original = Workspace._write_json_atomic

    def fail_manifest(path: Path, payload: dict) -> None:
        if path.name == "forge-workspace.json" and isinstance(payload.get("events"), list) and payload["events"]:
            raise OSError("injected manifest failure")
        original(path, payload)

    monkeypatch.setattr(Workspace, "_write_json_atomic", staticmethod(fail_manifest))
    services = ForgeServices.default(
        workspace_root=tmp_path,
        runner=LocalRunner(executable=str(executable)),
    )
    request = _request(ScfExecuteRequest, "scf", "123e4567-e89b-42d3-a456-426614174026")

    first = services.execute_scf(request)
    second = services.execute_scf(request)

    assert isinstance(first, ForgeErrorEnvelope)
    assert first.error_class == "persistence.failure"
    assert isinstance(second, ForgeErrorEnvelope)
    assert second.error_class == "operation.conflict"


def test_typed_service_event_failure_is_class_5_and_keeps_id_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["NORMAL END"])
    original = Workspace._write_json_atomic

    def fail_event(path: Path, payload: dict) -> None:
        if path.parent.name == "events":
            raise OSError("injected event failure")
        original(path, payload)

    monkeypatch.setattr(Workspace, "_write_json_atomic", staticmethod(fail_event))
    services = ForgeServices.default(
        workspace_root=tmp_path,
        runner=LocalRunner(executable=str(executable)),
    )
    request = _request(ScfExecuteRequest, "scf", "123e4567-e89b-42d3-a456-426614174028")

    first = services.execute_scf(request)
    claim_path = tmp_path / "scf" / "reports" / "claims" / f"{request.operation_id}.json"
    second = services.execute_scf(request)

    assert isinstance(first, ForgeErrorEnvelope)
    assert first.error_class == "persistence.failure"
    assert claim_path.exists()
    assert not (tmp_path / "scf" / "reports" / "events" / f"{request.operation_id}-execute.json").exists()
    assert isinstance(second, ForgeErrorEnvelope)
    assert second.error_class == "operation.conflict"


def test_prepare_and_modify_envelopes_retain_inputs_and_changes(tmp_path: Path) -> None:
    services = ForgeServices.default(workspace_root=tmp_path)
    structure = tmp_path / "scf" / "source.STRU"
    structure.parent.mkdir()
    structure.write_text(
        "ATOMIC_SPECIES\nSi 28.085500 Si.upf\n\nLATTICE_CONSTANT\n1.0\n"
        "LATTICE_CONSTANT_UNIT\nAngstrom\n\nLATTICE_VECTORS\n4 0 0\n0 4 0\n0 0 4\n\n"
        "ATOMIC_POSITIONS\nDirect\nSi\n0\n1\n0 0 0 m 1 1 1\n", encoding="utf-8"
    )
    prepared = services.prepare_scf(_request(ScfPrepareRequest, "scf", "123e4567-e89b-42d3-a456-426614174013", structure_path_rel="source.STRU"))
    modified = services.modify_scf(_request(ScfModifyRequest, "scf", "123e4567-e89b-42d3-a456-426614174014", input_updates={"ecutwfc": 90}))
    assert isinstance(prepared, ForgeResultEnvelope)
    assert {artifact.path_rel for artifact in prepared.artifacts} >= {"inputs/INPUT", "inputs/STRU", "inputs/KPT", "forge-unit.json"}
    assert isinstance(modified, ForgeResultEnvelope)
    assert modified.diagnostics["changes"]["INPUT"]["updates"] == {"ecutwfc": 90}
    assert "input_snapshot_before" in modified.diagnostics
    assert "input_snapshot_after" in modified.diagnostics
