# AGENTS.md

本文件为 `ABACUS-Forge` 子项目的开发模式、开发边界约束与开发者快速入口。
仓库介绍、路线图与使用示例请参阅本目录下的 [README.md](README.md)。

## 1. 开发者快速入口
- **开发定位**：`ABACUS-Forge` 是 `PAIMON` 主链 (`AI -> 协议层 -> AiiDA Workflow -> ABACUS-Forge -> ABACUS`) 中的最底层执行核心。
- **工作模式**：作为一个纯粹的 Python 库和 CLI 工具进行开发，向上面向 `aiida-abacus` 提供单元化调用接口。
- **设计原则**：所有新增能力必须遵循 `prepare`、`run`、`collect`、`export` 的基元划分，禁止编写包含多步物理过程的厚封装脚本。

## 2. 严格的开发边界与禁止项
为保证执行基座的轻量化与通用性，开发时**必须严格遵守**以下红线：
- **禁止依赖云服务编排**：严禁引入 Bohrium, DPDispatcher 等外部平台依赖。
- **禁止处理上层协议**：严禁包含任何与 MCP、ATP 相关的编解码逻辑。
- **禁止耦合 AiiDA 语义**：严禁在代码中处理 AiiDA Group、Node UUID 或特定的 AiiDA 命名策略。
- **禁止前端逻辑**：严禁包含页面状态管理或 UI 强耦合的交付物渲染逻辑。
- **禁止原样照搬 Legacy**：从 `abacus-test` 等旧代码库提取能力时，**必须剔除其厚封装工作流部分**，仅提取输入归一化、指标解析等底层能力。

## 3. 核心契约抽象原则
任何针对 `ABACUS-Forge` 的 PR 或 Agent 代码生成，必须符合以下 I/O 契约：
- **`prepare`**：只负责将结构文件和参数字典转化为合规的 ABACUS 输入目录（包含 `INPUT`, `STRU`, `KPT` 及软链接的赝势/轨道文件）。
- **`run`**：只负责将指定目录和资源参数（MPI/OpenMP）转换为合规的 shell 命令并拉起进程，不负责前置文件准备。
- **`collect/export`**：只负责解析工作目录中的输出文件（如 `OUT.*`），返回标准化的内存字典或 JSON 文件，不负责决定这些数据如何落库或展示。

## 4. 跨项目联动说明
在进行实质性开发前，强烈建议核对 PAIMON 主项目的总控契约：
- 架构主链与顶层契约：[PAIMON 主项目 AGENTS.md](../../AGENTS.md)
- 包边界划分：[PAIMON packages.md](../../docs/packages.md)