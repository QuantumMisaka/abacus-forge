"""Phonon local composite task pack."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from abacus_forge.composite.common import artifacts_under, collect_subtasks, ensure_root, require_prepared_inputs, run_subtasks, write_subtask, write_task_result
from abacus_forge.result import TaskResult


def prepare_phonon(
    workspace: str | Path,
    *,
    phonopy: str = "phonopy",
    setting_file: str = "setting.conf",
) -> TaskResult:
    root = ensure_root(workspace)
    input_params, structure, kpt_payload = require_prepared_inputs(root)
    input_params["calculation"] = "scf"
    input_params["cal_force"] = 1
    diagnostics: dict[str, Any] = {"phonopy": phonopy, "setting_file": setting_file}
    subtasks = []
    if shutil.which(phonopy) is None:
        sub = write_subtask(
            root,
            "phonon/ABACUS-001",
            input_params=input_params,
            structure=structure,
            kpt_payload=kpt_payload,
            metadata={"task": "phonon", "subtask_index": 1, "source": "fallback-single-displacement"},
        )
        diagnostics["optional_dependency_missing"] = "phonopy"
        subtasks.append({"workspace": str(sub.root), "source": "fallback-single-displacement"})
    else:
        completed = subprocess.run(
            [phonopy, setting_file, "--abacus", "-d"],
            cwd=root.root,
            capture_output=True,
            text=True,
            check=False,
        )
        diagnostics["phonopy_prepare_returncode"] = completed.returncode
        diagnostics["phonopy_prepare_stdout_tail"] = "\n".join(completed.stdout.splitlines()[-20:])
        diagnostics["phonopy_prepare_stderr_tail"] = "\n".join(completed.stderr.splitlines()[-20:])
        for index, stru_path in enumerate(sorted(root.root.glob("STRU-*")), start=1):
            sub = write_subtask(
                root,
                f"phonon/ABACUS-{index:03d}",
                input_params=input_params,
                structure=type(structure).from_input(stru_path, structure_format="stru"),
                kpt_payload=kpt_payload,
                metadata={"task": "phonon", "subtask_index": index, "source": stru_path.name},
            )
            subtasks.append({"workspace": str(sub.root), "source": stru_path.name})
    path = write_task_result(root, "reports/phonon_plan.json", {"task": "phonon", "subtasks": subtasks, "diagnostics": diagnostics})
    return TaskResult(
        task="phonon",
        workspace=root.root,
        status="prepared" if subtasks else "degraded",
        subtasks=subtasks,
        summary={"count": len(subtasks)},
        artifacts={str(path.relative_to(root.root)): str(path)},
        diagnostics=diagnostics,
    )


def run_phonon(workspace: str | Path, **kwargs: Any) -> TaskResult:
    root = ensure_root(workspace)
    subtasks = sorted((root.root / "phonon").glob("ABACUS-*"))
    return run_subtasks("phonon", root, subtasks, **kwargs)


def post_phonon(
    workspace: str | Path,
    *,
    phonopy: str = "phonopy",
    setting_file: str = "setting.conf",
    only_plot: bool = False,
) -> TaskResult:
    root = ensure_root(workspace)
    paths = sorted((root.root / "phonon").glob("ABACUS-*"))
    rows = collect_subtasks(paths)
    diagnostics: dict[str, Any] = {"phonopy": phonopy, "only_plot": only_plot}
    if shutil.which(phonopy) is None:
        diagnostics["optional_dependency_missing"] = "phonopy"
    else:
        if not only_plot:
            force_result = subprocess.run(
                [phonopy, "-f", *[str(path / "outputs" / "stdout.log") for path in paths]],
                cwd=root.root,
                capture_output=True,
                text=True,
                check=False,
            )
            diagnostics["phonopy_force_returncode"] = force_result.returncode
        plot_result = subprocess.run(
            [phonopy, "-p", setting_file, "--abacus", "-s"],
            cwd=root.root,
            capture_output=True,
            text=True,
            check=False,
        )
        diagnostics["phonopy_post_returncode"] = plot_result.returncode
    summary = {
        "subtask_count": len(rows),
        "completed_subtasks": sum(1 for row in rows if row["status"] == "completed"),
        "phonon_artifacts": [str(path.relative_to(root.root)) for path in root.root.glob("*.yaml")],
    }
    path = write_task_result(root, "reports/metrics_phonon.json", summary)
    return TaskResult(
        task="phonon",
        workspace=root.root,
        status="completed" if rows else "degraded",
        subtasks=rows,
        summary=summary,
        artifacts={**artifacts_under(root, "phonon"), str(path.relative_to(root.root)): str(path)},
        diagnostics=diagnostics,
    )
