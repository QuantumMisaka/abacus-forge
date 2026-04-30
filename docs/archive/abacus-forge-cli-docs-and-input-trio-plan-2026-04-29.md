# ABACUS-Forge 文档对齐与输入三件套 CLI 闭环开发计划

## Summary
- 目标：进一步审查并收敛 `ABACUS-Forge` 当前状态，完成关键模块文档与 docstring 对齐，并在此基础上补齐 `modify-input` 与 `modify-kpt` CLI，使输入三件套 `INPUT / STRU / KPT` 的 CLI 闭环成立。
- 范围：
  - 对齐 `README.md`、`AGENTS.md`、`src/abacus_forge/cli.py`、`src/abacus_forge/modify.py`、`src/abacus_forge/input_io.py`。
  - 新增 `modify-input` 与 `modify-kpt` CLI 子命令。
  - 为新增 CLI 与文档对齐补齐测试。
- 不在本轮范围：
  - 不扩展 `collect` / `run` 新语义。
  - 不引入新的 workflow、AiiDA 语义、Slurm 语义或多步厚封装。
  - 不把未来规划继续混写在当前能力说明中；规划拆出到单独文档。

## Current State Analysis
- `src/abacus_forge/cli.py` 当前已有 5 个子命令：`prepare`、`modify-stru`、`run`、`collect`、`export`。CLI 可用，但仅有模块级一句话 docstring，`build_parser()`、`main()` 与参数解析辅助函数均无完整 docstring。
- `deps/abacus-forge/README.md` 当前同时混有“已实现能力”“待实现示例”“远期路线图”。CLI 章节仍使用过时示例，如 `--stru`、`--job`、`-o`，与当前真实接口不一致；同时 README 仍承担部分“开发入口”职责。
- `deps/abacus-forge/AGENTS.md` 当前包含开发边界与“开发者快速入口”，但用户已明确要求将项目开发入口迁移到 `AGENTS.md`，并把 README 中的规划独立出来。
- `src/abacus_forge/modify.py` 已具备稳定的 Python API：
  - `modify_input()` 支持 `updates`、`remove_keys`、`destination`。
  - `modify_stru()` 已有 CLI 包装。
  - `modify_kpt()` 支持 `mesh` 与 `line` 两种模式：`mode`、`mesh`、`shifts`、`points`、`segments`、`destination`。
- `src/abacus_forge/input_io.py` 已支持：
  - `read_input()` / `write_input()`
  - `read_kpt()` / `write_kpt()` / `write_kpt_mesh()` / `write_kpt_line_mode()`
- 测试现状：
  - `tests/test_cli.py` 已覆盖 `prepare`、`modify-stru`、`collect`、`export`，但未覆盖 `modify-input` / `modify-kpt`。
  - `tests/test_modify.py` 已覆盖 `modify_input()`。
  - `tests/test_input_io.py` 已覆盖 `modify_kpt()` 的 Python API，包括 mesh 与 line。

## Assumptions & Decisions
- 文档范围按“关键模块全覆盖”执行：`README.md`、`AGENTS.md`、`cli.py`、`modify.py`、`input_io.py` 全部对齐。
- `README.md` 采用“当前能力优先”口径：
  - README 只保留当前已实现并验证过的能力、安装与使用方式、最小 Python API 示例、项目关键内容。
  - 规划与路线图拆到单独文档，避免继续混入当前用户手册。
- 项目开发入口迁移到 `AGENTS.md`：
  - `AGENTS.md` 成为开发边界、开发入口、开发流程和实现约束的第一入口。
  - `README.md` 不再承担开发规范入口。
- `modify-kpt` CLI 第一版做完整 `mesh + line`：
  - mesh 模式通过显式参数编辑。
  - line 模式通过重复参数传递点与标签，避免强依赖外部 JSON 文件。
- CLI 命令命名采用与现有 `modify-stru` 一致的风格：新增 `modify-input`、`modify-kpt` 两个薄包装子命令，而非引入统一但更复杂的泛型 `modify` 命令。
- 所有新增 CLI 仍坚持薄包装原则：仅映射已有 Python API，不在 CLI 层引入超出 API 的新业务语义。

