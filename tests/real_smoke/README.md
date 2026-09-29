# Real process smoke gates

The smoke gate consumes a prepared Forge workspace and never edits the source
workspace. The workspace must contain valid `inputs/INPUT`, `inputs/STRU`,
`inputs/KPT`, and all pseudopotential/orbital assets required by its INPUT.

```bash
export ABACUS_FORGE_REAL_SMOKE_WORKSPACE=/absolute/path/to/prepared-forge-workspace
export ABACUS_FORGE_ABACUS_EXECUTABLE=/absolute/path/to/abacus
conda run -n paimon python -m pytest -q --run-real-smoke -m real_smoke
```

The legacy SCF smoke above is intentionally a separate compatibility evidence
surface: it calls the legacy Python `execute_unit`/`collect_unit` API and only
checks the legacy result objects. The typed SCF smoke uses the machine CLI
(`operation execute --stdin` followed by `operation collect --stdin`) with
distinct UUIDv4 operation IDs, and checks the serialized operation envelope,
facts, audit events, manifest references, and contained artifact paths. Only
the typed test proves the typed machine path; neither test makes a scientific
acceptance decision.

To select only the typed SCF machine smoke:

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-real-smoke \
  tests/real_smoke/test_abacus_smoke.py -k typed_scf
```

On a checkout without the two external environment values, the focused local
selection is skipped (`1 skipped, 2 deselected` without `--run-real-smoke`),
and no real execution evidence is claimed. Supplying an invalid workspace or
executable fails the test rather than turning the missing input into a pass.

The typed Relax path is a separate, experimental machine-CLI smoke. It copies
the prepared source into a temporary workspace, runs one `execute` request and
one `collect` request with distinct operation IDs, and checks serialized
execution/collection, event, energy, and final-structure artifact facts. It
does not apply a physical convergence threshold. The default capability is
`relax`; set it to `cell-relax` for the other supported phase:

```bash
export ABACUS_FORGE_RELAX_SMOKE_WORKSPACE=/absolute/path/to/prepared-relax-workspace
export ABACUS_FORGE_ABACUS_EXECUTABLE=/absolute/path/to/abacus
export ABACUS_FORGE_RELAX_SMOKE_CAPABILITY=relax
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-real-smoke \
  tests/real_smoke/test_abacus_smoke.py -k typed_relax
```

The typed Relax test has its own environment gate and does not require the
legacy SCF variable `ABACUS_FORGE_REAL_SMOKE_WORKSPACE`. Missing Relax-specific
environment values skip with a precise reason. An invalid supplied workspace,
capability, or executable fails the test. No real Relax workspace is bundled
with Forge, so this test remains unproven until those values are supplied.

The typed MD path is a separate, experimental machine-CLI smoke. It copies a
prepared `calculation=md` workspace, runs one typed `execute` and one typed
`collect`, and checks the native `running_md.log` parser facts (the final
thermodynamic scalars), status, audit events, manifest references, and
contained artifacts. `MD_dump` facts remain a separate parser projection. Set
the MD-specific workspace together with the shared executable:

```bash
export ABACUS_FORGE_MD_SMOKE_WORKSPACE=/absolute/path/to/prepared-md-workspace
export ABACUS_FORGE_ABACUS_EXECUTABLE=/absolute/path/to/abacus
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-real-smoke \
  tests/real_smoke/test_abacus_smoke.py -k typed_md
```

The typed MD gate has its own workspace variable and does not require the SCF
or Relax workspace variables. Missing MD-specific values skip with a precise
reason; an invalid supplied workspace, executable, or non-MD `INPUT` fails.
The supplied source must not already contain generated `running_md.log` or
`MD_dump` files in collector-visible output areas, including the native
`inputs/OUT.*` layout; this prevents an old run from being mistaken for
evidence from the new execute call. The typed SCF and
Relax gates apply the same freshness rule to their `running_*.log` files,
including logs under `reports/`, and to the Forge fallback `out.log`. Relax
also rejects existing final-structure outputs (`STRU_FINAL`,
`STRU_FINAL.cif`, `STRU_ION_D`, `STRU_NOW`, `STRU_NOW.cif`, `STRU.cif`, or
`STRU`) in collector-visible output locations, including `inputs/OUT.*`.
Explicit non-generated `inputs/OUT.*` restart or handoff assets remain the
caller's responsibility and are not rejected by this evidence-only guard.
The gate checks parser facts only. It does not judge trajectory quality,
physical temperature/energy correctness, convergence, scheduling, or workflow
orchestration.

The ABACUS, PyATB and ATST process smokes are evidence gates, not scientific validation. They prove
only the selected Forge execution/collection integration and do not replace
convergence studies, platform validation, workflow/scheduler checks, or the
Paimon v1.2 benchmark. All capabilities remain experimental until their own
real gates and the other Stage 4 release conditions are satisfied.

The typed LCAO SCF smokes are additional opt-in gates over the same typed
machine path, asserting `basis_type=lcao` in the prepared INPUT. They come in
three variants with separate workspace variables, sharing
`ABACUS_FORGE_ABACUS_EXECUTABLE`:

```bash
export ABACUS_FORGE_ABACUS_EXECUTABLE=/absolute/path/to/abacus
export ABACUS_FORGE_LCAO_SMOKE_WORKSPACE=/absolute/path/to/si-lcao-scf-source
export ABACUS_FORGE_LCAO_NSPIN2_SMOKE_WORKSPACE=/absolute/path/to/fe-lcao-nspin2-source
export ABACUS_FORGE_LCAO_MATRICES_SMOKE_WORKSPACE=/absolute/path/to/si-lcao-matrices-source
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-real-smoke \
  tests/real_smoke/test_abacus_smoke.py -k lcao
