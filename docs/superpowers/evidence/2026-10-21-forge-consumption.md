# Forge 直接 NAO 与 manifest 消费验证

候选：`codex/forge-pyatb-installed-consumption`，基线 `f590367` 上的本轮 dirty
实现范围。规范与任务完成状态见[接续计划](../plans/2026-10-21-forge-consumption-followup.md)。

## 真实 PyATB 消费

使用当前 Forge 源码（显式 `PYTHONPATH=src`）和已有安装态 PyATB
`1.1.2.dev0+5f7e132`，CPython 3.12 / Linux x86_64。环境与 wheel 来源见
[10-19 安装记录](2026-10-19-forge-pyatb-installed-consumption.md)。这不是本轮
Forge wheel 安装验收，也没有重跑 ABACUS 或提交 SAI 作业。

来源是 10-19 留存的 develop/LTS Si LCAO nspin=1 矩阵与同一数值轨道。
每轨在新 workspace 分别调用机器 CLI prepare、execute、collect；采用显式
八个 `0/0.5` 分数坐标、等权重，等价于既有原生 PyATB 的 `mp_grid 2 2 2`。
原子选择 1/1、s/p，绝对能量窗口 [-15,25] eV、de=0.05、sigma=0.15、
EF=6.793680865 eV。此对比检验交接及适配，不是新的收敛或科学正确性结论。

| 轨道 | 执行 / 收集 | 谱点 | 对原生基线最大谱差 | raw ICOHP（eV） |
| --- | --- | --- | --- | --- |
| develop | completed / complete | 801 | 0 | 0.03990074886873039 |
| LTS | completed / complete | 801 | 0 | 0.03990074886873039 |

原生基线 raw ICOHP=0.03990074886873071 eV；比较容差 atol/rtol=1e-10。
各轨有三个 append-only operation events，源文件前后 SHA-256 一致。
collect 本身的 execution 为 not_run，scientific 保持 unassessed；执行状态从
独立 execute response 获取。

[原始摘要](2026-10-21-forge-consumption/summary.json)、
[回放脚本](2026-10-21-forge-consumption/replay_nao.py)、
[develop collect](2026-10-21-forge-consumption/develop/collect-response.json)、
[LTS collect](2026-10-21-forge-consumption/lts/collect-response.json)；同目录保留
prepare/execute/collect requests、responses、生成的 Input 和 metadata。
脚本绑定本机既有证据路径，重复运行需选择新的 output 目录，不能覆盖已有回放。

第一轮回放脚本误断言执行状态为 `succeeded`，实际标准状态为 `completed`，
导致脚本 exit 1；引擎已成功产出。修正断言后，两轨均通过，脚本 exit 0。
原始日志位于 `/home/james/scratch/forge-consumption-20261021/`；
首轮 `native-replay.log` 与修正后 `native-replay-r2.log` 分别保留。

## 离线行为

- 新 NAO 请求先因缺少 import 观察到 RED，之后 focused 166 项通过。
  required regression 初次 591 通过、3 个旧注册表快照未包含新增 capability；
  更新精确预期后 targeted 13 通过，额外路径碰撞回归后 14 通过。
- manifest 消费者先因示例文件缺失观察到 2 项 RED；实现后 owning suites
  43 通过（32 条既有 ASE/NumPy warnings）。使用真实 property CLI post JSON
  和小型 cube fixture 验证数值、source refs、缺源文件、派生文件移走及源文件改写。
- 生成的 direct-k Input 已由已安装 PyATB 原生 parser 接受；完整引擎回放见上。
- 完整离线回归（审查修复前）**1503 passed、35 skipped、173 warnings**，exit 0。
  两个审查发现：日志父路径 symlink 越界、nspin 浮点误接纳，均先复现 RED，修复后
  定向 **15 passed**，独立 reviewer 复核关闭，无未解决实质问题。
  [完整日志](2026-10-21-forge-consumption/offline-full.log)、
  [修复回归](2026-10-21-forge-consumption/nao-review-final-green.log)、
  [最终源文件摘要](2026-10-21-forge-consumption/candidate-source-sha256.json)。
  此后的修复仅收紧无效参数/越界路径并移除元数据重复定义，不改变本次正常回放输入
  的数值/执行路径；真实回放证据仍适用。
- CLI 帮助与示例同步，217 个相对文件链接可解析，diff whitespace 检查通过。
  交付仍保留在隔离工作树，未提交或发布。

## 范围

本轮真实证据限两轨 Si/nspin=1、小型显式 k 网格；nspin=2 是请求/交接回归
覆盖，尚无本轮真实材料验收。没有 PyATB nspin=4、COOP、Forge 新 wheel、
Paimon 全链路 Benchmark 或生产平台发布声明。旧 IAO 的真实证据另行保留。
