from __future__ import annotations

import pytest
import fcntl
import hashlib
import os
from pathlib import Path
import json
import signal
import stat
import sys
import threading
import time

import abacus_forge
from ase import Atoms
from ase.io import write as ase_write
from abacus_forge import (
    CollectService,
    ExecuteService,
    ForgeErrorEnvelope,
    ForgeResultEnvelope,
    ForgeServices,
    LocalRunner,
    ModifyService,
    OperationOutcome,
    PrepareService,
    RelaxServiceSet,
    ScfServiceSet,
    Workspace,
)
from abacus_forge.contracts import ScfCollectRequest, ScfExecuteRequest, ScfModifyRequest, ScfPrepareRequest
from abacus_forge.errors import ForgeRequestError
from abacus_forge.input_io import read_input
from abacus_forge.relax_contracts import RelaxCollectRequest, RelaxExecuteRequest, RelaxModifyRequest, RelaxPrepareRequest
from abacus_forge.result import RunResult
from tests.support.fake_executables import write_fake_abacus


def _prepared_scf_workspace_with_log(tmp_path: Path, content: str) -> Path:
    workspace = Workspace(tmp_path / "scf")
    workspace.ensure_layout()
    _write_prepared_inputs(workspace)
    (workspace.outputs_dir / "stdout.log").write_text(content + "\n", encoding="utf-8")
    return workspace.root


def _write_prepared_inputs(workspace: Workspace) -> None:
    (workspace.inputs_dir / "INPUT").write_text(
        "INPUT_PARAMETERS\ncalculation scf\n", encoding="utf-8"
    )
    for input_name in ("STRU", "KPT"):
        (workspace.inputs_dir / input_name).write_text("prepared\n", encoding="utf-8")


def _relax_source(workspace: Workspace) -> Path:
    source = workspace.root / "source.STRU"
    source.write_text(
        abacus_forge.AbacusStructure(
            Atoms("Si", positions=[[0.0, 0.0, 0.0]], cell=[4.0, 4.0, 4.0], pbc=True),
            source_format="ase",
        ).to_stru(),
        encoding="utf-8",
    )
    return source


def _prepare_relax_workspace(tmp_path: Path, capability: str = "relax") -> tuple[RelaxServiceSet, Workspace]:
    workspace = Workspace(tmp_path / capability)
    workspace.ensure_layout()
    source = _relax_source(workspace)
    services = RelaxServiceSet.default(workspace_root=tmp_path)
    result = services.prepare.prepare(
        _request(
            RelaxPrepareRequest,
            capability,
            f"123e4567-e89b-42d3-a456-426614174{130 if capability == 'relax' else 131}",
            structure_path_rel=source.name,
            parameters={"ecutwfc": 80},
            capability=capability,
        )
    )
    assert isinstance(result, OperationOutcome)
    return services, workspace


def _write_relax_collection_workspace(
    tmp_path: Path,
    *,
    capability: str = "relax",
    log_text: str | None = "TOTAL ENERGY = -4.2\n",
    final_structure: str | None = "stru",
    relax_report: dict[str, object] | None = None,
    report_json_text: str | None = None,
    input_calculation: str | None = None,
) -> Workspace:
    workspace = Workspace(tmp_path / "collection")
    workspace.ensure_layout()
    structure = Atoms("Si", positions=[[0.0, 0.0, 0.0]], cell=[4.0, 4.0, 4.0], pbc=True)
    structure_payload = abacus_forge.AbacusStructure(structure, source_format="ase").to_stru()
    calculation = input_calculation if input_calculation is not None else capability
    workspace.write_text("inputs/INPUT", f"INPUT_PARAMETERS\ncalculation {calculation}\n")
    workspace.write_text("inputs/STRU", structure_payload)
    workspace.write_text("inputs/KPT", "K_POINTS\n0\nGamma\n1 1 1 0 0 0\n")
    output_dir = workspace.outputs_dir / "OUT.ABACUS"
    output_dir.mkdir(parents=True, exist_ok=True)
    if log_text is not None:
        (output_dir / f"running_{capability}.log").write_text(log_text, encoding="utf-8")
    if final_structure == "stru":
        (output_dir / "STRU_ION_D").write_text(structure_payload, encoding="utf-8")
    elif final_structure == "cif":
        ase_write(output_dir / "STRU_NOW.cif", structure, format="cif")
    elif final_structure == "invalid":
        (output_dir / "STRU_ION_D").write_text("not an ABACUS structure\n", encoding="utf-8")
    if relax_report is not None:
        workspace.write_json("reports/metrics_relax.json", relax_report)
    if report_json_text is not None:
        workspace.write_text("reports/metrics_relax.json", report_json_text)
    return workspace


class _RecordingRunnerFactory:
    def __init__(self, executable: Path) -> None:
        self.executable = executable
        self.calls: list[dict[str, object]] = []

    def __call__(self, **kwargs: object) -> LocalRunner:
        self.calls.append(dict(kwargs))
        # Avoid requiring an MPI installation while still exercising the
        # request's mpi_ranks mapping.
        return LocalRunner(launcher=("true",), **kwargs)  # type: ignore[arg-type]


def test_narrow_services_use_runtime_protocols_and_map_execute_request_once(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "scf")
    workspace.ensure_layout()
    _write_prepared_inputs(workspace)
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["NORMAL END"])
    factory = _RecordingRunnerFactory(executable)
    services = ScfServiceSet.default(workspace_root=tmp_path, runner_factory=factory)

    assert isinstance(services.prepare, PrepareService)
    assert isinstance(services.modify, ModifyService)
    assert isinstance(services.execute, ExecuteService)
    assert isinstance(services.collect, CollectService)
    request = ScfExecuteRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174117",
        workspace_rel="scf",
        executable=str(executable),
        mpi_ranks=3,
        omp_threads=5,
        timeout_seconds=12.5,
    )

    result = services.execute.execute(request)

    assert isinstance(result, OperationOutcome)
    assert factory.calls == [{
        "executable": str(executable),
        "mpi_ranks": 3,
        "omp_threads": 5,
        "timeout_seconds": 12.5,
    }]


def test_typed_execute_runs_relative_path_executable_resolved_from_process_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A directory-qualified relative executable uses the caller's cwd at run time."""
    monkeypatch.chdir(tmp_path)
    workspace = Workspace(tmp_path / "workspace")
    workspace.ensure_layout()
    _write_prepared_inputs(workspace)
    (tmp_path / "bin").mkdir()
    write_fake_abacus(tmp_path / "bin" / "fake-abacus", stdout_lines=["NORMAL END"])

    request = ScfExecuteRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174119",
        workspace_rel="workspace",
        executable="bin/fake-abacus",
    )
    result = ScfServiceSet.default(workspace_root=tmp_path).execute.execute(request)

    assert isinstance(result, OperationOutcome)
    assert result.status.execution == "completed"
    assert result.envelope.diagnostics["failure_class"] == "none"
    assert "NORMAL END" in (workspace.outputs_dir / "stdout.log").read_text(encoding="utf-8")
    assert json.loads((workspace.root / "forge-result.json").read_text(encoding="utf-8"))["command"] == [
        "bin/fake-abacus"
    ]


def test_local_runner_runs_relative_path_launcher_and_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = Workspace(tmp_path / "workspace")
    workspace.ensure_layout()
    _write_prepared_inputs(workspace)
    (tmp_path / "bin").mkdir()
    write_fake_abacus(tmp_path / "bin" / "fake-abacus", stdout_lines=["NORMAL END"])
    launcher = tmp_path / "bin" / "launcher"
    launcher.write_text(
        f"#!{sys.executable}\nimport os\nimport sys\nos.execv(sys.argv[1], sys.argv[1:])\n",
        encoding="utf-8",
    )
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)

    result = LocalRunner(executable="bin/fake-abacus", launcher=("bin/launcher",)).run(workspace)

    assert result.status == "completed"
    assert result.returncode == 0
    assert "NORMAL END" in (workspace.outputs_dir / "stdout.log").read_text(encoding="utf-8")


def test_local_runner_resolves_basename_from_relative_override_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = Workspace(tmp_path / "workspace")
    workspace.ensure_layout()
    _write_prepared_inputs(workspace)
    (tmp_path / "bin").mkdir()
    write_fake_abacus(tmp_path / "bin" / "fake-abacus", stdout_lines=["NORMAL END"])

    result = LocalRunner(
        executable="fake-abacus",
        env_overrides={"PATH": os.pathsep.join(("bin", str(Path(sys.executable).parent)))},
    ).run(workspace)

    assert result.status == "completed"
    assert result.returncode == 0
    assert "NORMAL END" in (workspace.outputs_dir / "stdout.log").read_text(encoding="utf-8")
    assert result.command == ["fake-abacus"]


def test_local_runner_resolves_empty_path_component_from_process_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = Workspace(tmp_path / "workspace")
    workspace.ensure_layout()
    _write_prepared_inputs(workspace)
    write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["CALLER CWD"])
    write_fake_abacus(workspace.inputs_dir / "fake-abacus", stdout_lines=["WORKSPACE CWD"])

    result = LocalRunner(
        executable="fake-abacus",
        env_overrides={"PATH": os.pathsep.join(("", str(Path(sys.executable).parent)))},
    ).run(workspace)

    assert result.status == "completed"
    assert (workspace.outputs_dir / "stdout.log").read_text(encoding="utf-8").strip() == "CALLER CWD"


def test_local_runner_preserves_symlink_lexical_parent_for_relative_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = Workspace(tmp_path / "workspace")
    workspace.ensure_layout()
    _write_prepared_inputs(workspace)
    (tmp_path / "real" / "sub").mkdir(parents=True)
    (tmp_path / "link").symlink_to(tmp_path / "real" / "sub", target_is_directory=True)
    write_fake_abacus(tmp_path / "real" / "fake-abacus", stdout_lines=["LEXICAL TARGET"])
    write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["NORMALIZED TARGET"])

    result = LocalRunner(executable="link/../fake-abacus").run(workspace)

    assert result.status == "completed"
    assert (workspace.outputs_dir / "stdout.log").read_text(encoding="utf-8").strip() == "LEXICAL TARGET"
    assert result.command == ["link/../fake-abacus"]

def test_local_runner_preserves_relative_symlink_argv_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = Workspace(tmp_path / "workspace")
    workspace.ensure_layout()
    _write_prepared_inputs(workspace)
    (tmp_path / "bin").mkdir()
    target = tmp_path / "bin" / "target-abacus"
    target.write_text(f"#!{sys.executable}\nimport sys\nprint(sys.argv[0])\n", encoding="utf-8")
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    link = tmp_path / "bin" / "link-abacus"
    link.symlink_to(target)

    result = LocalRunner(executable="bin/link-abacus").run(workspace)

    assert result.status == "completed"
    assert result.returncode == 0
    assert (workspace.outputs_dir / "stdout.log").read_text(encoding="utf-8").strip() == str(link)
    assert result.command == ["bin/link-abacus"]


def test_local_runner_treats_dot_slash_engine_as_explicit_path_with_absolute_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = Workspace(tmp_path / "workspace")
    workspace.ensure_layout()
    _write_prepared_inputs(workspace)
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["DOT ENGINE"])

    result = LocalRunner(
        executable="./fake-abacus",
        env_overrides={"PATH": str(Path(sys.executable).parent)},
    ).run(workspace)

    assert result.status == "completed"
    assert result.returncode == 0
    assert (workspace.outputs_dir / "stdout.log").read_text(encoding="utf-8").strip() == "DOT ENGINE"
    assert result.command == ["./fake-abacus"]
    assert executable.exists()


