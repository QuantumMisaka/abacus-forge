# ABACUS-Forge 路线图

本页维护当前重点和待决候选，更新于 2026-10-15。当前用法见[使用指南](docs/guide.md)，接口与成熟度见[参考](docs/reference.md)，逐项任务和验收证据由下列 owning PLAN 维护。历史运行数字不作为当前候选的通过证明。

## 当前重点与未完成验收

| 事项 | 已有基础 | 仍需完成 | 维护入口 |
| --- | --- | --- | --- |
| 文档与代码体系收敛 | 文档、加载/能力映射、band 共享代码与测试分类整理已完成，并通过离线回归与独立审查；已合入本地 main。 | 后续清理按下方调查结论与触发条件推进。 | [本轮计划](docs/superpowers/plans/2026-10-13-forge-repository-consolidation.md) |
| COHP IAO 后处理 | typed postprocess W1 已合入；Paimon W2 已接线，当前 wheel/ZIP 无 system-site 后处理消费与 Si fixture 迁移等价通过。 | 当前候选真实引擎/平台验收、更广材料覆盖；legacy COHP parity 另行验收。 | [安装消费证据](docs/superpowers/evidence/2026-10-15-forge-cohp-installed-consumption.md) |
| Engine/Version Policy | native 兼容增量、离线 Stage 0 和 canonical checkout 四 capability parity 已集成；显式 PyATB handoff 支持新版 CSR 文件名。 | 可安装 abacuslite 版本与 exact extra、fresh environment 四 capability package parity，以及相应双轨发布证据。checkout 数值 parity 不替代可安装包验收。 | [版本政策计划](docs/superpowers/plans/2026-09-13-forge-engine-version-policy.md) |
| 真实进程与能力成熟度 | SCF/Relax/cell-relax/MD、PyATB 及部分 packs 已有各自候选的运行证据；所有 typed capability 仍为 experimental。 | 完整 ATST NEB 真实 workflow、未覆盖 packs 的实际执行/解析，以及具体发布候选的证据绑定。 | [Stage 5 计划](docs/superpowers/plans/2026-09-13-forge-stage5-evidence-gates.md)、[真实 smoke 入口](tests/real_smoke/README.md) |
| Paimon v1.3 上层迁移 | Forge 独立公共契约与局部 adapter/parity 证据已建立。 | 上层完整依赖与安装、全链路 benchmark、平台/生产验收由 Paimon owner 完成。 | [跨仓导航](docs/superpowers/README.md#跨仓迁移) |

LTS cell-relax 的历史 partial 个案来自多个有效最终结构候选的歧义，不能简单归因于“不写 STRU_FINAL”。原始运行结果保留，纠正后的诊断见版本政策计划的“C 阶段 native real-smoke 证据（2026-09-13）”。

## 独立设计候选

- [Contract System Draft](docs/superpowers/specs/2026-09-29-forge-contract-system-design.html) 接续早期 I/O knowledge-base 提案。request/schema 边界仍需设计收口；本轮整理不实施该系统，也不把它设为 Paimon 当前迁移的前置条件。
- [Typed BEC Draft](docs/superpowers/specs/2026-09-29-forge-typed-bec-design.html) 尚未批准、尚无实施 PLAN。legacy BEC pack 仍为 experimental；显式阶段交接、极化解析与公式/单位一致性需要在该设计中确认，不能把拟议设计写成已交付能力。
- PyATB properties、property/composite 聚合、更多 property 的 typed 化及额外 export 格式，按具体需求另立边界与验证；不从现有 band handoff、manifest 或 export 推导。

## 可废弃与依赖调整候选

2026-10-13 已完成 Forge `1503d0b` 与已知 Paimon checkout `da25adf21` 的有界调查；处置如下。本批不删除接口、不改变默认安装依赖。未发现本仓调用不等于没有外部消费者。

| 候选 | 调查结论与当前处置 | 下一步触发条件 |
| --- | --- | --- |
| 默认依赖 `dpdata` | **优先评估迁移，当前保留。** Forge 生产源码未检出引用；Paimon 的结构/轨迹工具直接使用。v1.3 历史 lock 包含它，但尚未证实上层安装声明独立承接该依赖。 | Paimon W3 明确直接专业依赖，验证当前候选的干净安装；Forge 完成移除依赖的候选安装/消费检查，并说明对其他安装消费者的影响。 |
| `api.suppress_legacy_events` | **保留兼容行为，降低清理优先级。** 无本仓或已查上层调用；它仍是可导入的上下文管理器，仅抑制 prepare_unit/modify_unit 事件，退出后恢复状态，并非无行为的空接口。 | 出现实际迁移需求时，先核对外部用途并刻画事件抑制范围，再决定兼容窗口。 |
| `Workspace.claim_v1_operation` | **保留轻量兼容别名。** 生产服务使用 operation_guard；三个 workspace 测试仍经别名保护 stale claim、owner token 和 tombstone 行为。 | 下次实质修改 admission 时核对外部使用；新行为测试优先覆盖 operation_guard，别名的兼容处置另行决定。 |
| 科学功能依赖的 extra 拆分 | **维持默认安装。** ASE/NumPy 支撑核心结构与数据；matplotlib 被默认开启的 band/DOS 绘图使用；pymatgen 支撑标准化并影响 prepare 对称性元数据。 | 有明确分层安装需求时，设计默认能力与降级语义，验证各安装组合；仅延迟 import 不足以支持改为 extra。 |

本仓实现依据：[依赖声明](pyproject.toml)、[事件抑制](src/abacus_forge/api.py)、[admission 与别名](src/abacus_forge/workspace.py)、[后处理默认值](src/abacus_forge/postprocess_contracts.py)、[结构标准化](src/abacus_forge/structure.py)。Paimon 调查限于其 `toolbox/ABACUS` 源码、安装材料与 W3 记录：`utils/stru_read.py`、`utils/abacus_structure_io.py`、`toolkits/trajectory_dataset.py` 有直接消费；历史 `2026-10-11-paimon-w3-current-clean-route-dfb878f8/current-clean-route.lock` 固定 `dpdata==1.1.0`，但不说明依赖来源，也不证明当前 kit 安装已验收。W3 状态继续由[跨仓 owner 入口](docs/superpowers/README.md#跨仓迁移)维护。

`run`、UnitSpec、task/sequence、property/composite packs 继续保留。legacy 或 experimental 标签本身不是废弃依据。

## 长期边界

Forge 继续只交付明确输入、一次本地进程或独立后处理以及事实结果。Slurm、云平台、ATP/MCP、AiiDA、workflow 编排、重试/恢复与科学判定留在外层；可选本地 TUI 只能作为已有 API/结构化 CLI 的薄壳。外部 atst-tools 承担其自身 NEB 链路逻辑，Forge 不接管站点调度。

实现历史、仍有效的 SPEC 和候选绑定的验证记录统一从[设计、计划与证据索引](docs/superpowers/README.md)进入；不在本页累积逐日流水账。