```

The nspin2 variant additionally asserts `nspin=2`; the matrices variant
asserts `out_mat_hs2=1` and `out_mat_r=1` and checks that the ABACUS process
generated the sparse HR/SR/rR matrices under `inputs/OUT.ABACUS/`. The gate
accepts both the v1.2/LTS-era file names (`data-HR-sparse_SPIN0.csr`,
`data-SR-sparse_SPIN0.csr`, `data-rR-sparse.csr`) and the v3.11-beta names
(`hrs1_nao.csr`, `sr_nao.csr`, `rr.csr`); which naming the typed
`pyatb-band` handoff can consume is a version-policy question recorded in the
Stage 5 evidence, not an assertion of this gate. The LCAO sources used for
the recorded evidence take PP/ORB from the Paimon v1.2 `abacus-pp-orb`
lineage (see the workspace `abacus-packages/` README). These gates check
process, parser, and artifact facts only; they make no convergence or
scientific acceptance decision.

Known version-matrix findings (recorded in the Stage 5 evidence):

- ABACUS develop (v3.11.0-beta8+56, `94576a801`): all nine real-smoke gates
  pass, but the LCAO sparse matrix files use the new `*_nao.csr`/`rr.csr`
  names, so a develop executable does not satisfy the current typed
  `pyatb-band` handoff file contract without an explicit rename or handoff
  extension.
- ABACUS LTS (v3.10.1, `f71921fe8`): the typed relax/cell-relax collection is
  `partial` because v3.10.1 does not write `STRU_FINAL` (it writes
  `STRU_ION_D`/`STRU_NOW.cif`), so the final-structure fact is unavailable;
  the other eight gates pass.

The typed PyATB band process smoke is an additional opt-in gate. It consumes a
caller-provided source directory with this layout and copies it into an isolated
temporary Forge workspace before running:

```text
<workspace>/source/STRU
<workspace>/source/data-HR-sparse_SPIN0.csr
<workspace>/source/data-HR-sparse_SPIN1.csr
<workspace>/source/data-SR-sparse_SPIN0.csr
<workspace>/source/data-rR-sparse.csr       # optional for the request, present in this gate
```

The source must not already contain generated PyATB files below
`inputs/Out/Band_Structure/` (for example `band_info.dat`, `band_up.dat`,
`band_dn.dat`, `band.pdf`, or `band.png`). Set the executable and the explicit
Fermi energy, then run:

```bash
export ABACUS_FORGE_PYATB_SMOKE_WORKSPACE=/absolute/path/to/pyatb-source-root
export ABACUS_FORGE_PYATB_EXECUTABLE=/absolute/path/to/pyatb
export ABACUS_FORGE_PYATB_SMOKE_FERMI_ENERGY=15.5241312077
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-real-smoke \
  tests/real_smoke/test_pyatb_smoke.py
```

The gate executes one typed `prepare`, one local PyATB process through typed
`execute`, and one explicit `collect`. It checks the generated handoff, native
band artifacts, parser-reported `band_gap`, operation events, artifact refs,
workspace containment, and `scientific=unassessed`. The command selected by the
execute operation is checked in the compatibility `forge-result.json`; the
frozen result envelope is not widened for this smoke. The reported band gap is
an observed parser metric, not a scientific acceptance decision. A missing
workspace, executable, or Fermi energy skips only when unset; an invalid value
fails the gate. This is process/parser/artifact compatibility evidence, not a
PyATB property or NEB workflow result.

The ATST-tools NEB process smoke is an additional opt-in gate. It uses the
explicitly selected ATST 2.2.4 executable and does not start ABACUS:

```bash
export ABACUS_FORGE_ATST_EXECUTABLE=/absolute/path/to/atst
conda run -n atst-dev env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-real-smoke \
  tests/real_smoke/test_atst_smoke.py
```

This test runs `atst neb make`, `atst run --dry-run`, and `atst neb summary/post`
through Forge's machine CLI, checking only process envelopes, status, contained
summary/CIF artifacts, and audit containment. It is process/API compatibility
evidence, not a real NEB execution, scientific validation, or maturity proof.

The vacancy property-pack process smoke is an additional opt-in gate. It
consumes a caller-provided prepared Forge workspace (with `inputs/INPUT`,
`inputs/STRU`, `inputs/KPT`, and all PP/ORB assets), builds one pristine and
one defect sub-workspace through `prepare_vacancy`, runs real ABACUS in both
through `run_vacancy`, and computes formation-energy parser facts with
`post_vacancy`:

```bash
export ABACUS_FORGE_VACANCY_SMOKE_WORKSPACE=/absolute/path/to/prepared-vacancy-source
export ABACUS_FORGE_ABACUS_EXECUTABLE=/absolute/path/to/abacus
# Optional: 1-based atom index to remove; defaults to 1.
export ABACUS_FORGE_VACANCY_SMOKE_INDEX=1
conda run -n abacus-env env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-real-smoke \
  tests/real_smoke/test_vacancy_smoke.py
```

The source may include an optional `vacancy/ref_energy.txt` file with one
`<element> <energy_eV>` pair per line; when present, `post_vacancy` computes
finite formation energies and reports `completed`; otherwise it reports
`degraded` with `null` formation values. Both outcomes are acceptable process
evidence. The gate checks pack orchestration, process completion, and parser
facts only. It does not judge formation-energy physical correctness,
convergence quality, or scientific acceptance.
