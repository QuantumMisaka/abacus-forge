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
        return command

    def preview(self, workspace: Workspace) -> dict[str, object]:
        """Return the command and environment that would be used for a run."""

        return {
            "command": self.build_command(workspace),
            "cwd": str(workspace.inputs_dir),
            "env": self._run_environment(),
            "timeout_seconds": self.timeout_seconds,
        }

    @staticmethod
    def _resolve_program(
        program: str,
        *,
        role: str,
        env: dict[str, str] | None = None,
    ) -> str:
        candidate = Path(program)
        if candidate.parent != Path():
            # Directory-qualified paths are relative to the caller's cwd.  Use
            # lexical anchoring so a symlink remains visible as argv[0].
            resolved = Path(os.path.abspath(os.fspath(candidate)))
            if resolved.exists() and resolved.is_file() and os.access(resolved, os.X_OK):
                return str(resolved)
            raise FileNotFoundError(f"{role} executable not found or not executable: {program}")

        # PATH entries are interpreted from the caller's cwd.  Resolve the
        # selected basename before entering the workspace so subprocess launch
        # does not reinterpret a relative PATH under ``cwd=inputs_dir``.
        search_cwd = Path.cwd()
        search_path = (env or os.environ).get("PATH", os.defpath)
        if all(not entry or Path(entry).is_absolute() for entry in search_path.split(os.pathsep)):
            resolved = shutil.which(program, path=search_path)
            if resolved is not None:
                return resolved
            raise FileNotFoundError(f"{role} executable not found or not executable: {program}")
        for entry in search_path.split(os.pathsep):
            directory = Path(entry) if entry else Path(".")
            if not directory.is_absolute():
                directory = search_cwd / directory
            resolved = Path(os.path.abspath(os.fspath(directory / program)))
            if resolved.exists() and resolved.is_file() and os.access(resolved, os.X_OK):
                return str(resolved)
        raise FileNotFoundError(f"{role} executable not found or not executable: {program}")

    def preflight(self, workspace: Workspace) -> None:
        """Verify every program required before starting the local process."""

        self._resolved_command(workspace)

    def _resolved_command(self, workspace: Workspace) -> list[str]:
        command = self.build_command(workspace)
        env = {**os.environ, **self._run_environment()}
        if self.launcher:
            command[0] = self._resolve_program(str(command[0]), role="launcher", env=env)
        elif self.mpi_ranks > 1:
            command[0] = self._resolve_program("mpirun", role="launcher", env=env)
        executable_index = len(self.launcher) if self.launcher else (3 if self.mpi_ranks > 1 else 0)
        command[executable_index] = self._resolve_program(
            str(command[executable_index]),
            role="engine",
            env=env,
        )
        return command

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
            execution_command = self._resolved_command(workspace)
        except FileNotFoundError as exc:
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text(str(exc) + "\n", encoding="utf-8")
            diagnostics.update(
                {
                    "failure_class": "missing_executable",
                    "termination": "not_started",
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
                execution_command,
                cwd=workspace.inputs_dir,
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, **self._run_environment()},
                timeout=self.timeout_seconds,
            )
            stdout = completed.stdout
            stderr = completed.stderr
            returncode = completed.returncode
            if returncode < 0:
                failure_class = "signal"
                termination = "signal"
            else:
                failure_class = "none" if returncode == 0 else "nonzero_exit"
                termination = "exited"
        except subprocess.TimeoutExpired as exc:
            stdout = _coerce_output(exc.stdout)
            stderr = _coerce_output(exc.stderr) or f"Command timed out after {self.timeout_seconds} seconds\n"
            returncode = 124
            failure_class = "timeout"
            termination = "timeout"

        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        diagnostics.update(
            {
                "failure_class": failure_class,
                "termination": termination,
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
    """Run several local workspaces using the legacy skip policy.

    This compatibility helper may infer ``skipped`` from existing output when
    ``skip_completed`` is true.  Typed v1 services must call ``LocalRunner.run``
    directly and use an explicit request-level dry-run instead.
    """

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
