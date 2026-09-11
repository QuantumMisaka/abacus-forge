# Task 2 report — core migration fact boundary

## Result

Task 2 is complete. The requested developer-facing operation boundaries and
core migration evidence notes are recorded. The task changes no production
code, tests, SPEC, README, public API, schema, result, status, CLI, or runtime
behavior.

Workflow routing: **L1**. This was a local, reversible documentation-only
change with an explicit file and verification boundary.

Changed documentation files:

- `AGENTS.md`: `execute` is canonical, `run` is compatibility-only,
  `collect` is observation-only, and `postprocess` is an independent typed
  operation.
- `docs/superpowers/plans/2026-09-11-forge-maturity-gates-integration.md`:
  added the dated Core migration fact matrix follow-up with fixture scope,
  exact benchmark commands/results, the required evidence-boundary sentence,
  and the experimental maturity rule.
- `docs/superpowers/plans/2026-09-01-forge-test-portfolio-governance.md`:
  added a completion/evidence link to
  `tests/benchmark/test_core_capability_facts.py` without rewriting the
  historical checklist or making the benchmark a default gate.

This report is the requested SDD evidence artifact.

## Baseline architecture check

Command:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q tests/test_architecture.py
```

Output:

```text
........                                                                 [100%]
8 passed in 5.61s
```

Exit code: `0`.

## Task 1 benchmark evidence

The Task 1 matrix was replayed from the current worktree before the
documentation edit. Its focused command produced:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q tests/benchmark/test_core_capability_facts.py --run-benchmark
....                                                                     [100%]
4 passed in 1.28s
```

Exit code: `0`.

The owning migration command produced:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q tests/benchmark/test_core_capability_facts.py tests/benchmark/test_abacustest_compatibility.py --run-benchmark
......                                                                   [100%]
6 passed in 1.73s
```

Exit code: `0`.

These are opt-in migration facts over the four isolated SCF, Relax,
cell-relax, and MD fixture projections. They do not establish scientific
correctness, convergence quality, orchestration, scheduler integration, or
stable maturity. Task 1's fixture/status deviations remain documented in
`task-1-report.md` and were not changed here.

## Post-edit verification

### `git diff --check`

Command:

```text
git diff --check
```

Output: no output.

Exit code: `0`.

### HTML and placeholder check

Command:

```text
python - <<'PY'
from pathlib import Path
from html.parser import HTMLParser

for path in Path("docs/superpowers/specs").glob("*.html"):
    HTMLParser().feed(path.read_text(encoding="utf-8"))
for path in (Path("AGENTS.md"), Path("docs/superpowers/plans/2026-09-11-forge-maturity-gates-integration.md"), Path("docs/superpowers/plans/2026-09-01-forge-test-portfolio-governance.md")):
    text = path.read_text(encoding="utf-8")
    assert "TBD" not in text and "TODO" not in text
print("HTML and placeholder checks passed")
PY
```

Output:

```text
HTML and placeholder checks passed
```

Exit code: `0`.

### Owning architecture check after editing

Command:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q tests/test_architecture.py
```

Output:

```text
........                                                                 [100%]
8 passed in 5.96s
```

Exit code: `0`.

## Concerns

There are no Task 2 blockers. The matrix remains an explicit opt-in
migration-evidence gate. All typed capabilities remain `experimental` until
the approved SPEC's separate compat, real-smoke, clean-environment, and
release decision gates are satisfied; no benchmark result is treated as a
default gate, scientific acceptance, or maturity promotion.
