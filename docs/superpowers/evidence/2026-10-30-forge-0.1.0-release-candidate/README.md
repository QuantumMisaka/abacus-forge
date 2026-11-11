# Forge 0.1.0 release candidate

## Status

Historical candidate provenance and distributions are recorded below. As checked on 2026-11-05, `v0.1.0` points to `d5585f5`, but PyPI publication has not occurred. The local 2026-11-05 fixes supersede this candidate for current-source validation; its CI and artifacts do not cover those fixes. Tag/version disposition remains with the owner.

## Identity

- Repository: `QuantumMisaka/abacus-forge`
- Candidate branch: `release/forge-0.1.0-candidate-20261030`
- Candidate commit: `d5585f5d1d9dbcbca57ca9efea11280eb1b0adb8`
- Project version: `0.1.0`
- Candidate is identical to `origin/main@d5585f5…`; it includes the contracted computation-factory design, Phase A withdrawal, SCF consumer launch facts, runtime-K admission, and convergence-related follow-ups。

## Release CI

| Field | Value |
| --- | --- |
| Workflow | `.github/workflows/ci.yml` |
| Run ID | `41033836714` |
| Event | `push` |
| Attempt | `1` |
| Head SHA | `d5585f5d1d9dbcbca57ca9efea11280eb1b0adb8` |
| Status / conclusion | completed / success |
| Matrix | `test` and `installed-package` for Python 3.10, 3.11, 3.12, 3.13 |
| Result | 8/8 jobs passed |

## Artifact

| Item | Value |
| --- | --- |
| Official artifact | `forge-distributions-3.12` |
| Artifact ID | `12966634008` |
| Expired | false |
| Artifact ZIP SHA-256 | `014cecc9cbe70bdcf8e24035735e7e48f18721c7e948c915368a0bfb289d2ccb` |
| Wheel | `abacus_forge-0.1.0-py3-none-any.whl` |
| Wheel SHA-256 | `a4bba28e3a4379a6079a0968a865c4bb5752eb9a31db1ad6158a029b8baa8ae5` |
| sdist | `abacus_forge-0.1.0.tar.gz` |
| sdist SHA-256 | `4a4eb2d949b6d79044ac90c70dfe6752c50cb3104adc3ddb39996c617bff687f` |

`scripts/release_validate.py verify-distributions` passed and returned exactly the wheel/sdist hashes above。

## Installed-package check

2026-11-05 follow-up: the retained `/tmp/forge-release-candidate-venv/pyvenv.cfg` has `include-system-site-packages = true`. This historical check establishes the Forge wheel import, but does not establish dependency isolation. A new venv without system-site packages was verified in the [2026-11-05 follow-up](../2026-11-05-forge-review-followup/README.md).

- Created a venv。
- Installed only the official CI wheel。
- `pip check`: no broken requirements。
- `abacus-forge --version`: `0.1.0`。
- Python import resolved to venv `site-packages`, not an editable checkout。
- `ScfExecuteRequest` exposes `launcher` / `env_overrides`。
- `abacus-forge capabilities` emitted valid JSON。

## Historical publication inputs

The following inputs bind only the frozen `d5585f5` candidate, not subsequent fixes:

```text
tag=v0.1.0
run_id=41033836714
artifact_id=12966634008
artifact_digest=sha256:014cecc9cbe70bdcf8e24035735e7e48f18721c7e948c915368a0bfb289d2ccb
head_sha=d5585f5d1d9dbcbca57ca9efea11280eb1b0adb8
run_attempt=1
```

Before dispatch, confirm the tag `v0.1.0` points directly to `d5585f5…` and PyPI Trusted Publisher is configured。These checks are also enforced by the publish workflow's verify job。

## Boundary

This record is for Forge package release readiness. It does not claim real ABACUS/SAI/GPU validation, Paimon replacement completion, or Benchmark parity。
