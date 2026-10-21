# ABACUS-Forge

ABACUS-Forge is a lightweight Python library and command-line tool for preparing ABACUS inputs, editing individual input files, running a local process, collecting output facts, and exporting results. It works with one workspace at a time. Workflow orchestration, cluster scheduling, platform integration, and scientific acceptance remain with the caller.

## Install and first workspace

Python 3.10 or newer is required. The first PyPI release is being prepared; today, install from the project Git URL if you have access, or from a wheel supplied by the maintainer. Neither route requires a source checkout in your working directory:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install 'git+https://github.com/QuantumMisaka/abacus-forge.git'
abacus-forge doctor
```

See [installation](docs/installation.md) for the wheel option, environment checks, and optional dependencies. The following runs in any empty directory with Forge installed. It creates a one-atom Si CIF, prepares an SCF workspace, and checks the typed dry-run state without starting ABACUS:

```bash
python - <<'PY'
from pathlib import Path
from uuid import uuid4
from ase import Atoms
from ase.io import write
from abacus_forge import OperationOutcome, ScfExecuteRequest, ScfServiceSet, prepare

root = Path("forge-first-run").resolve()  # use a fresh name to repeat
root.mkdir(exist_ok=False)
write(root / "Si.cif", Atoms("Si", positions=[[0, 0, 0]], cell=[5.43] * 3, pbc=True))
workspace = prepare(root / "scf", structure=root / "Si.cif", task="scf",
                    parameters={"basis_type": "pw", "ecutwfc": 40},
                    kpoints=[1, 1, 1], asset_mode="copy")
assert all((workspace.inputs_dir / name).is_file() for name in ("INPUT", "STRU", "KPT"))
outcome = ScfServiceSet.default(workspace_root=root).execute.execute(
    ScfExecuteRequest(str(uuid4()), "scf", executable="abacus", dry_run=True))
assert isinstance(outcome, OperationOutcome), outcome.to_dict()
status = outcome.envelope.status
assert (status.execution, status.collection, status.scientific) == (
    "skipped", "not_collected", "unassessed"), status.to_dict()
print(status.to_dict())
PY
```

This inspection structure has no pseudopotential, so it is **not** ready for an actual SCF calculation. For a real run, supply ABACUS, suitable pseudopotential files and, for LCAO, orbital files; inspect the generated `INPUT` and `STRU` before execution. The [full quickstart](docs/quickstart.md) gives the real-SCF commands and checks the human collector's top-level status and metrics. The [Agent guide](docs/agents.md) shows capability and schema discovery, typed JSON operations, missing prerequisites, and incomplete collection. A normal CLI exit is not scientific acceptance; the typed dry-run explicitly reports `scientific=unassessed`.

## Capability maturity

Capabilities exposed through multiple APIs do not necessarily share the same contract or maturity. The current typed capability descriptors mark SCF, Relax, cell-relax, MD, band/DOS/COHP postprocess, PyATB band handoff, direct NAO `pyatb-cohp`, polarization, BEC, ATST-NEB, and typed export as experimental. The bounded native BEC implementation is complete within its approved scope: typed `polarization/collect` and `bec/postprocess` reuse generic APIs for preparation, displacement, and single-stage execution, while cross-run orchestration remains with the caller. Fresh-wheel MgO validation covers one real `O_x` response; a full tensor, convergence, and scientific acceptance remain open. The existing legacy BEC pack is unchanged and remains experimental.

The typed band and DOS capabilities currently provide `postprocess` only. They do not provide typed band or DOS execution. Legacy task, unit, and sequence entry points remain available with their existing behavior.

Collected values are facts about available files and parser output. Forge reports `scientific=unassessed` for typed outcomes and does not decide whether a result is physically acceptable.

## Documentation

- [Installation](docs/installation.md), [first workspace](docs/quickstart.md), [Agent integration](docs/agents.md), and [public compatibility](docs/compatibility.md).
- [Documentation index](docs/README.md) — Chinese navigation for users and maintainers.
- [Usage guide](docs/guide.md) — CLI and Python paths, workspace preparation, execution, collection, and capability-specific examples.
- [API and workspace reference](docs/reference.md) — current interfaces, request boundaries, assets, outputs, and status semantics.
- [Architecture](docs/architecture.md) — code organization and extension points.
- [Development and test entry points](AGENTS.md) and [test guide](tests/README.md).
- [Roadmap](ROADMAP.md) — current work and separately tracked cleanup candidates.
- [Design and implementation governance](docs/superpowers/README.md).

### Previous README sections

These headings remain as navigation anchors for links to the former long README. The full content is maintained in the Chinese usage guide and reference.

<a id="agent-first-cli"></a>
#### Agent-first CLI

See the [Agent-first CLI guide](docs/guide.md#agent-first-cli).

<a id="cli-quick-start"></a>
<a id="cli-快速上手"></a>
#### CLI quick start

See the [CLI workflows](docs/guide.md#cli-workflows).

<a id="typed-banddos-postprocess-experimental"></a>
<a id="typed-banddos-postprocessexperimental"></a>
#### Typed band/DOS postprocess (experimental)

See [typed band/DOS postprocess](docs/guide.md#typed-banddos-postprocess).

<a id="typed-cohp-postprocess-experimental"></a>
<a id="typed-cohppostprocessexperimental"></a>
#### Typed COHP postprocess (experimental)

The typed `cohp` capability currently provides **IAO-COHP** (`method="iao"`): COHP evaluated in an IAO representation constructed from ABACUS NAO outputs. Direct NAO-COHP is not implemented by this typed capability. See [typed COHP postprocess](docs/guide.md#typed-cohp-postprocess).

<a id="typed-export-experimental"></a>
<a id="typed-exportexperimental"></a>
#### Typed export (experimental)

See [typed export](docs/guide.md#typed-export).

<a id="typed-pyatb-band-handoff-experimental"></a>
<a id="typed-pyatb-band-handoffexperimental"></a>
#### Typed PyATB band handoff (experimental)

See [typed PyATB band handoff](docs/guide.md#typed-pyatb-band-handoff).

Direct NAO-COHP is available separately through experimental `pyatb-cohp` prepare/execute/collect operations. It requires explicit matrices, numerical orbitals, Fermi energy, k points and weights. See [direct NAO-COHP](docs/guide.md#direct-nao-cohp).

<a id="typed-relax-operations"></a>
#### Typed Relax operations

See [typed Relax operations](docs/guide.md#typed-relax-operations).

<a id="typed-md-operations"></a>
#### Typed MD operations

See [typed MD operations](docs/guide.md#typed-md-operations).

<a id="typed-md-postprocess-experimental"></a>
<a id="typed-md-postprocessexperimental"></a>
#### Typed MD postprocess (experimental)

See [typed MD postprocess](docs/guide.md#typed-md-postprocess).

<a id="python-library"></a>
<a id="作为-python-库使用"></a>
#### Python library

See [Python usage](docs/guide.md#python-api).

<a id="directory-convention"></a>
<a id="目录约定"></a>
#### Directory convention

See [workspace layout and records](docs/reference.md#workspace-layout-and-records).
