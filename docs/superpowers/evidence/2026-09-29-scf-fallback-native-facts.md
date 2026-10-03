# SCF fallback native facts — 2026-09-29

Candidate: branch `fix/scf-fallback-facts`, base `079ea5a6`; base implementation `6704422` plus post-integration review fix `e8c0402`, both in `src/abacus_forge/collectors/abacus.py` and owning tests. The referenced real-SAI manifest below froze the pre-commit dirty content that is byte-equivalent to the base collector behavior. This is an L2 parser correction and additive diagnostic, with no request/result/workspace schema change.

- Recognize native `convergence has NOT been achieved!` and lowercase `@_@` variants as explicit negative evidence.
- Add `diagnostics.last_scf_converged`: final explicit SCF marker in the selected main log, or `None`. The fact intentionally excludes the generic `not converged` marker because relaxation status lines reuse that spelling; explicit `convergence has NOT been achieved` and `SCF NOT CONVERGED` remain SCF-negative facts. Preserve existing aggregate `metrics.converged` behavior: any negative marker, including final relaxation failure, remains negative evidence. Consumers needing the final SCF outcome must not infer it from the aggregate.
- Empty `time.json` (`{}`) retains stdout timing and its origin; nonempty JSON with missing/null `total` retains the existing `None` behavior and clears stale provenance.

Negative-marker and empty-JSON regressions were observed failing before fixes. Ordered mixed-marker tests cover both directions without weakening aggregate failure evidence. Independent integration review identified one boundary defect: an SCF pass followed by `Relaxation is not converged yet!` incorrectly set `last_scf_converged=false`; the regression failed before the SCF-specific marker split and passes after it. Validation:

```bash
conda run -n paimon env PYTHONPATH=src python -m pytest tests/test_result_contract.py tests/test_service_status.py tests/test_md_services.py tests/test_collect_abacus_reference.py -q
```

229 passed. The post-integration boundary regression is `5 passed, 24 deselected` when selected by test node; full offline validation is `1437 passed, 34 skipped`. Paimon uses a narrow four-field compatibility projection; its paired tests cover 30 log/timing combinations. On SAI, final job **1551103**, ABACUS LTS 3.10.1, 4V100/1 GPU/1 rank, completed with exit 0:0. H₂/PW converged and intentionally unconverged runs match the old collector in energy, convergence, normal-end and timing; the candidate executes with legacy imports blocked. This is direct fallback evidence, not Agent/Flow or benchmark acceptance.

Authoritative cross-repository implementation record and raw evidence: Paimon `toolbox/ABACUS/docs/reports/2026-09-29-paimon-w2-scf-fallback.md` and its `sai/` directory. The manifest binds the actual dirty source and inputs; Paimon's configured `ac870b7` pin does **not** contain this change. Candidate integration and deployment remain open under W3. No develop build or production deployment is claimed.

Independent same-family review closed both compatibility findings and verified all 2040 frozen manifest entries against the final local candidate; re-collection of the two returned SAI logs matched the saved oracle. Accepted as a verified candidate slice, with W3 deployment still open.
