# Forge 设计、计划与证据

本目录保存本地规范源、执行清单与候选验证记录。先读根目录 [AGENTS.md](../../AGENTS.md)；使用文档从 [docs/README.md](../README.md) 进入，现行代码职责见[架构说明](../architecture.md)。规范是否有效由批准状态与适用范围决定，不由文件日期或是否已有实现决定。

## 当前工作入口

Forge 已补安装态 CI：Python 3.10/3.12 的构建、安装与 optional parser parity 命令本地重放各 55 项通过；GitHub 托管运行与 wheel/sdist artifact 上传也已通过。见[验证记录](evidence/2026-10-21-forge-installed-package-ci.md)。Paimon Benchmark 由另一会话负责。

2026-10-21 Relax typed collect 增补 opt-in 最终应力 metric：真实日志回归通过，[PR #7](https://github.com/QuantumMisaka/abacus-forge/pull/7) 已合入 `main`，合并后托管 CI 通过。Paimon elastic 上层仍按其 owner 流程验收。

当前 optional parser 升级为 `abacuslite==1.2.2`；新候选、安装态回归及留存双轨输出回放见[1.2.2 接续](evidence/2026-10-21-forge-abacuslite-1.2.2-rebind.md)。该候选接替下述收口记录中暂留 1.2.0 的选择；历史证据按原包版本保留。

本轮本地 main 集成、候选依赖与消费缺口收口见[PLAN](plans/2026-10-21-forge-integration-candidate-closeout.md)和[交付记录](evidence/2026-10-21-forge-integration-candidate-closeout.md)。

2026-10-21 消费接续实现与独立审查已完成：新增直接 NAO `pyatb-cohp`、有限方法元数据和 manifest 消费示例；两轨 Si 真实 PyATB 回放通过。见[完成记录](plans/2026-10-21-forge-consumption-followup.md#完成记录)与[验证证据](evidence/2026-10-21-forge-consumption.md)。BEC 有界实现、离线回归与审查已完成；fresh wheel 安装验证通过，MgO 真实验证目前覆盖一个 O_x 响应。能力仍为 experimental，不代表全张量或收敛；敏感性与当前状态以[安装/实算接续计划](plans/2026-10-21-forge-installed-bec-validation.md)和[证据](evidence/2026-10-21-forge-installed-bec-validation.md)为准。实现已提交为 `5f38349` 并合入 `main`；本地候选已构建，依赖选择、安装与上层交接见[收口记录](evidence/2026-10-21-forge-integration-candidate-closeout.md)。`main` 已推送到 GitHub，PyPI 发布未执行。

当前 `main` `25cd715` 交接候选已构建并绑定 wheel `bd86aa0f…`；全离线、安装态包/解析、direct NAO COHP 与真实两轨 metadata 回放通过。见[候选记录](evidence/2026-10-21-forge-main-25cd715-candidate.md)。Paimon owner 仍需显式重绑并自行验收，本仓未发布。

完整 PyATB `sidereus-adam@5f7e132` wheel 与 Forge `be1c0bc` 的本机安装态 develop/LTS Si/nspin=1 消费已通过，见[安装证据](evidence/2026-10-19-forge-pyatb-installed-consumption.md)。Paimon 显式 SCF 矩阵输出/readiness、develop 文件名适配及候选 ZIP 两轨 Si 实算已完成，见[既有计划 P1](plans/2026-09-13-forge-engine-version-policy.md#paimon-pyatb-handoff)。Paimon owner 已补齐 replay 接线与 band 边缘事实；后续统一候选 kit 绑定并推进完整 Benchmark 与目标环境交付，见[当前交接核查](evidence/2026-10-21-forge-integration-candidate-closeout.md#实际-demobenchmark-交接)；本机 CPython 3.12 证据不扩展为 SAI、CPython 3.13 或完整发布通过。

ATST 上游实算已按用户决定复用，串行/并行真实轨迹通过当前安装组合的 Forge 消费回放，见[交接验收](evidence/2026-10-19-forge-atst-upstream-replay.md)；取消默认重复 NEB 计算任务。

双轨与 ATST 2.3.0 接续验证见[计划](plans/2026-10-19-forge-dual-track-atst230.md)与[实测记录](evidence/2026-10-19-forge-dual-track-atst230.md)。

2026-10-19 已有分支集成与文档状态收口见[本轮计划](plans/2026-10-19-forge-branch-document-closeout.md)。`dpdata` 按用户决定保留默认依赖。

2026-10-15 用户确认继续文档、COHP 完整输入、真实 NEB 和 parser 发布包调查，执行入口见[真实验收推进计划](plans/2026-10-15-forge-real-evidence-followup.md)。

| 工作 | 状态和入口 |
| --- | --- |
| 文档与代码体系收敛 | [已确认设计](specs/2026-10-13-forge-repository-consolidation-design.md) → [实施与验收计划](plans/2026-10-13-forge-repository-consolidation.md)。本批已完成并独立审查，已合入本地 main；保留公开行为与默认依赖，可废弃项单列。 |
| Engine/Version Policy | [SPEC](specs/2026-09-12-forge-engine-version-policy-design.html) → [分阶段计划](plans/2026-09-13-forge-engine-version-policy.md)。native / Stage 0 已集成；当前 exact extra 为 `abacuslite==1.2.2`，安装态四 capability parity 与旧真实输出双轨回放见[新证据](evidence/2026-10-21-forge-abacuslite-1.2.2-rebind.md)及[provenance](evidence/2026-10-21-forge-abacuslite-1.2.2-package-provenance.json)。原八格引擎运行见[10-19 实测](evidence/2026-10-19-forge-dual-track-atst230.md)；PyATB 两轨 Si/nspin=1 完整包消费见[安装证据](evidence/2026-10-19-forge-pyatb-installed-consumption.md)；更多配置与上层交接仍开放。 |
| 真实运行与迁移证据 | [Stage 5 计划](plans/2026-09-13-forge-stage5-evidence-gates.md)。当前 wheel 已补充有限步真实 NEB execute 与 postprocess 恢复证据，优化未收敛；完整迁移与外部发布事项仍开放。 |
| COHP postprocess W1 | [SPEC](specs/2026-10-15-forge-cohp-postprocess-design.md) → [PLAN](plans/2026-10-15-forge-cohp-postprocess.md)。IAO typed postprocess 已合入；Paimon W2 接线、当前 wheel/ZIP 无 system-site 后处理消费及完整真实 Si SCF 五组轨道回放已验证，见[安装证据](evidence/2026-10-15-forge-cohp-installed-consumption.md)和[真实输入证据](evidence/2026-10-15-forge-real-evidence.md)。legacy bridge、完整安装/平台及 Benchmark 验收仍开放。 |
| 2026-10-21 Forge 消费接续 | [NAO/PyATB SPEC](specs/2026-10-21-forge-pyatb-cohp-design.md) 与 [有限元数据/manifest 消费 SPEC](specs/2026-10-21-forge-consumption-metadata-design.md) → [完成 PLAN](plans/2026-10-21-forge-consumption-followup.md) 与[验证证据](evidence/2026-10-21-forge-consumption.md)。直接 NAO 接口及两轨 Si 回放通过；有限 contracts map 与现有 manifest 消费示例只覆盖各自 SPEC 范围。BEC 由下方已确认的有界 SPEC/PLAN 接续。 |
| 2026-10-21 Polarization/BEC | [已确认的有界 SPEC](specs/2026-10-21-forge-polarization-bec-design.md) → [实施 PLAN](plans/2026-10-21-forge-bec-implementation.md) → [安装与实算接续 PLAN](plans/2026-10-21-forge-installed-bec-validation.md)。新增实验性 `polarization/collect` 与 `bec/postprocess`；准备/位移/单次执行复用通用 API。本地实现、离线回归、独立审查与 fresh wheel 安装验证通过。MgO 当前只验证单个 O_x 响应；不代表全张量、收敛或 Paimon/SAI 验收。当前实验状态见[后继证据](evidence/2026-10-21-forge-installed-bec-validation.md)；legacy pack 不做数值替换。 |

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
| [直接 NAO / PyATB COHP](specs/2026-10-21-forge-pyatb-cohp-design.md)、[有限元数据与 manifest 消费](specs/2026-10-21-forge-consumption-metadata-design.md) | 2026-10-21 有界设计已按[完成计划](plans/2026-10-21-forge-consumption-followup.md)实施并验证。前者新增独立 direct NAO capability，不改变已批准的 IAO W1；后者只定义有限 discovery contracts map 与现有 manifest 的消费示例，不批准完整 Contract System 或 manifest Draft。 |
| [Polarization/BEC 有界实现](specs/2026-10-21-forge-polarization-bec-design.md) | 用户确认的 bounded implementation；新增 `polarization/collect` 与 `bec/postprocess`，本地实现、离线验证和 fresh wheel 安装验证完成。MgO 真实验证的有限进度与未证明项由[接续计划](plans/2026-10-21-forge-installed-bec-validation.md)和[证据](evidence/2026-10-21-forge-installed-bec-validation.md)维护。能力仍为 experimental；当前单列结果不等于全张量/收敛或 Paimon/SAI 验收。 |

## 草案与后继关系

| 草案 | 当前地位 |
| --- | --- |
| [abacuslite 插件维护位置与独立分发](specs/2026-10-16-abacuslite-independent-plugin-design.md) | 独立仓库与首轮包建设已批准，包内规范迁至 QuantumMisaka/abacuslite；此处保留设计历史与跨仓候选方案。正式 1.2.0 发布及 Forge 安装消费已有证据；ABACUS 兼容层与更广生产接入不能由此推定完成。 |
| [Contract System](specs/2026-09-29-forge-contract-system-design.html) | 完整设计仍为 Draft，未整体批准或实施；2026-10-21 的有限 contracts map 见[独立范围 SPEC](specs/2026-10-21-forge-consumption-metadata-design.md)，不继承该草案的 M1–M4、知识库或查询服务方案。 |
| [I/O Contract Knowledge Base](specs/2026-09-29-forge-io-contract-knowledge-base-design.html) | 历史 Draft；讨论由 Contract System 接续，保留原始依据。 |
| [Typed BEC 历史 HTML](specs/2026-09-29-forge-typed-bec-design.html) | 保留原文及后继指针；当前规范源为上方的 2026-10-21 BEC SPEC。旧 HTML 中与新规范冲突的设计不再作为当前实现依据。 |
| [Property manifest 历史 Draft](specs/2026-09-10-forge-property-manifest-design.html) | 规范仍为 Draft；[计划](plans/2026-09-10-forge-property-manifest.md)记录 provisional 实现与复核。2026-10-21 的[有限消费 SPEC](specs/2026-10-21-forge-consumption-metadata-design.md)增加可运行示例范围，不批准旧 manifest 规范或将能力提升为 stable。 |

## 实现记录与历史计划

下表按主题定位既有实现及其证据。历史任务模板中的未勾选项不自动等于当前待办；应结合该计划的状态、completion record 与绑定提交阅读。残余发布/跨仓门禁从上方当前入口追踪，不批量重写原始记录。

| 主题 | 计划/记录 |
| --- | --- |
| 基线与测试治理 | [基线统一](plans/2026-09-01-forge-baseline-unification.md)、[契约基础](plans/2026-09-01-forge-contract-foundation.md)、[测试组合治理](plans/2026-09-01-forge-test-portfolio-governance.md) |
| Service、CLI 与操作 | [SCF](plans/2026-09-02-forge-service-status-scf.md)、[Agent-first CLI](plans/2026-09-04-forge-agent-first-cli.md)、[Relax](plans/2026-09-06-forge-relax-operations.md)、[MD](plans/2026-09-10-forge-typed-md-operations.md) |
| 中立内核与输入资产 | [保真收敛](plans/2026-09-09-forge-core-fidelity.md)、[参照源码与取舍](plans/2026-09-09-forge-core-fidelity-references.md)、[显式资产](plans/2026-09-09-forge-typed-asset-materialization.md)、[PBE/ATST 边界](plans/2026-09-09-forge-default-pbe-and-atst-neb-boundary.md) |
| 后处理与外部引擎 | [Band/DOS](plans/2026-09-10-forge-typed-postprocess.md)、[MD postprocess](plans/2026-09-10-forge-typed-md-postprocess.md)、[MD 复核修正](plans/2026-09-11-forge-md-postprocess-review-fixes.md)、[ATST adapter](plans/2026-09-09-forge-atst-neb-adapter.md) |
| COHP W1 | [COHP postprocess](plans/2026-10-15-forge-cohp-postprocess.md) |
| 2026-10-21 direct NAO 与消费 | [消费接续](plans/2026-10-21-forge-consumption-followup.md)；其实现和验证状态以该计划为准。 |
| 2026-10-21 Polarization/BEC | [BEC 实施](plans/2026-10-21-forge-bec-implementation.md)；[安装与实算接续](plans/2026-10-21-forge-installed-bec-validation.md)及[证据](evidence/2026-10-21-forge-installed-bec-validation.md)维护安装态和当前真实材料验证。仍为 experimental。 |
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
- `docs/superpowers/plans/2026-10-19-paimon-v1.3-benchmark-parity-plan.md`：正在由另一工作会话推进的 Benchmark 阈值、执行器、候选交付包与 SAI 验收；当前进度以其 owner 记录为准。

Forge 独立交付，Paimon 的发布门槛不自动成为每次 Forge 发布的门槛。完整 Contract System 仍为未批准 Draft；有限 contracts map、manifest 消费示例与 BEC 后继设计分别由上方链接的 2026-10-21 SPEC 约束。optional parser package 继续按独立计划验收。已结项 `paimon/` 只作历史证据，不是 Forge 运行时依赖或上级规范。

## 文档生命周期与开发路由

- 新建 SPEC 使用 `specs/YYYY-MM-DD-<topic>-design.md`，Markdown 是唯一可编辑源，HTML 按需生成阅读视图。历史 HTML 保持原有规范地位，实际修订时按需迁移。
- PLAN 使用 `plans/YYYY-MM-DD-<topic>.md`，记录决策来源、文件责任、命令和验收边界；evidence 记录候选身份、环境、结果与未证明项。PLAN 和 evidence 不反向发明公共契约。
- 已批准 SPEC 高于 PLAN/ROADMAP；后继只在声明范围内取代前序。被取代材料保留原文件和后继链接，Draft 与 provisional implementation 显式区分。
- L1 做最近验证；L2 先建立行为证据，适用时 RED → GREEN → REFACTOR；L3α 先 brainstorming 与批准 SPEC，L3β 依据已确认决策 writing-plans。用户已授权的同范围执行不重复索取批准。
- 提交前检查 diff、owning tests 及相关 CLI 示例；默认回归不访问真实集群。完成声明绑定当前候选的命令输出；真实运行只证明相应操作/解析，不承担科学判断。

核心边界与禁止项集中维护在 [AGENTS.md](../../AGENTS.md)，本索引不再复制一套规则。