def test_local_runner_treats_dot_slash_launcher_as_explicit_path_with_mixed_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = Workspace(tmp_path / "workspace")
    workspace.ensure_layout()
    _write_prepared_inputs(workspace)
    write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["DOT LAUNCHER"])
    launcher = tmp_path / "launcher"
    launcher.write_text(
        f"#!{sys.executable}\nimport os\nimport sys\nos.execv(sys.argv[1], sys.argv[1:])\n",
        encoding="utf-8",
    )
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)

    result = LocalRunner(
        executable="./fake-abacus",
        launcher=("./launcher",),
        env_overrides={"PATH": os.pathsep.join((str(Path(sys.executable).parent), "relative-bin"))},
    ).run(workspace)

    assert result.status == "completed"
    assert result.returncode == 0
    assert (workspace.outputs_dir / "stdout.log").read_text(encoding="utf-8").strip() == "DOT LAUNCHER"
    assert result.command == ["./launcher", "./fake-abacus"]

def test_relax_service_set_exposes_typed_operations(tmp_path: Path) -> None:
    service_set_type = getattr(abacus_forge, "RelaxServiceSet", None)
    assert service_set_type is not None
    services = service_set_type.default(workspace_root=tmp_path)
    assert all(hasattr(services, name) for name in ("prepare", "modify", "execute", "collect"))


@pytest.mark.parametrize("capability", ["relax", "cell-relax"])
def test_relax_prepare_and_modify_use_capability_profile_and_snapshots(
    tmp_path: Path, capability: str
) -> None:
    services, workspace = _prepare_relax_workspace(tmp_path, capability)
    input_before = read_input(workspace.inputs_dir / "INPUT")
    assert input_before["calculation"] == capability
    assert json.loads((workspace.root / "forge-unit.json").read_text())[
        "task"
    ] == capability

    request = RelaxModifyRequest(
        operation_id=f"123e4567-e89b-42d3-a456-426614174{140 if capability == 'relax' else 141}",
        workspace_rel=capability,
        input_updates={"ecutwfc": 90},
        capability=capability,
    )
    result = services.modify.modify(request)

    assert isinstance(result, OperationOutcome)
    assert read_input(workspace.inputs_dir / "INPUT")["ecutwfc"] == "90"
    assert result.envelope.diagnostics["task"] == capability
    assert result.envelope.diagnostics["input_snapshot_before"] != result.envelope.diagnostics[
        "input_snapshot_after"
    ]
    event = json.loads(
        (workspace.reports_dir / "events" / f"{request.operation_id}-modify.json").read_text()
    )
    assert event["payload"] == result.to_dict()


def test_scf_modify_direct_service_updates_input_and_persists_facts(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "scf")
    workspace.ensure_layout()
    source = _relax_source(workspace)
    services = ScfServiceSet.default(workspace_root=tmp_path)
    prepared = services.prepare.prepare(
        ScfPrepareRequest(
            operation_id="123e4567-e89b-42d3-a456-426614174142",
            workspace_rel="scf",
            structure_path_rel=source.name,
            parameters={"ecutwfc": 80},
        )
    )
    assert isinstance(prepared, OperationOutcome)

    request = ScfModifyRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174143",
        workspace_rel="scf",
        input_updates={"ecutwfc": 90},
    )
    result = services.modify.modify(request)

    assert isinstance(result, OperationOutcome)
    assert result.operation_id == request.operation_id
    assert result.envelope.workspace_rel == request.workspace_rel
    assert result.envelope.operation == "modify"
    assert result.status.execution == "not_run"
    assert result.status.scientific == "unassessed"
    assert result.status.collection == "not_collected"
    assert read_input(workspace.inputs_dir / "INPUT")["ecutwfc"] == "90"
    diagnostics = result.envelope.diagnostics
    assert diagnostics["changes"]["INPUT"]["updates"] == {"ecutwfc": 90}
    assert diagnostics["input_snapshot_before"] != diagnostics["input_snapshot_after"]
    assert {artifact.path_rel for artifact in result.envelope.artifacts} >= {"inputs/INPUT"}

    event = json.loads(
        (workspace.reports_dir / "events" / f"{request.operation_id}-modify.json").read_text(
            encoding="utf-8"
        )
    )
    assert event["id"] == request.operation_id
    assert event["payload"] == result.to_dict()


@pytest.mark.parametrize("capability", ["relax", "cell-relax"])
def test_relax_execute_dry_run_is_explicit_and_does_not_start_runner(
    tmp_path: Path, capability: str
) -> None:
    class FailRunner:
        def __call__(self, **kwargs: object) -> object:
            raise AssertionError("dry-run must not construct or start a runner")

    services = RelaxServiceSet.default(workspace_root=tmp_path, runner_factory=FailRunner())
    request = RelaxExecuteRequest(
        operation_id=f"123e4567-e89b-42d3-a456-426614174{150 if capability == 'relax' else 151}",
        workspace_rel="job",
        dry_run=True,
        capability=capability,
    )
    result = services.execute.execute(request)

    assert isinstance(result, OperationOutcome)
    assert result.status.execution == "skipped"
    assert result.status.scientific == "unassessed"
    assert result.operation_id == request.operation_id
    payload = json.loads(
        (tmp_path / "job" / "reports" / "events" / f"{request.operation_id}-execute.json").read_text()
    )["payload"]
    assert payload == result.to_dict()
    assert json.loads((tmp_path / "job" / "forge-result.json").read_text())["task"] == capability


@pytest.mark.parametrize("returncode,expected_execution", [(0, "completed"), (7, "failed")])
@pytest.mark.parametrize("capability", ["relax", "cell-relax"])
def test_relax_execute_persists_process_facts_for_each_capability(
    tmp_path: Path,
    returncode: int,
    expected_execution: str,
    capability: str,
) -> None:
    services, workspace = _prepare_relax_workspace(tmp_path, capability)
    executable = write_fake_abacus(
        tmp_path / f"fake-{capability}",
        stdout_lines=["TOTAL ENERGY = -3.2", "NORMAL END"],
        returncode=returncode,
    )
    request = RelaxExecuteRequest(
        operation_id=f"123e4567-e89b-42d3-a456-426614174{160 + returncode + (10 if capability == 'cell-relax' else 0)}",
        workspace_rel=capability,
        executable=str(executable),
        capability=capability,
    )
    result = services.execute.execute(request)

    assert isinstance(result, OperationOutcome)
    assert result.status.execution == expected_execution
    assert result.envelope.diagnostics["failure_class"] == (
        "none" if returncode == 0 else "nonzero_exit"
    )
    assert result.envelope.metrics[0].value == returncode
    assert {artifact.path_rel for artifact in result.envelope.artifacts} >= {
        "outputs/stdout.log",
        "outputs/stderr.log",
    }
    event = json.loads(
        (workspace.reports_dir / "events" / f"{request.operation_id}-execute.json").read_text()
    )
    assert event["payload"] == result.to_dict()


@pytest.mark.parametrize("capability", ["relax", "cell-relax"])
def test_relax_execute_timeout_preserves_process_fact(capability: str, tmp_path: Path) -> None:
    services, workspace = _prepare_relax_workspace(tmp_path, capability)
    executable = tmp_path / "slow-abacus"
    executable.write_text(
        f"#!{sys.executable}\nimport time\ntime.sleep(0.2)\n", encoding="utf-8"
    )
    executable.chmod(executable.stat().st_mode | stat.S_IEXEC)
    request = RelaxExecuteRequest(
        operation_id=f"123e4567-e89b-42d3-a456-426614174{180 if capability == 'relax' else 181}",
        workspace_rel=capability,
        executable=str(executable),
        timeout_seconds=0.02,
        capability=capability,
    )
    result = services.execute.execute(request)

    assert isinstance(result, OperationOutcome)
    assert result.status.execution == "failed"
    assert result.envelope.diagnostics["failure_class"] == "timeout"
    assert result.envelope.diagnostics["termination"] == "timeout"


def test_legacy_forge_services_is_a_serialization_equivalent_shim(tmp_path: Path) -> None:
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["NORMAL END"])
    direct_root = tmp_path / "direct"
    facade_root = tmp_path / "facade"
    for root in (direct_root, facade_root):
        _write_prepared_inputs(Workspace(root / "scf").ensure_layout())
    request = ScfExecuteRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174118", workspace_rel="scf", executable=str(executable)
    )

    direct = ScfServiceSet.default(workspace_root=direct_root).execute.execute(request)
    facade = ForgeServices.default(
        workspace_root=facade_root, runner=LocalRunner(executable=str(executable))
    ).execute_scf(request)

    assert isinstance(direct, OperationOutcome)
    assert isinstance(facade, OperationOutcome)
    assert direct.to_dict() == facade.to_dict()


def test_legacy_facade_injected_runner_takes_precedence_over_request_fields(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "scf").ensure_layout()
    _write_prepared_inputs(workspace)
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["NORMAL END"])
    request = ScfExecuteRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174120",
        workspace_rel="scf",
        executable="request-value-that-must-not-run",
    )
    result = ForgeServices.default(
        workspace_root=tmp_path,
        runner=LocalRunner(executable=str(executable)),
    ).execute_scf(request)

    assert isinstance(result, OperationOutcome)
    assert result.status.execution == "completed"
    assert result.envelope.diagnostics["failure_class"] == "none"


def test_outcome_contains_each_artifact_ref_once(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "scf").ensure_layout()
    (workspace.outputs_dir / "stdout.log").write_text("NORMAL END\n", encoding="utf-8")
    result = ScfServiceSet.default(workspace_root=tmp_path).collect.collect(
        ScfCollectRequest(operation_id="123e4567-e89b-42d3-a456-426614174119", workspace_rel="scf")
    )

    assert isinstance(result, OperationOutcome)
    refs = result.envelope.to_dict()["diagnostics"]["artifact_refs"]
    keys = [(ref["operation_id"], ref["artifact_id"]) for ref in refs]
    assert len(keys) == len(set(keys))


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


def test_typed_execute_reports_current_stdout_normal_end_fact(tmp_path: Path) -> None:
    _write_prepared_inputs(Workspace(tmp_path / "scf").ensure_layout())
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["NORMAL END"])
    result = ForgeServices.default(
        workspace_root=tmp_path,
        runner=LocalRunner(executable=str(executable)),
    ).execute_scf(
        _request(
            ScfExecuteRequest,
            "scf",
            "123e4567-e89b-42d3-a456-426614174034",
        )
    )

    assert isinstance(result, OperationOutcome)
    assert result.envelope.diagnostics["normal_end"] is True
    assert result.envelope.diagnostics["normal_end_source"] == "outputs/stdout.log"
    assert any(
        observation.name == "normal_end" and observation.source == "log"
        for observation in result.observations
    )
    assert "outputs/stdout.log" in {
        artifact.path_rel for artifact in result.envelope.artifacts
    }


