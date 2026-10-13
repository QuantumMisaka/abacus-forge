# Forge 文档与代码体系整理设计

状态：设计方向已确认（2026-10-13）；用户随后授权以 subagent-driven-development 执行，进展和验收见[实施计划](../plans/2026-10-13-forge-repository-consolidation.md)。

决策来源：本轮仓库审查后，用户选择“首轮保留已有公开能力和调用行为，将可废弃项单列”，并提出英文 README、中文详细文档及清晰的文档职责和指向。本文件固化这些决定与整理边界。

上位规范：[契约优先重构](2026-09-01-forge-contract-first-rearchitecture-design.html)、[Service/Status](2026-09-02-forge-service-status-migration-design.html)。本设计不改变 operation、请求/结果 schema、workspace 持久化或跨仓责任。设计决策由本文维护，执行清单与证据由关联 PLAN 维护。

## 1. 整理目标与依据

让 Forge 的轻量定位落实到使用与维护：用户容易找到入口，基础模块可以独立消费，一个能力的共享信息减少重复维护，当前说明与历史证据各有归属。

审查基线为 `main@5c978b0`。README 有 1031 行，安装说明位于第 336 行；`docs/superpowers/` 有 11 份 SPEC、34 份 PLAN，详细使用说明主要集中在 README。生产源码约 2.1 万行；规模本身不作为删除能力的依据。

具体整理依据：

- [包入口](../../../src/abacus_forge/__init__.py) 导出 122 个名称；导入 `abacus_forge.input_io` 会连带加载 MD 后处理、PyATB、ATST 等模块。该观察证明加载耦合，不直接证明性能不合格。
- [discovery](../../../src/abacus_forge/discovery.py) 与 [machine CLI](../../../src/abacus_forge/machine_cli.py) 分别维护 capability/request 映射。
- [typed 后处理算法](../../../src/abacus_forge/postprocess_algorithms.py) 复用 [legacy unit 后处理](../../../src/abacus_forge/unit_postprocess.py) 的私有函数，能带前缀识别存在两处实现。
- 测试收集共 1471 项，其中 615 项未归入 portfolio marker；当前全量回归覆盖这些测试，正向 marker 选择不能覆盖相应全部行为。
- 主线离线回归已验证 `1437 passed, 34 skipped`。这是审查基线，不是后续变更的验收结果，也不是引擎、平台或科学验收。

## 2. 首轮兼容边界

保留现有公开能力、导入路径和 CLI 调用行为。兼容包括参数默认值、资产来源与 copy/link 语义、输出文件、状态、错误及 artifact/event 协议。

primitive、UnitSpec、typed operation、task/sequence 与 composite/property pack 的适用范围必须说明清楚。typed prepare 与 legacy prepare 的资产语义不同，typed band/DOS 目前只覆盖 postprocess；不能以整理为由将所有入口强制映射为同一调用链。文档可按使用场景明确推荐入口，同时保留完整能力说明。

首轮优先收敛顶层加载、简单静态能力映射、公共算法归属和模块责任。已有 SCF/Relax/MD service 的共享实现继续复用；不以文件长度或减少文件数作为重构目标。具体目录移动和内部拆分依据消费者盘点确定，保留必要的兼容转发。

安装依赖也属于消费边界。移除依赖或改为 extra 前，必须核对实际引用、上层消费及干净安装；影响默认安装能力的调整单列评估，不作为纯内部重构暗含实施。

## 3. 语言与文档职责

README 采用英文，作为唯一维护的根级产品入口，不新增需要双向同步的中文 README。详细使用、架构和开发治理文档以中文为主；README 清楚标注中文文档链接，保留足以独立完成安装与最小调用的英文说明。

命令、API 名称、字段、错误码和机器输出保留原文。历史证据、原始日志和已有规范不为了统一语言进行批量翻译；实质整理对应文档时再统一其说明语言。

下表规定内容归属。优先使用少量职责清晰的文档，只有内容规模或读者路径确有需要时再拆分专题。

| 位置 | 读者与回答的问题 | 内容边界 |
| --- | --- | --- |
| `README.md`（英文） | 初次接触者：项目做什么、如何安装、如何完成最小调用？ | 定位、前置条件、安装、最小示例、能力概览与成熟度、导航；详细字段和迁移历史交给对应文档。 |
| `docs/README.md`（中文） | 所有读者：接下来去哪里查？ | 文档总导航，按使用、开发、验证、当前设计与历史资料组织链接；不复制各处正文和状态。 |
| `docs/guide.md`（中文） | 科研用户和 Agent 接入者：具体场景怎么操作？ | CLI/Python 使用路径、输入准备、执行收集、后处理、pack 与兼容入口的适用范围及示例。 |
| `docs/reference.md`（中文） | 调用者：当前接口、字段、文件和能力边界是什么？ | 当前接口与 workspace 参考；链接 `--help`、schema discovery 和对应有效 SPEC，避免复制整套机器 schema。 |
| `docs/architecture.md`（中文） | 开发者：代码如何分层、能力扩展改哪里、依据是什么？ | 当前模块责任、依赖方向、兼容层、扩展与测试定位、开发参照；规范性语义链接有效 SPEC。 |
| `AGENTS.md`（中文为主） | 人类与 AI 开发者：必须遵守哪些边界、先读哪里？ | 保留简短约束和入口，不承载接口手册与逐日进度。 |
| `ROADMAP.md`（中文） | 维护者：当前推进什么、哪些仍未验收、哪些只是清理候选？ | 当前重点及专项 PLAN 链接，单列可废弃候选；逐项执行状态归 owning PLAN，历史命令结果归 evidence。 |
| `tests/README.md` | 开发者：运行什么测试、能证明什么？ | 测试分层和门禁的唯一入口；real-smoke 的准备与运行细节链接既有 `tests/real_smoke/README.md`。 |
| `docs/superpowers/README.md` | 设计与实施者：哪个规范有效、哪个计划在途？ | 治理和设计/计划索引，区分有效规范、草案、实施计划及历史记录。 |
| `docs/superpowers/{specs,plans,evidence}/` 与 `docs/archive/` | 维护者和回溯者 | 分别保存规范、执行、证据和历史材料，按生命周期导航。 |

