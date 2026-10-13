# Task 3 report: Project legacy results into v1 envelopes

- Base: `cd0492f0f44df37f9ec143451dea4bdac9513f01`
- RED: added envelope and event-order tests, then ran the focused suite. It failed with two expected missing-behavior failures: the collection envelope omitted the expected `stdout_log` artifact ID, and no workspace event manifest was created.
- Implementation: added additive `to_envelope()` projections for run, collection, and composite task results; scalar metric projection with JSON-safe legacy diagnostics; deterministic, workspace-relative artifact records and external-artifact warnings; and successful prepare/modify/execute/collect v1 operation event recording. Legacy `to_dict()` methods and `forge-unit.json`/`forge-result.json` writes remain unchanged.
- Changed files: `src/abacus_forge/result.py`, `src/abacus_forge/api.py`, `tests/test_result_contract.py`, `tests/test_units.py`.
- Owning tests: `32 passed` (`tests/test_result_contract.py tests/test_units.py tests/test_api.py`).
- Full regression: `141 passed, 2 skipped`.
- Head/commit: final commit with title `feat: record forge v1 operation envelopes` (hash reported with handoff).
- Risks: event files use the existing workspace UUID event IDs; envelope artifact metadata computes file hashes when files exist, so very large artifact collections incur read-time hashing cost.

## Review fix round

- Addressed all three P1 findings: direct dry-run collection now projects `skipped / unassessed / not_collected`; reserved log IDs are used only for canonical workspace logs and prefixed aggregate logs receive deterministic path hashes; every projection records omitted external artifacts under diagnostics warnings.
- Added focused regressions for dry-run axes, aggregate artifact ID uniqueness, and Run/Task external-artifact diagnostics.
- Verification: owning suites `35 passed`; full suite `144 passed, 2 skipped`.
- Commit: final amended commit with title `feat: record forge v1 operation envelopes` (hash reported with handoff).

## Re-review fix round 2

- Changed collection dry-run detection to depend solely on `CollectionResult.status == "dry-run"`; added a regression covering direct construction without diagnostics.
- Verification: owning suites `36 passed`; full suite `145 passed, 2 skipped`.
- Commit: final amended commit with title `feat: record forge v1 operation envelopes` (hash reported with handoff).