def test_typed_execute_reports_changed_native_running_log_and_ignores_stale_log(
    tmp_path: Path,
) -> None:
    workspace = Workspace(tmp_path / "scf").ensure_layout()
    _write_prepared_inputs(workspace)
    running_log = workspace.outputs_dir / "OUT.ABACUS" / "running_scf.log"
    running_log.parent.mkdir(parents=True, exist_ok=True)
    running_log.write_text("previous invocation incomplete\n", encoding="utf-8")
    executable = tmp_path / "runner.py"
    executable.write_text(
        f"#!{sys.executable}\n"
        "from pathlib import Path\n"
        "Path('../outputs/OUT.ABACUS/running_scf.log').write_text('Total  Time  : 1.0 seconds\\n')\n",
        encoding="utf-8",
    )
    executable.chmod(executable.stat().st_mode | stat.S_IEXEC)
    result = ForgeServices.default(
        workspace_root=tmp_path,
        runner=LocalRunner(executable=str(executable)),
    ).execute_scf(
        _request(ScfExecuteRequest, "scf", "123e4567-e89b-42d3-a456-426614174035")
    )

    assert isinstance(result, OperationOutcome)
    assert result.envelope.diagnostics["normal_end"] is True
    assert result.envelope.diagnostics["normal_end_source"] == "outputs/OUT.ABACUS/running_scf.log"
    assert any(
        artifact.path_rel == "outputs/OUT.ABACUS/running_scf.log"
        for artifact in result.envelope.artifacts
    )


def test_typed_execute_omits_old_normal_end_when_log_only_appends_without_marker(
    tmp_path: Path,
) -> None:
    workspace = Workspace(tmp_path / "scf").ensure_layout()
    _write_prepared_inputs(workspace)
    running_log = workspace.outputs_dir / "OUT.ABACUS" / "running_scf.log"
    running_log.parent.mkdir(parents=True, exist_ok=True)
    running_log.write_text("NORMAL END\n", encoding="utf-8")
    executable = tmp_path / "runner.py"
    executable.write_text(
        f"#!{sys.executable}\n"
        "from pathlib import Path\n"
        "with Path('../outputs/OUT.ABACUS/running_scf.log').open('a', encoding='utf-8') as stream:\n"
        "    stream.write('next invocation started, then crashed\\n')\n"
        "raise SystemExit(7)\n",
        encoding="utf-8",
    )
    executable.chmod(executable.stat().st_mode | stat.S_IEXEC)
    result = ForgeServices.default(
        workspace_root=tmp_path,
        runner=LocalRunner(executable=str(executable)),
    ).execute_scf(
        _request(ScfExecuteRequest, "scf", "123e4567-e89b-42d3-a456-426614174046")
    )

    assert isinstance(result, OperationOutcome)
    assert result.envelope.diagnostics["failure_class"] == "nonzero_exit"
    assert "normal_end" not in result.envelope.diagnostics


def test_typed_execute_omits_old_normal_end_when_growing_log_rewrites_prefix(
    tmp_path: Path,
) -> None:
    workspace = Workspace(tmp_path / "scf").ensure_layout()
    _write_prepared_inputs(workspace)
    running_log = workspace.outputs_dir / "OUT.ABACUS" / "running_scf.log"
    running_log.parent.mkdir(parents=True, exist_ok=True)
    running_log.write_text("AAA\nNORMAL END\n", encoding="utf-8")
    executable = tmp_path / "runner.py"
    executable.write_text(
        f"#!{sys.executable}\n"
        "from pathlib import Path\n"
        "Path('../outputs/OUT.ABACUS/running_scf.log').write_text('BBB\\nNORMAL END\\ncrashed\\n', encoding='utf-8')\n"
        "raise SystemExit(7)\n",
        encoding="utf-8",
    )
    executable.chmod(executable.stat().st_mode | stat.S_IEXEC)
    result = ForgeServices.default(
        workspace_root=tmp_path,
        runner=LocalRunner(executable=str(executable)),
    ).execute_scf(
        _request(ScfExecuteRequest, "scf", "123e4567-e89b-42d3-a456-426614174048")
    )

    assert isinstance(result, OperationOutcome)
    assert result.envelope.diagnostics["failure_class"] == "nonzero_exit"
    assert "normal_end" not in result.envelope.diagnostics


def test_typed_execute_omits_old_normal_end_when_log_is_truncated(
    tmp_path: Path,
) -> None:
    workspace = Workspace(tmp_path / "scf").ensure_layout()
    _write_prepared_inputs(workspace)
    running_log = workspace.outputs_dir / "OUT.ABACUS" / "running_scf.log"
    running_log.parent.mkdir(parents=True, exist_ok=True)
    running_log.write_text("NORMAL END\nstale tail\n", encoding="utf-8")
    executable = tmp_path / "runner.py"
    executable.write_text(
        f"#!{sys.executable}\n"
        "from pathlib import Path\n"
        "Path('../outputs/OUT.ABACUS/running_scf.log').write_text('NORMAL END\\n', encoding='utf-8')\n"
        "raise SystemExit(7)\n",
        encoding="utf-8",
    )
    executable.chmod(executable.stat().st_mode | stat.S_IEXEC)
    result = ForgeServices.default(
        workspace_root=tmp_path,
        runner=LocalRunner(executable=str(executable)),
    ).execute_scf(
        _request(ScfExecuteRequest, "scf", "123e4567-e89b-42d3-a456-426614174047")
    )

    assert isinstance(result, OperationOutcome)
    assert result.envelope.diagnostics["failure_class"] == "nonzero_exit"
    assert "normal_end" not in result.envelope.diagnostics


def test_typed_execute_omits_stale_normal_end_and_keeps_nonzero_independent(
    tmp_path: Path,
) -> None:
    workspace = Workspace(tmp_path / "scf").ensure_layout()
    _write_prepared_inputs(workspace)
    running_log = workspace.outputs_dir / "OUT.ABACUS" / "running_scf.log"
    running_log.parent.mkdir(parents=True, exist_ok=True)
    running_log.write_text("NORMAL END\n", encoding="utf-8")
    executable = tmp_path / "runner.py"
    executable.write_text(f"#!{sys.executable}\nraise SystemExit(7)\n", encoding="utf-8")
    executable.chmod(executable.stat().st_mode | stat.S_IEXEC)
    result = ForgeServices.default(
        workspace_root=tmp_path,
        runner=LocalRunner(executable=str(executable)),
    ).execute_scf(
        _request(ScfExecuteRequest, "scf", "123e4567-e89b-42d3-a456-426614174036")
    )

    assert isinstance(result, OperationOutcome)
    assert result.envelope.diagnostics["failure_class"] == "nonzero_exit"
    assert "normal_end" not in result.envelope.diagnostics


def test_typed_execute_ignores_touch_only_stale_running_log(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "scf").ensure_layout()
    _write_prepared_inputs(workspace)
    running_log = workspace.outputs_dir / "OUT.ABACUS" / "running_scf.log"
    running_log.parent.mkdir(parents=True, exist_ok=True)
    running_log.write_text("NORMAL END\n", encoding="utf-8")
    executable = tmp_path / "runner.py"
    executable.write_text(
        f"#!{sys.executable}\nfrom pathlib import Path\n"
        "Path('../outputs/OUT.ABACUS/running_scf.log').touch()\nraise SystemExit(7)\n",
        encoding="utf-8",
    )
    executable.chmod(executable.stat().st_mode | stat.S_IEXEC)
    result = ForgeServices.default(workspace_root=tmp_path, runner=LocalRunner(executable=str(executable))).execute_scf(
        _request(ScfExecuteRequest, "scf", "123e4567-e89b-42d3-a456-426614174044")
    )
    assert isinstance(result, OperationOutcome)
    assert result.envelope.diagnostics["failure_class"] == "nonzero_exit"
    assert "normal_end" not in result.envelope.diagnostics


def test_typed_execute_detects_same_size_running_log_rewrite(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "scf").ensure_layout()
    _write_prepared_inputs(workspace)
    running_log = workspace.outputs_dir / "OUT.ABACUS" / "running_scf.log"
    running_log.parent.mkdir(parents=True, exist_ok=True)
    running_log.write_text("XXXXXXXXXX\n", encoding="utf-8")
    size_before = running_log.stat().st_size
    executable = tmp_path / "runner.py"
    executable.write_text(
        f"#!{sys.executable}\nfrom pathlib import Path\n"
        "Path('../outputs/OUT.ABACUS/running_scf.log').write_text('NORMAL END\\n')\n",
        encoding="utf-8",
    )
    executable.chmod(executable.stat().st_mode | stat.S_IEXEC)
    result = ForgeServices.default(workspace_root=tmp_path, runner=LocalRunner(executable=str(executable))).execute_scf(
        _request(ScfExecuteRequest, "scf", "123e4567-e89b-42d3-a456-426614174045")
    )
    assert isinstance(result, OperationOutcome)
    assert result.envelope.diagnostics["normal_end"] is True
    assert running_log.stat().st_size == size_before


def test_typed_execute_keeps_normal_end_when_process_exits_nonzero(tmp_path: Path) -> None:
    _write_prepared_inputs(Workspace(tmp_path / "scf").ensure_layout())
    executable = tmp_path / "runner.py"
    executable.write_text(f"#!{sys.executable}\nprint('NORMAL END')\nraise SystemExit(7)\n", encoding="utf-8")
    executable.chmod(executable.stat().st_mode | stat.S_IEXEC)
    result = ForgeServices.default(
        workspace_root=tmp_path,
        runner=LocalRunner(executable=str(executable)),
    ).execute_scf(_request(ScfExecuteRequest, "scf", "123e4567-e89b-42d3-a456-426614174037"))
    assert isinstance(result, OperationOutcome)
    assert result.envelope.diagnostics["failure_class"] == "nonzero_exit"
    assert result.envelope.diagnostics["normal_end"] is True


def test_typed_execute_omits_ambiguous_changed_running_logs(tmp_path: Path) -> None:
    _write_prepared_inputs(Workspace(tmp_path / "scf").ensure_layout())
    executable = tmp_path / "runner.py"
    executable.write_text(
        f"#!{sys.executable}\nfrom pathlib import Path\n"
        "base = Path('../outputs/OUT.ABACUS'); base.mkdir(parents=True, exist_ok=True)\n"
        "for name in ('running_scf.log', 'running_relax.log'): (base / name).write_text('Total  Time  : 1\\n')\n",
        encoding="utf-8",
    )
    executable.chmod(executable.stat().st_mode | stat.S_IEXEC)
    result = ForgeServices.default(workspace_root=tmp_path, runner=LocalRunner(executable=str(executable))).execute_scf(
        _request(ScfExecuteRequest, "scf", "123e4567-e89b-42d3-a456-426614174038")
    )
    assert isinstance(result, OperationOutcome)
    assert "normal_end" not in result.envelope.diagnostics


@pytest.mark.parametrize("source_kind", ["escaped", "symlink", "missing", "directory"])
def test_typed_execute_invalid_normal_end_source_preserves_execute_outcome(
    tmp_path: Path, source_kind: str
) -> None:
    workspace = Workspace(tmp_path / "scf").ensure_layout()
    _write_prepared_inputs(workspace)
    stdout = workspace.outputs_dir / "stdout.log"
    stderr = workspace.outputs_dir / "stderr.log"
    source = tmp_path / "outside.log" if source_kind == "escaped" else workspace.outputs_dir / f"{source_kind}.log"
    if source_kind == "symlink":
        source.symlink_to(tmp_path / "outside.log")
    elif source_kind == "directory":
        source.mkdir()
    elif source_kind != "missing":
        source.write_text("NORMAL END\n", encoding="utf-8")

    class SidecarRunner:
        def run(self, current_workspace: Workspace) -> RunResult:
            stdout.write_text("done\n", encoding="utf-8")
            stderr.write_text("", encoding="utf-8")
            return RunResult(current_workspace.root, ["fake"], 0, "completed", stdout, stderr, 1, {}, True, source)

    result = ForgeServices.default(workspace_root=tmp_path, runner=SidecarRunner()).execute_scf(
        _request(ScfExecuteRequest, "scf", f"123e4567-e89b-42d3-a456-4266141740{39 + ['escaped','symlink','missing','directory'].index(source_kind)}")
    )
    assert isinstance(result, OperationOutcome)
    assert result.envelope.status.execution == "completed"
    assert "normal_end" not in result.envelope.diagnostics