## Proposed Changes

### 1. 对齐 README 与 AGENTS 的职责边界
- 文件：`deps/abacus-forge/README.md`
- 变更：
  - 删除或改写所有“待实现”“目标接口示例”式表述，改成当前已实现能力说明。
  - 更新 CLI 章节为真实命令：`prepare` / `modify-stru` / `modify-input` / `modify-kpt` / `run` / `collect` / `export`。
  - 明确开发态与安装态运行方式，例如开发态需要 `PYTHONPATH=src python -m abacus_forge.cli ...`，安装态使用 `abacus-forge ...`。
  - 保留项目关键内容：定位、边界、已实现核心能力、最小 CLI 示例、最小 Python API 示例、目录约定。
  - 不再混写未来工作流与规划；改为链接到独立规划文档。
- 文件：`deps/abacus-forge/AGENTS.md`
- 变更：
  - 将“开发者快速入口”扩展为明确的开发入口，包括：
    - 先看哪里：`AGENTS.md -> README.md -> tests/`
    - 如何本地运行 CLI / pytest
    - 开发边界与新增命令必须遵守的薄包装原则
  - 保留并强化 PAIMON 主线边界约束，确保文档与当前实现一致。
- 文件：新增单独规划文档，位置待实现时确定在 `deps/abacus-forge/` 下的 markdown 文档中。
- 原因：
  - 当前 README 已不适合同时承担用户手册与规划文档角色。
  - 用户已明确要求“README 保留关键内容，规划独立，开发入口迁移到 AGENTS.md”。

### 2. 为关键模块补齐 docstring
- 文件：`deps/abacus-forge/src/abacus_forge/cli.py`
- 变更：
  - 为模块 docstring 改成更完整的职责说明。
  - 为 `build_parser()`、`main()`、`_parse_parameters()`、`_parse_numeric_mapping()`、`_parse_float_list()` 补齐 docstring。
  - 若新增 line 模式解析辅助函数，也同步补齐 docstring。
- 文件：`deps/abacus-forge/src/abacus_forge/modify.py`
- 变更：
  - 为 `modify_input()`、`modify_stru()`、`modify_kpt()` 与关键内部归一化函数补齐 docstring。
  - docstring 中明确输入类型、支持的修改维度、目标文件写出语义与错误条件。
- 文件：`deps/abacus-forge/src/abacus_forge/input_io.py`
- 变更：
  - 为 `read_input()`、`write_input()`、`read_kpt()`、`write_kpt()`、`write_kpt_mesh()`、`write_kpt_line_mode()` 补齐 docstring。
  - 明确 KPT mesh / line 结构化 payload 的约定。
- 原因：
  - 当前 docstring 明显不足，无法支撑“源码即文档”的快速维护。
  - 本轮的 CLI 闭环需要 docstring 与 README 同步收敛。

### 3. 新增 `modify-input` CLI 子命令
- 文件：`deps/abacus-forge/src/abacus_forge/cli.py`
- 变更：
  - 新增 `modify-input` 子命令。
  - 建议参数：
    - 位置参数：`source`
    - 必选：`--output`
    - 重复参数：`--set KEY=VALUE`
    - 重复参数：`--remove KEY`
    - 可选：`--header TEXT`
  - 执行逻辑：
    - 使用现有 `modify_input()` 完成读入、更新、删除、写出。
    - stdout 返回最小 JSON 摘要，例如输出路径和最终 key 数量，保持与 `modify-stru` 风格一致。
  - 错误处理：
    - 复用 `_parse_parameters()` 解析 `KEY=VALUE`。
    - 非法 `KEY=VALUE` 直接 `SystemExit`，与现有 CLI 风格保持一致。
- 文件：`deps/abacus-forge/tests/test_cli.py`
- 变更：
  - 新增 `modify-input` CLI 测试：
    - 文件源 -> set/remove -> 输出文件校验
    - 非法参数格式报错
- 原因：
  - `modify_input()` 已具备稳定 Python API，是最直接可闭环到 CLI 的输入编辑能力。

