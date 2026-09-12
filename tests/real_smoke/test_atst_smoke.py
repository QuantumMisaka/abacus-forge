from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from tests.support.process import run_cli


def _json_document(process) -> dict[str, object]:
    assert process.stderr == ""
    value = json.loads(process.stdout)
    assert isinstance(value, dict)
    return value


def _assert_contained_artifacts(workspace: Path, envelope: dict[str, object]) -> set[str]:
    body = envelope["envelope"]
    assert isinstance(body, dict)
    artifacts = body["artifacts"]
    assert isinstance(artifacts, list)
    paths: set[str] = set()
    for item in artifacts:
        assert isinstance(item, dict)
        path_rel = item["path_rel"]
        assert isinstance(path_rel, str)
        path = Path(path_rel)
        assert not path.is_absolute() and ".." not in path.parts
        resolved = (workspace / path).resolve(strict=True)
        resolved.relative_to(workspace.resolve())
        assert resolved.is_file()
        paths.add(path_rel)
    return paths


@pytest.mark.real_smoke
def test_atst_neb_machine_process_smoke(tmp_path: Path) -> None:
    configured = os.environ.get("ABACUS_FORGE_ATST_EXECUTABLE")
    if not configured:
        pytest.skip("set ABACUS_FORGE_ATST_EXECUTABLE")
    from ase import Atoms
    from ase.calculators.singlepoint import SinglePointCalculator
    from ase.io import write

    executable = Path(configured)
    if executable.parent != Path():
        if not executable.is_file() or not os.access(executable, os.X_OK):
            pytest.fail(f"ABACUS_FORGE_ATST_EXECUTABLE is not executable: {executable}")
        executable = executable.resolve()
    else:
        found = shutil.which(configured)
        if found is None:
            pytest.fail(f"ABACUS_FORGE_ATST_EXECUTABLE is not executable: {configured}")
        executable = Path(found).resolve()

    # Forge invokes the configured ATST adapter by its stable CLI name. Put
    # the explicitly selected executable first so this gate tests that binary.
    env = {"PATH": str(executable.parent) + os.pathsep + os.environ.get("PATH", "")}
    init = Atoms("H", positions=[[0.0, 0.0, 0.0]], cell=[8.0, 8.0, 8.0], pbc=True)
    final = init.copy()
    final.positions[0, 0] = 0.5
    write(tmp_path / "init.traj", init)
    write(tmp_path / "final.traj", final)
    config = tmp_path / "workflow.yaml"
    config.write_text(
        "calculation:\n"
        "  type: neb\n"
        "  init_chain: inputs/init_neb_chain.traj\n"
        "calculator:\n"
        "  name: abacus\n"
        "  abacus:\n"
        "    command: abacus\n",
        encoding="utf-8",
    )

    base = {
        "schema_version": "forge.request/v1",
        "capability": "atst-neb",
        "workspace_rel": ".",
    }
    prepare = run_cli(
        "operation", "prepare", "--stdin", cwd=tmp_path, env=env,
        input_text=json.dumps({
            **base,
            "operation": "prepare",
            "operation_id": "123e4567-e89b-42d3-a456-426614174230",
            "init_structure_path_rel": "init.traj",
            "final_structure_path_rel": "final.traj",
            "chain_path_rel": "inputs/init_neb_chain.traj",
            "n_images": 1,
            "method": "linear",
        }),
    )
    prepared = _json_document(prepare)
    assert prepare.returncode == 0
    assert prepared["envelope"]["status"]["execution"] == "completed"
    _assert_contained_artifacts(tmp_path, prepared)
    assert (tmp_path / "inputs/init_neb_chain.traj").is_file()

    # `neb make` intentionally produces structures only.  Give postprocess a
    # separate finite-energy/force trajectory so ATST summary can consume it;
    # this is parser/process coverage, not a physical NEB result.
    post_chain = []
    for energy, position in ((0.0, 0.0), (1.0, 0.5), (0.0, 1.0)):
        image = init.copy()
        image.positions[0, 0] = position
        image.calc = SinglePointCalculator(
            image, energy=energy, forces=[[0.0, 0.0, 0.0]]
        )
        post_chain.append(image)
    write(tmp_path / "inputs/neb.traj", post_chain)

    executed = run_cli(
        "operation", "execute", "--stdin", cwd=tmp_path, env=env,
        input_text=json.dumps({
            **base,
            "operation": "execute",
            "operation_id": "123e4567-e89b-42d3-a456-426614174231",
            "config_path_rel": "workflow.yaml",
            "dry_run": True,
        }),
    )
    execution = _json_document(executed)
    assert executed.returncode == 0
    assert execution["envelope"]["status"]["execution"] == "skipped"
    _assert_contained_artifacts(tmp_path, execution)

    postprocessed = run_cli(
        "operation", "postprocess", "--stdin", cwd=tmp_path, env=env,
        input_text=json.dumps({
            **base,
            "operation": "postprocess",
            "operation_id": "123e4567-e89b-42d3-a456-426614174232",
            "trajectory_path_rel": "inputs/neb.traj",
            "summary_path_rel": "reports/atst/neb-summary.json",
            "output_prefix": "outputs/atst/neb-ts",
        }),
    )
    post = _json_document(postprocessed)
    assert postprocessed.returncode == 0
    assert post["envelope"]["status"]["execution"] == "completed"
    assert post["envelope"]["status"]["collection"] == "complete"
    paths = _assert_contained_artifacts(tmp_path, post)
    assert "reports/atst/neb-summary.json" in paths
    assert "outputs/atst/neb-ts.cif" in paths
    assert (tmp_path / "reports/forge-workspace.json").is_file()
