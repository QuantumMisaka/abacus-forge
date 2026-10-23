# Forge main `972477c` standalone public candidate

状态：当前 standalone public candidate 绑定 `main@972477c`，包含 PR #13 的 CI/release hardening 和 Python 支持声明。

## Artifact chain

- main CI：[run `39956848080`](https://github.com/QuantumMisaka/abacus-forge/actions/runs/39956848080)，completed / success，矩阵为 Python 3.10/3.12/3.13。
- 本地构建 wheel：`abacus_forge-0.1.0-py3-none-any.whl`，SHA-256 `ac2f46d3669dac280470e6b8fd24ca03aa60385f4b799f1b2e2f941cf6042b29`。
- 本地构建 sdist：`abacus_forge-0.1.0.tar.gz`，SHA-256 `719817d6a5244f929ab486779838548f62db36768796e2bf0cf8379bcafef20e`。
- fresh CPython 3.12 wheel 安装后，`--version`、`doctor --json`、capabilities 和 SCF schema discovery 全部通过。

机器可读 provenance 见 [candidate.json](candidate.json)。

## Boundary

- 未创建 release tag。
- 未触发 publish workflow。
- 未上传 PyPI。
- Paimon 尚未采用该 standalone candidate。

2026-10-23 provenance correction：重新下载本候选 CI artifact 后，确认原始 JSON 中的
wheel/sdist `size_bytes` 有误；两个 SHA-256 不变，实际 byte size 已在
[candidate.json](candidate.json) 中更正并保留原值。
