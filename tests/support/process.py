from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_cli(
    *args: str | Path,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    source_path = str(PROJECT_ROOT / "src")
    merged_env["PYTHONPATH"] = source_path + os.pathsep + merged_env.get("PYTHONPATH", "")
    if env:
        merged_env.update(env)
    command: Sequence[str] = [sys.executable, "-m", "abacus_forge.cli", *(str(arg) for arg in args)]
    options: dict[str, object] = {
        "cwd": cwd,
        "env": merged_env,
        "text": True,
        "capture_output": True,
        "timeout": 30,
    }
    if input_text is None:
        options["stdin"] = subprocess.DEVNULL
    else:
        options["input"] = input_text
    return subprocess.run(command, **options)  # type: ignore[arg-type]