### 4. 新增 `modify-kpt` CLI 子命令
- 文件：`deps/abacus-forge/src/abacus_forge/cli.py`
- 变更：
  - 新增 `modify-kpt` 子命令。
  - 参数设计：
    - 位置参数：`source`
    - 必选：`--output`
    - `--mode mesh|line`
    - mesh 模式参数：
      - `--mesh i j k` 或重复整数参数方案，最终固定为三整数输入
      - `--shifts i j k`
    - line 模式参数：
      - `--segments N`
      - 重复参数 `--point "kx,ky,kz[:LABEL]"`，例如 `--point 0,0,0:Gamma --point 0.5,0,0:X`
  - 执行逻辑：
    - 若指定 `--mode mesh`，调用 `modify_kpt(..., mode="mesh", mesh=..., shifts=...)`
    - 若指定 `--mode line`，解析 `--point` 为 `points=[{"coords": [...], "label": ...}, ...]` 后传给 `modify_kpt()`
    - 输出最小 JSON 摘要，如 `mode`、`output`
  - 辅助函数：
    - 在 `cli.py` 中新增 line 点解析函数，负责把 `kx,ky,kz[:LABEL]` 转为结构化 payload。
  - 错误处理：
    - 缺少 3 个 mesh 值、非法 shifts、非法 point 坐标、line 模式无 point、mode 与参数不匹配时，统一以 `SystemExit` 或 `ValueError` 转换为 CLI 失败。
- 文件：`deps/abacus-forge/tests/test_cli.py`
- 变更：
  - 新增 `modify-kpt` mesh 模式测试。
  - 新增 `modify-kpt` line 模式测试。
  - 覆盖从已有文件读入并修改、以及输出后可被 `read_kpt()` 正确解析。
- 原因：
  - 用户明确要求输入三件套 CLI 闭环。
  - 当前 `modify_kpt()` Python API 已稳定，CLI 只需做薄包装与参数解析。

### 5. 视需要补充 README 的 Python API 最小示例
- 文件：`deps/abacus-forge/README.md`
- 变更：
  - 更新 Python API 代码块，替换当前未实现的 `workflows.elastic` 示例。
  - 改为真实可运行的最小示例，如：
    - `prepare(...)`
    - `run(...)`
    - `collect(...)`
    - `modify_input(...)` / `modify_kpt(...)` / `modify_stru(...)`
- 原因：
  - 当前示例引用 `abacus_forge.workflows.elastic`，与仓库现状不符，容易误导。

## Implementation Notes
- `modify-input` 与 `modify-kpt` 都采用“单文件读 -> 内存更新 -> 可选写回”的薄包装，延续现有 `modify-stru` 交互风格。
- `modify-kpt` 的 line 模式点输入采用 `kx,ky,kz[:LABEL]`：
  - 好处：一条参数即可表达点和标签，命令行可读性高。
  - 与现有 payload 结构一一对应，不需要新增外部中间格式。
- 文档对齐时要显式区分：
  - 当前已实现能力
  - 未来规划文档
  - 开发者入口与约束

## Verification Steps
- 文档核对：
  - 手动检查 `README.md` 中 CLI 命令、参数名、示例与 `cli.py --help` 一致。
  - 手动检查 `AGENTS.md` 已承担开发入口角色，README 不再承担开发规范入口。
- 测试：
  - 运行 `python -m pytest deps/abacus-forge/tests/test_cli.py -q`
  - 运行 `python -m pytest deps/abacus-forge/tests/test_modify.py -q`
  - 运行 `python -m pytest deps/abacus-forge/tests/test_input_io.py -q`
  - 运行 `python -m pytest deps/abacus-forge/tests -q`
- 诊断：
  - 对修改过的 `cli.py`、`modify.py`、`input_io.py`、`README.md` 相关 Python 文件执行 diagnostics 检查。
- 手动 CLI 验证：
  - `PYTHONPATH=src python -m abacus_forge.cli --help`
  - `PYTHONPATH=src python -m abacus_forge.cli modify-input --help`
  - `PYTHONPATH=src python -m abacus_forge.cli modify-kpt --help`
  - 构造一个最小 `INPUT` 和 `KPT` 文件，验证新命令输出文件可被 `read_input()` / `read_kpt()` 解析。
