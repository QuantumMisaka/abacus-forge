# AGENTS.md

本文件是 `ABACUS-Forge` 子项目的人类与 AI 开发第一入口，负责说明开发定位、边界、验证与文档路由。
用户向说明与当前 CLI / Python API 用法请参阅 [README.md](README.md)，项目规划与路线图请参阅 [ROADMAP.md](ROADMAP.md)。详细的文档先行治理在 [docs/superpowers/README.md](docs/superpowers/README.md)。

## 1. 开发者快速入口
- **先看顺序**：`AGENTS.md -> README.md -> tests/`
- **开发定位**：`ABACUS-Forge` 是协议与平台无关的 ABACUS 科学计算内核，同时服务 ABACUS Agent（Paimon）v1.3 适配层和独立 CLI 用户。
- **工作模式**：作为纯 Python 库和 Agent-first CLI 工具开发，向上提供单元化调用接口，不承担上层 workflow 编排职责。
- **核心原则**：所有新增能力必须落在薄包装基元内，遵循 `prepare`、`modify-*`、`execute`、`collect`、`export` 的职责边界；`run` 仅作为兼容别名。
- **成熟度原则**：仅有 mock/fixture 测试的 property pack 一律标记为实验性，不得冒充已通过真实 ABACUS 验收的稳定能力。

## 2. 本地开发与验证
- **CLI 开发态运行**：
  - 在本仓库根目录执行
  - `PYTHONPATH=src python -m abacus_forge.cli --help`
- **测试入口**：
  - `conda run -n paimon python -m pytest tests/test_cli.py -q`
  - `conda run -n paimon python -m pytest -q`
- `tests/README.md` 是测试分层和门禁的唯一入口；新增测试先选择最近的行为边界和 marker。
- 默认回归不得访问真实集群；`real_smoke` 与 `benchmark` 只能通过显式 pytest 选项运行。
- 删除或合并测试前必须记录真实 mutation 及剩余测试的失败证据；不得以测试数量或覆盖率替代行为证据。
- 第三方 warning 只能按精确模块与消息过滤；项目自身 warning 应修复，不得静默。
- `compat`/`benchmark` 是迁移证据，`real_smoke` 是发布证据；以上任何一类测试单独都不能证明物理收敛或 HPC 调度器正确性。
- New Forge artifacts exposed across an operation boundary require a v1 `ArtifactRecord` and a regression asserting a workspace-relative path.
- `reports/forge-workspace.json` and `reports/events/*.json` are append-only audit records; do not replace them with a mutable last-result file.
- Run `tests/test_contracts.py`, `tests/test_workspace.py`, and the owning API/result tests whenever contracts or workspace persistence change.
- **开发习惯**：
  - 新增 CLI 时，必须同时补充对应 pytest 用例。
  - 修改 `README.md` 中 CLI 示例时，必须核对 `--help` 与测试覆盖是否同步。

## 3. 严格的开发边界与禁止项
为保证执行基座的轻量化与通用性，开发时必须严格遵守以下红线：
- **禁止依赖云服务编排**：严禁引入 Bohrium、DPDispatcher 等外部平台依赖。
- **禁止处理上层协议**：严禁包含 MCP、ATP 等协议编解码逻辑。
- **禁止耦合 AiiDA 语义**：严禁在 Forge 中处理 AiiDA Group、Node UUID、特定命名策略等上层语义。
- **禁止前端逻辑**：严禁引入页面状态管理或 UI 强耦合交付物渲染逻辑。
- **禁止原样照搬 Legacy workflow**：从 `abacus-test` 等旧库提取能力时，必须剥离厚工作流，只保留输入归一化、指标解析等底层能力。

## 4. 核心契约抽象原则
任何针对 `ABACUS-Forge` 的实现或 PR，必须符合以下 I/O 契约：
- **`prepare`**：只负责将结构与参数转化为合规的 ABACUS 输入目录，包括 `INPUT`、`STRU`、`KPT` 与赝势/轨道文件组织。
- **`modify-*`**：只负责对单个输入文件或单个结构载荷做轻量编辑，不负责批量编排和任务链管理。
- **`run`**：只负责将指定目录与资源参数转换为本地进程执行，不负责前置准备与后置分析。
- **`collect/export`**：只负责解析工作目录输出并返回标准化结果或 JSON，不负责落库、展示和平台化交付。

## 5. 文档职责与开发路由
- **`README.md`**：面向科研用户和调用者；只记录当前能力、成熟度、安装与稳定用法。
- **`AGENTS.md`**：面向人类与 AI 开发者；只记录边界、验证和文档入口，不承载详细设计。
- **`docs/superpowers/specs/*.html`**：公共 API/schema、workspace、CLI 协议、迁移或跨仓边界的规范源；批准后高于 plan 与 roadmap。
- **`docs/superpowers/plans/*.md`**：从已批准 SPEC 推导的执行清单，不得反向发明或改变架构。
- **`ROADMAP.md`**：方向和候选里程碑，不是 API 或持久化契约。

按当前 Superpowers 路由开发：L1 局部可逆修改做最小验证；L2 行为变更先建立回归证据，适用时使用 TDD；L3α（设计未定的公共边界）先 `brainstorming` 和 SPEC，L3β（用户已拍板的多步骤工作）先 `writing-plans`。L3 的 SPEC/PLAN 必须存入 `docs/superpowers/`；实施前应取得对应设计/计划批准。完成声明只认 diff 与命令输出。

当前 Paimon v1.3 迁移的设计基线是 [契约优先重构 SPEC](docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html)。在它获批前，不得以重构名义修改公共 CLI、结果 schema、workspace 持久化语义或 ATP adapter 边界。

## 6. 跨项目联动说明
在进行实质性开发前，应核对工作区当前产品边界：
- [工作区 AGENTS.md](../AGENTS.md)
- 已结项 `paimon/` 仅是历史设计和能力抽取证据，不是 Forge 的上级规范或运行时依赖。
