from __future__ import annotations

import multiprocessing
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from ase import Atoms

from abacus_forge.api import prepare
from abacus_forge.composite import prepare_vibration
from abacus_forge.runner import LocalRunner
from abacus_forge.workspace import Workspace


pytestmark = pytest.mark.integration


def _tick(path: Path) -> None:
    """Write from an unrelated process so over-broad cleanup is observable."""
    for tick in range(1000):
        with path.open("a", encoding="utf-8") as stream:
            stream.write(f"unrelated {tick}\n")
        time.sleep(0.02)


def _wait_for_tick(path: Path) -> None:
    deadline = time.monotonic() + 2
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert path.exists()


def _assert_stopped_writing(path: Path) -> None:
    before = path.stat().st_size
    time.sleep(0.12)
    assert path.stat().st_size == before


def _spawning_executable(path: Path, child_result: Path) -> Path:
    pid_record = child_result.with_name(child_result.name + ".pids")
    child_code = "\n".join(
        [
            "import time",
            "from pathlib import Path",
            f"path = Path({str(child_result)!r})",
            "for tick in range(1000):",
            "    with path.open('a', encoding='utf-8') as stream:",
            "        stream.write(f'child {tick}\\n')",
            "    time.sleep(0.02)",
        ]
    )
    parent_code = "\n".join(
        [
            "import os",
            "from pathlib import Path",
            "import subprocess",
            "import sys",
            f"child = subprocess.Popen([sys.executable, '-c', {child_code!r}],",
            "    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)",
            f"Path({str(pid_record)!r}).write_text("
            "f\"{os.getpid()} {child.pid}\\n\", encoding='utf-8')",
            "print('launcher running', flush=True)",
            "child.wait()",
        ]
    )
    path.write_text(f"#!{sys.executable}\n{parent_code}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)
    return path


def _write_interruptible_caller(path: Path, executable: Path, workspace: Path) -> Path:
    source = "\n".join(
        [
            "import threading",
            "import os",
            "import signal",
            "import sys",
            "from pathlib import Path",
            "from abacus_forge.runner import LocalRunner",
            "from abacus_forge.workspace import Workspace",
            "",
            "def send_sigint():",
            "    os.kill(os.getpid(), signal.SIGINT)",
            "",
            "timer = threading.Timer(0.18, send_sigint)",
            "timer.start()",
            "try:",
            "    LocalRunner(",
            f"        executable={str(executable)!r}, timeout_seconds=None",
            f"    ).run(Workspace(Path({str(workspace)!r})))",
            "    print('runner unexpectedly returned', flush=True)",
            "    raise SystemExit(3)",
            "except KeyboardInterrupt:",
            "    print('CALLER_INTERRUPTED', flush=True)",
            "    raise SystemExit(42)",
            "finally:",
            "    timer.cancel()",
            "    timer.join()",
        ]
    )
    path.write_text(source, encoding="utf-8")
    return path


def _kill_recorded_processes(pid_record: Path) -> None:
    if not pid_record.exists():
        return
    for raw in pid_record.read_text(encoding="utf-8").split():
        try:
            os.kill(int(raw), signal.SIGKILL)
        except (OSError, ValueError):
            pass


@pytest.mark.skipif(os.name != "posix", reason="controlled process groups require POSIX")
def test_local_runner_timeout_terminates_only_its_process_group(
    tmp_path: Path,
) -> None:
    workspace = Workspace(tmp_path / "runner")
    workspace.ensure_layout()
    child_result = tmp_path / "child-result.log"
    executable = _spawning_executable(tmp_path / "spawning-engine", child_result)
    unrelated_result = tmp_path / "unrelated-result.log"
    unrelated = multiprocessing.Process(target=_tick, args=(unrelated_result,), daemon=True)
    unrelated.start()
    try:
        _wait_for_tick(unrelated_result)
        result = LocalRunner(executable=str(executable), timeout_seconds=0.18).run(workspace)

        assert result.returncode == 124
        assert result.status == "failed"
        assert result.diagnostics["failure_class"] == "timeout"
        assert result.diagnostics["termination"] == "timeout"
        stdout = (workspace.outputs_dir / "stdout.log").read_text(encoding="utf-8")
        assert stdout.count("launcher running") == 1
        assert "Command timed out after 0.18 seconds" in (
            workspace.outputs_dir / "stderr.log"
        ).read_text(encoding="utf-8")

        # The runner must wait for descendants to stop before materializing
        # caller-visible logs and results.
        _assert_stopped_writing(child_result)
        assert unrelated.is_alive()
        _wait_for_tick(unrelated_result)
        before = unrelated_result.stat().st_size
        time.sleep(0.12)
        assert unrelated_result.stat().st_size > before
    finally:
        unrelated.terminate()
        unrelated.join(timeout=2)
        if unrelated.is_alive():
            unrelated.kill()
            unrelated.join(timeout=2)


@pytest.mark.composite
@pytest.mark.skipif(os.name != "posix", reason="controlled process groups require POSIX")
def test_execute_subtask_timeout_terminates_spawned_descendants(
    tmp_path: Path,
) -> None:
    from abacus_forge.composite.plan import execute_subtask, list_subtasks

    root = tmp_path / "task-root"
    prepare(
        root,
        structure=Atoms("H", positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True),
        task="scf",
    )
    prepare_vibration(root, atom_indices=[1])
    unit = list_subtasks(root, "vibration").subtasks[0]
    unit_workspace = Path(unit["workspace"])
    child_result = unit_workspace / "outputs" / "child-result.log"
    executable = _spawning_executable(tmp_path / "spawning-engine", child_result)
    runner = LocalRunner(executable=str(executable), timeout_seconds=0.18)

    record = execute_subtask(root, "vibration", unit["unit_id"], runner=runner)

    assert record["status"] == "failed"
    assert record["run"]["returncode"] == 124
    assert record["run"]["diagnostics"]["failure_class"] == "timeout"
    assert record["run"]["diagnostics"]["termination"] == "timeout"
    _wait_for_tick(child_result)
    _assert_stopped_writing(child_result)
    stdout = (unit_workspace / "outputs" / "stdout.log").read_text(encoding="utf-8")
    stderr = (unit_workspace / "outputs" / "stderr.log").read_text(encoding="utf-8")
    assert stdout.count("launcher running") == 1
    assert "Command timed out after 0.18 seconds" in stderr


@pytest.mark.skipif(os.name != "posix", reason="controlled process groups require POSIX")
def test_local_runner_interrupt_cleans_group_and_preserves_partial_logs(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "interrupted"
    workspace = Workspace(workspace_root)
    workspace.ensure_layout()
    child_result = tmp_path / "interrupt-child-result.log"
    executable = _spawning_executable(tmp_path / "interrupt-engine", child_result)
    caller = _write_interruptible_caller(
        tmp_path / "interrupt-caller.py", executable, workspace_root
    )
    repo_root = Path(__file__).resolve().parents[1]
    process = subprocess.Popen(
        [sys.executable, str(caller)],
        cwd=repo_root,
        env={**os.environ, "PYTHONPATH": str(repo_root / "src")},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=8)
    except subprocess.TimeoutExpired:
        _kill_recorded_processes(child_result.with_name(child_result.name + ".pids"))
        process.kill()
        process.communicate()
        raise

    assert process.returncode == 42
    assert "CALLER_INTERRUPTED" in stdout
    assert not stderr
    _wait_for_tick(child_result)
    _assert_stopped_writing(child_result)
    partial = (workspace.outputs_dir / "stdout.log").read_text(encoding="utf-8")
    assert partial.count("launcher running") == 1
