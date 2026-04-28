"""Local process runner primitive."""

from __future__ import annotations

import os
import shutil
import subprocess
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
        self._resolve_executable()
        command = self.build_command(workspace)
        stdout_path = workspace.outputs_dir / "stdout.log"
        stderr_path = workspace.outputs_dir / "stderr.log"
        env = {"OMP_NUM_THREADS": str(self.omp_threads)}

        completed = subprocess.run(
            command,
            cwd=workspace.root,
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, **env},
        )
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")

        if check and completed.returncode != 0:
            raise subprocess.CalledProcessError(
                completed.returncode,
                command,
                output=completed.stdout,
                stderr=completed.stderr,
            )

        return RunResult(
            workspace=workspace.root,
            command=command,
            returncode=completed.returncode,
            status="completed" if completed.returncode == 0 else "failed",
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            omp_threads=self.omp_threads,
            diagnostics={
                "launcher": list(self.launcher),
                "extra_args": list(self.extra_args),
                "mpi_ranks": self.mpi_ranks,
                "omp_threads": self.omp_threads,
            },
        )
