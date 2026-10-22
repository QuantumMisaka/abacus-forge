# Forge main `3acf5cf` standalone public candidate

状态：当前 standalone public candidate 绑定 `main@3acf5cf6`。这是 PR #9 合入后的 merge commit；相对 public-release 实现 `cc68920` 只包含 ROADMAP、导航和 Al-FCC 证据文档，`src/`、`tests/`、`pyproject.toml` 无差异。

## Artifact chain

- merge CI：[run `39810350192`](https://github.com/QuantumMisaka/abacus-forge/actions/runs/39810350192)，completed / success。
- artifact：`forge-distributions-3.12`，ID `12438949131`，未过期。
- wheel：`abacus_forge-0.1.0-py3-none-any.whl`，307943 B，SHA-256 `f40cf487163cae048ef7f2900713cffe6e6326821718a2f6e51fc64c79a82a7e`。该 wheel 与 public-release 独立终审 wheel 完全一致。
- sdist：`abacus_forge-0.1.0.tar.gz`，11764006 B，SHA-256 `00b2053b85ff73ce2c60dff34eead2f3a0b6c54eb20b9910efdd8b738efd2b65`；新 hash 来自本轮合入的 evidence 文档。

机器可读 provenance 见 [candidate.json](candidate.json)。

## Post-merge fresh-wheel smoke

CPython 3.12.3 fresh `uv` venv、`python -I` 安装 CI wheel 后验证：

- `abacus-forge 0.1.0`
- `doctor --json` 可解析且 `status=ready`
- capabilities 可发现 13 项，包括 `scf`
- `schema scf execute` 可解析，`dry_run.type=boolean`

该 smoke 不是新增真实引擎验收；它只验证 merge commit 后的安装态入口未被文档/证据合入破坏。

## Boundary

- 未创建 release tag。
- 未触发 publish workflow。
- 未上传 PyPI。
- Paimon 尚未采用该 standalone candidate；历史 `4106f33` 仍是单独记录的 Paimon 兼容调查候选。
