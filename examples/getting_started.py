"""Installed-package, engine-free Forge introduction.

Run from any directory with ``python getting_started.py --workspace first-run``.
The one-atom structure has no pseudopotential and is for input inspection only;
it cannot be used for a real ABACUS calculation until real assets are supplied.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from ase import Atoms
from ase.io import write as write_structure

from abacus_forge import (
    ForgeErrorEnvelope,
    OperationOutcome,
    ScfCollectRequest,
    ScfExecuteRequest,
    ScfServiceSet,
    prepare,
)


def run_example(root: Path, *, exercise_errors: bool = False) -> dict:
    """Create a new example workspace and inspect real Forge status records."""
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=False)
    atoms = Atoms("Si", positions=[[0.0, 0.0, 0.0]], cell=[5.43, 5.43, 5.43], pbc=True)
    structure_path = root / "Si.cif"
    write_structure(structure_path, atoms)
    prepared = prepare(
        root / "scf",
        structure=structure_path,
        task="scf",
        parameters={"basis_type": "pw", "ecutwfc": 40},
        kpoints=[1, 1, 1],
        asset_mode="copy",
    )
    expected = [prepared.inputs_dir / name for name in ("INPUT", "STRU", "KPT")]
    if any(not path.is_file() for path in expected):
        raise RuntimeError("prepare did not create INPUT, STRU and KPT")

    services = ScfServiceSet.default(workspace_root=root)
    dry = services.execute.execute(ScfExecuteRequest(
        str(uuid4()), "scf", executable="abacus", dry_run=True,
    ))
    if not isinstance(dry, OperationOutcome):
        raise RuntimeError(f"dry-run returned an error: {dry.to_dict()}")
    status = dry.envelope.status
    if (status.execution, status.collection, status.scientific) != (
        "skipped", "not_collected", "unassessed"
    ):
        raise RuntimeError(f"unexpected dry-run status: {status.to_dict()}")

    summary = {
        "structure_file": str(structure_path.relative_to(root)),
        "prepared_files": [str(path.relative_to(root)) for path in expected],
        "dry_run_status": status.to_dict(),
        "dry_run_diagnostics": dry.envelope.to_dict()["diagnostics"],
        "engine_started": False,
        "assets_are_real": False,
    }
    if exercise_errors:
        # A missing executable is a precondition error, never a successful run.
        absent = services.execute.execute(ScfExecuteRequest(
            str(uuid4()), "scf", executable="forge-example-missing-abacus-executable", dry_run=False,
        ))
        if not isinstance(absent, ForgeErrorEnvelope) or absent.error_class != "precondition.missing":
            raise RuntimeError(f"missing executable was not reported: {absent.to_dict()}")
        summary["missing_executable"] = absent.to_dict()

        # A new workspace with no INPUT/STRU/KPT also fails before launching.
        no_inputs = services.execute.execute(ScfExecuteRequest(
            str(uuid4()), "empty", executable="forge-example-missing-abacus-executable", dry_run=False,
        ))
        if not isinstance(no_inputs, ForgeErrorEnvelope) or no_inputs.error_class != "precondition.missing":
            raise RuntimeError(f"missing inputs were not reported: {no_inputs.to_dict()}")
        summary["missing_inputs"] = no_inputs.to_dict()

        # Collecting the prepared directory has no ABACUS output. A normal
        # process exit would still be insufficient; inspect collection state.
        collected = services.collect.collect(ScfCollectRequest(str(uuid4()), "scf"))
        if not isinstance(collected, OperationOutcome):
            raise RuntimeError(f"collect returned an error: {collected.to_dict()}")
        if collected.envelope.status.collection not in ("partial", "missing_output"):
            raise RuntimeError("engine-free collect unexpectedly claimed complete output")
        summary["collect_without_engine_status"] = collected.envelope.status.to_dict()
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True, help="new directory; must not exist")
    parser.add_argument("--exercise-errors", action="store_true", help="also show missing executable/input and incomplete collection")
    args = parser.parse_args()
    print(json.dumps(run_example(args.workspace, exercise_errors=args.exercise_errors), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