def test_typed_stdout_normal_end_reuses_single_stdout_artifact(tmp_path: Path) -> None:
    _write_prepared_inputs(Workspace(tmp_path / "scf").ensure_layout())
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["NORMAL END"])
    result = ForgeServices.default(workspace_root=tmp_path, runner=LocalRunner(executable=str(executable))).execute_scf(
        _request(ScfExecuteRequest, "scf", "123e4567-e89b-42d3-a456-426614174043")
    )
    assert isinstance(result, OperationOutcome)
    assert sum(item.path_rel == "outputs/stdout.log" for item in result.envelope.artifacts) == 1


def test_legacy_run_result_serialization_excludes_normal_end_sidecar(tmp_path: Path) -> None:
    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
    result = RunResult(tmp_path, ["fake"], 0, "completed", stdout, stderr, 1, {}, True, tmp_path / "normal.log")
    assert set(result.to_dict()) == {"workspace", "command", "returncode", "status", "stdout_path", "stderr_path", "omp_threads", "diagnostics"}
    assert "normal_end" not in result.to_envelope().to_dict()["diagnostics"]


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
    _write_prepared_inputs(Workspace(tmp_path / "scf").ensure_layout())
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
    expected_diagnostics = {"dry_run": True, "artifact_refs": []}
    assert result.envelope.to_dict()["diagnostics"] == expected_diagnostics
    event = json.loads(
        (tmp_path / "scf" / "reports" / "events" / f"{result.operation_id}-execute.json").read_text()
    )
    assert event["payload"]["envelope"]["diagnostics"] == expected_diagnostics


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
    calls = {name: 0 for name in ("prepare_with_assets", "modify_input", "collect")}
    for name in calls:
        original = getattr(services_module, name)

        def counted(*args, _name=name, _original=original, **kwargs):
            calls[_name] += 1
            return _original(*args, **kwargs)

        monkeypatch.setattr(services_module, name, counted)

    runner_calls = 0
    original_run = LocalRunner.run

    def counted_run(self, *args, **kwargs):
        nonlocal runner_calls
        runner_calls += 1
        return original_run(self, *args, **kwargs)

    monkeypatch.setattr(LocalRunner, "run", counted_run)
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
    expected_manifest = {
        "kind": "abacus-forge.unit", "task": "scf", "unit": "default",
        "engine": "abacus", "prepared": True, "source_workdir": None, "metadata": {},
    }
    manifest_path = structure.parent / "forge-unit.json"
    assert json.loads(manifest_path.read_text()) == expected_manifest
    assert manifest_path.read_bytes() == json.dumps(
        expected_manifest, indent=2, sort_keys=True
    ).encode("utf-8")
    assert prepared.envelope.to_dict()["diagnostics"]["asset_materialization"] == []
    assert json.loads((structure.parent / "meta.json").read_text())["metadata"] == {"unit": "default"}
    modified = services.modify_scf(
        _request(ScfModifyRequest, "scf", modify_id, input_updates={"ecutwfc": 90})
    )
    assert read_input(structure.parent / "inputs/INPUT")["ecutwfc"] == "90"
    assert json.loads((structure.parent / "forge-result.json").read_text()) == {
        "step": "modify", "workspace": str(structure.parent), "task": "scf",
        "unit": "default", "engine": "abacus", "status": "completed",
        "modified_files": ["INPUT"],
        "changes": {"INPUT": {"updates": {"ecutwfc": 90}, "removed": []}},
    }
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
    assert calls == {"prepare_with_assets": 1, "modify_input": 1, "collect": 1}
    assert runner_calls == 1
    assert next(metric.value for metric in collected.envelope.metrics if metric.name == "total_energy") == -3.2


def test_typed_scf_service_returns_structured_error_without_event(tmp_path: Path) -> None:
    services = ForgeServices.default(workspace_root=tmp_path)
    result = services.execute_scf(object())
    assert isinstance(result, ForgeErrorEnvelope)
    assert result.operation_id is None
    assert result.workspace_rel is None


@pytest.mark.parametrize(
    "method_name",
    [
        "prepare_scf",
        "modify_scf",
        "execute_scf",
        "collect_scf",
    ],
)
def test_typed_scf_services_do_not_copy_context_from_wrong_request_type(
    tmp_path: Path,
    method_name: str,
) -> None:
    class ForeignRequest:
        operation_id = "bad"
        workspace_rel = "../bad"

    result = getattr(ForgeServices.default(workspace_root=tmp_path), method_name)(ForeignRequest())

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.invalid"
    assert result.operation_id is None
    assert result.workspace_rel is None


@pytest.mark.parametrize(
    ("method_name", "typed_request", "missing_path", "operation_id"),
    [
        (
            "modify_scf",
            ScfModifyRequest(
                operation_id="123e4567-e89b-42d3-a456-426614174211",
                workspace_rel="scf",
                input_updates={"ecutwfc": 90},
            ),
            "inputs/INPUT",
            "123e4567-e89b-42d3-a456-426614174211",
        ),
        (
            "execute_scf",
            ScfExecuteRequest(
                operation_id="123e4567-e89b-42d3-a456-426614174212",
                workspace_rel="scf",
            ),
            "inputs/INPUT",
            "123e4567-e89b-42d3-a456-426614174212",
        ),
        (
            "execute_scf",
            ScfExecuteRequest(
                operation_id="123e4567-e89b-42d3-a456-426614174213",
                workspace_rel="scf",
            ),
            "inputs/STRU",
            "123e4567-e89b-42d3-a456-426614174213",
        ),
        (
            "execute_scf",
            ScfExecuteRequest(
                operation_id="123e4567-e89b-42d3-a456-426614174214",
                workspace_rel="scf",
            ),
            "inputs/KPT",
            "123e4567-e89b-42d3-a456-426614174214",
        ),
    ],
)
def test_typed_scf_missing_inputs_are_admitted_preconditions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    typed_request: ScfModifyRequest | ScfExecuteRequest,
    missing_path: str,
    operation_id: str,
) -> None:
    workspace = Workspace(tmp_path / "scf")
    workspace.ensure_layout()
    for relative_path in ("inputs/INPUT", "inputs/STRU", "inputs/KPT"):
        if relative_path != missing_path:
            (workspace.root / relative_path).write_text("prepared\n", encoding="utf-8")

    services_module = __import__("abacus_forge.services", fromlist=["services"])

    def fail_modify(*args, **kwargs):
        raise AssertionError("missing-input precondition must stop before modify primitive")

    monkeypatch.setattr(services_module, "modify_input", fail_modify)

    class FailRunner:
        def preflight(self, workspace):
            raise AssertionError("missing-input precondition must stop before runner preflight")

        def run(self, workspace):
            raise AssertionError("missing-input precondition must stop before runner")

    services = ForgeServices.default(workspace_root=tmp_path, runner=FailRunner())  # type: ignore[arg-type]
    first = getattr(services, method_name)(typed_request)

    assert isinstance(first, ForgeErrorEnvelope)
    assert first.error_class == "precondition.missing"
    assert (workspace.reports_dir / "claims" / f"{operation_id}.json").exists()
    assert not list((workspace.reports_dir / "events").glob(f"{operation_id}-*.json"))

    second = getattr(services, method_name)(typed_request)
    assert isinstance(second, ForgeErrorEnvelope)
    assert second.error_class == "operation.conflict"


def test_typed_scf_internal_failure_returns_error_without_caller_event(tmp_path: Path) -> None:
    class FailingRunner:
        def run(self, workspace):
            raise RuntimeError("runner fixture failed")

    workspace = abacus_forge.Workspace(tmp_path / "scf")
    workspace.ensure_layout()
    _write_prepared_inputs(workspace)
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
    _write_prepared_inputs(workspace)
    (workspace.outputs_dir / "running_scf.log").write_text("SCF CONVERGED\nNORMAL END\n", encoding="utf-8")
    execute_id = "123e4567-e89b-42d3-a456-426614174009"
    collect_id = "123e4567-e89b-42d3-a456-426614174010"
    services.execute_scf(_request(ScfExecuteRequest, "scf", execute_id))
    collected = services.collect_scf(_request(ScfCollectRequest, "scf", collect_id))
    assert isinstance(collected, OperationOutcome)
    assert collected.status.execution == "not_run"


def test_typed_execute_duplicate_request_id_runs_once_and_returns_conflict(tmp_path: Path) -> None:
    _write_prepared_inputs(Workspace(tmp_path / "scf").ensure_layout())
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
    _write_prepared_inputs(Workspace(tmp_path / "scf").ensure_layout())
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
    _write_prepared_inputs(Workspace(tmp_path / "scf").ensure_layout())
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
    _write_prepared_inputs(Workspace(tmp_path / "scf").ensure_layout())
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
    _write_prepared_inputs(Workspace(tmp_path / "scf").ensure_layout())
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
    services = ForgeServices.default(workspace_root=tmp_path)
    request = _request(ScfExecuteRequest, "scf", "123e4567-e89b-42d3-a456-426614174030", dry_run=True)
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


def test_typed_prepare_asset_fields_reach_service_precondition_validation(tmp_path: Path) -> None:
    request = ScfPrepareRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174230",
        workspace_rel="scf",
        structure_path_rel="missing.STRU",
        pseudo_sources={"Si": "missing.upf"},
        orbital_sources={"Si": "missing.orb"},
        asset_mode="copy",
    )

    result = ForgeServices.default(workspace_root=tmp_path).prepare_scf(request)

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "precondition.missing"
    assert result.operation_id == request.operation_id
    assert result.workspace_rel == request.workspace_rel


_SI_O_TYPED_STRU = (
    "ATOMIC_SPECIES\n"
    "Si 28.085500 Si.source.upf\n"
    "O 15.999000 O.source.upf\n\n"
    "NUMERICAL_ORBITAL\n"
    "Si.source.orb\n"
    "O.source.orb\n\n"
    "LATTICE_CONSTANT\n1.0\n"
    "LATTICE_CONSTANT_UNIT\nAngstrom\n\n"
    "LATTICE_VECTORS\n"
    "4 0 0\n0 4 0\n0 0 4\n\n"
    "ATOMIC_POSITIONS\nDirect\n"
    "Si\n0\n1\n0 0 0 m 1 1 1\n"
    "O\n0\n1\n0.5 0.5 0.5 m 1 1 1\n"
)


def _typed_si_o_fixture(root: Path, workspace_rel: str = "scf") -> Path:
    workspace = root / workspace_rel
    workspace.mkdir(parents=True, exist_ok=True)
    source = workspace / "source.STRU"
    source.write_text(_SI_O_TYPED_STRU, encoding="utf-8")
    return source


def _external_typed_assets(root: Path) -> dict[str, Path]:
    external = root.parent / f"{root.name}-external-assets"
    external.mkdir(parents=True, exist_ok=True)
    assets = {
        "Si_upf": external / "Si.external.upf",
        "O_upf": external / "O.external.upf",
        "Si_orb": external / "Si.external.orb",
        "O_orb": external / "O.external.orb",
    }
    for name, path in assets.items():
        path.write_bytes(f"{name} bytes\n".encode("utf-8"))
    return assets


