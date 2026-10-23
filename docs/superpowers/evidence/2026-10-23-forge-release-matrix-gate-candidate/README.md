# Forge release-matrix-gate branch candidate

状态：runtime candidate 绑定 `chore/release-matrix-gate@68d42658`，对应
[PR #15](https://github.com/QuantumMisaka/abacus-forge/pull/15)。远端 CI 已通过；
该分支尚未合入 main，因此当前 main 的 standalone public candidate 仍是
[`972477c`](../2026-10-23-forge-main-972477c-candidate/README.md)。

## Gate change

- 两条 CI 矩阵均补齐 Python 3.11。
- `REQUIRED_JOBS` 从 pyproject 的 Python classifiers 派生，当前要求 3.10、
  3.11、3.12、3.13 各有 `test` 与 `installed-package` 成功 job。
- `tests/test_release.py` 的 drift regression 检查 declared Python versions、
  两条 CI matrix 和 release required jobs 一致。

## Validation

- [Push CI `39963085204`](https://github.com/QuantumMisaka/abacus-forge/actions/runs/39963085204)
  completed / success，八个 required job 全部通过。
- 本地 CPython 3.11 隔离 venv 完整默认离线回归：**1583 passed, 35 skipped**。
- CPython 3.12 fresh uv venv 安装 wheel `[dev,abacuslite,phonon]`，
  `abacuslite==1.2.2`；`pip`/`uv` 依赖检查通过，六文件安装态/parity 门禁为
  **64 passed**。
- 安装 smoke：`--version` 返回 `0.1.0`，`doctor --json` 为 `ready`，
  capabilities 为 13 个，SCF execute schema discovery 正常。
- CI 的 `forge-distributions-3.12` artifact 已实际下载；wheel/sdist metadata
  validation 通过。wheel SHA-256 为 `ac2f46d3…`，sdist SHA-256 为
  `bed45080…`；完整尺寸和 hash 见 [candidate.json](candidate.json)。

## Boundary

本记录只证明 release matrix gate 与候选制品身份。未创建 release tag，未发布
PyPI，未执行 Paimon 采用或科学验收；PR #15 合入前不能把该分支 candidate 当作
main public candidate。
