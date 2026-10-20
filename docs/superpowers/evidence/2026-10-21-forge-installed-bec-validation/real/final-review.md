# Independent final evidence review

Reviewer: existing `consumption_final_review` agent, read-only.
Reviewed current candidate wheel and final retained validation artifacts.
Result: passed, no blocking finding.

- 788 archived file digests matched at review time (before this review record was added).
- Checked 8 SCF / 24 NSCF logs, receipts, collector status and before/after charge hashes.
- Independently recalculated from native sensitivity logs:
  half displacement -1.954850069282992 e;
  denser mesh -1.955397438111399 e.
  Differences from installed results were below 2e-13 e.
- Actual KPT, installed test command and result completeness markers matched the report.
- Claims remain MgO O_x, finite sensitivity, experimental; no full tensor,
  scientific convergence or Paimon/platform acceptance claim.

Earlier review findings resolved: distinguish ASE atom 2 from serialized atom 1;
label charge copy hashes before execute and retain after-execute changes;
preserve actual installed-only pytest command (pytest main was not run with -I).