def test_typed_prepare_materializes_external_assets_and_persists_provenance(
    tmp_path: Path,
) -> None:
    _typed_si_o_fixture(tmp_path)
    assets = _external_typed_assets(tmp_path)
    request = ScfPrepareRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174231",
        workspace_rel="scf",
        structure_path_rel="source.STRU",
        pseudo_sources={"Si": str(assets["Si_upf"]), "O": str(assets["O_upf"])},
        orbital_sources={"Si": str(assets["Si_orb"]), "O": str(assets["O_orb"])},
    )

    result = ScfServiceSet.default(workspace_root=tmp_path).prepare.prepare(request)

    assert isinstance(result, OperationOutcome)
    workspace = tmp_path / "scf"
    stru = (workspace / "inputs/STRU").read_text(encoding="utf-8")
    assert "Si 28.085500 Si.external.upf" in stru
    assert "O 15.999000 O.external.upf" in stru
    assert "Si.external.orb" in stru
    assert "O.external.orb" in stru
    provenance = result.envelope.to_dict()["diagnostics"]["asset_materialization"]
    assert isinstance(provenance, list)
    assert [item["destination"] for item in provenance] == [
        "inputs/Si.external.upf",
        "inputs/O.external.upf",
        "inputs/Si.external.orb",
        "inputs/O.external.orb",
    ]
    assert all(item["mode"] == "copy" for item in provenance)
    for item in provenance:
        source = Path(item["source"])
        destination = workspace / item["destination"]
        assert source.read_bytes() == destination.read_bytes()
        assert item["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
        assert item["destination_sha256"] == hashlib.sha256(destination.read_bytes()).hexdigest()
        artifact = next(record for record in result.envelope.artifacts if record.path_rel == item["destination"])
        assert artifact.sha256 == item["destination_sha256"]

    manifest = json.loads((workspace / "forge-unit.json").read_text(encoding="utf-8"))
    assert manifest["metadata"]["asset_materialization"] == provenance
    event = json.loads(
        (workspace / "reports/events" / f"{request.operation_id}-prepare.json").read_text(
            encoding="utf-8"
        )
    )
    assert event["payload"] == result.to_dict()
    assert event["payload"]["envelope"]["diagnostics"]["asset_materialization"] == provenance


def test_typed_prepare_partial_maps_override_only_named_species_and_retain_source_metadata(
    tmp_path: Path,
) -> None:
    _typed_si_o_fixture(tmp_path)
    assets = _external_typed_assets(tmp_path)
    request = ScfPrepareRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174232",
        workspace_rel="scf",
        structure_path_rel="source.STRU",
        pseudo_sources={"Si": str(assets["Si_upf"])},
        orbital_sources={"Si": str(assets["Si_orb"])},
    )

    result = ScfServiceSet.default(workspace_root=tmp_path).prepare.prepare(request)

    assert isinstance(result, OperationOutcome)
    workspace = tmp_path / "scf"
    stru = (workspace / "inputs/STRU").read_text(encoding="utf-8")
    assert "Si 28.085500 Si.external.upf" in stru
    assert "O 15.999000 O.source.upf" in stru
    assert "Si.external.orb" in stru
    assert "O.source.orb" in stru
    provenance = result.envelope.to_dict()["diagnostics"]["asset_materialization"]
    assert [item["species"] for item in provenance] == ["Si", "Si"]
    assert not (workspace / "inputs/O.external.upf").exists()
    assert not (workspace / "inputs/O.external.orb").exists()


def test_typed_prepare_preflight_stru_failure_writes_no_assets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _typed_si_o_fixture(tmp_path)
    assets = _external_typed_assets(tmp_path)
    preparation_module = __import__("abacus_forge.preparation", fromlist=["preparation"])

    def fail_preflight(*args: object, **kwargs: object) -> str:
        del args, kwargs
        raise ForgeRequestError("STRU preflight failed")

    monkeypatch.setattr(preparation_module.AbacusStructure, "to_stru", fail_preflight)
    request = ScfPrepareRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174236",
        workspace_rel="scf",
        structure_path_rel="source.STRU",
        pseudo_sources={"Si": str(assets["Si_upf"])},
    )

    result = ScfServiceSet.default(workspace_root=tmp_path).prepare.prepare(request)

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.invalid"
    inputs = tmp_path / "scf/inputs"
    assert not (inputs / "STRU").exists()
    assert not (inputs / assets["Si_upf"].name).exists()


def test_typed_prepare_uses_one_preflight_stru_render_before_materialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _typed_si_o_fixture(tmp_path)
    assets = _external_typed_assets(tmp_path)
    preparation_module = __import__("abacus_forge.preparation", fromlist=["preparation"])
    original_to_stru = preparation_module.AbacusStructure.to_stru
    calls = 0

    def fail_if_rendered_after_materialization(self: object, *args: object, **kwargs: object) -> str:
        nonlocal calls
        calls += 1
        rendered = original_to_stru(self, *args, **kwargs)
        if calls > 1:
            raise RuntimeError("STRU rendered after asset materialization")
        return rendered

    monkeypatch.setattr(
        preparation_module.AbacusStructure,
        "to_stru",
        fail_if_rendered_after_materialization,
    )
    request = ScfPrepareRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174237",
        workspace_rel="scf",
        structure_path_rel="source.STRU",
        pseudo_sources={"Si": str(assets["Si_upf"])},
    )

    result = ScfServiceSet.default(workspace_root=tmp_path).prepare.prepare(request)

    assert isinstance(result, OperationOutcome)
    assert calls == 1
    assert (tmp_path / "scf/inputs" / assets["Si_upf"].name).read_bytes() == assets["Si_upf"].read_bytes()


def test_typed_prepare_unexpected_non_stru_parser_failure_is_internal_and_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "scf"
    workspace.mkdir(parents=True)
    source = workspace / "source.cif"
    source.write_text("not parsed", encoding="utf-8")
    assets = _external_typed_assets(tmp_path)
    preparation_module = __import__("abacus_forge.preparation", fromlist=["preparation"])

    def fail_parser(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise RuntimeError("unexpected parser defect")

    monkeypatch.setattr(preparation_module.AbacusStructure, "from_input", classmethod(fail_parser))
    request = ScfPrepareRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174238",
        workspace_rel="scf",
        structure_path_rel=source.name,
        pseudo_sources={"Si": str(assets["Si_upf"])},
    )

    result = ScfServiceSet.default(workspace_root=tmp_path).prepare.prepare(request)

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "internal.failure"
    inputs = workspace / "inputs"
    assert not (inputs / "STRU").exists()
    assert not (inputs / assets["Si_upf"].name).exists()


@pytest.mark.parametrize(
    ("case", "asset_mode", "pseudo_sources", "expected_error"),
    [
        ("unknown", "copy", {"C": "unknown.upf"}, "request.invalid"),
        ("missing", "copy", {"Si": "missing.upf"}, "precondition.missing"),
        ("collision", "copy", {"Si": "one/Same.upf", "O": "two/Same.upf"}, "request.invalid"),
        ("external-link", "link", {"Si": "__external__/Si.external.upf"}, "request.invalid"),
    ],
)
def test_typed_prepare_asset_failures_are_fail_closed_before_domain_writes(
    tmp_path: Path,
    case: str,
    asset_mode: str,
    pseudo_sources: dict[str, str],
    expected_error: str,
) -> None:
    _typed_si_o_fixture(tmp_path)
    assets = _external_typed_assets(tmp_path)
    if case == "collision":
        (tmp_path / "scf/one").mkdir()
        (tmp_path / "scf/two").mkdir()
        (tmp_path / "scf/one/Same.upf").write_bytes(b"one")
        (tmp_path / "scf/two/Same.upf").write_bytes(b"two")
    elif case == "external-link":
        external = tmp_path.parent / f"{tmp_path.name}-external-link.upf"
        external.write_bytes(b"external")
        pseudo_sources = {"Si": str(external)}
    request = ScfPrepareRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174233",
        workspace_rel="scf",
        structure_path_rel="source.STRU",
        pseudo_sources=pseudo_sources,
        asset_mode=asset_mode,
    )

    result = ScfServiceSet.default(workspace_root=tmp_path).prepare.prepare(request)

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == expected_error
    inputs = tmp_path / "scf/inputs"
    assert not (inputs / "STRU").exists()
    assert not any(path.suffix in {".upf", ".orb", ".vp"} for path in inputs.iterdir())
    assert assets["Si_upf"].exists()


@pytest.mark.parametrize("basename", ["bad name.upf", "#hidden.upf"])
def test_typed_prepare_rejects_non_token_asset_basename_before_writes(
    tmp_path: Path, basename: str
) -> None:
    _typed_si_o_fixture(tmp_path)
    source = tmp_path / "scf" / basename
    source.write_bytes(b"invalid basename")
    request = ScfPrepareRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174239",
        workspace_rel="scf",
        structure_path_rel="source.STRU",
        pseudo_sources={"Si": str(source)},
    )

    result = ScfServiceSet.default(workspace_root=tmp_path).prepare.prepare(request)

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.invalid"
    inputs = tmp_path / "scf/inputs"
    assert not (inputs / "STRU").exists()
    assert not any(inputs.iterdir())


def test_typed_prepare_disambiguates_case_folded_artifact_ids(tmp_path: Path) -> None:
    _typed_si_o_fixture(tmp_path)
    first = tmp_path / "scf" / "a" / "atom.upf"
    second = tmp_path / "scf" / "b" / "ATOM.upf"
    first.parent.mkdir(); second.parent.mkdir()
    first.write_bytes(b"first"); second.write_bytes(b"second")
    request = ScfPrepareRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174240",
        workspace_rel="scf",
        structure_path_rel="source.STRU",
        pseudo_sources={"Si": str(first), "O": str(second)},
    )

    result = ScfServiceSet.default(workspace_root=tmp_path).prepare.prepare(request)

    assert isinstance(result, OperationOutcome)
    input_artifacts = [a for a in result.envelope.artifacts if a.role == "input"]
    ids = [a.id for a in input_artifacts]
    assert len(ids) == len(set(ids))
    assert "input-stru" in ids
    assert "input-input" in ids
    assert "input-atom.upf" not in ids
    assert sum(item.startswith("input-atom.upf-") for item in ids) == 2


def test_typed_prepare_rejects_partial_orbital_map_without_orbital_metadata(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "scf"
    workspace.mkdir(parents=True)
    (workspace / "source.STRU").write_text(
        "ATOMIC_SPECIES\nSi 28.085500 Si.upf\nO 15.999000 O.upf\n\n"
        "LATTICE_CONSTANT\n1.0\nLATTICE_CONSTANT_UNIT\nAngstrom\n\n"
        "LATTICE_VECTORS\n4 0 0\n0 4 0\n0 0 4\n\n"
        "ATOMIC_POSITIONS\nDirect\nSi\n0\n1\n0 0 0 m 1 1 1\n"
        "O\n0\n1\n0.5 0.5 0.5 m 1 1 1\n",
        encoding="utf-8",
    )
    orbital = workspace / "Si.orb"
    orbital.write_bytes(b"si orbital")
    request = ScfPrepareRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174241",
        workspace_rel="scf",
        structure_path_rel="source.STRU",
        orbital_sources={"Si": str(orbital)},
    )

    result = ScfServiceSet.default(workspace_root=tmp_path).prepare.prepare(request)

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.invalid"
    inputs = workspace / "inputs"
    assert not (inputs / "STRU").exists()
    assert not (inputs / orbital.name).exists()


