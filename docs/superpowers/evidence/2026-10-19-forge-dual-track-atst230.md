# Forge 安装态双轨真实解析与 ATST 2.3.0 交接

2026-10-19 执行；基线 `1cc82ab`。本轮未修改 Forge 运行时代码，测试助手修复仅影响安装态子进程验证。对应[执行计划](../plans/2026-10-19-forge-dual-track-atst230.md)。

## 结果

- 新建 Python 3.12 隔离 venv；当前 Forge wheel、PyPI abacuslite **1.2.0** 与 ATST **2.3.0** 实际安装。默认 dpdata 保留。包版本、wheel SHA、每格输入和日志 SHA 见 [summary.json](2026-10-19-forge-dual-track-atst230/summary.json)。abacuslite wheel SHA 与既有 1.2.0 release provenance 一致。
- 现有 `test_abacuslite_dual_track.py` 完整八格门禁：**1 passed，91.20s**。单测内部依次执行 develop/LTS × PW SCF/relax/cell-relax/MD，每格真实启动一次 ABACUS，对同份新输出比较 native 与已发布 parser 的 typed 指标、状态、产物和来源。不含 skip。
- develop 实际日志版本 `v3.11.0-beta8`，commit `94576a801`；LTS `v3.10.1`，commit `f71921fe8`。本次绑定已有明确版本，不宣称验证最新上游 develop。
- 八格中六格 collection complete；LTS relax 与 cell-relax 都为 **partial**，最终结构候选歧义保留，两后端状态一致。这是 parity 通过，不是全部解析完整或科学收敛。摘要中的 execution=not_run 是单独 collection envelope 的投影；真实 execute 已由门禁检查 returncode=0。
- 已安装 ATST 2.3.0 的 make/dry-run/summary/post machine CLI 交接：**1 passed，12.17s**，保留 7 条 ASE/NumPy 第三方弃用 warning。覆盖 artifact containment 和追加审计，不启动 ABACUS NEB。

## 验收助手修复

发现 `tests/support/process.py` 总向 CLI 子进程注入 checkout/src，原来即使 pytest 已通过 installed-only 校验，CLI 仍可能消费源码。新增父环境与调用方覆盖两条回归，原助手 **2 failed**；修复后在 installed-only 模式清空 PYTHONPATH，并用 `python -I -m abacus_forge.cli` 启动子进程。普通开发态继续从源码加载。

首轮 ATST 1 passed（12.57s）仅保留源码子进程证据，不冒充安装消费；修复后的 12.17s 记录才是本轮安装态结论。双轨测试直接调用已安装包，不经过该助手，其 91.20s 证据不受影响。相关 CLI/architecture 回归 **51 passed，1 条第三方 warning**，70.10s；RED/GREEN 输出保留在证据目录（RED 副本仅去行尾空格，原始日志留在 scratch）。

## 复现与工件

- [run_matrix.py](2026-10-19-forge-dual-track-atst230/run_matrix.py)：显式传 repo、source-root、两套 executable、全新 output 目录；来源必须恰为 INPUT/STRU/KPT 与 Si.upf，不允许旧输出混入。relax 从 cell-relax 源显式改 calculation，执行后 INPUT 哈希另记。
- [matrix.json](2026-10-19-forge-dual-track-atst230/matrix.json)、[receipt.json](2026-10-19-forge-dual-track-atst230/receipt.json)、[输入与真实日志归档](2026-10-19-forge-dual-track-atst230/real-inputs-and-logs.tar.gz)保留复现输入、实际日志版本与原始证据；归档含 sources 目录，可解包后作为 source-root。脚本当前接收 pw-scf/pw-cell-relax/pw-md 目录，归档 sources 使用 capability 名；复现时将 scf/cell-relax/md 映射为对应 pw-* 名称。
- 引擎运行前 source 本地 ABACUS toolchain setup；使用 OMP/OPENBLAS 单线程。现有 matrix 路径为本机记录，迁移机器须提供相同引擎或重新生成证据。
- 原始环境与完整八格输出保留在 `/home/james/scratch/forge-dual-track-atst230-20261019/`。`installed.lock` 是版本/本地 wheel 安装收据，不是跨机器可直接使用的制品分发锁。
- 首次 no-build-isolation 构建缺 hatchling；改为隔离构建成功。首次安装因无 Forge wheel 失败，构建完成后重试成功；未改共享 Conda。

独立复核已检查三个 wheel、Forge 69 个 Python 文件与源码的逐字节一致性、八格 INPUT/日志及归档哈希，未发现阻断问题。环境依赖检查通过，见同目录 `installation.json` 与 `pip-check.txt`。

## 尚未证明

当前指定 PW/nspin=1 八格发布 parser 证据已补齐；更广引擎版本、LCAO/nspin 组合与双轨 PyATB 交接另行验证。ATST 2.3.0 的有限步真实 NEB 与收敛路径仍开放，旧 2.2.8 GPU NEB 证据不覆盖新组合。本轮不晋升 stable、不完成 Paimon/SIF/平台验收、不发布。
