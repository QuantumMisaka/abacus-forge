# Forge 文档导航

本页按读者问题指向维护位置，不复制产品说明或契约正文。

## 使用 Forge

- [根 README](../README.md)：英文产品入口、安装、最小本地调用和能力成熟度概览。
- [使用指南](guide.md)：从 primitive、UnitSpec、task/sequence 或 pack 选择调用面，并按场景使用 CLI 和 Python API。
- [接口与 workspace 参考](reference.md)：typed request、能力发现、资产路径、输出记录和状态语义。
- [仓内示例](../examples/README.md)：使用现有 NiO 结构准备本地 workspace，以及站点运行脚本的适用范围。

## 开发与验证

- [开发入口与边界](../AGENTS.md)：仓库约束、文档路由、L1/L2/L3 开发路径。
- [架构说明](architecture.md)：现行模块职责、依赖方向和扩展/测试定位。
- [测试说明](../tests/README.md)：测试层级和门禁的唯一入口。
- [真实运行 smoke 说明](../tests/real_smoke/README.md)：显式 opt-in 的真实进程验证与证据边界。
- [路线图](../ROADMAP.md)：当前重点和单列的可废弃候选；候选不代表已批准删除。

## 设计、计划与历史

- [Superpowers 治理入口](superpowers/README.md)：有效规范、草案、计划和证据的索引与状态说明。
- [契约优先重构 SPEC](superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html) 和 [Service/Status 细化 SPEC](superpowers/specs/2026-09-02-forge-service-status-migration-design.html)：当前公共 operation、结果、workspace、CLI 与兼容迁移的上位设计基线。
- [2026-10-13 文档与代码体系整理设计](superpowers/specs/2026-10-13-forge-repository-consolidation-design.md) 与 [实施计划](superpowers/plans/2026-10-13-forge-repository-consolidation.md)：本轮已确认边界与分工。
- [历史归档](archive/README.md)：旧项目评审、历史实施记录与工具生成的任务报告；不作为当前开发待办或规范。

用户阅读路径：README → 使用指南/参考 → 必要时对应有效 SPEC。开发路径：AGENTS → 架构说明 → owning SPEC/PLAN 与测试说明。Paimon 跨仓迁移状态由其 owner 文档维护；仅消费 Forge 不要求读取该迁移历史。
