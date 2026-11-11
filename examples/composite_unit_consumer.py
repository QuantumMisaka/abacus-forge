"""Consume one vibration expansion without installing ABACUS.

This example uses public Forge APIs and a caller-owned controlled executable.
It intentionally demonstrates partial/out-of-order gathering and an explicit retry
of one selected unit; it does not claim scientific acceptance.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from ase import Atoms

from abacus_forge.api import prepare
from abacus_forge.composite import (
    collect_subtask,
    execute_subtask,
    gather_subtasks,
    list_subtasks,
    prepare_vibration,
)
from abacus_forge.runner import LocalRunner


def controlled_executable(path: Path) -> Path:
    """Write a deterministic stand-in engine that only prints process facts."""

    path.write_text(
        "#!/usr/bin/env python3\n"
        "print('NATOM = 1')\n"
        "print('SCF CONVERGED')\n"
        "print('NORMAL END')\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | 0o111)
    return path


def main(root: Path | str | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, help="new or empty workspace root")
    args = parser.parse_args() if root is None else argparse.Namespace(root=Path(root))
    root = args.root or Path(tempfile.mkdtemp(prefix="forge-vibration-example-"))
    root.mkdir(parents=True, exist_ok=True)

    prepare(root, structure=Atoms("H", positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True), task="scf")
    prepare_vibration(root, atom_indices=[1])
    units = list_subtasks(root, "vibration").subtasks
    print(f"prepared {len(units)} vibration units in {root}")

    engine = controlled_executable(root / ".example-engine")
    runner = LocalRunner(executable=str(engine))
    records = []
    # Consume units in an order chosen by the caller; gather restores plan order.
    for unit in reversed(units[:2]):
        execution = execute_subtask(root, "vibration", unit["unit_id"], runner=runner)
        print(f"{unit['unit_id']}: execution={execution['status']}")
        records.append(collect_subtask(root, "vibration", unit["unit_id"]))

    records_by_id = {record["unit_id"]: record for record in records}
    partial = gather_subtasks(root, "vibration", records_by_id.values())
    print(f"partial gather: {partial.status}, missing={len(partial.summary['missing_units'])}")

    # Retry only the first selected unit. Previous attempts remain append-only;
    # the caller explicitly chooses the latest collection record for this gather.
    selected = units[0]["unit_id"]
    retry = execute_subtask(root, "vibration", selected, runner=runner)
    retried = collect_subtask(root, "vibration", selected)
    records_by_id[retried["unit_id"]] = retried
    print(f"{selected}: retry={retry['status']}")
    after_retry = gather_subtasks(root, "vibration", records_by_id.values())
    print(f"after selected retry: {after_retry.status}, missing={len(after_retry.summary['missing_units'])}")


if __name__ == "__main__":
    main()
