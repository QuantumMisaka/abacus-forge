# AGENTS.md

本文件是 `ABACUS-Forge` 子项目的开发第一入口，负责说明开发定位、开发边界、快速运行方式与跨项目协同约束。
用户向说明与当前 CLI / Python API 用法请参阅 [README.md](README.md)，项目规划与路线图请参阅 [ROADMAP.md](ROADMAP.md)。

## 1. 开发者快速入口
- **先看顺序**：`AGENTS.md -> README.md -> tests/`
- **开发定位**：`ABACUS-Forge` 是 `PAIMON` 主链 `AI -> 协议层 -> AiiDA Workflow -> ABACUS-Forge -> ABACUS` 中的最底层执行核心。
- **工作模式**：作为纯 Python 库和 CLI 工具开发，向上提供单元化调用接口，不承担上层 workflow 编排职责。
- **核心原则**：所有新增能力必须落在薄包装基元内，遵循 `prepare`、`modify-*`、`run`、`collect`、`export` 的职责边界。

## 2. 本地开发与验证
- **CLI 开发态运行**：
  - `cd deps/abacus-forge`
  - `PYTHONPATH=src python -m abacus_forge.cli --help`
- **测试入口**：
  - `python -m pytest deps/abacus-forge/tests/test_cli.py -q`
  - `python -m pytest deps/abacus-forge/tests -q`
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

## 5. 文档职责划分
- **`AGENTS.md`**：开发入口、开发约束、实现边界、验证方式。
- **`README.md`**：当前已实现能力、安装方式、CLI/Python API 使用方法。
- **`ROADMAP.md`**：未来规划、候选方向、阶段性里程碑。

## 6. 跨项目联动说明
在进行实质性开发前，建议核对 PAIMON 主项目总控契约：
- 架构主链与顶层契约：[PAIMON 主项目 AGENTS.md](../../AGENTS.md)
- 包边界划分：[PAIMON packages.md](../../docs/packages.md)
