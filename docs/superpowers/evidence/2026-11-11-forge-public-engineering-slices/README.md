# 2026-11-11 Forge public engineering slices

Identity: accepted over `QuantumMisaka/abacus-forge main@5621845`, reviewed at `c65931d`, and integrated by [PR #19](https://github.com/QuantumMisaka/abacus-forge/pull/19) as `main@f2c1cbe`; package version `0.1.0`. These results are source-local acceptance and do not publish PyPI or select a post-`v0.1.0` tag.

## Task 5 — execution lifecycle

- `LocalRunner` now starts each controlled execution in a new process group and on timeout sends SIGTERM, escalates to SIGKILL if needed, drains the pipes, then writes exactly one copy of stdout/stderr and returns `returncode=124`, `failure_class=timeout`.
- A caller `KeyboardInterrupt` follows the same cleanup boundary, preserves partial logs, stops the controlled descendants, and re-raises the original interrupt.
- Direct runner and composite `execute_subtask` regressions cover a spawning controlled executable, continued child writes before cleanup, unrelated-process survival, non-duplicated timeout logs, and interrupt cleanup.
- Verification: `tests/test_runner.py` — 3 passed; owning gate `test_runner.py test_workspace.py test_service_status.py test_composite_plan.py test_api.py` — 300 passed, 1 skipped. Independent review initially found duplicate timeout output and interrupt leakage; both were reproduced red, fixed, and covered by green tests.
- Boundary: descendants that deliberately escape the original process group cannot be safely cleaned without risking unrelated processes. Group-member enumeration is Linux `/proc`-based; non-Linux falls back to POSIX group signaling and pipe drain.

## Task 6 — continuous verification (local slice)

- `test_phonon_cli_and_python_preserve_angstrom_geometry_and_harmonic_response` now calls `pytest.importorskip("phonopy")` before importing `phonopy.file_IO`.
- The installed-package CI job gained an installed-only expansion/CLI/release step covering composite plan, elastic/vibration/phonon expansion, shared composite consumption, CLI, installed package mode, release, and abacuslite release gate with `PYTHONPATH=""`.
- Verification: missing-phonopy selector changed from `ModuleNotFoundError`/exit 1 to `1 skipped`/exit 0; full expansion file — 6 passed, 21 skipped; phonopy environment target — 1 passed; local installed-only CI selection — 132 passed; workflow parsed successfully. Runs `42944462372` and `42944518379` on the implementation commit, plus final-candidate `c65931d` runs `42944923407` and `42944930428`, completed all default-source and installed-package jobs for Python 3.10, 3.11, 3.12, and 3.13 ([PR #19](https://github.com/QuantumMisaka/abacus-forge/pull/19)).

## Task 7 — Agent-consumable task expansion

- `docs/agents.md`, compatibility, guide, and discovery remain explicit that composite units are separate from typed capabilities. Wheel `capabilities` returned 13 typed capabilities, no `phonon/elastic/vibration` entries, and SCF operations `prepare|modify|execute|collect`; therefore no compatibility schema was added.
- `examples/composite_unit_consumer.py` uses only public APIs and a caller-owned controlled executable to demonstrate vibration plan, independent execution/collection, caller-selected ordering, degraded gather with missing units, and explicit selected-unit retry.
- A wheel built from the current source was installed into a fresh isolated venv. The example printed `partial gather: degraded, missing=5` and `after selected retry: degraded, missing=5`; installed-only composite/runner/packaging tests passed (7 passed, then 8 passed after the packaging contract gained a fourth test).

## Task 8 — narrowed distributions

- Current build artifacts (`/tmp/forge-combined-build5`, not release artifacts):
  - sdist `abacus_forge-0.1.0.tar.gz`, 216 members, SHA-256 `11655d07ec33902dedcafe69c6ad217c0be83d3140ae25a3eafb8f3fb85d5374`;
  - wheel `abacus_forge-0.1.0-py3-none-any.whl`, 83 members, SHA-256 `aa29c206aa553274cc08cf949fb941c389ca1f98a6b3d9938eaa98ee207371d0`.
- The sdist retains source, tests (including required engine-log fixtures), examples, release validator, current user docs, repository entry documents, CI workflow, and exactly three required parser provenance records. It excludes `.scratch`, archive/history plans/specs, and broad evidence payloads.
- Clean `python -m build` exit 0; archive inspection confirmed no `.scratch`, archive, plans, or broad evidence payload and confirmed the new composite example/test files. Fresh-wheel install, `pip check`, public imports, composite example, and extracted-sdist documentation/release/package tests passed (31 passed, 4 source-distribution-specific skips), followed by the complete default extracted-sdist/installed-wheel suite: 1727 passed, 59 skipped.
- Repository history-link audit remains a source-checkout gate; in a narrowed sdist it is skipped explicitly by `PKG-INFO` detection rather than silently claiming all development history ships in the distribution.

## Task 9 — contribution entry

- Added `CONTRIBUTING.md`, bug/feature issue templates, and a PR template describing setup, owning-test selection, evidence, compatibility, provenance, and scientific-acceptance boundaries.
- A clean `git clone --no-local` at `c65931d` into `/tmp`, with no parent workplace or private Skill on path, was installed editable into a fresh Python 3.13 venv using only the documented public `[dev]` dependencies. Focused contribution tests passed (`11 passed`); the composite example again reached degraded gather with five missing units and explicit retry; `abacus-forge --version`, 13-capability discovery, and `pip check` passed. Source documentation-link tests and existing package provenance/license checks also passed. No missing reuse provenance was found by those gates.

## Remaining

Task 5–9 are complete. PR #19 merged the reviewed candidate as `main@f2c1cbe`; main CI run `42974464142` completed all Python 3.10–3.13 source and installed-package jobs and retained its tested distributions. Remaining work is the owner version/tag decision and explicitly authorized PyPI upload followed by fresh public-index validation. No release is published and `v0.1.0` is unchanged.
