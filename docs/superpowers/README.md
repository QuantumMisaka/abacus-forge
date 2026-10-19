# Forge 设计、计划与证据

本目录保存本地规范源、执行清单与候选验证记录。先读根目录 [AGENTS.md](../../AGENTS.md)；使用文档从 [docs/README.md](../README.md) 进入，现行代码职责见[架构说明](../architecture.md)。规范是否有效由批准状态与适用范围决定，不由文件日期或是否已有实现决定。

## 当前工作入口

当前优先闭合完整 PyATB 候选的安装态 develop/LTS 消费，再交接 Paimon v1.3 W3，见[主线下一切片](plans/2026-09-13-forge-engine-version-policy.md#返回-forge-主线下一执行切片)。PyATB 本地 `sidereus-adam@5f7e132` 的源码修复与 77 项回归已完成，上游 PR #36–#38 已提交；完整候选 wheel 安装消费仍开放。历史交接见[集成基线](evidence/2026-10-19-forge-pyatb-sidereus-baseline.md)。

ATST 上游实算已按用户决定复用，串行/并行真实轨迹通过当前安装组合的 Forge 消费回放，见[交接验收](evidence/2026-10-19-forge-atst-upstream-replay.md)；取消默认重复 NEB 计算任务。

双轨与 ATST 2.3.0 接续验证见[计划](plans/2026-10-19-forge-dual-track-atst230.md)与[实测记录](evidence/2026-10-19-forge-dual-track-atst230.md)。

2026-10-19 已有分支集成与文档状态收口见[本轮计划](plans/2026-10-19-forge-branch-document-closeout.md)。`dpdata` 按用户决定保留默认依赖。

2026-10-15 用户确认继续文档、COHP 完整输入、真实 NEB 和 parser 发布包调查，执行入口见[真实验收推进计划](plans/2026-10-15-forge-real-evidence-followup.md)。

| 工作 | 状态和入口 |
| --- | --- |
| 文档与代码体系收敛 | [已确认设计](specs/2026-10-13-forge-repository-consolidation-design.md) → [实施与验收计划](plans/2026-10-13-forge-repository-consolidation.md)。本批已完成并独立审查，已合入本地 main；保留公开行为与默认依赖，可废弃项单列。 |
| Engine/Version Policy | [SPEC](specs/2026-09-12-forge-engine-version-policy-design.html) → [分阶段计划](plans/2026-09-13-forge-engine-version-policy.md)。native / Stage 0 已集成；`abacuslite` 1.2.0 已发布并完成同一轮 rebind，Forge exact extra 为 `abacuslite==1.2.0`，安装态四 capability parity 已重跑通过，见[1.2.0 证据](evidence/2026-10-19-forge-abacuslite-1.2.0-rebind.md)与[provenance](evidence/2026-10-19-forge-abacuslite-1.2.0-package-provenance.json)。当前 wheel + 发布 parser 的指定 PW/nspin=1 八格真实双轨 parity 已补齐，见 [10-19 实测](evidence/2026-10-19-forge-dual-track-atst230.md)；更多配置及双轨 PyATB 交接仍开放。 |
| 真实运行与迁移证据 | [Stage 5 计划](plans/2026-09-13-forge-stage5-evidence-gates.md)。当前 wheel 已补充有限步真实 NEB execute 与 postprocess 恢复证据，优化未收敛；完整迁移与外部发布事项仍开放。 |
| COHP postprocess W1 | [SPEC](specs/2026-10-15-forge-cohp-postprocess-design.md) → [PLAN](plans/2026-10-15-forge-cohp-postprocess.md)。IAO typed postprocess 已合入；Paimon W2 接线、当前 wheel/ZIP 无 system-site 后处理消费及完整真实 Si SCF 五组轨道回放已验证，见[安装证据](evidence/2026-10-15-forge-cohp-installed-consumption.md)和[真实输入证据](evidence/2026-10-15-forge-real-evidence.md)。legacy bridge、完整安装/平台及 Benchmark 验收仍开放。 |

2026-10-19 用户要求以可复用集成基座为重点并纳入 `abacustools`。既有 SPEC/PLAN 的职责复核、工作区参考分工、COHP 方法来源与建议推进顺序见[参考复核](plans/2026-09-09-forge-core-fidelity-references.md#integration-review-20261019)。这是参考与导航更新，不改变 Approved/Draft 状态。

## 有效设计基线

| 规范 | 适用范围 |
| --- | --- |
| [2026-09-01 契约优先重构](specs/2026-09-01-forge-contract-first-rearchitecture-design.html) | Approved；产品边界、契约和总体迁移。 |
| [2026-09-02 Service/Status](specs/2026-09-02-forge-service-status-migration-design.html) | Approved；operation identity、受理、execution/collection、v1 CLI/error 与兼容迁移。仅在这些细化范围内优先于 09-01。 |
| [Typed MD postprocess](specs/2026-09-10-forge-typed-md-postprocess-design.html) | Approved for this implementation thread；显式 trajectory 与独立后处理。 |
| [Typed export](specs/2026-09-10-forge-typed-export-design.html) | Approved；显式 operation outcome 的事实序列化。 |
| [PyATB artifact manifest](specs/2026-09-10-forge-typed-pyatb-artifact-manifest-design.html)、[nspin=4](specs/2026-09-10-forge-typed-pyatb-nspin4-design.html) | Approved；限定的 manifest 与 HR 路由。 |
| [Engine/Version Policy](specs/2026-09-12-forge-engine-version-policy-design.html) | 设计已收口，Stage 0 已验证；后端配置、错误优先级与解析分工。未完成阶段按 PLAN 验收。 |
| [2026-10-13 仓库整理](specs/2026-10-13-forge-repository-consolidation-design.md) | 用户确认的兼容整理与文档归属，不修改上述公共契约。 |
| [COHP postprocess W1](specs/2026-10-15-forge-cohp-postprocess-design.md) | 用户确认“按此推进”；仅覆盖 IAO typed postprocess，SCF 编排和 legacy bridge显式排除。 |

## 草案与后继关系

| 草案 | 当前地位 |
| --- | --- |
| [abacuslite 插件维护位置与独立分发](specs/2026-10-16-abacuslite-independent-plugin-design.md) | 独立仓库与首轮包建设已批准，包内规范迁至 QuantumMisaka/abacuslite；此处保留设计历史与跨仓候选方案。正式 1.2.0 发布及 Forge 安装消费已有证据；ABACUS 兼容层与更广生产接入不能由此推定完成。 |
| [Contract System](specs/2026-09-29-forge-contract-system-design.html) | Draft；接续下列知识库提案，未批准、未实施。 |
| [I/O Contract Knowledge Base](specs/2026-09-29-forge-io-contract-knowledge-base-design.html) | 历史 Draft；讨论由 Contract System 接续，保留原始依据。 |
| [Typed BEC](specs/2026-09-29-forge-typed-bec-design.html) | Draft；显式阶段、解析和科学计算语义仍待收口，无实施 PLAN。 |
| [Property manifest](specs/2026-09-10-forge-property-manifest-design.html) | 仍是 Draft；[计划](plans/2026-09-10-forge-property-manifest.md)已有 provisional 实现与复核，不能反推规范已获批准或能力已稳定。 |

## 实现记录与历史计划

下表按主题定位既有实现及其证据。历史任务模板中的未勾选项不自动等于当前待办；应结合该计划的状态、completion record 与绑定提交阅读。残余发布/跨仓门禁从上方当前入口追踪，不批量重写原始记录。

| 主题 | 计划/记录 |
| --- | --- |
| 基线与测试治理 | [基线统一](plans/2026-09-01-forge-baseline-unification.md)、[契约基础](plans/2026-09-01-forge-contract-foundation.md)、[测试组合治理](plans/2026-09-01-forge-test-portfolio-governance.md) |
| Service、CLI 与操作 | [SCF](plans/2026-09-02-forge-service-status-scf.md)、[Agent-first CLI](plans/2026-09-04-forge-agent-first-cli.md)、[Relax](plans/2026-09-06-forge-relax-operations.md)、[MD](plans/2026-09-10-forge-typed-md-operations.md) |
| 中立内核与输入资产 | [保真收敛](plans/2026-09-09-forge-core-fidelity.md)、[参照源码与取舍](plans/2026-09-09-forge-core-fidelity-references.md)、[显式资产](plans/2026-09-09-forge-typed-asset-materialization.md)、[PBE/ATST 边界](plans/2026-09-09-forge-default-pbe-and-atst-neb-boundary.md) |
| 后处理与外部引擎 | [Band/DOS](plans/2026-09-10-forge-typed-postprocess.md)、[MD postprocess](plans/2026-09-10-forge-typed-md-postprocess.md)、[MD 复核修正](plans/2026-09-11-forge-md-postprocess-review-fixes.md)、[ATST adapter](plans/2026-09-09-forge-atst-neb-adapter.md) |
| COHP W1 | [COHP postprocess](plans/2026-10-15-forge-cohp-postprocess.md) |
| PyATB 与导出 | [Band handoff](plans/2026-09-10-forge-typed-pyatb-band.md)、[manifest](plans/2026-09-10-forge-typed-pyatb-artifact-manifest.md)、[nspin=4](plans/2026-09-10-forge-typed-pyatb-nspin4.md)、[可选 rR](plans/2026-09-11-forge-typed-pyatb-optional-rr.md)、[export](plans/2026-09-10-forge-typed-export.md) |
| 解析、状态与前置条件 | [原生输出保真](plans/2026-09-10-forge-abacus-native-collection-fidelity.md)、[collection metadata](plans/2026-09-10-forge-typed-collection-metadata.md)、[Fermi 单位](plans/2026-09-12-forge-native-fermi-unit.md)、[calculation 校验](plans/2026-09-12-forge-typed-calculation-guards.md)、[normal_end](plans/2026-09-12-forge-typed-execute-normal-end.md) |
| 历史集成与运行门禁 | [主线集成](plans/2026-09-11-forge-mainline-integration.md)、[maturity gates](plans/2026-09-11-forge-maturity-gates-integration.md)、[迁移事实](plans/2026-09-11-forge-core-migration-facts.md)、[SCF smoke](plans/2026-09-10-forge-typed-scf-real-smoke.md)、[MD smoke](plans/2026-09-11-forge-typed-md-real-smoke.md)、[freshness](plans/2026-09-11-forge-real-smoke-freshness.md) |

## 验证证据

证据只支持其中列出的代码版本、环境和行为范围；离线 fixture、真实进程和科学验收不可互相替代。当前测试运行方式见 [tests/README.md](../../tests/README.md)。

- [Stage 5 历史候选](evidence/2026-09-13-forge-stage5-evidence.md)：离线、package、process/real smoke 及未证明项。
- [2026-10-15 真实输入与 NEB](evidence/2026-10-15-forge-real-evidence.md)：完整 Si SCF 的 COHP 五组回放、有限步真实 NEB 与后处理恢复、abacuslite 发布包查询；明确保留失败和未收敛状态。
- [版本政策设计复核](evidence/2026-09-13-forge-engine-version-policy-review.md)、[Stage 0](evidence/2026-09-14-forge-engine-version-policy-stage0.md)、[Stage 1 package](evidence/2026-09-14-forge-stage1-package-gate.md)：分别查看设计、源码兼容和安装证据范围。
- [统一候选 clean package](evidence/2026-09-27-unified-candidate-clean-package.md)：候选 wheel 与隔离环境，不代表所有 optional extra 完成。
- [abacuslite 1.2.0 rebind](evidence/2026-10-19-forge-abacuslite-1.2.0-rebind.md)、[provenance](evidence/2026-10-19-forge-abacuslite-1.2.0-package-provenance.json)：已发布 1.2.0 包绑定、安装态四 capability parity 重跑与缺包 fail-closed；不含 develop/LTS 真实引擎双轨证据。
- [abacuslite 1.1.0 exact extra](evidence/2026-10-19-forge-abacuslite-exact-extra.md)、[provenance](evidence/2026-10-19-forge-abacuslite-1.1.0-package-provenance.json)：1.1.0 interim pin 的历史记录，保持冻结。
- [SCF fallback/native facts](evidence/2026-09-29-scf-fallback-native-facts.md)、[vacancy real smoke](evidence/2026-09-29-vacancy-real-smoke.md)：对应修正与实际运行记录，均不自动晋升 stable。
- 已结项评审、旧实施材料及迁出的工具任务报告见[历史归档索引](../archive/README.md)。仍有效的 SPEC 不因已经实现而移入历史归档；新的工具临时状态留在被忽略的本地目录。

## 跨仓迁移

Paimon v1.3 的 owner 在 app-tools 仓；当前工作区 checkout 名为 `app-tools-forge`。相对该仓 `toolbox/ABACUS/` 的入口：

- `docs/superpowers/specs/2026-09-29-paimon-v1.3-backend-architecture.html`：Reviewed / 实施基线，定义两个产品的边界、开发参照和 M0–M4 验收。
- `docs/superpowers/plans/2026-09-13-paimon-v1.3-forge-migration.md`：W0–W4 执行总表，维护 adapter、依赖、全链路 benchmark 和平台验收。

Forge 独立交付，Paimon 的发布门槛不自动成为每次 Forge 发布的门槛。Contract System、BEC 与 optional parser package 各有独立设计和验收。已结项 `paimon/` 只作历史证据，不是 Forge 运行时依赖或上级规范。

## 文档生命周期与开发路由

- 新建 SPEC 使用 `specs/YYYY-MM-DD-<topic>-design.md`，Markdown 是唯一可编辑源，HTML 按需生成阅读视图。历史 HTML 保持原有规范地位，实际修订时按需迁移。
- PLAN 使用 `plans/YYYY-MM-DD-<topic>.md`，记录决策来源、文件责任、命令和验收边界；evidence 记录候选身份、环境、结果与未证明项。PLAN 和 evidence 不反向发明公共契约。
- 已批准 SPEC 高于 PLAN/ROADMAP；后继只在声明范围内取代前序。被取代材料保留原文件和后继链接，Draft 与 provisional implementation 显式区分。
- L1 做最近验证；L2 先建立行为证据，适用时 RED → GREEN → REFACTOR；L3α 先 brainstorming 与批准 SPEC，L3β 依据已确认决策 writing-plans。用户已授权的同范围执行不重复索取批准。
- 提交前检查 diff、owning tests 及相关 CLI 示例；默认回归不访问真实集群。完成声明绑定当前候选的命令输出；真实运行只证明相应操作/解析，不承担科学判断。

核心边界与禁止项集中维护在 [AGENTS.md](../../AGENTS.md)，本索引不再复制一套规则。
