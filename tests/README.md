# Forge test portfolio

The default suite is deterministic and offline. Markers describe evidence,
not implementation ownership:

| Marker | Evidence boundary | Release role |
| --- | --- | --- |
| `core` | INPUT/STRU/KPT, structures, transformations, DOS data, source import boundaries | required PR gate |
| `integration` | prepare/execute/collect/unit/task boundaries | required PR gate |
| `cli` | CLI dispatch and process contracts | required PR gate |
| `compat` | ABACUS/abacustest output compatibility | required migration gate |
| `pyatb` | PyATB mapping and collection | required when PyATB bridge is enabled |
| `composite` | local composite pack wiring | deterministic regression, not physics proof |
| `experimental` | mock/fixture-only property packs | non-stable evidence |
| `real_smoke` | seven supplied ABACUS workspace smokes (PW + LCAO) plus the external PyATB and ATST process smokes | opt-in release evidence |
| `benchmark` | normalized migration projections | opt-in migration evidence |

Commands:

```bash
conda run -n paimon python -m pytest -q
conda run -n paimon python -m pytest -q -m 'not experimental and not real_smoke and not benchmark'
conda run -n paimon python -m pytest -q -m experimental
conda run -n paimon python -m pytest -q --run-benchmark -m benchmark
conda run -n paimon python -m pytest -q --run-real-smoke -m real_smoke
```

The legacy SCF smoke and typed SCF machine smoke are separate evidence
surfaces. The legacy test calls the compatibility Python API; the typed test
calls only the machine CLI and is the evidence for the typed SCF operation
path. The typed SCF test copies the prepared workspace with links materialized,
runs one `operation execute` and one `operation collect` request with distinct
UUIDv4 operation IDs, and checks factual envelopes, audit events, manifest
references, and contained artifact paths. It uses the shared
`ABACUS_FORGE_REAL_SMOKE_WORKSPACE` and
`ABACUS_FORGE_ABACUS_EXECUTABLE` values:

```bash
export ABACUS_FORGE_REAL_SMOKE_WORKSPACE=/absolute/path/to/prepared-forge-workspace
export ABACUS_FORGE_ABACUS_EXECUTABLE=/absolute/path/to/abacus
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-real-smoke \
  tests/real_smoke/test_abacus_smoke.py -k typed_scf
```

The typed SCF and Relax smokes are opt-in and use only the machine CLI. The
typed SCF gate checks the copied `inputs/INPUT` declares `calculation=scf` before
the first execute call. The typed Relax gate copies a prepared workspace before
running one `execute` and one `collect` request with different operation IDs;
both calls use the long parent-process timeout. Set the shared executable and the
Relax-specific workspace; `ABACUS_FORGE_RELAX_SMOKE_CAPABILITY` defaults to
`relax` and accepts only `relax` or `cell-relax`:

```bash
export ABACUS_FORGE_RELAX_SMOKE_WORKSPACE=/absolute/path/to/prepared-relax-workspace
export ABACUS_FORGE_ABACUS_EXECUTABLE=/absolute/path/to/abacus
export ABACUS_FORGE_RELAX_SMOKE_CAPABILITY=relax
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-real-smoke \
  tests/real_smoke/test_abacus_smoke.py -k typed_relax
```

The typed Relax test has its own workspace gate and does not require the SCF
workspace variable. Missing real-smoke inputs skip with a precise reason;
supplied invalid paths, capabilities, or executables fail. These tests record
serialized outcome/event/artifact facts only and do not assess physical
convergence.

The typed MD test is an independent, experimental machine-CLI gate. It uses
`ABACUS_FORGE_MD_SMOKE_WORKSPACE` plus the shared
`ABACUS_FORGE_ABACUS_EXECUTABLE`, copies a prepared workspace whose
`inputs/INPUT` declares `calculation=md`, and runs one typed `execute` followed
by one typed `collect`:

