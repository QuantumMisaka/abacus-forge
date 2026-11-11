# Contributing to ABACUS-Forge

ABACUS-Forge is a protocol-neutral library and Agent-first CLI for preparing,
executing, collecting, and post-processing ABACUS workspaces. Before proposing a
change, read the [README](README.md), [public compatibility policy](docs/compatibility.md),
and test boundaries in [tests/README.md](tests/README.md).

## Development setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
```

Optional scientific paths require their declared extras, for example
`python -m pip install -e '.[dev,phonon]'`. Do not substitute a local checkout for
an installed optional dependency when recording package-acceptance evidence.

## Choosing checks

Select owning tests by observable behavior rather than by the number of files changed:

- Runner, workspace, service, and composite changes need their focused integration
  and CLI tests as described in [tests/README.md](tests/README.md).
- Public documentation, examples, and compatibility text need the corresponding
  documentation and getting-started tests.
- Packaging changes need clean-environment build, install, import, example checks,
  and archive inspection.
- Real scientific validation must state its engine, inputs, versions, and accepted
  scope; offline tests and mocks never establish physical correctness.

Include the commands you ran, exit status, and artifacts a reviewer must inspect.
For a regression, first reduce it to a failing focused test or reproducible CLI
transcript, then change production code.

## Change expectations

- Keep documented request/result contracts, exit-code meanings, and append-only
  workspace records compatible under the current public policy.
- Extend existing capability, schema, runner, collector, and composite seams rather
  than adding a parallel framework or second registry.
- Preserve repository evidence and provenance even when it is excluded from source
  distributions.
- Attribute third-party code and fixtures explicitly; check the applicable license
  before copying or adapting material.
- A passing test suite does not itself establish scientific acceptance. Keep
  collection facts, machine status, and scientific judgment separate.

## Issues and pull requests

For a bug report, include Forge version, Python version, installed extras, minimal
input or command sequence, complete error/output, and expected result. For contract
or packaging changes, also identify the affected consumer and compatibility decision.

Pull requests should have a bounded purpose, current upstream baseline, focused
tests, and evidence links. Record deliberately deferred validation; do not describe
skipped checks as passed.
