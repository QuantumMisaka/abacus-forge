# First workspace: prepare and inspect without ABACUS

Install Forge using [one of the current package sources](installation.md). The commands below work from any empty directory after activating that environment. They generate one small Si structure, prepare `INPUT`, `STRU`, and `KPT`, and make one typed dry-run request. The structure has **no pseudopotential**; it is only for input inspection and cannot be executed as a real SCF calculation.

```bash
python - <<'PY'
from pathlib import Path
from uuid import uuid4

from ase import Atoms
from ase.io import write
from abacus_forge import OperationOutcome, ScfExecuteRequest, ScfServiceSet, prepare

root = Path("forge-first-run").resolve()  # choose a fresh name for another run
root.mkdir(exist_ok=False)
write(root / "Si.cif", Atoms("Si", positions=[[0, 0, 0]], cell=[5.43] * 3, pbc=True))
workspace = prepare(
    root / "scf", structure=root / "Si.cif", task="scf",
    parameters={"basis_type": "pw", "ecutwfc": 40},
    kpoints=[1, 1, 1], asset_mode="copy",
)
for name in ("INPUT", "STRU", "KPT"):
    assert (workspace.inputs_dir / name).is_file(), name

outcome = ScfServiceSet.default(workspace_root=root).execute.execute(
    ScfExecuteRequest(str(uuid4()), "scf", executable="abacus", dry_run=True)
)
assert isinstance(outcome, OperationOutcome), outcome.to_dict()
status = outcome.envelope.status
assert (status.execution, status.collection, status.scientific) == (
    "skipped", "not_collected", "unassessed"
), status.to_dict()
print("Prepared:", *(workspace.inputs_dir / name for name in ("INPUT", "STRU", "KPT")), sep="\n  ")
print("Dry-run status:", status.to_dict())
PY
```

The dry-run writes an operation record and a skipped result in `forge-first-run/scf`. It does **not** start ABACUS or create scientific output. `execution=skipped` and `collection=not_collected` are the expected result; `scientific=unassessed` never means the calculation is accepted. [The companion example script](../examples/getting_started.py) runs the same path and can also demonstrate missing executable, missing inputs, and no-output collection with `--exercise-errors`.

For a real plane-wave SCF, supply a valid pseudopotential and ABACUS executable. Start a **new** workspace so the inspection-only STRU is not reused:

```bash
abacus-forge doctor --executable /path/to/abacus --asset /path/to/Si.upf
abacus-forge prepare forge-first-run/real-scf \
  --structure forge-first-run/Si.cif --task scf \
  --parameter basis_type=pw --parameter ecutwfc=70 \
  --kpoint 3 --kpoint 3 --kpoint 3 \
  --pseudo-path /path/to/pseudopotential-directory --asset-mode copy
abacus-forge execute forge-first-run/real-scf --executable /path/to/abacus --mpi 1 --omp 1
abacus-forge collect forge-first-run/real-scf --json > forge-first-run/real-scf/collection.json
python - <<'PY'
import json
import math
from pathlib import Path

result = json.loads(Path("forge-first-run/real-scf/collection.json").read_text())
metrics = result["metrics"]
energy = metrics.get("total_energy")
if (result["status"] != "completed" or metrics.get("converged") is not True
        or isinstance(energy, bool) or not isinstance(energy, (int, float))
        or not math.isfinite(energy)):
    raise SystemExit(f"SCF collection incomplete: status={result['status']}; inspect collection.json diagnostics")
print("Collected total energy (eV):", energy)
PY
```

The pseudopotential directory must contain the species file Forge selects for Si. Inspect `forge-first-run/real-scf/inputs/STRU` and `INPUT` before running; confirm that the STRU pseudopotential name matches the copied file in `inputs/`. Use `--orbital-path /path/to/orbitals` and an appropriate `basis_type` for LCAO. This human `collect --json` command returns a legacy `CollectionResult`: its top-level `status` is `completed`, `unfinished`, `failed`, or `missing-output`, with parser facts under `metrics` and details under `diagnostics`. It has no `checks` field. A zero CLI exit alone does not mean the SCF collection is complete; the example checks the legacy status, convergence marker, and finite energy. The caller still judges whether the scientific settings and result are suitable. For typed `envelope.status.collection` values such as `partial` or `missing_output`, and typed checks, use the [Agent guide](agents.md).
