from __future__ import annotations

import pytest
import fcntl
from pathlib import Path
import json
import signal
import stat
import sys
import threading
import time

import abacus_forge
from abacus_forge import ForgeErrorEnvelope, ForgeResultEnvelope, ForgeServices, LocalRunner, OperationOutcome, Workspace
from abacus_forge.contracts import ScfCollectRequest, ScfExecuteRequest, ScfModifyRequest, ScfPrepareRequest
from abacus_forge.result import RunResult
from tests.support.fake_executables import write_fake_abacus


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

    assert isinstance(result, OperationOutcome)
    assert result.status.execution == "completed"


@pytest.mark.parametrize(
    ("behavior", "expected_failure", "expected_termination", "expected_returncode", "operation_suffix"),
    [
        ("print('zero')", "none", "exited", 0, "030"),
        ("print('bad'); raise SystemExit(7)", "nonzero_exit", "exited", 7, "031"),
        ("import time; time.sleep(0.25)", "timeout", "timeout", 124, "032"),
        ("import os, signal; os.kill(os.getpid(), signal.SIGTERM)", "signal", "signal", -signal.SIGTERM, "033"),
    ],
)
def test_typed_execute_real_local_runner_preserves_process_termination_facts(
    tmp_path: Path,
    behavior: str,
    expected_failure: str,
    expected_termination: str,
    expected_returncode: int,
    operation_suffix: str,
) -> None:
    executable = tmp_path / "runner.py"
    executable.write_text(f"#!{sys.executable}\n{behavior}\n", encoding="utf-8")
    executable.chmod(executable.stat().st_mode | stat.S_IEXEC)
    request = ScfExecuteRequest(
        operation_id=f"123e4567-e89b-42d3-a456-426614174{operation_suffix}",
        workspace_rel="scf",
    )
    result = ForgeServices.default(
        workspace_root=tmp_path,
        runner=LocalRunner(executable=str(executable), timeout_seconds=0.05 if expected_failure == "timeout" else None),
    ).execute_scf(request)
    assert isinstance(result, OperationOutcome)
    assert result.envelope.diagnostics["failure_class"] == expected_failure
    assert result.envelope.diagnostics["termination"] == expected_termination
    assert result.envelope.metrics[0].value == expected_returncode
    assert {artifact.path_rel for artifact in result.envelope.artifacts} >= {"outputs/stdout.log", "outputs/stderr.log"}
    event = json.loads((tmp_path / "scf" / "reports" / "events" / f"{request.operation_id}-execute.json").read_text())
    assert event["payload"] == result.to_dict()


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

    assert isinstance(result, OperationOutcome)
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


def _request(request_type, workspace: str, operation_id: str, **kwargs):
    return request_type(operation_id=operation_id, workspace_rel=workspace, **kwargs)


def test_typed_scf_services_persist_request_ids_and_facts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    services_module = __import__("abacus_forge.services", fromlist=["services"])
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

    assert isinstance(prepared, OperationOutcome)
    assert isinstance(modified, OperationOutcome)
    assert isinstance(executed, OperationOutcome)
    assert isinstance(collected, OperationOutcome)
    assert collected.status.scientific == "unassessed"
    manifest = json.loads((tmp_path / "scf" / "reports" / "forge-workspace.json").read_text())
    assert [event["id"] for event in manifest["events"]] == [prepare_id, modify_id, execute_id, collect_id]
    assert [event["operation"] for event in manifest["events"]] == ["prepare", "modify", "execute", "collect"]
    assert isinstance(modified, OperationOutcome)
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
    assert isinstance(collected, OperationOutcome)
    assert collected.status.execution == "not_run"


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
    assert isinstance(first, OperationOutcome)
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
    assert sum(isinstance(result, OperationOutcome) for result in results) == 1
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
    assert all(isinstance(result, OperationOutcome) for result in results)


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


