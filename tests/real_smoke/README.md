# Real ABACUS smoke

The smoke gate consumes a prepared Forge workspace and never edits the source
workspace. The workspace must contain valid `inputs/INPUT`, `inputs/STRU`,
`inputs/KPT`, and all pseudopotential/orbital assets required by its INPUT.

```bash
export ABACUS_FORGE_REAL_SMOKE_WORKSPACE=/absolute/path/to/prepared-forge-workspace
export ABACUS_FORGE_ABACUS_EXECUTABLE=/absolute/path/to/abacus
conda run -n paimon python -m pytest -q --run-real-smoke -m real_smoke
```

The typed Relax path is a separate, experimental machine-CLI smoke. It copies
the prepared source into a temporary workspace, runs one `execute` request and
one `collect` request with distinct operation IDs, and checks serialized
execution/collection, event, energy, and final-structure artifact facts. It
does not apply a physical convergence threshold. The default capability is
`relax`; set it to `cell-relax` for the other supported phase:

```bash
export ABACUS_FORGE_REAL_SMOKE_WORKSPACE=/absolute/path/to/prepared-workspace
export ABACUS_FORGE_RELAX_SMOKE_WORKSPACE=/absolute/path/to/prepared-relax-workspace
export ABACUS_FORGE_ABACUS_EXECUTABLE=/absolute/path/to/abacus
export ABACUS_FORGE_RELAX_SMOKE_CAPABILITY=relax
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-real-smoke \
  tests/real_smoke/test_abacus_smoke.py -k typed_relax
```

`ABACUS_FORGE_REAL_SMOKE_WORKSPACE` is also required by the module-level
real-smoke gate; it can be the same prepared directory when selecting only
`typed_relax`. Missing Relax-specific environment values skip with a precise
reason. An invalid supplied workspace, capability, or executable fails the
test. No real Relax workspace is bundled with Forge, so this test remains
unproven until those values are supplied.

This gate proves Forge execution and collection integration only. It does not
replace convergence studies, platform validation, or the Paimon v1.2 benchmark.
