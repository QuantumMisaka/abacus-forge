# ABACUS-Forge

ABACUS-Forge is a lightweight Python library and command-line tool for preparing ABACUS inputs, editing individual input files, running a local process, collecting output facts, and exporting results. It works with one workspace at a time. Workflow orchestration, cluster scheduling, platform integration, and scientific acceptance remain with the caller.

## Install

Python 3.10 or newer is required. Install the package from this repository:

```bash
python -m pip install .
```

The optional phonon pack requires `phonopy`:

```bash
python -m pip install '.[phonon]'
```

The optional `abacuslite` parser backend requires the published `abacuslite` package. The extra pins the exact verified release:

```bash
python -m pip install '.[abacuslite]'
```

Running an ABACUS calculation also requires an ABACUS executable available to the local process and the pseudopotential and, where needed, orbital files referenced by the input. Forge does not provide these external assets or install ABACUS.

To inspect the installed command surface without ABACUS inputs:

```bash
abacus-forge --help
abacus-forge capabilities
```

## Minimal local calculation

Start with a structure file and the resource files you intend ABACUS to use. The following prepares an SCF workspace, executes ABACUS, then collects facts. Replace the structure and asset paths with files available in your environment.

```bash
abacus-forge prepare runs/Si_scf \
  --structure path/to/Si.cif \
  --task scf \
  --parameter ecutwfc=70 \
  --kpoint 3 --kpoint 3 --kpoint 1 \
  --pseudo-path path/to/pseudopotentials \
  --orbital-path path/to/orbitals \
  --asset-mode copy
abacus-forge execute runs/Si_scf --executable abacus --mpi 1 --omp 1
abacus-forge collect runs/Si_scf --json
```

Preparation creates the `INPUT`, `STRU`, and `KPT` files. Check the generated input and resource references before execution. A `prepare` call can also be used on its own to inspect generated inputs before ABACUS is available.

For Python use, the primitive API exposes the same preparation and collection boundaries:

```python
from abacus_forge import collect, prepare

workspace = prepare(
    "runs/Si_scf",
    structure="path/to/Si.cif",
    task="scf",
    parameters={"ecutwfc": 70},
    kpoints=[3, 3, 1],
    pseudo_path="path/to/pseudopotentials",
    orbital_path="path/to/orbitals",
    asset_mode="copy",
)
result = collect(workspace)
print(result.status)
```

The Python example prepares and collects; it does not start ABACUS. See the [usage guide](docs/guide.md) for execution, typed operations, unit APIs, sequences, and packs.

## Capability maturity

Capabilities exposed through multiple APIs do not necessarily share the same contract or maturity. The current typed capability descriptors mark SCF, Relax, cell-relax, MD, band/DOS/COHP postprocess, PyATB band handoff, direct NAO `pyatb-cohp`, polarization, BEC, ATST-NEB, and typed export as experimental. The bounded native BEC implementation is complete within its approved scope: typed `polarization/collect` and `bec/postprocess` reuse generic APIs for preparation, displacement, and single-stage execution, while cross-run orchestration remains with the caller. Fresh-wheel MgO validation covers one real `O_x` response; a full tensor, convergence, and scientific acceptance remain open. The existing legacy BEC pack is unchanged and remains experimental.

The typed band and DOS capabilities currently provide `postprocess` only. They do not provide typed band or DOS execution. Legacy task, unit, and sequence entry points remain available with their existing behavior.

Collected values are facts about available files and parser output. Forge reports `scientific=unassessed` for typed outcomes and does not decide whether a result is physically acceptable.

## Documentation

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