def test_typed_service_event_directory_failure_is_class_5_and_keeps_id_blocked(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "scf"
    events_dir = workspace_root / "reports" / "events"
    events_dir.parent.mkdir(parents=True)
    events_dir.write_text("blocked", encoding="utf-8")
    request = _request(ScfExecuteRequest, "scf", "123e4567-e89b-42d3-a456-426614174029", dry_run=True)
    services = ForgeServices.default(workspace_root=tmp_path)

    first = services.execute_scf(request)
    claim_path = workspace_root / "reports" / "claims" / f"{request.operation_id}.json"
    second = services.execute_scf(request)

    assert isinstance(first, ForgeErrorEnvelope)
    assert first.error_class == "persistence.failure"
    assert claim_path.exists()
    assert events_dir.is_file()
    assert not (events_dir / f"{request.operation_id}-execute.json").exists()
    assert isinstance(second, ForgeErrorEnvelope)
    assert second.error_class == "operation.conflict"


def test_typed_service_unlock_failure_after_commit_is_class_5_and_event_blocks_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["NORMAL END"])
    services = ForgeServices.default(
        workspace_root=tmp_path,
        runner=LocalRunner(executable=str(executable)),
    )
    request = _request(ScfExecuteRequest, "scf", "123e4567-e89b-42d3-a456-426614174030")
    original_flock = fcntl.flock
    unlock_calls = 0

    def fail_commit_unlock(fd: int, operation: int) -> None:
        nonlocal unlock_calls
        if operation == fcntl.LOCK_UN:
            unlock_calls += 1
            if unlock_calls == 2:
                raise OSError("injected unlock failure")
        original_flock(fd, operation)

    monkeypatch.setattr(fcntl, "flock", fail_commit_unlock)
    first = services.execute_scf(request)
    monkeypatch.setattr(fcntl, "flock", original_flock)
    event_path = tmp_path / "scf" / "reports" / "events" / f"{request.operation_id}-execute.json"
    claim_path = tmp_path / "scf" / "reports" / "claims" / f"{request.operation_id}.json"
    second = services.execute_scf(request)

    assert isinstance(first, ForgeErrorEnvelope)
    assert first.error_class == "persistence.failure"
    assert json.loads(event_path.read_text(encoding="utf-8"))["id"] == request.operation_id
    assert not claim_path.exists()
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
    assert isinstance(prepared, OperationOutcome)
    assert {artifact.path_rel for artifact in prepared.envelope.artifacts} >= {"inputs/INPUT", "inputs/STRU", "inputs/KPT", "forge-unit.json"}
    assert isinstance(modified, OperationOutcome)
    assert modified.envelope.diagnostics["changes"]["INPUT"]["updates"] == {"ecutwfc": 90}
    assert "input_snapshot_before" in modified.envelope.diagnostics
    assert "input_snapshot_after" in modified.envelope.diagnostics


@pytest.mark.parametrize(
    ("operation", "primitive_name", "error_type"),
    [
        ("prepare", "prepare_unit", TypeError),
        ("prepare", "prepare_unit", ValueError),
        ("modify", "modify_unit", TypeError),
        ("modify", "modify_unit", ValueError),
    ],
)
def test_primitive_internal_error_is_not_request_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    primitive_name: str,
    error_type: type[Exception],
) -> None:
    services_module = __import__("abacus_forge.services", fromlist=["services"])

    def broken_primitive(*args, **kwargs):
        raise error_type("unexpected primitive defect")

    monkeypatch.setattr(services_module, primitive_name, broken_primitive)
    workspace = Workspace(tmp_path / "scf")
    workspace.ensure_layout()
    structure = workspace.root / "source.STRU"
    structure.write_text("not used by broken primitive", encoding="utf-8")
    operation_id = "123e4567-e89b-42d3-a456-426614174115"
    services = ForgeServices.default(workspace_root=tmp_path)
    request = (
        ScfPrepareRequest(operation_id=operation_id, workspace_rel="scf", structure_path_rel="source.STRU")
        if operation == "prepare"
        else ScfModifyRequest(operation_id=operation_id, workspace_rel="scf", input_updates={"ecutwfc": 90})
    )

    result = getattr(services, f"{operation}_scf")(request)

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "internal.failure"
    event_paths = list((workspace.reports_dir / "events").glob(f"{operation_id}-*.json"))
    assert event_paths == []
    claim_path = workspace.reports_dir / "claims" / f"{operation_id}.json"
    assert claim_path.exists()
    conflict = getattr(services, f"{operation}_scf")(request)
    assert isinstance(conflict, ForgeErrorEnvelope)
    assert conflict.error_class == "operation.conflict"


