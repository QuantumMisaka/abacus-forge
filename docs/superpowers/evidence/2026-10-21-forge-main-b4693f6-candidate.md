# Forge `b4693f6` 上层交接候选

状态：**已由 [`25cd715`](2026-10-21-forge-main-25cd715-candidate.md) 取代**。本记录保留
当时的候选身份；不要把它当作当前 `main` 交付候选。

## 候选身份

- 源码：`main` `b4693f6f8e335555efcde0ede0a0e2a4222be56c`，工作树 clean。
- 构建：`git archive HEAD` 后用 `python -m build` 隔离环境构建（build 1.6.1 /
  hatchling 1.32.4）。
- wheel：`abacus_forge-0.1.0-py3-none-any.whl`，
  SHA256 `18b8a6c47987b6a87fb4589a769cd417245de7fce4bec8bb7f1cebfe6dc3f5d7`。
- sdist：`abacus_forge-0.1.0.tar.gz`，
  SHA256 `a773afd995c85916f51e8654ce123cf440c15d58c81b8e560d10befb317470f2`。
- wheel 内 76 个 `abacus_forge/*.py` 与该 commit 源码逐字节一致；optional parser
  extra 为 `abacuslite==1.2.2`。相对上一候选，本候选包含 relax 最终 stress envelope
  修复和 `pyatb-cohp nspin=2` 交接回归。

## 安装态验证

本地 CPython 3.11 venv（带 system-site-packages）安装该 wheel 和
`abacuslite==1.2.2` 后：

- 使用 `ABACUS_FORGE_INSTALLED_PACKAGE_ONLY=1`、显式 wheel 路径和 1.2.2 canonical
  fixtures 运行 package contract、metadata drift、parser backend 和 canonical
  parity：**55 passed**。
- 同一安装态运行 relax stress 真实日志回归和 direct NAO `nspin=2` 交接回归：
  **2 passed**。

同一 commit 的 GitHub hosted CI run
[39533651763](https://github.com/QuantumMisaka/abacus-forge/actions/runs/39533651763)
在 Python 3.10/3.12 上完成 source、build、install 和 optional parser parity 并成功。
本地 pip check 因复用的 system-site 环境包含无关 Paimon/AiiDA 缺项而不可用，
因此本记录不声明 fresh isolated `pip check`；fresh 安装证据以上述 CI 为准。

## 边界

不执行 PyPI 或 GitHub release。Paimon owner 若采用，必须显式把候选 kit 重绑到该
wheel/commit，并按其 owning PLAN 重新验收受影响的 demo/Benchmark 入口；本记录不
替代 Paimon Benchmark、SAI 或科学验收。
