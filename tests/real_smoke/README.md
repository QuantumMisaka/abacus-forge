# Real ABACUS smoke

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
The gate checks parser facts only. It does not judge trajectory quality,
physical temperature/energy correctness, convergence, scheduling, or workflow
orchestration.

All four smoke tests are evidence gates, not scientific validation. They prove
only the selected Forge execution/collection integration and do not replace
convergence studies, platform validation, workflow/scheduler checks, or the
Paimon v1.2 benchmark. All capabilities remain experimental until their own
real gates and the other Stage 4 release conditions are satisfied.
