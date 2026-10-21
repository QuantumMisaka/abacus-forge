# ABACUS-Forge 路线图

本页维护当前重点和待决候选，更新于 2026-10-21。当前用法见[使用指南](docs/guide.md)，接口与成熟度见[参考](docs/reference.md)，逐项任务和验收证据由下列 owning PLAN 维护。历史运行数字不作为当前候选的通过证明。

本轮 NAO/BEC/消费扩展已于 `5f38349` 合入本地 main，集成后回归通过；
本轮优先升级 optional parser 到 `abacuslite==1.2.2`，当前候选与验收见
[1.2.2 接续](docs/superpowers/evidence/2026-10-21-forge-abacuslite-1.2.2-rebind.md)；此前集成证据见
[交付收口](docs/superpowers/evidence/2026-10-21-forge-integration-candidate-closeout.md)。
`25cd715` 的上层交接候选见[候选记录](docs/superpowers/evidence/2026-10-21-forge-main-25cd715-candidate.md)。

## 当前重点与未完成验收

| 事项 | 已有基础 | 仍需完成 | 维护入口 |
| --- | --- | --- | --- |
| 文档与代码体系收敛 | 文档、加载/能力映射、band 共享代码与测试分类整理已完成，并通过离线回归与独立审查；已合入本地 main。 | 后续清理按下方调查结论与触发条件推进。 | [本轮计划](docs/superpowers/plans/2026-10-13-forge-repository-consolidation.md) |
| COHP IAO 后处理 | typed postprocess W1 已合入；Paimon W2、安装态 Si fixture 与完整真实 Si SCF 五组轨道后处理已验证，总曲线迁移等价与 s/p 分解一致性通过。 | 更广材料覆盖与上层完整平台链验收；legacy COHP parity 另行验收。 | [真实输入证据](docs/superpowers/evidence/2026-10-15-forge-real-evidence.md)、[安装消费](docs/superpowers/evidence/2026-10-15-forge-cohp-installed-consumption.md) |
| 直接 NAO / PyATB COHP 与有限消费接续 | 2026-10-21 有界 direct NAO 接口、有限 contracts map 和现有 manifest 消费示例已实现并完成离线验证、独立审查及两轨 Si 回放。 | 更广材料/自旋覆盖、目标平台与上层验收另行推进；此范围不改变 IAO W1、不批准完整 Contract System Draft，也不批准 property manifest Draft。 | [NAO/PyATB SPEC](docs/superpowers/specs/2026-10-21-forge-pyatb-cohp-design.md)、[元数据/manifest 消费 SPEC](docs/superpowers/specs/2026-10-21-forge-consumption-metadata-design.md)、[完成计划与证据](docs/superpowers/plans/2026-10-21-forge-consumption-followup.md)、[验证记录](docs/superpowers/evidence/2026-10-21-forge-consumption.md) |
| Polarization 与 BEC typed operations | 有界实现、离线回归与审查已完成；fresh wheel 安装验证通过，MgO 真实计算已验证单个 O_x 响应。能力仍为 experimental，legacy BEC pack 未做数值替换。 | 当前真实材料验证仅覆盖单列；不代表完整张量或收敛，也不构成 Paimon/SAI 验收。敏感性与其余状态由后继计划维护。 | [BEC SPEC](docs/superpowers/specs/2026-10-21-forge-polarization-bec-design.md)、[实现计划](docs/superpowers/plans/2026-10-21-forge-bec-implementation.md)、[安装与实算接续计划](docs/superpowers/plans/2026-10-21-forge-installed-bec-validation.md)、[验证证据](docs/superpowers/evidence/2026-10-21-forge-installed-bec-validation.md) |
| Engine/Version Policy | 当前 exact extra 为 `abacuslite==1.2.2`；已安装发布包的四 capability canonical parity 与留存 develop/LTS 八格真实输出回放按新候选验证，native 仍默认。 | 更广版本、材料/自旋与上层交付仍开放；1.2.2 回放复用旧计算输出，不是新引擎执行。LTS relax/cell-relax 原有 partial 保留。完整 PyATB 候选安装消费已有证据，当前 native wheel 限 CPython 3.12 / Linux x86_64 / glibc ≥ 2.39。 | [1.2.2 接续](docs/superpowers/evidence/2026-10-21-forge-abacuslite-1.2.2-rebind.md)、[版本政策计划](docs/superpowers/plans/2026-09-13-forge-engine-version-policy.md) |
| 真实进程与能力成熟度 | SCF/Relax/cell-relax/MD、PyATB 及部分 packs 已有各自候选的运行证据；当前 wheel 的 ATST 2.2.8 + LTSv3.10.1 有限步 NEB 执行与后处理恢复已通过核对，未收敛；所有 typed capability 仍为 experimental。 | ATST 2.3.0 安装态 CLI 与上游真实轨迹消费已通过，见[交接验收](docs/superpowers/evidence/2026-10-19-forge-atst-upstream-replay.md)。不默认重复上游 NEB；后续按接口变化补适配验证，未覆盖 packs 继续按能力验收。 | [本轮真实证据](docs/superpowers/evidence/2026-10-15-forge-real-evidence.md)、[Stage 5 计划](docs/superpowers/plans/2026-09-13-forge-stage5-evidence-gates.md)、[真实 smoke 入口](tests/real_smoke/README.md) |
| Paimon v1.3 上层迁移 | Forge 独立公共契约与局部 adapter/parity 证据已建立；显式 SCF 矩阵输出、actual/readiness 与 develop 文件名适配已完成，独立 CPython 3.12 环境中的候选 ZIP 已通过两轨 Si SCF→PyATB band 实算。 | Paimon replay 和 band 边缘事实已补齐，Si canary 通过；当前 kit 的新旧 ZIP 绑定需由 owner 统一，完整 Benchmark/SAI 验收继续推进。`25cd715` wheel 候选可评估，Paimon 尚未采用；默认路由 14/15 PARTIAL 为 PyATB 显式调用策略。 | [跨仓导航](docs/superpowers/README.md#跨仓迁移)、[当前候选](docs/superpowers/evidence/2026-10-21-forge-main-25cd715-candidate.md) |

LTS cell-relax 的历史 partial 个案来自多个有效最终结构候选的歧义，不能简单归因于“不写 STRU_FINAL”。原始运行结果保留，纠正后的诊断见版本政策计划的“C 阶段 native real-smoke 证据（2026-09-13）”。

## 集成推进重点

以人类与 Agent 共用的 Python/CLI 契约、事实结果和显式产物交接体现平台价值。
优先闭合已有能力的独立消费、Paimon 默认链和干净安装，再按真实需求扩展能力。
`abacustools` 纳入底层格式、算法与使用场景参考；专业引擎继续由 abacuslite、
ATST、PyATB 等各自维护。参考不自动成为运行时依赖。

既有规范复核、仓库责任和建议顺序见[集成参考复核](docs/superpowers/plans/2026-09-09-forge-core-fidelity-references.md#integration-review-20261019)，
COHP 的共同 NAO 输入、IAO 选择来源及局限见[方法溯源](docs/superpowers/plans/2026-09-09-forge-core-fidelity-references.md#cohp-provenance-20261019)。
执行状态仍由上表 owning PLAN 与 Paimon W0–W4 维护，不建立第二套总计划。

## 独立设计候选

- [Contract System 完整 Draft](docs/superpowers/specs/2026-09-29-forge-contract-system-design.html) 仍未整体批准。2026-10-21 的有限 contracts map 由[独立 SPEC](docs/superpowers/specs/2026-10-21-forge-consumption-metadata-design.md)定义，不代表 M1–M4 或知识库/查询服务已批准。
- [BEC 历史设计](docs/superpowers/specs/2026-09-29-forge-typed-bec-design.html) 的后继是已确认的[有界 polarization/BEC SPEC](docs/superpowers/specs/2026-10-21-forge-polarization-bec-design.md)。本地实现/离线验证已完成；安装态与 MgO 单列真实验证及其敏感性状态由[后继计划](docs/superpowers/plans/2026-10-21-forge-installed-bec-validation.md)和[证据](docs/superpowers/evidence/2026-10-21-forge-installed-bec-validation.md)维护。当前证据不代表全张量或收敛；能力仍为 experimental，legacy pack 保持原样。
- [Property manifest Draft](docs/superpowers/specs/2026-09-10-forge-property-manifest-design.html) 继续保留 Draft 状态。2026-10-21 [有限消费 SPEC](docs/superpowers/specs/2026-10-21-forge-consumption-metadata-design.md) 对既有 manifest 定义调用方消费示例，不批准原规范或提升成熟度。
- PyATB properties、property/composite 聚合、更多 property 的 typed 化及额外 export 格式，按具体需求另立边界与验证；不从现有 band handoff、manifest 或 export 推导。

## 可废弃与依赖调整候选

2026-10-13 已完成 Forge `1503d0b` 与已知 Paimon checkout `da25adf21` 的有界调查；处置如下。本批不删除接口、不改变默认安装依赖。未发现本仓调用不等于没有外部消费者。

| 候选 | 调查结论与当前处置 | 下一步触发条件 |
| --- | --- | --- |
| 默认依赖 `dpdata` | **保留，不列为移除候选。** 2026-10-19 用户确认该库会持续用于 ABACUS 数据处理；当前默认依赖保持不变。 | 无移除任务；后续数据能力按具体需求复用。 |
| `api.suppress_legacy_events` | **保留兼容行为，降低清理优先级。** 无本仓或已查上层调用；它仍是可导入的上下文管理器，仅抑制 prepare_unit/modify_unit 事件，退出后恢复状态，并非无行为的空接口。 | 出现实际迁移需求时，先核对外部用途并刻画事件抑制范围，再决定兼容窗口。 |
| `Workspace.claim_v1_operation` | **保留轻量兼容别名。** 生产服务使用 operation_guard；三个 workspace 测试仍经别名保护 stale claim、owner token 和 tombstone 行为。 | 下次实质修改 admission 时核对外部使用；新行为测试优先覆盖 operation_guard，别名的兼容处置另行决定。 |
| 科学功能依赖的 extra 拆分 | **维持默认安装。** ASE/NumPy 支撑核心结构与数据；matplotlib 被默认开启的 band/DOS 绘图使用；pymatgen 支撑标准化并影响 prepare 对称性元数据。 | 有明确分层安装需求时，设计默认能力与降级语义，验证各安装组合；仅延迟 import 不足以支持改为 extra。 |

本仓实现依据：[依赖声明](pyproject.toml)、[事件抑制](src/abacus_forge/api.py)、[admission 与别名](src/abacus_forge/workspace.py)、[后处理默认值](src/abacus_forge/postprocess_contracts.py)、[结构标准化](src/abacus_forge/structure.py)。Paimon 调查限于其 `toolbox/ABACUS` 源码、安装材料与 W3 记录：`utils/stru_read.py`、`utils/abacus_structure_io.py`、`toolkits/trajectory_dataset.py` 有直接消费；历史 `2026-10-11-paimon-w3-current-clean-route-dfb878f8/current-clean-route.lock` 固定 `dpdata==1.1.0`，但不说明依赖来源，也不证明当前 kit 安装已验收。W3 状态继续由[跨仓 owner 入口](docs/superpowers/README.md#跨仓迁移)维护。

`run`、UnitSpec、task/sequence、property/composite packs 继续保留。legacy 或 experimental 标签本身不是废弃依据。

## 长期边界

Forge 继续只交付明确输入、一次本地进程或独立后处理以及事实结果。Slurm、云平台、ATP/MCP、AiiDA、workflow 编排、重试/恢复与科学判定留在外层；可选本地 TUI 只能作为已有 API/结构化 CLI 的薄壳。外部 atst-tools 承担其自身 NEB 链路逻辑，Forge 不接管站点调度。

实现历史、仍有效的 SPEC 和候选绑定的验证记录统一从[设计、计划与证据索引](docs/superpowers/README.md)进入；不在本页累积逐日流水账。