@pytest.mark.parametrize(
    ("operation", "primitive_name", "error_type"),
    [
        ("prepare", "prepare_with_assets", TypeError),
        ("prepare", "prepare_with_assets", ValueError),
        ("modify", "modify_input", TypeError),
        ("modify", "modify_input", ValueError),
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
    _write_prepared_inputs(workspace)
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
    _write_prepared_inputs(Workspace(tmp_path / "scf").ensure_layout())
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
    _write_prepared_inputs(Workspace(tmp_path / "scf").ensure_layout())
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
    _write_prepared_inputs(Workspace(tmp_path / "scf").ensure_layout())
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
    _write_prepared_inputs(Workspace(tmp_path / "scf").ensure_layout())
    class BrokenRunner:
        def run(self, workspace):
            raise runner_error

    result = ForgeServices.default(workspace_root=tmp_path, runner=BrokenRunner()).execute_scf(
        ScfExecuteRequest(operation_id="123e4567-e89b-42d3-a456-426614174106", workspace_rel="scf")
    )
    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "internal.failure"


def test_unexpected_runner_exception_before_start_is_internal_error(tmp_path: Path) -> None:
    _write_prepared_inputs(Workspace(tmp_path / "scf").ensure_layout())
    class BrokenRunner:
        def run(self, workspace):
            raise RuntimeError("opaque runner failure")

    result = ForgeServices.default(workspace_root=tmp_path, runner=BrokenRunner()).execute_scf(
        ScfExecuteRequest(operation_id="123e4567-e89b-42d3-a456-426614174104", workspace_rel="scf")
    )
    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "internal.failure"


def test_empty_runner_exception_message_is_normalized_to_internal_error(tmp_path: Path) -> None:
    _write_prepared_inputs(Workspace(tmp_path / "scf").ensure_layout())

    def empty_runner_factory(**kwargs: object) -> object:
        del kwargs
        raise RuntimeError()

    request = ScfExecuteRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174105", workspace_rel="scf"
    )
    result = ScfServiceSet.default(
        workspace_root=tmp_path,
        runner_factory=empty_runner_factory,
    ).execute.execute(request)

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "internal.failure"
    assert result.message


def test_nonempty_runner_exception_message_is_preserved(tmp_path: Path) -> None:
    _write_prepared_inputs(Workspace(tmp_path / "scf").ensure_layout())

    class FailureRunner:
        def run(self, workspace):
            raise RuntimeError("runner detail")

    request = ScfExecuteRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174105", workspace_rel="scf"
    )
    result = ScfServiceSet.default(
        workspace_root=tmp_path,
        runner_factory=lambda **_: FailureRunner(),
    ).execute.execute(request)

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.message == "runner detail"


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


@pytest.mark.parametrize(
    "log_text,expected",
    [(None, "missing_output"), ("", "missing_output"),
     ("SCF CONVERGED\n", "partial"), ("NORMAL END\n", "partial"),
     ("TOTAL ENERGY = -4.2\n", "complete"),
     ("TOTAL ENERGY = -4.2\nSCF NOT CONVERGED\n", "complete"),
     ("TOTAL ENERGY = 1e999\nSCF CONVERGED\n", "partial")],
)
def test_scf_collection_factual_completeness(tmp_path: Path, log_text: str | None, expected: str) -> None:
    workspace = Workspace(tmp_path / "scf").ensure_layout()
    if log_text is not None:
        workspace.write_text("outputs/stdout.log", log_text)
    result = ScfServiceSet.default(workspace_root=tmp_path).collect.collect(
        ScfCollectRequest(operation_id="123e4567-e89b-42d3-a456-426614174301", workspace_rel="scf")
    )
    assert isinstance(result, OperationOutcome)
    assert result.status.collection == expected
    if log_text == "TOTAL ENERGY = -4.2\n":
        assert {item.name for item in result.observations}.isdisjoint(
            {"converged", "converge", "electronic_convergence"}
        )
        assert not result.envelope.checks
    if log_text and "NOT CONVERGED" in log_text:
        assert {item.name: item.value for item in result.observations}["electronic_convergence"] is False


@pytest.mark.parametrize("defect", ["report", "time", "ambiguous"])
def test_scf_collection_parse_degradation_is_partial(tmp_path: Path, defect: str) -> None:
    workspace = Workspace(tmp_path / "scf").ensure_layout()
    workspace.write_text("outputs/stdout.log", "TOTAL ENERGY = -4.2\nSCF CONVERGED\n")
    if defect == "ambiguous":
        workspace.write_text("outputs/out.log", "TOTAL ENERGY = -9.0\n")
    else:
        workspace.write_text("reports/metrics_relax.json" if defect == "report" else "outputs/time.json", "{broken")
    result = ScfServiceSet.default(workspace_root=tmp_path).collect.collect(
        ScfCollectRequest(operation_id="123e4567-e89b-42d3-a456-426614174302", workspace_rel="scf")
    )
    assert isinstance(result, OperationOutcome)
    assert result.status.collection == "partial"


def test_scf_collection_preserves_array_and_structure_observations(tmp_path: Path) -> None:
    workspace = _write_relax_collection_workspace(
        tmp_path, capability="scf",
        log_text="TOTAL ENERGY = -4.2\nTOTAL-FORCE (eV/Angstrom)\nSi1 0.1 0.2 0.3\n",
    )
    result = ScfServiceSet.default(workspace_root=tmp_path).collect.collect(
        ScfCollectRequest(operation_id="123e4567-e89b-42d3-a456-426614174303", workspace_rel="collection")
    )
    assert isinstance(result, OperationOutcome)
    observations = {item.name: item for item in result.observations}
    assert observations["forces"].to_dict()["value"] == [[0.1, 0.2, 0.3]]
    assert observations["structure_snapshot"].source == "file"
    assert observations["final_structure_snapshot"].source == "file"


@pytest.mark.parametrize("capability", ["scf", "relax"])
def test_typed_collection_excludes_prior_audit_and_resolved_aliases(tmp_path: Path, capability: str) -> None:
    workspace = _write_relax_collection_workspace(tmp_path, capability=capability)
    services = (ScfServiceSet if capability == "scf" else RelaxServiceSet).default(workspace_root=tmp_path)
    request_type = ScfCollectRequest if capability == "scf" else RelaxCollectRequest
    extra = {} if capability == "scf" else {"capability": capability}
    first = services.collect.collect(request_type(
        operation_id="123e4567-e89b-42d3-a456-426614174304", workspace_rel="collection", **extra
    ))
    assert isinstance(first, OperationOutcome)
    for index, target in enumerate((
        "reports/events/123e4567-e89b-42d3-a456-426614174304-collect.json",
        "reports/forge-workspace.json", "reports/.forge-operation.lock", "reports/.forge-workspace.lock",
        "reports/claims/123e4567-e89b-42d3-a456-426614174305.json",
    )):
        (workspace.outputs_dir / f"alias-{index}.json").symlink_to(workspace.root / target)
    second = services.collect.collect(request_type(
        operation_id="123e4567-e89b-42d3-a456-426614174305", workspace_rel="collection", **extra
    ))
    assert isinstance(second, OperationOutcome)
    paths = {item.path_rel for item in second.envelope.artifacts}
    assert paths == {item.path_rel for item in first.envelope.artifacts}
    assert not any(path.startswith(("reports/events/", "reports/claims/")) for path in paths)
    assert paths.isdisjoint({"reports/forge-workspace.json", "reports/.forge-operation.lock", "reports/.forge-workspace.lock"})