用户阅读路径：英文 README → 中文 guide/reference → 必要时有效 SPEC。开发阅读路径：AGENTS → architecture → owning SPEC/PLAN 与测试。仅消费 Forge 不要求读取 Paimon 跨仓迁移历史。

## 4. 内容归属与迁移纪律

- 同一完整说明只保留一个主要维护位置；其他入口使用简短摘要和链接。用户指南描述当前行为，SPEC 定义批准的契约，PLAN 记录实施，evidence 记录对应候选的验证。
- 每份有效设计明确状态、适用范围、上位或后继规范；历史 PLAN 中的原始未勾选模板不能被误读为当前待办。已完成记录可以标记为历史，仍有效的 SPEC 不因年代或已经实现而归档。
- 新建或实际迁移的规范以 Markdown 为唯一可编辑源；历史 HTML SPEC 保留原有规范地位。将 AGENTS 和治理入口中的仅 HTML 路由与此约定对齐，HTML 阅读视图按需生成。
- 搬迁正文时同步本仓链接、已知跨仓引用和行为示例测试的读取位置；保留必要的旧路径/锚点导航。测试继续执行示例并校验行为，不能因 README 缩短而删除保护。
- Forge 本地文档独立说明自己的产品、架构和发布边界；Paimon 的工具覆盖、完整 Benchmark 和平台迁移状态链接其 owner 文档，不复制为 Forge 的发布门槛。
- Contract System、BEC 等独立草案不随此次整理被批准或实施；其问题、取代关系和未决设计继续显式保留。

## 5. 可废弃项单列

“候选”仅表示值得调查，不等于已经废弃、允许删除或已完成迁移。以下是初始盘点；实施后当前候选清单归入 ROADMAP 的独立清理章节，保留替代路径、消费者和处理结论。

| 候选 | 当前依据 | 作出废弃决定前需要确认 |
| --- | --- | --- |
| 默认依赖中的 `dpdata` | Forge 生产源码未找到引用；Paimon 的结构/轨迹交付仍直接使用它。 | Forge 的包契约、已知消费者是否隐式依赖其安装；上层依赖声明与 clean install。 |
| `api.suppress_legacy_events` | 本仓查到定义及对应状态读取，未查到该上下文管理器的调用。 | 外部导入与历史兼容承诺、移除后 legacy 事件行为。 |
| `Workspace.claim_v1_operation` 别名 | 转发至 `operation_guard`；已有测试调用，ROADMAP 已记录后续收敛触发点。 | 外部使用、替代入口、兼容窗口和相同行为证据。 |

`run` 别名、UnitSpec、sequence 与 property/composite packs 本轮继续保留。它们不会因带有 legacy/experimental 标签而自动进入删除范围。

## 6. 可观察的完成标准

1. 英文 README 能独立说明安装与最小调用，并明确指向中文详细文档；其示例与实际 CLI/API 一致。
2. 用户能区分 typed operation、便利入口和兼容行为；开发者能从导航定位实现、有效规范、owning tests 和在途计划。
3. 当前能力、成熟度和已知限制不与历史结果混写；搬迁后本仓与已知消费者文档链接有效。
4. 基础文本 I/O 导入不再连带加载无关的 MD/PyATB/ATST service；导出兼容仍可验证。性能评价单独基于测量，不以模块数替代。
5. 共享能力映射和公共算法有明确维护位置；对应发现、解码、API/CLI 及兼容行为仍由独立预期验证。
6. 测试分类覆盖应归类的用例，默认回归保持离线；代码变更通过 owning tests 与受影响消费者验证。契约/workspace 相关变更沿用已有门禁，测试合并或删除沿用真实 mutation 证据要求。
7. 可废弃候选与实施任务分开，候选调查不会静默改变公开行为、默认安装能力或科学能力范围。

验证按改动范围执行。文档重组核对链接、示例与文档行为测试；代码整理使用基线/候选行为证据和对应测试；引擎交接或安装行为受影响时补相应 smoke/clean-install 证据。既有证据未受影响时复用，不为纯文档改动重复真实计算。
