# Vacancy property-pack real-smoke process evidence (2026-09-29)

## Scope

First real ABACUS execution through the `vacancy` composite property pack,
using the opt-in real-smoke gate added in `466ef98`. This proves the pack
orchestration (prepare → run → post) with real ABACUS processes on pristine
and defect sub-workspaces. It does **not** claim formation-energy scientific
acceptance or stable maturity promotion.

## Execution environment

- Forge: `d35f164` (main branch, test/docs-only commits on top of `ac870b7`)
- ABACUS LTS v3.10.1: commit `f71921fe8`
  - executable SHA-256: `51f898a40698200db79bacfdc5a0c799847d712941f7da04773a474022412d8f`
- Source workspace: `abacus-packages/smoke-sources/vacancy-si-lcao`
  - Forge `prepare` output (PP/ORB inside `inputs/`, `asset_mode=copy`)
  - INPUT SHA-256: `1a13dcbeacb999a4dd84aab0d674b1a7b5300a18f93e9f4e29bb1f8863e2f6aa`
  - STRU SHA-256: `8c4c248905c74511b4cd3c56aa6bf94f06ffd2aaa9bf5b1c33a52507fc268901`
  - KPT SHA-256: `92b917107d9df11da28a465cc4900f3574956a057ddf9f7ad125e75c956ec508`
- System: Si diamond LCAO SCF, `ecutwfc=100`, `ks_solver=genelpa`, 2×2×2 k-mesh
- Vacancy index: 1 (one Si atom removed from the 2-atom primitive cell)
- MPI ranks: 1; OMP threads: 1; timeout: 1800 s

## Test command

```bash
conda run -n abacus-env env \
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  ABACUS_FORGE_VACANCY_SMOKE_WORKSPACE=<workspace> \
  ABACUS_FORGE_ABACUS_EXECUTABLE=<abacus> \
  ABACUS_FORGE_VACANCY_SMOKE_INDEX=1 \
  LD_LIBRARY_PATH=<scalapack>:<openblas>:<fftw> \
  python -m pytest tests/real_smoke/test_vacancy_smoke.py \
  -q --run-real-smoke -p no:cacheprovider
```

Result: `1 passed` (9.03 s / 9.11 s across two runs).

## Verified facts

The gate asserted (from `test_vacancy_smoke.py`):

1. `prepare_vacancy` returned `prepared` with `count=1` defect subtask.
2. `run_vacancy` returned `completed` with `total=2` subtasks, `failed=0`.
3. `post_vacancy` returned a valid status; both sub-workspace `collect`
   results exposed finite `total_energy` metrics (parser-arithmetic facts).
4. Formation-energy entry exists for `defect_001` (value may be `None`
   when no reference energy file is provided; both outcomes accepted).
5. Pack-level subtask roles include `pristine` and at least one `defect`.

No reference energy file was supplied in this run, so formation energies
are reported as `None` (degraded). Both pristine and defect SCF completed
with parseable finite total energies, proving the ABACUS execution and
collection pipeline for the vacancy pack.

## Boundary

This is process/parser/artifact compatibility evidence. It does not judge
formation-energy physical correctness, convergence quality, or vacancy
formation-energy scientific validity. The vacancy pack remains experimental.
