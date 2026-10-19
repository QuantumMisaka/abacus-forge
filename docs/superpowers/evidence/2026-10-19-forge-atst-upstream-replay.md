# ATST 上游实算复用与 Forge 产物交接验收

2026-10-19，用户确认优先复用 ATST 自身的真实 NEB 验收。Forge 本轮不运行 execute、不启动 ABACUS、不提交集群作业；只检查适配契约与消费真实产物。基线 `c357c33`，生产源码未修改。

## 上游证据与版本边界

上游来源为 `atst-tools@f287091` 的 `docs/reports/ABACUSLITE_230_CLOSEOUT_2026-10-19.md` 和 `docs/releases/RELEASE_NOTES_2.3.0.md`，身份与文件 SHA 记录在 [upstream-binding.json](2026-10-19-forge-atst-upstream-replay/upstream-binding.json)。

- GPU job **1848462**：COMPLETED / 0:0，18 stages、13 real-engine cases，包含串行与并行 NEB。归档 SHA256 `4565d61aa42e7ed1878b44d754728bc27e7d0f5148b129599fb3392a5e7bb3e7` 已在本轮读取时重新核验。
- 该实算 producer 为 ATST 候选 `49c8626`、abacuslite **1.1.0**；不是正式依赖 1.2.0 组合的实算。正式 ATST 2.3.0 tag `b8c3218` 提高依赖下限为 1.2.0，并记录了安装消费复验。
- `49c8626..v2.3.0` 的 CLI、runtime、runner 和 NEB 源码没有差异；生产 Python 唯一变化是缺包提示中的最低版本。相较 Forge 既有 2.2.8，CLI 实现新增的是 vibration validate，不改变 Forge 使用的 NEB 命令参数。
- 当前消费端为上一轮同一隔离环境中的已发布 ATST **2.3.0**（wheel SHA `80a5e2422176df48bfdcc1e88bd66a11cdcb953c735ae86fe62cb91004fd5729`）、abacuslite **1.2.0** 及已安装 Forge wheel。Forge 运行时与上一轮安装身份一致。

## 消费回放结果

[replay.py](2026-10-19-forge-atst-upstream-replay/replay.py)仅从已核验归档提取指定常规文件，以全新 workspace 保存源轨迹及上游事实。通过隔离 Python 的 Forge machine CLI 发出独立 postprocess 请求；调用安装环境中的 ATST executable。没有重新生成能量或力。

| 来源 | 输入与选择 | Forge 交付 | 审计与事实核对 |
| --- | --- | --- | --- |
| 串行 NEB | H2，8 帧、每带 4 图像；`n_max=2` | completed / complete / unassessed；11 个 ArtifactRecord | 1 条事件；源文件 SHA 不变；末带四图的能量、最大力与上游 persisted_band 一致 |
| 并行 NEB | H2，8 帧、每带 4 图像；`n_max=2` | completed / complete / unassessed；11 个 ArtifactRecord | 1 条事件；源文件 SHA 不变；末带四图的能量、最大力与上游 persisted_band 一致 |

每个产物均核对 workspace-relative 路径、contained 实际文件、字节大小及 SHA256。交付包括 summary、CIF、latest 轨迹/extxyz、重启链、PDF 和日志；完整请求、响应、事件和工件见[回放归档](2026-10-19-forge-atst-upstream-replay/replay-artifacts.tar.gz)，[结果摘要](2026-10-19-forge-atst-upstream-replay/summary.json)保留上游事实。数值一致容差为绝对 `1e-10`，只证明消费保真，不是收敛或势垒准确性。

`conda run --no-capture-output -n abacus-env python -m pytest -q tests/test_atst_neb.py` → **22 passed，2.09s**。覆盖命令构造、非零退出、超时、路径和产物保护等适配边界；这些受控回归不冒充真实引擎失败测试。此前 [2.3.0 安装态 make/dry-run/summary/post](2026-10-19-forge-dual-track-atst230.md)证据继续适用。

## 结论与后续触发条件

本次未发现需要 Forge 重复真实 NEB 的适配缺口。取消“默认重跑 ATST 2.3.0 NEB”作为 Forge 待办；ATST 算法、优化收敛和资源拓扑验证由上游 owner 维护，Forge 对自己的命令/状态/产物/审计负责。

若后续 executable/launcher、工作目录/环境传递、命令参数或产物格式变化，先补最近边界回归与上游产物回放；仅当缺口必须由实际进程组合证明时，增加最小真实执行检查。正式 2.3.0 + abacuslite 1.2.0 的新组合 NEB 实算不是本轮证明项，也不自动成为 Forge 重复计算的任务。

复现命令：以此前隔离环境 Python `-I replay.py --archive /absolute/runtime-result.tar.gz --output /absolute/new-directory` 运行；原归档位置和 SHA 在 upstream-binding、脚本及上游报告中记录。完整本机回放位于 `/home/james/scratch/forge-atst-upstream-replay-final-20261019/`。本轮未推送或发布。

独立交付复核通过：上游版本差异与报告哈希、两组回放归档及版本边界表述均无阻断问题。120 个本地文档链接目标存在，回放归档 SHA 与记录一致，`git diff --check` 通过。