```bash
export ABACUS_FORGE_MD_SMOKE_WORKSPACE=/absolute/path/to/prepared-md-workspace
export ABACUS_FORGE_ABACUS_EXECUTABLE=/absolute/path/to/abacus
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-real-smoke \
  tests/real_smoke/test_abacus_smoke.py -k typed_md
```

It checks native `running_md.log` parser facts, status, events, manifest and
contained artifacts; it does not evaluate trajectory quality or any scientific
threshold. `MD_dump` facts are collected as a separate factual projection.
Missing MD-specific inputs skip, while supplied invalid paths or a non-MD
workspace fail. The typed MD gate does not change legacy SCF/Relax smoke
behavior. The supplied source must not already contain generated
`running_md.log` or `MD_dump` files in collector-visible output areas (including
the native `inputs/OUT.*` layout), so a
no-op executable cannot pass by reusing an old MD result. Typed SCF and Relax
use the same collector-aware guard for their `running_*.log` files (including
`reports/`) and fallback `out.log`; Relax also guards final-structure outputs
outside `inputs/` and `reports/` (native outputs under `inputs/OUT.*` are also
guarded). Explicit non-generated `inputs/OUT.*` handoff assets remain allowed.
This is a real-smoke input condition only; normal Forge
execute/collect behavior is unchanged.

When no external real workspace or executable is supplied, each focused typed
selection skips and no real execution evidence is claimed. No smoke result is
promoted to stable capability evidence; the current capabilities remain
experimental until their own real gates and the remaining Stage 4 release
conditions are complete.

## Contract and workspace gate

Changes to versioned records, workspace persistence, or operation-boundary
artifacts must run the offline contract gate below, together with any owning
API/result tests:

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_contracts.py tests/test_workspace.py tests/test_result_contract.py tests/test_units.py tests/test_service_status.py
```

`tests/test_contracts.py` owns record validation, `tests/test_workspace.py`
owns the append-only manifest and event paths, and
`tests/test_result_contract.py` plus `tests/test_units.py` own result/API
projections, and `tests/test_service_status.py` owns the typed service's public
error and observation mapping. The v1 workspace manifest and event records are additive; legacy
`forge-unit.json` and `forge-result.json` compatibility outputs remain covered
by the unit tests.

`tests/test_machine_cli.py` owns the in-process machine decoder, discovery,
rendering, and service-dispatch contracts. `tests/test_cli_process.py` owns
subprocess stdout/stderr/exit behavior and API/process parity. The two suites
are the machine-path unit and process gates and should be run together for
transport changes. `tests/test_architecture.py` owns the AST-only production
import boundary and the current machine-surface documentation contracts; it
is registered as `core`.

`tests/fixtures/abacus-native-md` is a compact format fixture, not a science
case. It covers the repository-local ABACUSTest `!FINAL_ETOT_IS` marker and
the native ABACUS MD `running_md.log`/`MD_dump` shapes, including Ry-to-eV
projection and workspace-relative typed artifact facts. The fixture does not
provide real execution evidence or a physical acceptance judgment.

The typed SCF and Relax service tests additionally own the migration boundary:
`ForgeServices`/`RelaxServiceSet` return execution/collection facts and
observations, and any legacy `scientific` projection remains `unassessed`.
`dry_run` is explicit, and typed execution never infers a skip from an existing
`NORMAL END` log. Relax collection keeps parser/file facts separate from
scientific acceptance.
`run_many(skip_completed=True)` remains covered as a legacy compatibility helper
for composite tasks and is intentionally not part of the typed status protocol.

Deleting or merging a test requires a named production mutation that the
remaining test still catches. A passing count alone is not evidence.

Evidence limits: `core`, `integration`, `cli`, and `composite` are deterministic
PR gates; `compat` and `benchmark` are migration evidence; `real_smoke` is
release evidence. None of these alone proves physical convergence or HPC
scheduler correctness.