def test_typed_services_return_operation_outcome_and_event_carries_same_facts(tmp_path: Path) -> None:
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["SCF CONVERGED", "NORMAL END"])
    services = ForgeServices.default(workspace_root=tmp_path, runner=LocalRunner(executable=str(executable)))
    request = ScfExecuteRequest(operation_id="123e4567-e89b-42d3-a456-426614174101", workspace_rel="scf")

    result = services.execute_scf(request)

    assert isinstance(result, OperationOutcome)
    assert result.operation_id == request.operation_id
    assert any(observation.name == "returncode" for observation in result.observations)
    event = json.loads((tmp_path / "scf" / "reports" / "events" / f"{request.operation_id}-execute.json").read_text())
    assert event["payload"] == result.to_dict()


@pytest.mark.parametrize("diagnostics", [{"failure_class": "nonzero_exit"}, {"failure_class": "timeout"}, {"failure_class": "signal"}])
def test_started_runner_failures_return_failed_operation_outcome(tmp_path: Path, diagnostics: dict[str, str]) -> None:
    class StartedFailureRunner:
        def run(self, workspace):
            workspace.ensure_layout()
            stdout = workspace.outputs_dir / "stdout.log"
            stderr = workspace.outputs_dir / "stderr.log"
            stdout.write_text("started\n", encoding="utf-8")
            stderr.write_text("failed\n", encoding="utf-8")
            return RunResult(workspace.root, ["fake-abacus"], 1, "failed", stdout, stderr, 1, diagnostics)

    result = ForgeServices.default(workspace_root=tmp_path, runner=StartedFailureRunner()).execute_scf(
        ScfExecuteRequest(operation_id="123e4567-e89b-42d3-a456-426614174102", workspace_rel="scf")
    )
    assert isinstance(result, OperationOutcome)
    assert result.status.execution == "failed"
    assert result.envelope.diagnostics["failure_class"] == diagnostics["failure_class"]


def test_missing_executable_is_precondition_error_not_failed_result(tmp_path: Path) -> None:
    request = ScfExecuteRequest(operation_id="123e4567-e89b-42d3-a456-426614174103", workspace_rel="scf")
    services = ForgeServices.default(workspace_root=tmp_path, runner=LocalRunner(executable="does-not-exist"))

    result = services.execute_scf(request)

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "precondition.missing"
    event_path = tmp_path / "scf" / "reports" / "events" / f"{request.operation_id}-execute.json"
    claim_path = tmp_path / "scf" / "reports" / "claims" / f"{request.operation_id}.json"
    assert not event_path.exists()
    assert claim_path.exists()
    conflict = services.execute_scf(request)
    assert isinstance(conflict, ForgeErrorEnvelope)
    assert conflict.error_class == "operation.conflict"


@pytest.mark.parametrize("runner_error", [FileNotFoundError("runner fixture"), OSError("runner fixture")])
def test_unknown_prestart_runner_errors_are_internal(tmp_path: Path, runner_error: Exception) -> None:
    class BrokenRunner:
        def run(self, workspace):
            raise runner_error

    result = ForgeServices.default(workspace_root=tmp_path, runner=BrokenRunner()).execute_scf(
        ScfExecuteRequest(operation_id="123e4567-e89b-42d3-a456-426614174106", workspace_rel="scf")
    )
    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "internal.failure"


