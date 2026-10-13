# Forge 文档与代码体系整理实施计划

状态：执行中。2026-10-13 用户已确认设计取舍，并要求以 subagent-driven-development 推进；本计划承接该授权，不重复索取同范围批准。

设计：[文档与代码体系整理](../specs/2026-10-13-forge-repository-consolidation-design.md)。目标为英文产品 README、中文详细文档、明确的内容归属，以及保留公开行为的加载、能力映射、公共算法和测试分类收敛。

隔离工作区：`/home/james/.codex/worktrees/7037/abacus-forge`；分支 `codex/forge-repository-consolidation-20261013`；实现基线 `5c978b0c88b0654dc0a03e43f93eee4e42a72441`。此前已审阅的设计与导航从原工作区复制进来，原工作区不改动。

基线证据：同一源码/环境的默认离线回归 `1437 passed, 34 skipped in 100.60s`；收集 `1471` 项，其中 `615` 项无 portfolio marker。基线证据来自本轮审查的实际命令输出，复用而不伪造 RED。

## 实施边界与协作

- 保留公开导入路径、CLI 命令、参数默认值、能力覆盖、request/result/error、资产和 workspace 审计语义。默认依赖不在本批移除或转为 extra；候选单列。
- 多调用面按适用范围整理，不把 legacy/unit/sequence 自动改为 typed 行为，不实施 Contract System 或 BEC 草案。
- 同一隔离工作区内分配互不重叠的写入范围；子代理不提交、不操作共享 index、不再派生代理。控制器统一记录、审查、验证和提交。
- 子代理修改前均以计划建立后的干净提交为 BASE；完成后停止所辖写入，控制器检查完整 dirty diff（包含新增文件）。最终独立审查绑定控制器提交的完整基线到候选范围。

### Task 1：产品入口与使用文档

- [ ] 将 README 改为简洁的英文产品入口，保留安装、最小可运行示例、能力成熟度与中文文档导航。
- [ ] 建立 `docs/README.md`、`docs/guide.md`、`docs/reference.md`，分别承担导航、任务使用路径和接口/产物参考；搬迁现有有效细节，保留必要旧锚点导航，避免全文复制到多处。
- [ ] 说明 typed operation、primitive、UnitSpec、task/sequence 与 packs 的差异及适用场景；示例不得提升成熟度或暗改资产/状态语义。

Ownership：文档作者仅写上述四个文件。控制器负责 architecture/governance/roadmap；测试作者负责文档示例测试。文档作者与测试作者约定 `docs/guide.md` 的 `## Agent-first CLI` 保留两份现有 execute JSON 示例，README 可使用独立的最小 smoke 示例。

验收：检查新旧 README 内容去向、相对链接和旧锚点；文档示例继续经真实 CLI 解析/执行既有 dry-run 边界，相关 `--help` 可用。纯文案不造行为 RED。

### Task 2：包加载与共享能力映射

- [ ] 使基础 `abacus_forge.input_io` 导入不加载无关 service/engine/科学库；根包既有 122 项公开导出保持可获取、对象身份与导入路径兼容。
- [ ] 收敛 discovery 与 machine CLI 的 capability/request 映射，保持 discovery JSON、schema、解码、错误优先级和 service 路由行为；只使用相称的静态映射，不引入插件框架。
- [ ] 增加有独立保护价值的导入隔离/导出兼容回归，观察加载隔离的基线失败；已有机器面回归用于行为保持对比。

Ownership：`src/abacus_forge/__init__.py`、`discovery.py`、`machine_cli.py`、必要的小型静态映射模块与 `tests/test_imports.py`；不得写 `tests/test_architecture.py` 或 docs。测试文件自行声明 `core` marker。

验收：导入隔离在子进程中检查；全部旧导出与原对象相同，重复/并发基本导入正常；capabilities/schema 输出与基线等价；`tests/test_machine_cli.py`、`tests/test_cli_process.py`、相关 machine/contract suites 通过。源码包布局与 wheel 导入由控制器验证。

### Task 3：公共 band 后处理归属

- [ ] 将 typed 与 legacy 共享的表格输出/绘图及能带前缀识别归入中立模块，两个调用面复用同一实现。
- [ ] 保留 legacy 私有入口必要转发、函数签名与默认行为；显式 typed 路径不再从 legacy unit 模块借用实现。
- [ ] 复用现有后处理、API/unit 回归建立基线/候选等价；必要时补混合列布局和默认输出的独立行为断言。

Ownership：`src/abacus_forge/band_data.py`、`unit_postprocess.py`、`postprocess_algorithms.py`、必要的中立 band 输出模块及 `tests/test_postprocess_algorithms.py`。不得修改 CLI、包入口和其他测试作者所辖文件。

验收：`tests/test_postprocess_algorithms.py tests/test_postprocess_services.py tests/test_postprocess_machine_cli.py tests/test_units.py tests/test_tasks.py` 通过；能量列、默认文件内容与可选图行为保持。不以删除测试或放宽预期获得通过。

### Task 4：测试分类与验收入口

- [ ] 补齐 portfolio marker 归类；已有保护保留，默认仍隔离 benchmark/real_smoke，新增未归类文件应能暴露而非静默遗漏。
- [ ] 更新 `tests/test_architecture.py` 的文档行为测试读取位置，保留真实 CLI 校验；配合 Task 1 的示例搬迁。
- [ ] 整理中文 `tests/README.md` 与 `tests/real_smoke/README.md`，保留有效命令/环境/证据范围，纠正旧版本问题归因并链接证据。

Ownership：`tests/conftest.py`、`tests/test_architecture.py`、上述两个测试 README；确需验证选择行为时可新增小型 owning test。不删除或合并原测试。

验收：收集的每项适用测试有 portfolio marker；正向 marker 选择覆盖对应文件，默认 real_smoke/benchmark 仍跳过。旧示例行为验证继续通过；执行无真实集群访问。

### Task 5：架构、文档治理与最终集成（控制器）

- [ ] 建立中文 `docs/architecture.md`，映射现行职责/代码/参考/扩展与测试定位。
- [ ] 收敛 AGENTS、ROADMAP、`docs/superpowers/README.md`：Markdown 新规范、有效设计/草案/历史导航、当前专项入口及独立可废弃候选；保留上位规范地位和历史证据。
- [ ] 检查已知本仓和跨仓 README 链接，保留兼容锚点；标明旧 I/O Draft 与 Contract System Draft 的关系，不把独立草案修成批准设计。
- [ ] 统一检查各包完整 diff、文档链接和示例、架构与契约/workspace 门禁、默认全量离线回归、wheel/公开导入检查。
- [ ] 冻结候选，独立整体审查，处理真实发现并复验；记录结果和剩余候选，保留工作区交付。

当前环境可用 `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider`。全量测试统一由控制器在包集成后执行；各包先运行上述 focused suites，日志路径与实际结果回报控制器。文档验证按现有可执行检查或直接链接/锚点检查进行，不增设文档框架。

## Rulings 与进展

- Ruling：保留默认依赖和所有现有调用面，仅列出可废弃候选 — 本轮批准的是兼容收敛 — 若遗漏实际安装/调用依赖，会破坏上层消费。
- Ruling：先完成可独立验证的加载、映射和 band 共享代码整理，不批量重排全部生产目录 — 以降低实际耦合为目标 — 大范围移动会增加导入路径与跨仓迁移成本。
- 初始化：原工作区已有设计未提交，复制到隔离工作区纳入本任务；子代理分配前由控制器建立干净恢复点。

## 验收记录

待各包实现与整体验证后填入实际命令、输出、候选身份和审查结论；未执行门禁不记为通过。
