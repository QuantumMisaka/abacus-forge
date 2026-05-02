"""Local process runner primitive."""

from __future__ import annotations

import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from abacus_forge.result import RunResult
from abacus_forge.workspace import Workspace


@dataclass(slots=True)
class LocalRunner:
    """Build and execute a local ABACUS command."""

    executable: str = "abacus"
    mpi_ranks: int = 1
    omp_threads: int = 1
    launcher: Sequence[str] = field(default_factory=tuple)
    extra_args: Sequence[str] = field(default_factory=tuple)
    timeout_seconds: float | None = None
    env_overrides: dict[str, str] = field(default_factory=dict)

    def build_command(self, workspace: Workspace) -> list[str]:
        command: list[str] = []
        if self.launcher:
            command.extend(self.launcher)
        elif self.mpi_ranks > 1:
            command.extend(["mpirun", "-np", str(self.mpi_ranks)])
        command.append(self.executable)
        command.extend(self.extra_args)
        command.extend(["--input-dir", str(workspace.inputs_dir)])
        return command

    def preview(self, workspace: Workspace) -> dict[str, object]:
        """Return the command and environment that would be used for a run."""

        return {
            "command": self.build_command(workspace),
            "cwd": str(workspace.root),
            "env": self._run_environment(),
            "timeout_seconds": self.timeout_seconds,
        }

    def _resolve_executable(self) -> str:
        candidate = Path(self.executable)
        if candidate.parent != Path():
            resolved = candidate if candidate.is_absolute() else candidate.resolve()
            if resolved.exists() and resolved.is_file() and os.access(resolved, os.X_OK):
                return str(resolved)
            raise FileNotFoundError(f"Executable not found or not executable: {self.executable}")

        resolved = shutil.which(self.executable)
        if resolved is None:
            raise FileNotFoundError(f"Executable not found or not executable: {self.executable}")
        return resolved

    def run(self, workspace: Workspace, check: bool = False) -> RunResult:
        workspace.ensure_layout()
        command = self.build_command(workspace)
        stdout_path = workspace.outputs_dir / "stdout.log"
        stderr_path = workspace.outputs_dir / "stderr.log"
        diagnostics = {
            "launcher": list(self.launcher),
            "extra_args": list(self.extra_args),
            "mpi_ranks": self.mpi_ranks,
            "omp_threads": self.omp_threads,
            "timeout_seconds": self.timeout_seconds,
            "env_overrides": dict(self.env_overrides),
        }
        try:
            self._resolve_executable()
        except FileNotFoundError as exc:
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text(str(exc) + "\n", encoding="utf-8")
            diagnostics.update(
                {
                    "failure_class": "missing_executable",
                    "stderr_tail": str(exc),
                    "stdout_tail": "",
                }
            )
            if check:
                raise
            return RunResult(
                workspace=workspace.root,
                command=command,
                returncode=127,
                status="failed",
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                omp_threads=self.omp_threads,
                diagnostics=diagnostics,
            )

        try:
            completed = subprocess.run(
                command,
                cwd=workspace.root,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, **self._run_environment()},
                timeout=self.timeout_seconds,
            )
            stdout = completed.stdout
            stderr = completed.stderr
            returncode = completed.returncode
            failure_class = "none" if returncode == 0 else "nonzero_exit"
        except subprocess.TimeoutExpired as exc:
            stdout = _coerce_output(exc.stdout)
            stderr = _coerce_output(exc.stderr) or f"Command timed out after {self.timeout_seconds} seconds\n"
            returncode = 124
            failure_class = "timeout"

        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        diagnostics.update(
            {
                "failure_class": failure_class,
                "stdout_tail": _tail(stdout),
                "stderr_tail": _tail(stderr),
            }
        )

        if check and returncode != 0:
            raise subprocess.CalledProcessError(
                returncode,
                command,
                output=stdout,
                stderr=stderr,
            )

        return RunResult(
            workspace=workspace.root,
            command=command,
            returncode=returncode,
            status="completed" if returncode == 0 else "failed",
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            omp_threads=self.omp_threads,
            diagnostics=diagnostics,
        )

    def _run_environment(self) -> dict[str, str]:
        env = {"OMP_NUM_THREADS": str(self.omp_threads)}
        env.update({str(key): str(value) for key, value in self.env_overrides.items()})
        return env


def run_many(
    workspaces: Sequence[str | Path | Workspace],
    *,
    runner: LocalRunner | None = None,
    max_workers: int = 1,
    skip_completed: bool = True,
) -> list[RunResult]:
    """Run several local workspaces without introducing scheduler semantics."""

    local_runner = runner or LocalRunner()
    normalized = [item if isinstance(item, Workspace) else Workspace(Path(item)) for item in workspaces]
    if max_workers <= 1:
        return [_run_one_for_many(workspace, runner=local_runner, skip_completed=skip_completed) for workspace in normalized]
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(
            executor.map(
                lambda workspace: _run_one_for_many(workspace, runner=local_runner, skip_completed=skip_completed),
                normalized,
            )
        )


def _run_one_for_many(workspace: Workspace, *, runner: LocalRunner, skip_completed: bool) -> RunResult:
    workspace.ensure_layout()
    if skip_completed and _looks_completed(workspace):
        stdout_path = workspace.outputs_dir / "stdout.log"
        stderr_path = workspace.outputs_dir / "stderr.log"
        stdout_path.touch(exist_ok=True)
        stderr_path.touch(exist_ok=True)
        return RunResult(
            workspace=workspace.root,
            command=runner.build_command(workspace),
            returncode=0,
            status="skipped",
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            omp_threads=runner.omp_threads,
            diagnostics={"skip_completed": True, "failure_class": "none"},
        )
    return runner.run(workspace)


def _looks_completed(workspace: Workspace) -> bool:
    for candidate in (
        workspace.outputs_dir / "stdout.log",
        workspace.outputs_dir / "OUT.ABACUS" / "running_scf.log",
        workspace.outputs_dir / "OUT.ABACUS" / "running_relax.log",
        workspace.outputs_dir / "OUT.ABACUS" / "running_cell-relax.log",
        workspace.outputs_dir / "OUT.ABACUS" / "running_md.log",
    ):
        if not candidate.exists():
            continue
        content = candidate.read_text(encoding="utf-8", errors="ignore")
        if "SCF CONVERGED" in content.upper() or "TOTAL  TIME" in content.upper() or "NORMAL END" in content.upper():
            return True
    return False


def _tail(text: str, *, lines: int = 20) -> str:
    return "\n".join(text.splitlines()[-lines:])


def _coerce_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return value
