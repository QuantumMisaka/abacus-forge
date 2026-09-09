# Task 2 report — explicit PyATB handoff and collection algorithms

Base revision: `a2561d3` (Task 2 base; `docs: plan typed PyATB band handoff`)

## RED

Command:

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_pyatb_typed.py
```

Raw result before implementation:

```text
ImportError while importing test module ...
ImportError: cannot import name 'collect_typed_pyatb_band' from 'abacus_forge.pyatb'
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

## GREEN

The owning suite and unchanged legacy PyATB suite pass:

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_pyatb_typed.py tests/test_pyatb.py
....................                                                     [100%]
20 passed in 1.01s
```

`git diff --check` also passed.

## Implementation

- Added explicit `prepare_typed_pyatb_band` and `collect_typed_pyatb_band` helpers
  to `src/abacus_forge/pyatb.py`; legacy helper bodies and signatures were not
  changed.
- Typed preparation validates all contained source files and destination
  conflicts before writing, stages relative links or independent `copy2`
  snapshots, emits source/destination SHA-256 provenance, and renders explicit
  PyATB `Input` and `KPT_band` files for spin-1 and spin-2 routes.
- Typed collection only indexes declared contained output files, reports
  missing/malformed/escaped paths, and exposes a parseable textual `band_gap`
  only as a `reported` metric with `scientific=unassessed`.
- Added temporary-workspace tests for link/copy provenance, containment,
  collisions/no-partial-write, STRU parsing, spin routes, generated files,
  explicit output collection and facts-only behavior.

## Remaining scope

No real PyATB execution, service/CLI dispatch, scheduler integration or
scientific acceptance logic was added; those belong to later tasks/stages.

## Fix round R1

The fix round started from the Task 2 implementation revision `940706a` and
kept the Task 2 base revision above as `a2561d3`.

### RED

Added regressions for lexical provenance of an existing link alias, copy-mode
alias rejection without mutation, unsafe matrix/line-point tokens, and
spin-section band-gap parsing.

Command:

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_pyatb_typed.py
```

Raw result:

```text
.........FF.FF..FFFFFF....FF.                                            [100%]
12 failed, 17 passed in 1.22s
```

The failures were the intended pre-fix regressions: alias provenance resolved
to `source/hr.csr`, copy mode retained the alias, unsafe comma/braces/label
tokens were rendered, and the parser selected the first spin section.

### GREEN and acceptance

The final owning and unchanged legacy suites pass:

```text
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider tests/test_pyatb_typed.py tests/test_pyatb.py
...................................                                      [100%]
35 passed in 1.40s
```

`git diff --check` passed with no output (exit 0).

### R1 implementation

- Existing exact symlink aliases retain lexical destination provenance in link
  mode; copy mode rejects any existing symlink before staging or generated
  file writes.
- Typed preparation rejects whitespace, comma, braces, `#`, and `//` in
  matrix basenames and line-point labels immediately before filesystem work,
  while leaving the public request contract permissive.
- Band-gap parsing prefers the `For total band:` section and only publishes a
  single unambiguous match when no total section exists; ambiguous spin gaps
  remain factual parser absence.

Fix-round implementation commit: `ec97e35` (`fix: tighten typed PyATB handoff boundaries`).
