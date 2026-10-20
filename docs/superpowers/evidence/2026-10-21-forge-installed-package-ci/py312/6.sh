test -d "$ABACUS_FORGE_CANONICAL_ABACUSLITE_FIXTURES"
python -m pytest -q --run-benchmark \
  tests/test_package_contract.py \
  tests/test_package_metadata_drift.py \
  tests/test_parser_backend.py \
  tests/benchmark/test_abacuslite_canonical_parity.py
