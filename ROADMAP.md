# ABACUS-Forge 路线图

更新于 2026-11-05。Forge 面向人类研发者与通用 Agent 提供独立的 ABACUS 科学计算基元和可组合任务单元。当前重点是让外部用户能够独立安装、正确消费并参与维护。产品边界由[收缩设计](docs/superpowers/specs/2026-10-29-forge-computation-factory-target-architecture-design.md)约束，当前接口见[使用指南](docs/guide.md)与[参考](docs/reference.md)。

## 已交付基础

| 范围 | 当前可用性与依据 |
| --- | --- |
| prepare/modify/execute/collect/postprocess/export、typed CLI 与环境诊断 | 已有实现与公开兼容边界；各 capability 的操作范围以真实 discovery/schema 为准，不能从同名 legacy 命令推断。 |
| SCF launcher/env 与默认安装态消费 | Forge 切片与复审已完成，[SCF 计划](docs/superpowers/plans/2026-10-29-forge-scf-consumer-chain.md)结项。 |
| 声子、弹性与振动展开 | 已实现清单、独立单元消费、显式汇总与 CPU 后处理；`82af7d5` 本地验收见[交付证据](docs/superpowers/evidence/2026-11-05-forge-task-expansion/README.md)。仍为 experimental。 |
| COHP/PyATB、polarization/BEC 与 parser 消费 | 有界实现和相应验证已完成；真实材料、方法及环境覆盖见[规范/证据导航](docs/superpowers/README.md)。不把局部实算扩大为全能力科学验收。 |
| 发布与安装态管线 | 初版管线和四版本矩阵已落地；当前新能力还需补持续覆盖及正式候选验收，PyPI 发布未完成。 |

以上完成项不再作为待实现功能。已实现的有效 SPEC 继续维护；旧候选、测试数量和 Paimon Benchmark 保留在原记录，不作为当前组合的替代证明。

## 下一阶段：独立公开交付

只由[公开交付 PLAN 的 Task 5–10](docs/superpowers/plans/2026-10-21-forge-public-release.md#工程化接续待实施)维护待办与验收：

1. 修复受控执行树的 timeout/中断生命周期。
2. 补默认依赖与 phonon extra 的真实 CI 覆盖，让新单元链进入安装态验证。
3. 让 Agent 找到实际可用的 composite 入口，提供可独立运行的展开/汇总示例。
4. 收窄发行内容，保留构建、使用和必要验证资产；补独立贡献入口。
5. 集成候选、跑远端矩阵并确定后继版本/tag；获明确发布授权后完成索引安装验收。

当前 package 为 0.1.0，旧 v0.1.0 tag 不覆盖新能力；本路线图不选择后继版本，也不改写现有 tag。

## 后续消费者与资源

Paimon 先在最新 v2 基线上接声子的 CPU 准备→独立计算单元→CPU 汇总，再复用到振动和弹性。Forge 弹性目前是 13 单元，不能默认为 Paimon 25 单元方法的同等替换。目录交接、指定单元恢复可以先离线验证；真实 allocation、launcher/GPU 绑定、科学对拍和 Benchmark 由对应 owner 后续验收。

参考仓需要时刷新并比较版本；冻结旧对照与新参考分别保留。参考更新不自动升级运行依赖，不要求所有工作区仓库同步到同一时间点。

<a id="可废弃与依赖调整候选"></a>

## 保留与退出

- dpdata 继续保留默认依赖；其他科学依赖的 extra 拆分只有出现明确消费需求时再评估，不以“轻量”为理由静默缩减功能。
- UnitSpec、task/sequence、兼容事件与既有 property manifest 保留实际行为。废弃需有消费者调查和迁移依据，不能仅凭 legacy/experimental 标签删除。
- 已撤回 Phase A registry/ExecutionIdentity/ResourceSpec 等平行框架不重启。Contract System / I/O 知识库草案、已被取代的旧 BEC 设计进入[历史归档](docs/archive/retired-designs/README.md)。
- Forge 不承担 ATP/MCP、AiiDA、资源调度、项目 DAG runtime 或科学接受决策。公开发行不等待全部 Paimon 迁移完成。
