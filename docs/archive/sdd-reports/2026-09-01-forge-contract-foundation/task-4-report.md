# Task 4 report: Document the additive Forge v1 workspace records

- Scope: documentation-only update to `README.md`, `AGENTS.md`, and `tests/README.md`.
- README now distinguishes the legacy `meta.json`, `forge-unit.json`, and `forge-result.json` compatibility files from the additive v1 records at `reports/forge-workspace.json` and `reports/events/*.json`. It documents `forge.workspace/v1`, `forge.result/v1` event payloads, workspace-relative `ArtifactRecord.path_rel` values, and append-only audit semantics without changing existing command examples.
- AGENTS now requires v1 `ArtifactRecord` coverage for operation-boundary artifacts, preserves the append-only manifest/event records, and names the contract/workspace/API-result regression gate.
- `tests/README.md` now documents the owning tests and the required offline command.
- Explicit scope boundary: this task does not add request-file CLI support, typed operation requests, expanded status policy, ATP integration, stable property packs, or real acceptance work.

## Verification

```text
$ git diff --check
exit=0

$ conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m abacus_forge.cli --help
exit=0
usage: abacus-forge [-h]
                    {prepare,modify-input,modify-stru,modify-kpt,modify,run,execute,collect,export,scf,relax,cell-relax,md,band,dos,eos,elastic,vibration,phonon,convergence,charge-density,spin-density,charge-diff,elf,bader,workfunc,vacancy,bec}
                    ...
... (help completed successfully)

$ conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_contracts.py tests/test_workspace.py tests/test_result_contract.py tests/test_units.py
exit=0
.................................                                        [100%]
33 passed in 3.26s
```

- Commit: `docs: describe forge v1 workspace records` (final HEAD hash is reported in the handoff).
- Risk: documentation can drift if persistence or compatibility output changes; the named contract/workspace/API-result tests are the regression gate. No runtime behavior or test code was changed.
