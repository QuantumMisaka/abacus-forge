# Changelog

## 0.1.0 — prepared, not yet published

First public release candidate for the protocol-neutral ABACUS Forge library and CLI.

- Owner-authorized pre-release withdrawal of the unused Phase A
  `capability_registry` records and `capability-contracts` command introduced
  at `3d3ae52`. Existing capabilities/schema discovery and computation
  contracts are retained; see [migration guidance](docs/compatibility.md).

- `pip` installable wheel and source distribution, Python 3.10 or newer.
- Human-oriented prepare, execute, collect primitives and typed JSON capabilities/schema/operation interface for agents.
- Read-only `doctor` environment report and `--version` entry point.
- Optional `abacuslite==1.2.2` parser extra; ABACUS, PyATB and ATST executable integrations remain explicit.
- Documented request/result contracts remain versioned; scientific acceptance belongs to the caller. Some specialized property operations are experimental and have limited real-engine validation.

The PyPI release has not yet occurred. See [release procedure](docs/releasing.md).
