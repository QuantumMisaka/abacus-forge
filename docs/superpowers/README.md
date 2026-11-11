# Forge 设计、计划与证据

本页是维护者的状态与规范导航，更新于 2026-11-05。用户用法从 [docs/README.md](../README.md) 进入；开发先读 [AGENTS.md](../../AGENTS.md) 和[架构说明](../architecture.md)。有效 SPEC 持续约束对应接口；PLAN 完成后转为实施记录，不能因历史 checkbox 未勾选而自动重启。

## 当前唯一工程化接续

[公开交付 PLAN 的 Task 10](plans/2026-10-21-forge-public-release.md#工程化接续待实施) 集中管理最终集成与发行。Task 5–9 已完成：受控执行生命周期、四版本安装态 CI、Agent composite 消费示例、收窄发行内容和独立贡献入口均有实现与证据。

当前工程化候选为 branch `codex/forge-public-engineering-20261111@c65931d`，package `0.1.0`。该候选通过 Python 3.10–3.13 source/installed-package CI、完整 extracted-sdist/installed-wheel 默认套件（1727 passed / 59 skipped）和独立贡献者 focused 验收，见[2026-11-11 证据](evidence/2026-11-11-forge-public-engineering-slices/README.md)。该候选已由 [PR #19](https://github.com/QuantumMisaka/abacus-forge/pull/19) 合并为 `main@f2c1cbe`，main CI run `42974464142` 全部成功。后继版本/tag、授权 PyPI 上传和公开索引验收仍未执行；历史 `v0.1.0` 不包含这些改动。

## 已完成并收口

| 切片 | 结项范围与依据 | 转交后的责任 |
| --- | --- | --- |
| Phase A 收缩 | `f02588c` 已进入 main；平行 registry/types/CLI 已撤回，[计划](plans/2026-10-29-forge-computation-factory-phase-a.md)结项。 | 不重启七层架构或 Phase A–F。 |
| SCF consumer chain 与复审 | Forge 实现已集成；`2dfcae8` 修复、fresh-wheel/default service stub 交接完成，[计划](plans/2026-10-29-forge-scf-consumer-chain.md)与[证据](evidence/2026-11-05-forge-review-followup/README.md)。 | 后继候选 CI/发行进入公开交付 PLAN；Paimon 平台验收留给其 owner。 |
| 声子/弹性/振动任务展开 | 单元枚举、独立 execute/collect、显式 gather/post 与安装态验收完成，[计划](plans/2026-11-05-forge-task-expansion.md)结项。 | 远端持续验证/公共入口进入接续；Paimon/资源不倒置为本切片未完成。 |
| 初版 doctor、用户入口与发布管线 | [公开交付 Task 1–4](plans/2026-10-21-forge-public-release.md#初版交付记录已完成)实现及原候选验收完成。 | 实际 PyPI 发布仍开放；不重做已有 doctor/CLI。 |
| 四版本 release matrix 一致性 | [矩阵计划](plans/2026-10-23-forge-release-matrix-gate.md)完成，`68d42658` 已在 main。 | 新能力覆盖是新的具体缺口，不是重建矩阵。 |
| 仓库整理、COHP、有限元数据、BEC 与依赖消费 | 各有界实施已完成，见下方主题记录。 | 更广材料、平台或完整物性验收不由代码完成自动关闭；按实际需求继续。 |

整体替代判断见[架构审查](evidence/2026-11-05-forge-architecture-replacement-audit/README.md)及[并行展开 report 第 7 节](evidence/2026-11-05-forge-architecture-replacement-audit/phonon-elastic-vibration-parallel-report.md#7-用户授权后的-forge-实现接续)。Forge 13 / Paimon 25 个弹性应变单元的方法差异、完整能力迁移与 runner timeout 边界分别记录，不用同一“全部收口”状态掩盖。

## 有效设计基线

| 规范 | 适用范围 |
| --- | --- |
| [2026-10-29 算筹工场收缩设计](specs/2026-10-29-forge-computation-factory-target-architecture-design.md) | 现行产品与组合边界；撤回平行框架，保留 v1 契约。任务展开优先，资源接入后置；三类单元消费已落地。 |
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
| [公开交付与社区消费](specs/2026-10-21-forge-public-release-design.md) | 用户入口、环境诊断、公共兼容、发行内容与独立贡献边界；2026-11-05 接续实施归同一公开交付 PLAN。 |

## 退出当前开发入口的设计

| 材料 | 处置与理由 |
| --- | --- |
| Contract System M1–M4 / I/O Contract Knowledge Base | 未整体批准，与收缩方向不符；2026-11-05 从活动 SPEC 正文移出，归档到[退役设计](../archive/retired-designs/README.md)。不再作为待批准框架或开发前置。有限 discovery contracts map 仍按其 10-21 SPEC 生效。 |
| 09-29 Typed BEC 草案 | 已被 10-21 有界 SPEC 替代，且旧解释有已知错误；归档并保留原路径指引。 |
| [Property manifest 原始记录](specs/2026-09-10-forge-property-manifest-design.html) | 保留 provisional/Draft 的兼容依据：当前代码有实际文件事实索引。继续受 10-21 有限消费范围约束，不批准更大框架，也不因 Draft 标签删除现有行为。 |
| [abacuslite 独立分发记录](specs/2026-10-16-abacuslite-independent-plugin-design.md) | 相关包规范与后续发布归独立仓库；Forge 只维护消费边界，不复制其开发清单。 |

删除的是当前约束和重复待办；有效接口、来源与验收历史继续保留。三个退役 HTML 的原路径只提供状态和归档/后继链接，防止旧引用误导；具体清单在[归档索引](../archive/README.md)。

## 实现记录与历史计划

以下用于追溯实现和原候选证据，均不是要求重新执行的总待办。原始模板/checkbox 不追填为历史执行事实。已有实现由后继验收覆盖的基础契约、Agent CLI 与 collection fact matrix 已补状态说明。Engine/Version 的跨仓、目标系统与更广材料事项仍需按该计划的具体范围辨认。

| 主题 | 计划/记录 |
| --- | --- |
| 基线与测试治理 | [基线统一](plans/2026-09-01-forge-baseline-unification.md)、[契约基础](plans/2026-09-01-forge-contract-foundation.md)、[测试组合治理](plans/2026-09-01-forge-test-portfolio-governance.md) |
| Service、CLI 与操作 | [SCF](plans/2026-09-02-forge-service-status-scf.md)、[Agent-first CLI](plans/2026-09-04-forge-agent-first-cli.md)、[Relax](plans/2026-09-06-forge-relax-operations.md)、[MD](plans/2026-09-10-forge-typed-md-operations.md) |
| 中立内核与输入资产 | [保真收敛](plans/2026-09-09-forge-core-fidelity.md)、[参照源码与取舍](plans/2026-09-09-forge-core-fidelity-references.md)、[显式资产](plans/2026-09-09-forge-typed-asset-materialization.md)、[PBE/ATST 边界](plans/2026-09-09-forge-default-pbe-and-atst-neb-boundary.md) |
| 后处理与外部引擎 | [Band/DOS](plans/2026-09-10-forge-typed-postprocess.md)、[MD postprocess](plans/2026-09-10-forge-typed-md-postprocess.md)、[MD 复核修正](plans/2026-09-11-forge-md-postprocess-review-fixes.md)、[ATST adapter](plans/2026-09-09-forge-atst-neb-adapter.md) |
| COHP W1 | [COHP postprocess](plans/2026-10-15-forge-cohp-postprocess.md) |
| 2026-10-21 direct NAO 与消费 | [消费接续](plans/2026-10-21-forge-consumption-followup.md)；其实现和验证状态以该计划为准。后续 collect 已收紧 PyATB orbital-map metadata 校验并通过全离线、安装态与两轨真实 metadata 回放。 |
| 2026-10-21 Polarization/BEC | [BEC 实施](plans/2026-10-21-forge-bec-implementation.md)；[安装与实算接续](plans/2026-10-21-forge-installed-bec-validation.md)及[证据](evidence/2026-10-21-forge-installed-bec-validation.md)维护安装态和当前真实材料验证。仍为 experimental。 |
| PyATB 与导出 | [Band handoff](plans/2026-09-10-forge-typed-pyatb-band.md)、[manifest](plans/2026-09-10-forge-typed-pyatb-artifact-manifest.md)、[nspin=4](plans/2026-09-10-forge-typed-pyatb-nspin4.md)、[可选 rR](plans/2026-09-11-forge-typed-pyatb-optional-rr.md)、[export](plans/2026-09-10-forge-typed-export.md) |
| 解析、状态与前置条件 | [原生输出保真](plans/2026-09-10-forge-abacus-native-collection-fidelity.md)、[collection metadata](plans/2026-09-10-forge-typed-collection-metadata.md)、[Fermi 单位](plans/2026-09-12-forge-native-fermi-unit.md)、[calculation 校验](plans/2026-09-12-forge-typed-calculation-guards.md)、[normal_end](plans/2026-09-12-forge-typed-execute-normal-end.md) |
| 历史集成与运行门禁 | [主线集成](plans/2026-09-11-forge-mainline-integration.md)、[maturity gates](plans/2026-09-11-forge-maturity-gates-integration.md)、[迁移事实](plans/2026-09-11-forge-core-migration-facts.md)、[SCF smoke](plans/2026-09-10-forge-typed-scf-real-smoke.md)、[MD smoke](plans/2026-09-11-forge-typed-md-real-smoke.md)、[freshness](plans/2026-09-11-forge-real-smoke-freshness.md) |

<a id="跨仓迁移"></a>

## 验证与跨仓责任

- 当前测试分类、默认离线与 opt-in 入口由 [tests/README.md](../../tests/README.md)维护；源码、安装态、真实引擎与科学验收分别记录。
- 历史候选证据按原提交保留。代表入口：[Stage 5](evidence/2026-09-13-forge-stage5-evidence.md)、[双轨与 ATST](evidence/2026-10-19-forge-dual-track-atst230.md)、[abacuslite 1.2.2 消费](evidence/2026-10-21-forge-abacuslite-1.2.2-rebind.md)、[旧发行候选](evidence/2026-10-30-forge-0.1.0-release-candidate/README.md)。不在本导航滚动复制旧 Benchmark 分数或分支状态。
- Paimon v3 的 adapter、旧依赖解除、kit/平台和 Benchmark 由 app-tools migration owner 维护。其 `toolbox/ABACUS/docs/superpowers/plans/2026-09-13-paimon-v1.3-forge-migration.md` 是迁移入口；开始实质开发前先同步并合并最新 v2 基线，再绑定候选 checkout/commit。目录名与 toolbox 版本不能独立决定产品线。
- 参考仓按[参考记录](plans/2026-09-09-forge-core-fidelity-references.md)理解来源；刷新上游与采用新 runtime pin 分开处理。历史 `paimon/` AiiDA 原型不恢复为规范源。

## 文档维护

Markdown 是新建 SPEC/PLAN 的唯一可编辑源，HTML 按需生成阅读视图；仍有效的历史 HTML 维持原规范地位。后继只在声明范围内替代前序。完成的 PLAN 保留结果和剩余责任指针；新的具体缺口进入相应 owning PLAN，不通过重开旧清单扩大 scope。临时工具报告不进入产品文档，历史材料从[归档](../archive/README.md)读取。
