# Real ABACUS smoke

The smoke gate consumes a prepared Forge workspace and never edits the source
workspace. The workspace must contain valid `inputs/INPUT`, `inputs/STRU`,
`inputs/KPT`, and all pseudopotential/orbital assets required by its INPUT.

```bash
export ABACUS_FORGE_REAL_SMOKE_WORKSPACE=/absolute/path/to/prepared-forge-workspace
export ABACUS_FORGE_ABACUS_EXECUTABLE=/absolute/path/to/abacus
conda run -n paimon python -m pytest -q --run-real-smoke -m real_smoke
```

This gate proves Forge execution and collection integration only. It does not
replace convergence studies, platform validation, or the Paimon v1.2 benchmark.