def test_unexpected_runner_exception_before_start_is_internal_error(tmp_path: Path) -> None:
    class BrokenRunner:
        def run(self, workspace):
            raise RuntimeError("opaque runner failure")

    result = ForgeServices.default(workspace_root=tmp_path, runner=BrokenRunner()).execute_scf(
        ScfExecuteRequest(operation_id="123e4567-e89b-42d3-a456-426614174104", workspace_rel="scf")
    )
    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "internal.failure"


def test_unexpected_collector_value_error_is_internal_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_collect(workspace):
        raise ValueError("parser bug, not a malformed request")

    services_module = __import__("abacus_forge.services", fromlist=["services"])
    monkeypatch.setattr(services_module, "collect", broken_collect)
    result = ForgeServices.default(workspace_root=tmp_path).collect_scf(
        ScfCollectRequest(operation_id="123e4567-e89b-42d3-a456-426614174107", workspace_rel="scf")
    )
    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "internal.failure"


def test_prepare_rejects_symlink_target_outside_workspace(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "scf").ensure_layout()
    outside = tmp_path / "outside.STRU"
    outside.write_text("external", encoding="utf-8")
    (workspace.inputs_dir / "external.STRU").symlink_to(outside)
    source = workspace.root / "source.STRU"
    source.write_text(
        "ATOMIC_SPECIES\nSi 28.085500 Si.upf\n\nLATTICE_CONSTANT\n1.0\n"
        "LATTICE_CONSTANT_UNIT\nAngstrom\n\nLATTICE_VECTORS\n4 0 0\n0 4 0\n0 0 4\n\n"
        "ATOMIC_POSITIONS\nDirect\nSi\n0\n1\n0 0 0 m 1 1 1\n", encoding="utf-8"
    )
    result = ForgeServices.default(workspace_root=tmp_path).prepare_scf(
        ScfPrepareRequest(operation_id="123e4567-e89b-42d3-a456-426614174108", workspace_rel="scf", structure_path_rel="source.STRU")
    )
    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.path"


def test_modify_rejects_symlink_target_outside_workspace(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "scf").ensure_layout()
    outside = tmp_path / "outside.INPUT"
    outside.write_text("ecutwfc 80\n", encoding="utf-8")
    (workspace.inputs_dir / "INPUT").symlink_to(outside)
    result = ForgeServices.default(workspace_root=tmp_path).modify_scf(
        ScfModifyRequest(operation_id="123e4567-e89b-42d3-a456-426614174109", workspace_rel="scf", input_updates={"ecutwfc": 90})
    )
    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.path"


def test_collect_delivers_false_convergence_without_scientific_projection(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "scf").ensure_layout()
    (workspace.outputs_dir / "stdout.log").write_text("SCF NOT CONVERGED\n", encoding="utf-8")
    result = ForgeServices.default(workspace_root=tmp_path).collect_scf(
        ScfCollectRequest(operation_id="123e4567-e89b-42d3-a456-426614174105", workspace_rel="scf")
    )
    assert isinstance(result, OperationOutcome)
    assert result.status.scientific == "unassessed"
    assert all(observation.value not in ("accepted", "guarded", "rejected") for observation in result.observations)


def test_missing_prepare_structure_is_admitted_before_precondition_check(tmp_path: Path) -> None:
    services = ForgeServices.default(workspace_root=tmp_path)
    request = ScfPrepareRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174120",
        workspace_rel="scf",
        structure_path_rel="source.STRU",
    )

    first = services.prepare_scf(request)
    second = services.prepare_scf(request)

    assert isinstance(first, ForgeErrorEnvelope)
    assert first.error_class == "precondition.missing"
    assert isinstance(second, ForgeErrorEnvelope)
    assert second.error_class == "operation.conflict"
    assert list((tmp_path / "scf" / "reports" / "events").glob("*.json")) == []


