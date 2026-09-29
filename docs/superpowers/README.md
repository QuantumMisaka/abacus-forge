# ABACUS-Forge 文档先行开发治理

本目录把架构决策与实施清单留在仓内，使人类开发者、Codex 和其他 AI 开发者消费同一份本地事实。它是轻量入口，不复制全局 Superpowers 指令；执行者仍须先读取根目录 `AGENTS.md` 与命中的 Skill。

## Paimon v1.3 跨仓迁移导航

2026-09-29 总体设计入口位于 app-tools 仓 `toolbox/ABACUS/docs/superpowers/specs/2026-09-29-paimon-v1.3-backend-architecture.html`（当前工作区 checkout 为 `app-tools-forge`）。该 Reviewed / 实施基线汇总两个产品的定位、目标架构、开发参考、M0–M4 落地与验收模式；执行总表为同仓 `docs/superpowers/plans/2026-09-13-paimon-v1.3-forge-migration.md` 的 W0–W4，路径相对 `toolbox/ABACUS/`。

Forge 继续独立交付，以下已批准的公共契约与能力专项 SPEC 仍拥有其范围。总体设计不批量覆盖这些契约，不将 Paimon 发布门槛施加到每次 Forge 发布。原有实现/证据 PLAN 保留原状态；未完成的跨仓依赖、adapter 与 benchmark 事项在迁移总表关联，optional abacuslite extra、Contract System 和 BEC 仍按各自设计推进。

## 文档层级

| 文档 | 读者 | 职责 | 是否可改变实现边界 |
| --- | --- | --- | --- |
| 根目录 `README.md` | 科研用户、调用者 | 当前能力、成熟度、安装和稳定用法 | 否 |
| 根目录 `AGENTS.md` | 人类与 AI 开发者 | 边界、验证、文档路由和开发约束 | 否；只指向规范源 |
| `specs/*.html` | 维护者、评审者 | 公共 API/schema、持久化 workspace、迁移和跨仓边界的规范源 | 是，批准后 |
| `plans/*.md` | 实施者 | 从 SPEC 推导出的可执行任务、测试和提交检查点 | 否 |
| `evidence/*.md` | 维护者、发布评审者 | 绑定候选提交的门禁命令、环境、结果与未决证据 | 否 |
| `../archive/` | 回溯者 | 已结项或已取代的历史材料 | 否 |

重构规范由两份已批准的本地 SPEC 共同构成：[契约优先重构 SPEC](./specs/2026-09-01-forge-contract-first-rearchitecture-design.html) 定义产品边界与 contract-first 总体迁移；[Service/Status 细化 SPEC](./specs/2026-09-02-forge-service-status-migration-design.html) 冻结 operation identity、执行/收集状态、v1 CLI/error 协议与兼容迁移。后者仅在其细化范围内优先；未覆盖的边界仍以 2026-09-01 SPEC 为准。

## 路由

| 级别 | 适用变化 | 必需产物与验证 |
| --- | --- | --- |
| L1 | 局部、可逆、无公共行为或架构变化的修复/文档勘误 | 最小 diff 与最近测试/文档检查 |
| L2 | 有界行为变更、bugfix、局部重构 | 先建立行为证据；适用时 TDD 的 RED → GREEN → REFACTOR；运行拥有该行为的测试 |
| L3α | 公共 API/schema、workspace 持久化、CLI 协议、adapter 边界或架构仍有决策 | `brainstorming` → HTML SPEC → 用户批准 → `writing-plans` → 执行 |
| L3β | 用户已拍板且方案唯一的多步骤迁移 | `writing-plans`，在 plan 头部记录决策来源；用户批准后执行 |

对 L3，SPEC 与 PLAN 都必须落在本目录。PLAN 不得发明或推翻 SPEC；发现设计冲突时停止扩大实现，回到设计澄清并更新 SPEC。

2026-09-13 [Engine/Version Policy SPEC](./specs/2026-09-12-forge-engine-version-policy-design.html) 已完成设计收口，新增后端配置、错误优先级与解析分工，保留既有 final 候选兼容；[分阶段 PLAN](./plans/2026-09-13-forge-engine-version-policy.md) 的 A 与 Stage 0（含 canonical checkout parity）已在开发分支推进，C/D 的可安装 extra、真实双轨和外部迁移仍待验收。

## 日常门禁

- 开始前：阅读 `AGENTS.md`、相关 README、最近 SPEC/PLAN 与拥有该行为的测试。
- 修改可观察行为：先写会失败的回归或验收证据；只改文档/测试治理时记录基线和受影响门禁。
- 提交前：运行 `git diff --check`、最小充分 pytest 命令、相关 CLI `--help` 或进程契约检查；默认回归不得访问网络、调度器、真实集群或用户工作目录。
- 宣称稳定操作/解析能力前：除确定性测试外，必须有对应的 real smoke 证据；benchmark 和 fixture 不替代真实运行证据，科学判断由上层人类/Agent 完成。
- 完成时：在 PR/提交说明或 PLAN 中写明命令和输出；不以覆盖率、测试数量或自评替代行为证据。

## 写作与生命周期

- 设计未定的 L3 使用 `specs/YYYY-MM-DD-<topic>-design.html`；不要在 README 或 AGENTS 中塞入详细设计。
- 已批准设计的实施使用 `plans/YYYY-MM-DD-<topic>.md`，并包含准确的文件、接口、测试、命令和预期结果。
- SPEC 被取代时保留原文件，在其顶部标记 superseded 并链接后继规范；不要删除历史决策。
- 一个没有被 README、AGENTS、SPEC、PLAN 或测试引用的治理规则应被删除或下沉，避免入口文档膨胀。

## Forge 特有红线

- Forge 核心不承载 ATP/MCP/AiiDA/平台/调度器/UI 语义；可选 TUI 若实现，只能作为 Python API 或结构化 CLI envelope 之上的薄壳，Paimon adapter 只在上层消费 Forge 的协议无关事实。
- 数字 Task-ID 与交互菜单不得成为核心 API/CLI 协议。
- `abacus-agent-tools`、`abacustest`、`abacuslab`、`abacuscopilot`、PyATB 与 VASPKIT 是能力、兼容性或 UX 参考，不能成为绕过 Forge 边界的运行时捷径。