@pytest.mark.parametrize("capability", ["scf", "relax"])
@pytest.mark.parametrize("log_name", ["stdout.log", "OUT.ABACUS/running_scf.log", "banner.log"])
def test_typed_collection_does_not_parse_external_log_aliases(
    tmp_path: Path, capability: str, log_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _write_relax_collection_workspace(tmp_path, capability=capability, log_text=None)
    outside = tmp_path / "outside.log"
    outside.write_text("WELCOME TO ABACUS\nTOTAL ENERGY = -777.0\nSCF CONVERGED\n", encoding="utf-8")
    (workspace.outputs_dir / log_name).symlink_to(outside)
    original_read_text = Path.read_text
    external_reads = []
    def guarded_read(path: Path, *args: object, **kwargs: object) -> str:
        if path.resolve() == outside.resolve():
            external_reads.append(str(path))
        return original_read_text(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", guarded_read)
    services = (ScfServiceSet if capability == "scf" else RelaxServiceSet).default(workspace_root=tmp_path)
    request_type = ScfCollectRequest if capability == "scf" else RelaxCollectRequest
    extra = {} if capability == "scf" else {"capability": capability}
    result = services.collect.collect(request_type(
        operation_id="123e4567-e89b-42d3-a456-426614174306", workspace_rel="collection", **extra
    ))
    assert isinstance(result, OperationOutcome)
    assert external_reads == []
    assert result.status.collection == "missing_output"
    assert all(item.name != "total_energy" for item in result.observations)


@pytest.mark.parametrize("capability", ["scf", "relax"])
@pytest.mark.parametrize("discovery", ["fallback", "banner"])
@pytest.mark.parametrize("same_source", [True, False], ids=["alias", "distinct"])
def test_typed_collection_log_ambiguity_counts_resolved_sources(
    tmp_path: Path, capability: str, discovery: str, same_source: bool
) -> None:
    workspace = _write_relax_collection_workspace(
        tmp_path, capability=capability,
        log_text="TOTAL ENERGY = -4.2\n" if discovery == "banner" else None,
    )
    source_name, other_name = ("stdout.log", "out.log") if discovery == "fallback" else ("z-banner.log", "a-banner.log")
    source = workspace.outputs_dir / source_name
    other = workspace.outputs_dir / other_name
    text = "Atomic-orbital Based Ab-initio\nTOTAL ENERGY = -4.2\n"
    source.write_text(text, encoding="utf-8")
    if same_source:
        other.symlink_to(source)
    else:
        other.write_text(text, encoding="utf-8")

    services = (ScfServiceSet if capability == "scf" else RelaxServiceSet).default(workspace_root=tmp_path)
    request_type = ScfCollectRequest if capability == "scf" else RelaxCollectRequest
    extra = {} if capability == "scf" else {"capability": capability}
    result = services.collect.collect(request_type(
        operation_id="123e4567-e89b-42d3-a456-426614174308", workspace_rel="collection", **extra
    ))

    assert isinstance(result, OperationOutcome)
    assert result.status.collection == ("complete" if same_source else "partial")
    assert {item.name: item.value for item in result.observations}["total_energy"] == -4.2
    diagnostics = result.envelope.diagnostics
    assert diagnostics["output_log_selection_ambiguous"] is (not same_source)
    assert diagnostics["log_selection_ambiguous"] is False
    expected_sources = {str(source)} if same_source else {str(source), str(other)}
    assert set(diagnostics["output_log_candidates"]) == expected_sources
    assert len(diagnostics["output_log_candidates"]) == len(expected_sources)
    if same_source:
        assert diagnostics["output_log_path"] == str(source)
        assert not diagnostics["output_log_ignored_paths"]
    if discovery == "fallback":
        assert set(diagnostics["fallback_log_candidates"]) == expected_sources
        assert diagnostics["selected_log_path"] == str(source)
        if same_source:
            assert not diagnostics["ignored_log_paths"]

    legacy = abacus_forge.collect(workspace)
    assert legacy.diagnostics["output_log_selection_ambiguous"] is True
    assert legacy.diagnostics["output_log_path"] == str(other)


def test_typed_collection_domain_alias_preserves_report_facts(tmp_path: Path) -> None:
    workspace = _write_relax_collection_workspace(
        tmp_path, capability="scf", relax_report={"ionic_steps": [1, 2]}
    )
    (workspace.outputs_dir / "report-alias.json").symlink_to(workspace.reports_dir / "metrics_relax.json")
    result = ScfServiceSet.default(workspace_root=tmp_path).collect.collect(
        ScfCollectRequest(operation_id="123e4567-e89b-42d3-a456-426614174307", workspace_rel="collection")
    )
    assert isinstance(result, OperationOutcome)
    observations = {item.name: item for item in result.observations}
    assert observations["relax_metrics"].to_dict()["value"] == {"ionic_steps": [1, 2]}
    assert [item.path_rel for item in result.envelope.artifacts].count("reports/metrics_relax.json") == 1


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
    _write_prepared_inputs(Workspace(tmp_path / "scf").ensure_layout())
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
    _write_prepared_inputs(Workspace(tmp_path / "scf").ensure_layout())
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["NORMAL END"])
    runner_module = __import__("abacus_forge.runner", fromlist=["runner"])
    original_which = runner_module.shutil.which
    monkeypatch.setattr(
        runner_module.shutil,
        "which",
        lambda name, path=None: None if name == "mpirun" else original_which(name, path=path),
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
    _write_prepared_inputs(Workspace(tmp_path / "scf").ensure_layout())
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


@pytest.mark.parametrize("operation", ["prepare", "modify", "execute", "collect"])
def test_relax_and_scf_services_reject_the_other_request_family_without_side_effects(
    tmp_path: Path, operation: str
) -> None:
    operation_ids = {
        "prepare": "123e4567-e89b-42d3-a456-426614174130",
        "modify": "123e4567-e89b-42d3-a456-426614174131",
        "execute": "123e4567-e89b-42d3-a456-426614174132",
        "collect": "123e4567-e89b-42d3-a456-426614174133",
    }
    request_types = {
        "prepare": (ScfPrepareRequest, RelaxPrepareRequest),
        "modify": (ScfModifyRequest, RelaxModifyRequest),
        "execute": (ScfExecuteRequest, RelaxExecuteRequest),
        "collect": (ScfCollectRequest, RelaxCollectRequest),
    }
    scf_type, relax_type = request_types[operation]
    kwargs = {
        "prepare": {"structure_path_rel": "source.STRU"},
        "modify": {"input_updates": {"ecutwfc": 90}},
        "execute": {},
        "collect": {},
    }[operation]
    scf_request = _request(scf_type, "job", operation_ids[operation], **kwargs)
    relax_request = _request(
        relax_type,
        "job",
        f"123e4567-e89b-42d3-a456-426614174{134 + list(request_types).index(operation)}",
        capability="relax",
        **kwargs,
    )
    scf_services = ScfServiceSet.default(workspace_root=tmp_path)
    relax_services = RelaxServiceSet.default(workspace_root=tmp_path)

    def invoke(service_set, request):
        service = getattr(service_set, operation)
        return getattr(service, operation)(request)

    scf_result = invoke(scf_services, relax_request)
    relax_result = invoke(relax_services, scf_request)

    assert isinstance(scf_result, ForgeErrorEnvelope)
    assert isinstance(relax_result, ForgeErrorEnvelope)
    assert scf_result.error_class == "request.invalid"
    assert relax_result.error_class == "request.invalid"
    assert not tmp_path.exists() or not list(tmp_path.iterdir())


def test_relax_execute_rejects_input_from_another_capability_before_runner_start(
    tmp_path: Path,
) -> None:
    workspace = Workspace(tmp_path / "job").ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\n")
    workspace.write_text("inputs/STRU", "prepared\n")
    workspace.write_text("inputs/KPT", "prepared\n")
    calls = 0

    def fail_runner_factory(**kwargs: object) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("capability mismatch must stop before runner construction")

    request = RelaxExecuteRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174135",
        workspace_rel="job",
        capability="relax",
    )
    result = RelaxServiceSet.default(
        workspace_root=tmp_path, runner_factory=fail_runner_factory
    ).execute.execute(request)

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "precondition.missing"
    assert calls == 0
    assert not (workspace.root / "forge-result.json").exists()
    assert not list((workspace.reports_dir / "events").glob("*.json"))


def test_relax_collect_rejects_input_from_another_capability_before_parsing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _write_relax_collection_workspace(tmp_path, input_calculation="scf")
    services_module = __import__("abacus_forge.services", fromlist=["services"])

    def fail_collect(workspace):
        raise AssertionError("capability mismatch must stop before collection")

    monkeypatch.setattr(services_module, "collect", fail_collect)
    request = RelaxCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174136",
        workspace_rel="collection",
        capability="relax",
    )
    result = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(request)

    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "precondition.missing"
    assert not list((workspace.reports_dir / "events").glob("*.json"))


def test_relax_duplicate_request_id_returns_conflict_without_rewriting_facts(tmp_path: Path) -> None:
    services = RelaxServiceSet.default(workspace_root=tmp_path)
    request = RelaxExecuteRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174137",
        workspace_rel="job",
        capability="cell-relax",
        dry_run=True,
    )
    first = services.execute.execute(request)
    result_path = tmp_path / "job" / "forge-result.json"
    event_path = tmp_path / "job" / "reports" / "events" / f"{request.operation_id}-execute.json"
    before = (result_path.read_bytes(), event_path.read_bytes())
    second = services.execute.execute(request)

    assert isinstance(first, OperationOutcome)
    assert isinstance(second, ForgeErrorEnvelope)
    assert second.error_class == "operation.conflict"
    assert (result_path.read_bytes(), event_path.read_bytes()) == before


@pytest.mark.parametrize(
    ("capability", "log_text", "final_structure", "expected_collection"),
    [
        ("relax", None, "stru", "missing_output"),
        ("relax", "SCF NOT CONVERGED\n", "stru", "partial"),
        ("relax", "TOTAL ENERGY = -4.2\n", None, "partial"),
        ("cell-relax", "TOTAL ENERGY = -4.2\n", "stru", "complete"),
    ],
)
def test_relax_collection_status_uses_factual_output_completeness(
    tmp_path: Path,
    capability: str,
    log_text: str | None,
    final_structure: str | None,
    expected_collection: str,
) -> None:
    workspace = _write_relax_collection_workspace(
        tmp_path,
        capability=capability,
        log_text=log_text,
        final_structure=final_structure,
    )
    request = RelaxCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174138",
        workspace_rel="collection",
        capability=capability,
    )
    result = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(request)

    assert isinstance(result, OperationOutcome)
    assert result.status.execution == "not_run"
    assert result.status.scientific == "unassessed"
    assert result.status.collection == expected_collection
    if final_structure is None:
        assert all(observation.name != "final_structure_snapshot" for observation in result.observations)


def test_relax_collection_complete_ignores_optional_and_convergence_warnings(
    tmp_path: Path,
) -> None:
    workspace = _write_relax_collection_workspace(tmp_path)
    request = RelaxCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174139",
        workspace_rel="collection",
        capability="relax",
    )
    result = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(request)

    assert isinstance(result, OperationOutcome)
    assert result.status.collection == "complete"
    assert result.envelope.warnings
    assert "No explicit convergence marker found in logs." in result.envelope.warnings
    assert "time.json is absent." in result.envelope.warnings
    assert "No report JSON artifacts found." in result.envelope.warnings
    assert {metric.name for metric in result.envelope.metrics}.isdisjoint({"converged", "converge"})
    assert all(observation.name not in {"converged", "converge"} for observation in result.observations)
    assert not result.envelope.checks
    assert result.envelope.diagnostics["final_structure_selection_ambiguous"] is False


def test_relax_collection_keeps_false_electronic_convergence_without_ionic_fallback(
    tmp_path: Path,
) -> None:
    workspace = _write_relax_collection_workspace(
        tmp_path,
        log_text="TOTAL ENERGY = -4.2\nSCF NOT CONVERGED\n",
        relax_report={"final_structure_available": True, "ionic_steps": [1, 2]},
    )
    request = RelaxCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174140",
        workspace_rel="collection",
        capability="relax",
    )
    result = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(request)

    assert isinstance(result, OperationOutcome)
    assert result.status.collection == "complete"
    assert {metric.name for metric in result.envelope.metrics} >= {"converged", "converge"}
    observations = {observation.name: observation for observation in result.observations}
    assert observations["electronic_convergence"].value is False
    assert observations["relax_metrics"].to_dict()["value"] == {
        "final_structure_available": True,
        "ionic_steps": [1, 2],
    }
    assert "converged" not in result.envelope.diagnostics["legacy_metrics"]["relax_summary"]
    assert "converged" not in result.envelope.diagnostics["legacy_metrics"]["relax_metrics"]
    assert "converged" not in observations["relax_summary"].to_dict()["value"]


def test_relax_collection_preserves_explicit_ionic_convergence_and_nested_facts(
    tmp_path: Path,
) -> None:
    workspace = _write_relax_collection_workspace(
        tmp_path,
        log_text=(
            "TOTAL ENERGY = -4.2\nSCF CONVERGED\n"
            "TOTAL-FORCE (eV/Angstrom)\nSi1 0.1 0.2 0.3\n"
            "TOTAL-STRESS (KBAR)\n1 2 3\n4 5 6\n7 8 9\n"
        ),
        relax_report={"converged": True, "final_structure_available": True, "ionic_steps": [1, 2]},
    )
    request = RelaxCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174141",
        workspace_rel="collection",
        capability="relax",
    )
    result = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(request)

    assert isinstance(result, OperationOutcome)
    assert result.status.collection == "complete"
    observations = {observation.name: observation for observation in result.observations}
    assert observations["electronic_convergence"].value is True
    assert observations["forces"].source == "parser"
    assert observations["stress"].source == "parser"
    assert observations["relax_metrics"].source == "parser"
    assert observations["relax_summary"].source == "parser"
    assert observations["structure_snapshot"].source == "file"
    assert observations["final_structure_snapshot"].source == "file"
    assert observations["relax_summary"].value["converged"] is True
    assert any(artifact.path_rel == "outputs/OUT.ABACUS/STRU_ION_D" for artifact in result.envelope.artifacts)
    assert all(not Path(artifact.path_rel).is_absolute() for artifact in result.envelope.artifacts)


def test_relax_collection_preserves_scalar_metadata_and_nested_report_shape(tmp_path: Path) -> None:
    workspace = _write_relax_collection_workspace(
        tmp_path,
        log_text=(
            "!FINAL_ETOT_IS -8.0 eV\nNATOM = 2\n"
            "TOTAL-STRESS (KBAR)\n"
            "1 2 3\n4 5 6\n7 8 9\n"
        ),
        relax_report={"converged": True, "ionic_steps": [1, 2]},
    )
    request = RelaxCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174142",
        workspace_rel="collection",
        capability="relax",
    )

    result = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(request)

    assert isinstance(result, OperationOutcome)
    metrics = {metric.name: metric for metric in result.envelope.metrics}
    assert metrics["total_energy"].unit == "eV"
    assert metrics["pressure"].unit == "kbar"
    assert metrics["pressure"].kind == "derived"
    assert metrics["total_energy"].source_artifact_id is not None
    assert metrics["pressure"].source_artifact_id == metrics["total_energy"].source_artifact_id
    nested = result.envelope.to_dict()["diagnostics"]["legacy_metrics"]["relax_metrics"]
    assert nested == {"converged": True, "ionic_steps": [1, 2]}
    report_observation = next(item for item in result.observations if item.name == "relax_metrics")
    assert report_observation.to_dict()["value"] == {"converged": True, "ionic_steps": [1, 2]}