def test_missing_explicit_launcher_is_precondition_before_process_start(tmp_path: Path) -> None:
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["NORMAL END"])
    services = ForgeServices.default(
        workspace_root=tmp_path,
        runner=LocalRunner(executable=str(executable), launcher=("missing-launcher",)),
    )
    request = ScfExecuteRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174121", workspace_rel="scf"
    )

    first = services.execute_scf(request)
    second = services.execute_scf(request)

    assert isinstance(first, ForgeErrorEnvelope)
    assert first.error_class == "precondition.missing"
    assert isinstance(second, ForgeErrorEnvelope)
    assert second.error_class == "operation.conflict"
    assert not (tmp_path / "scf" / "forge-result.json").exists()


def test_missing_generated_mpirun_is_precondition_before_process_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["NORMAL END"])
    runner_module = __import__("abacus_forge.runner", fromlist=["runner"])
    original_which = runner_module.shutil.which
    monkeypatch.setattr(
        runner_module.shutil,
        "which",
        lambda name: None if name == "mpirun" else original_which(name),
    )
    services = ForgeServices.default(
        workspace_root=tmp_path,
        runner=LocalRunner(executable=str(executable), mpi_ranks=2),
    )
    request = ScfExecuteRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174122", workspace_rel="scf"
    )

    result = services.execute_scf(request)

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "precondition.missing"
    assert (tmp_path / "scf" / "reports" / "claims" / f"{request.operation_id}.json").exists()


@pytest.mark.parametrize(
    ("blocked_name", "blocked_kind"),
    [
        ("reports", "file"),
        ("reports/.forge-operation.lock", "directory"),
        ("reports/claims", "file"),
        ("reports/events", "file"),
    ],
)
def test_audit_infrastructure_io_is_persistence_error(
    tmp_path: Path, blocked_name: str, blocked_kind: str
) -> None:
    workspace_root = tmp_path / "scf"
    workspace_root.mkdir()
    blocked = workspace_root / blocked_name
    if blocked_kind == "directory":
        blocked.mkdir(parents=True)
    else:
        blocked.parent.mkdir(parents=True, exist_ok=True)
        blocked.write_text("blocked", encoding="utf-8")

    result = ForgeServices.default(workspace_root=tmp_path).execute_scf(
        ScfExecuteRequest(
            operation_id="123e4567-e89b-42d3-a456-426614174123",
            workspace_rel="scf",
            dry_run=True,
        )
    )

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "persistence.failure"


def test_execute_provenance_has_unique_runtime_facts(tmp_path: Path) -> None:
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["NORMAL END"])
    request = ScfExecuteRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174124", workspace_rel="scf"
    )
    result = ForgeServices.default(
        workspace_root=tmp_path,
        runner=LocalRunner(executable=str(executable), omp_threads=4),
    ).execute_scf(request)

    assert isinstance(result, OperationOutcome)
    stages = {artifact.path_rel: artifact.stage for artifact in result.envelope.artifacts}
    assert stages["outputs/stdout.log"] == "execute"
    assert stages["outputs/stderr.log"] == "execute"
    metric_kinds = {metric.name: metric.kind for metric in result.envelope.metrics}
    assert metric_kinds["returncode"] == "runtime"
    assert metric_kinds["omp_threads"] == "runtime"
    observations_by_name = {observation.name: observation for observation in result.observations}
    assert len(observations_by_name) == len(result.observations)
    assert observations_by_name["returncode"].source == "runtime"
    assert sum(observation.name == "returncode" for observation in result.observations) == 1
    event = json.loads(
        (tmp_path / "scf" / "reports" / "events" / f"{request.operation_id}-execute.json").read_text()
    )
    assert event["payload"] == result.to_dict()
