# ABACUSTest ABACUS-SCF reference fixture

This directory is a minimal, self-contained copy of the files consumed by
`tests/test_collect_abacus_reference.py`.

- Source repository: `git@github.com:QuantumMisaka/abacus-test`
- Source commit: `1c9acbca026234ba91cdc19bca2f989d19d2ccff`
- Source path: `tests/test_collectdata/abacus-scf/`
- Purpose: collector compatibility regression for force, stress, pressure,
  virial, timing, and ABACUS log-selection behavior
- License: GNU Lesser General Public License v3.0; see `LICENCE` in this
  directory

Only the files read by the regression are copied. The fixture is test data and
is not included in the installed `abacus_forge` Python package.