def test_relax_collection_external_output_without_forge_manifest_is_supported(tmp_path: Path) -> None:
    workspace = _write_relax_collection_workspace(tmp_path)
    assert not (workspace.root / "forge-unit.json").exists()
    request = RelaxCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174142",
        workspace_rel="collection",
        capability="relax",
    )
    result = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(request)

    assert isinstance(result, OperationOutcome)
    assert result.status.collection == "complete"


@pytest.mark.parametrize("filename", ["STRU_FINAL", "STRU_FINAL.cif", "STRU_NOW", "STRU_NOW.cif"])
def test_relax_collection_supports_native_abacus_final_structure_names(
    tmp_path: Path, filename: str
) -> None:
    workspace = _write_relax_collection_workspace(tmp_path, final_structure=None)
    structure = Atoms("Si", positions=[[0.0, 0.0, 0.0]], cell=[4.0, 4.0, 4.0], pbc=True)
    output = workspace.outputs_dir / "OUT.ABACUS" / filename
    if filename.endswith(".cif"):
        ase_write(output, structure, format="cif")
    else:
        output.write_text(abacus_forge.AbacusStructure(structure, source_format="ase").to_stru(), encoding="utf-8")

    request = RelaxCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174150",
        workspace_rel="collection",
        capability="relax",
    )
    result = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(request)

    assert isinstance(result, OperationOutcome)
    assert result.status.collection == "complete"
    assert result.envelope.diagnostics["final_structure_path"].endswith(filename)


def test_relax_collection_prefers_native_final_over_per_step_structure(tmp_path: Path) -> None:
    workspace = _write_relax_collection_workspace(tmp_path, final_structure=None)
    output_dir = workspace.outputs_dir / "OUT.ABACUS"
    structure = Atoms("Si", positions=[[0.0, 0.0, 0.0]], cell=[4.0, 4.0, 4.0], pbc=True)
    structure_payload = abacus_forge.AbacusStructure(structure, source_format="ase").to_stru()
    (output_dir / "STRU_NOW").write_text(structure_payload, encoding="utf-8")
    (output_dir / "STRU_FINAL").write_text(structure_payload, encoding="utf-8")
    request = RelaxCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174151",
        workspace_rel="collection",
        capability="relax",
    )

    result = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(request)

    assert isinstance(result, OperationOutcome)
    assert result.status.collection == "complete"
    assert result.envelope.diagnostics["final_structure_path"].endswith("STRU_FINAL")


def test_relax_collection_accepts_native_structure_in_inputs_out_handoff(tmp_path: Path) -> None:
    workspace = _write_relax_collection_workspace(tmp_path, final_structure=None)
    output_dir = workspace.inputs_dir / "OUT.ABACUS"
    output_dir.mkdir(parents=True, exist_ok=True)
    structure = Atoms("Si", positions=[[0.0, 0.0, 0.0]], cell=[4.0, 4.0, 4.0], pbc=True)
    (output_dir / "STRU_FINAL").write_text(
        abacus_forge.AbacusStructure(structure, source_format="ase").to_stru(),
        encoding="utf-8",
    )
    request = RelaxCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174152",
        workspace_rel="collection",
        capability="relax",
    )

    result = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(request)

    assert isinstance(result, OperationOutcome)
    assert result.status.collection == "complete"
    assert result.envelope.diagnostics["final_structure_path"].endswith("STRU_FINAL")


def test_relax_collection_ambiguous_log_or_final_structure_is_partial(tmp_path: Path) -> None:
    workspace = _write_relax_collection_workspace(tmp_path)
    duplicate_log = workspace.outputs_dir / "other" / "running_relax.log"
    duplicate_log.parent.mkdir(parents=True)
    duplicate_log.write_text("TOTAL ENERGY = -4.2\n", encoding="utf-8")
    workspace.write_text("outputs/stdout.log", "TOTAL ENERGY = -4.2\n")
    request = RelaxCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174143",
        workspace_rel="collection",
        capability="relax",
    )
    ambiguous_log = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(request)

    assert isinstance(ambiguous_log, OperationOutcome)
    assert ambiguous_log.status.collection == "partial"
    assert ambiguous_log.envelope.diagnostics["log_selection_ambiguous"] is True

    second_workspace = _write_relax_collection_workspace(tmp_path / "second")
    structure = Atoms("Si", positions=[[0.0, 0.0, 0.0]], cell=[4.0, 4.0, 4.0], pbc=True)
    ase_write(
        second_workspace.outputs_dir / "OUT.ABACUS" / "STRU_NOW.cif",
        structure,
        format="cif",
    )
    second_request = RelaxCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174144",
        workspace_rel="second/collection",
        capability="relax",
    )
    ambiguous_structure = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(second_request)

    assert isinstance(ambiguous_structure, OperationOutcome)
    assert ambiguous_structure.status.collection == "partial"
    assert ambiguous_structure.envelope.diagnostics["final_structure_selection_ambiguous"] is True


def test_relax_collection_duplicate_final_structure_basename_is_partial(tmp_path: Path) -> None:
    workspace = _write_relax_collection_workspace(tmp_path)
    primary = workspace.outputs_dir / "OUT.ABACUS" / "STRU_ION_D"
    duplicate = workspace.outputs_dir / "other" / "STRU_ION_D"
    duplicate.parent.mkdir(parents=True)
    duplicate.write_text(primary.read_text(encoding="utf-8"), encoding="utf-8")
    request = RelaxCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174147",
        workspace_rel="collection",
        capability="relax",
    )

    result = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(request)

    assert isinstance(result, OperationOutcome)
    assert result.status.collection == "partial"


def test_relax_collection_parse_failure_and_escaped_final_symlink_are_partial(
    tmp_path: Path,
) -> None:
    malformed = _write_relax_collection_workspace(tmp_path, final_structure="invalid")
    malformed_request = RelaxCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174145",
        workspace_rel="collection",
        capability="relax",
    )
    malformed_result = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(malformed_request)

    assert isinstance(malformed_result, OperationOutcome)
    assert malformed_result.status.collection == "partial"
    assert malformed_result.envelope.diagnostics["final_structure_parse_error"]
    assert all(observation.name != "final_structure_snapshot" for observation in malformed_result.observations)

    second_root = tmp_path / "symlink"
    symlink_workspace = _write_relax_collection_workspace(second_root)
    outside = second_root / "outside.STRU"
    outside.write_text((symlink_workspace.outputs_dir / "OUT.ABACUS" / "STRU_ION_D").read_text(), encoding="utf-8")
    final_path = symlink_workspace.outputs_dir / "OUT.ABACUS" / "STRU_ION_D"
    final_path.unlink()
    final_path.symlink_to(outside)
    symlink_request = RelaxCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174146",
        workspace_rel="symlink/collection",
        capability="relax",
    )
    symlink_result = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(symlink_request)

    assert isinstance(symlink_result, OperationOutcome)
    assert symlink_result.status.collection == "partial"
    assert all(artifact.path_rel != "outputs/OUT.ABACUS/STRU_ION_D" for artifact in symlink_result.envelope.artifacts)
    assert all(observation.name != "final_structure_snapshot" for observation in symlink_result.observations)


@pytest.mark.parametrize(
    ("capability", "operation_id"),
    [
        ("relax", "123e4567-e89b-42d3-a456-426614174148"),
        ("cell-relax", "123e4567-e89b-42d3-a456-426614174149"),
    ],
)
def test_relax_collect_returns_live_artifacts_with_current_hashes(
    tmp_path: Path, capability: str, operation_id: str
) -> None:
    workspace = _write_relax_collection_workspace(tmp_path, capability=capability)
    request = RelaxCollectRequest(
        operation_id=operation_id,
        workspace_rel="collection",
        capability=capability,
    )

    result = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(request)

    assert isinstance(result, OperationOutcome)
    artifact_paths = {artifact.path_rel for artifact in result.envelope.artifacts}
    assert "reports/forge-workspace.json" not in artifact_paths
    assert not any(path.startswith("reports/claims/") for path in artifact_paths)
    for artifact in result.envelope.artifacts:
        path = workspace.root / artifact.path_rel
        assert path.is_file(), artifact.path_rel
        assert artifact.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
        assert artifact.size_bytes == path.stat().st_size


@pytest.mark.parametrize(
    ("capability", "internal_target", "operation_id"),
    [
        ("relax", "claim", "123e4567-e89b-42d3-a456-426614174154"),
        ("relax", "manifest", "123e4567-e89b-42d3-a456-426614174155"),
        ("cell-relax", "claim", "123e4567-e89b-42d3-a456-426614174156"),
        ("cell-relax", "manifest", "123e4567-e89b-42d3-a456-426614174157"),
    ],
)
def test_relax_collect_filters_output_aliases_to_internal_bookkeeping(
    tmp_path: Path, capability: str, internal_target: str, operation_id: str
) -> None:
    workspace = _write_relax_collection_workspace(tmp_path, capability=capability)
    target = (
        workspace.reports_dir / "claims" / f"{operation_id}.json"
        if internal_target == "claim"
        else workspace.reports_dir / "forge-workspace.json"
    )
    alias = workspace.outputs_dir / f"{internal_target}-alias.json"
    alias.symlink_to(target)
    request = RelaxCollectRequest(
        operation_id=operation_id,
        workspace_rel="collection",
        capability=capability,
    )

    result = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(request)

    assert isinstance(result, OperationOutcome)
    for artifact in result.envelope.artifacts:
        path = workspace.root / artifact.path_rel
        resolved_rel = path.resolve().relative_to(workspace.root.resolve()).as_posix()
        assert resolved_rel != "reports/forge-workspace.json"
        assert not resolved_rel.startswith("reports/claims/")
        assert resolved_rel not in {
            "reports/.forge-operation.lock",
            "reports/.forge-workspace.lock",
        }
        assert path.is_file(), artifact.path_rel
        assert artifact.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
        assert artifact.size_bytes == path.stat().st_size


@pytest.mark.parametrize(
    ("capability", "operation_id"),
    [
        ("relax", "123e4567-e89b-42d3-a456-426614174152"),
        ("cell-relax", "123e4567-e89b-42d3-a456-426614174153"),
    ],
)
def test_relax_collect_reselects_output_stru_after_input_stru(
    tmp_path: Path, capability: str, operation_id: str
) -> None:
    workspace = _write_relax_collection_workspace(
        tmp_path,
        capability=capability,
        final_structure=None,
    )
    final_structure = Atoms(
        "Si",
        positions=[[0.5, 0.5, 0.5]],
        cell=[5.0, 5.0, 5.0],
        pbc=True,
    )
    workspace.write_text(
        "outputs/OUT.ABACUS/STRU",
        abacus_forge.AbacusStructure(final_structure, source_format="ase").to_stru(),
    )
    request = RelaxCollectRequest(
        operation_id=operation_id,
        workspace_rel="collection",
        capability=capability,
    )

    result = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(request)

    assert isinstance(result, OperationOutcome)
    assert result.status.collection == "complete"
    observations = {observation.name: observation for observation in result.observations}
    final_snapshot = observations["final_structure_snapshot"].value
    assert final_snapshot["source"].endswith("outputs/OUT.ABACUS/STRU")
    assert final_snapshot["volume"] == pytest.approx(125.0)
    assert result.envelope.diagnostics["final_structure_path"].endswith(
        "outputs/OUT.ABACUS/STRU"
    )
    assert any(
        artifact.path_rel == "outputs/OUT.ABACUS/STRU"
        for artifact in result.envelope.artifacts
    )
