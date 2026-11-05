# Forge 可组合任务展开实施清单

用户在 2026-11-05 确认“先实现可并行任务单元展开，资源分配后续接入”，随后授权“按此落实”。本计划直接执行该要求，依据[收缩设计](../specs/2026-10-29-forge-computation-factory-target-architecture-design.md)与[专项 report](../evidence/2026-11-05-forge-architecture-replacement-audit/phonon-elastic-vibration-parallel-report.md)，不另设审批或框架建设阶段。

交付：Forge 本体的声子、弹性、振动 prepare 生成可重载的单元清单；调用方可以分别执行/采集任意单元，再把显式结果交给汇总和后处理。默认整链/批量入口继续可用。具体 allocation、SAI/Slurm 与 Paimon ATP Tool 接线不在本轮实现范围；Paimon 当前源码只作领域算法与接口对照，不修改过期 migration checkout。

基线：`abacus-forge/main@7b54d28`，package `0.1.0`。原有 untracked `worktree-retention-20261024/` 不属于本轮写集。

## 接口与边界

- 复用 `composite` 的 prepare/run/post、Workspace、LocalRunner、collection、TaskResult 和 ArtifactRecord；不新建 registry、ExecutionIdentity、资源模型或 DAG runtime。
- 扩展现有 `reports/<task>_plan.json`：每个单元有稳定 `unit_id`、相对 `workspace_rel` 和科学展开参数；输出中的绝对工作路径仅为当前绑定，不作为迁移依据。
- 共享 `composite/plan.py` 提供 `save_plan`、`load_plan`、`list_subtasks`、`execute_subtask`、`collect_subtask`、`gather_subtasks`。执行和采集分别调用，不隐式补算。
- 计划持久化各单元 INPUT/STRU/KPT 内容摘要，防止位移/应变输入变更后混用旧结果；这是特定输入配对检查，不是完整环境身份或资源准入。重准备已有计划需显式选择新的工作区。
- 单元执行配置由调用方提供现有 LocalRunner；同一工作区操作复用已有 guard，不将 sibling 单元串行化。不实现后台作业管理。
- gather 显式消费按 `unit_id` 标记的 collection records，按计划顺序汇集；重复、未知或输入不匹配的记录拒绝，缺失/失败项作为部分结果保留。阶段产物沿用 v1 workspace-relative ArtifactRecord。
- 三个 post 接受显式 `results`，此时不得隐式 collect 或 execute；原无 results 调用保持兼容便利。数值分析复用专业库，缺事实或依赖时不得用占位结果报告物性完成。仍标记 experimental，不宣称科学 parity。
- CLI 在现有 composite 命令中增加 units / execute-unit / collect-unit / gather，以及 post 的 `--results` 文件消费；不改变 typed machine v1 请求协议。

## 工作包

- [x] 共享单元清单、单元执行/采集、显式 gather。验证乱序、并发、单项失败、缺失、重复与目录迁移；保存每个单元自己的结果，不让一个分支异常吞掉其他结果。
- [x] 声子：实际位移生成、计划重载、显式力汇总与专业库后处理；取消缺依赖时未位移结构冒充有效计划的行为。保留既有 CLI 兼容入口。
- [x] 弹性与振动：保存科学展开参数，显式应力/力结果消费，完整性检查及科学后处理；复用现有数值核或专业库，不引入旧两包。
- [ ] CLI、使用文档和实例贯通；完成 owning tests、全离线及干净 wheel 安装消费检查；一次整体独立审查，修正实际问题，更新专项 report。

## 验证

先用实际输入准备和受控 executable / collection fixtures 验证单元生命周期；并发用 barrier 或子进程重叠证据，不以设置线程池参数冒充执行重叠。科学库使用可手算的力/应力响应，检验编号与物性计算接线；不把合成响应写成真实 ABACUS 结果。

新增 CLI 用真实进程检查 JSON/退出码；新 plan/gather 产物检查 ArtifactRecord 的相对路径。完整回归使用已有干净 Python 3.12 环境；新 wheel 在新 venv 中消费，明确区别源码、安装态与真实 GPU 验收。

## 进度与裁决

- 2026-11-05：用户授权后开始实施。资源接入保持后续事项，Paimon 生产与 migration checkout 均不修改。
- 过程预算：本计划 1 份；两个独立领域实现者，共享接口与集成由主代理负责；终审 1 次。
