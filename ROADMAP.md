# ABACUS-Forge 路线图

本页维护当前重点和待决候选，更新于 2026-10-13。当前用法见[使用指南](docs/guide.md)，接口与成熟度见[参考](docs/reference.md)，逐项任务和验收证据由下列 owning PLAN 维护。历史运行数字不作为当前候选的通过证明。

## 当前重点与未完成验收

| 事项 | 已有基础 | 仍需完成 | 维护入口 |
| --- | --- | --- | --- |
| 文档与代码体系收敛 | 用户已确认保留公开行为、英文 README、中文详细文档；本轮已进入实施。 | 加载/能力映射/公共算法与测试分类收敛、完整回归和独立审查。 | [本轮计划](docs/superpowers/plans/2026-10-13-forge-repository-consolidation.md) |
| Engine/Version Policy | native 兼容增量、离线 Stage 0 和 canonical checkout 四 capability parity 已集成；显式 PyATB handoff 支持新版 CSR 文件名。 | 可安装 abacuslite 版本与 exact extra、fresh environment 四 capability package parity，以及相应双轨发布证据。checkout 数值 parity 不替代可安装包验收。 | [版本政策计划](docs/superpowers/plans/2026-09-13-forge-engine-version-policy.md) |
| 真实进程与能力成熟度 | SCF/Relax/cell-relax/MD、PyATB 及部分 packs 已有各自候选的运行证据；所有 typed capability 仍为 experimental。 | 完整 ATST NEB 真实 workflow、未覆盖 packs 的实际执行/解析，以及具体发布候选的证据绑定。 | [Stage 5 计划](docs/superpowers/plans/2026-09-13-forge-stage5-evidence-gates.md)、[真实 smoke 入口](tests/real_smoke/README.md) |
| Paimon v1.3 上层迁移 | Forge 独立公共契约与局部 adapter/parity 证据已建立。 | 上层完整依赖与安装、全链路 benchmark、平台/生产验收由 Paimon owner 完成。 | [跨仓导航](docs/superpowers/README.md#跨仓迁移) |

LTS cell-relax 的历史 partial 个案来自多个有效最终结构候选的歧义，不能简单归因于“不写 STRU_FINAL”。原始运行结果保留，纠正后的诊断见版本政策计划的“C 阶段 native real-smoke 证据（2026-09-13）”。

## 独立设计候选

- [Contract System Draft](docs/superpowers/specs/2026-09-29-forge-contract-system-design.html) 接续早期 I/O knowledge-base 提案。request/schema 边界仍需设计收口；本轮整理不实施该系统，也不把它设为 Paimon 当前迁移的前置条件。
- [Typed BEC Draft](docs/superpowers/specs/2026-09-29-forge-typed-bec-design.html) 尚未批准、尚无实施 PLAN。legacy BEC pack 仍为 experimental；显式阶段交接、极化解析与公式/单位一致性需要在该设计中确认，不能把拟议设计写成已交付能力。
- PyATB properties、property/composite 聚合、更多 property 的 typed 化及额外 export 格式，按具体需求另立边界与验证；不从现有 band handoff、manifest 或 export 推导。

## 可废弃与依赖调整候选

下列项仅进入调查清单，本批不删除、不改变默认安装依赖。依赖调整须核对源码使用、上层消费者和干净安装；兼容接口删除须明确替代路径与迁移窗口。

| 候选 | 当前依据 | 决定前所需证据 |
| --- | --- | --- |
| 默认依赖 `dpdata` | Forge 生产代码未找到直接引用；Paimon 自身仍有使用。 | 包契约和已知消费者是否依赖传递安装；上层独立声明与 clean install。 |
| `api.suppress_legacy_events` | 本仓有定义和状态读取，未找到该上下文管理器调用。 | 外部导入盘点、历史兼容承诺和 legacy 事件等价性。 |
| `Workspace.claim_v1_operation` | `operation_guard` 的兼容别名，已有测试调用。 | 外部消费者、替代入口、兼容窗口及相同行为验证。 |
| 科学功能依赖的 extra 拆分 | matplotlib/pymatgen 等有实际功能使用，基础 I/O 可独立加载。 | 哪些默认安装能力受影响、可选依赖错误提示、分层安装门禁；不能仅因导入变轻而移除。 |

`run`、UnitSpec、task/sequence、property/composite packs 继续保留。legacy 或 experimental 标签本身不是废弃依据。

## 长期边界

Forge 继续只交付明确输入、一次本地进程或独立后处理以及事实结果。Slurm、云平台、ATP/MCP、AiiDA、workflow 编排、重试/恢复与科学判定留在外层；可选本地 TUI 只能作为已有 API/结构化 CLI 的薄壳。外部 atst-tools 承担其自身 NEB 链路逻辑，Forge 不接管站点调度。

实现历史、仍有效的 SPEC 和候选绑定的验证记录统一从[设计、计划与证据索引](docs/superpowers/README.md)进入；不在本页累积逐日流水账。
