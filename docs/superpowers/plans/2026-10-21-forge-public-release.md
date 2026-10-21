# Forge 0.1.0 独立公开交付计划

来源：用户明确要求按首版交付建议推进，强调架构、完整性、方法和体验。规范为[首版设计](../specs/2026-10-21-forge-public-release-design.md)，复用上位 v1 契约。基线 `42c23a4`；独立分支 `codex/forge-public-release-010`，工作树 `forge-integration-reference-review`。Paimon 由另一会话负责，主 checkout 的 elastic 归因分支不修改。

### Task 1：诊断和版本入口
- [x] 实现独立只读 doctor / --version 与人读、JSON 输出，缺程序/文件可操作提示。
- [x] 行为回归先验证缺口，覆盖无引擎正常、显式缺项、只读和安装态 CLI；保留既有调用行为。

### Task 2：人类与 Agent 上手
- [x] 用公共 API/CLI 提供自包含免引擎路径、真实 SCF 操作方法和 Agent 消费示例。
- [x] README/指南明确推荐入口、资产、状态和支持范围；补公开兼容说明。
- [x] clean wheel 环境实际跑文档/示例；验证错误与 partial，不依赖本机绝对路径或 PYTHONPATH。

### Task 3：发行管线
- [x] tag/成功 CI run/制品身份验证与 PyPI OIDC 发布工作流；发布说明和维护者 runbook。
- [x] 构建与 metadata 校验、发布验证器负向回归、CI 检查；查询外部配置，先完成本地可审阅结果。

### Task 4：整体交付
- [x] 完整离线回归、两版安装态与用户路径，独立审查并解决实质问题。
- [ ] 集成与远端 CI，形成具体发行候选；不覆盖并行 owner 状态。
- 延后（用户本轮明确要求）：PyPI 账户配置与实际发布、发布后 fresh index install。本轮完成其余配置、实现与验收，不以此声称 PyPI 已上线。

任务分工：诊断 worker 仅 doctor/CLI 与 owning tests；用户路径 worker 仅用户文档/示例/用户路径 tests；发布 worker 仅 release workflow/验证器/发布文档与测试。主控维护规范、计划、索引、项目元数据及 CI 集成，并负责审查、构建和发布动作。共享 Git index 仅主控操作。

验收记录见[本轮证据](../evidence/2026-10-21-forge-public-release.md)。独立终审已完成，legacy/typed 状态说明差异已修正。GitHub `pypi` environment 与 `v*` tag policy 已配置；不触发发行。
