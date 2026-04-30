# ABACUS-Forge stdout 日志发现与解析对齐实施计划

## Summary
- 目标：调研 `abacus-test collectdata` 对“stdout 被重定向到任意名称日志文件”的处理方式，并在 `ABACUS-Forge` 当前实现基础上规划一个细致、可实施、边界清晰的方案。
- 本轮结论：
  - 参考 `abacus-test` 的核心思路是“基于内容关键字自动发现屏幕输出文件”，而不是强依赖文件名。
  - Forge 不应机械复刻 `abacus-test` 的 `FindOutput()` 行为，而应在其基础上做“确定性排序 + 有限扫描范围 + 显式覆盖入口”。
  - 方案应同时覆盖 Python API 与 CLI。
- 计划范围：
  - 调整 `collect()` 的 stdout 类日志发现策略。
  - 引入显式覆盖入口，允许用户直接指定 stdout 日志路径。
  - 增强 diagnostics，使自动发现与覆盖决策透明可追踪。
- 不在本轮范围：
  - 不改变 `running_{calculation}.log` 作为主计算日志的定位。
  - 不做递归的全工作区深度扫描。
  - 不将多个 `running_*.log` 聚合成统一结果序列。

## Current State Analysis

### 1. `abacus-test collectdata` 的当前做法
- 文件：`repo/abacus-test/abacustest/lib_collectdata/resultAbacus.py`
  - `self.OUTPUTf = output if output is not None else comm.FindOutput(self.PATH, keyinfo="Atomic-orbital Based Ab-initio")`
  - 说明 `collectdata` 对屏幕输出文件支持“显式指定 output 路径”与“自动发现”两种模式。
- 文件：`repo/abacus-test/abacustest/lib_collectdata/comm.py`
  - `FindOutput(path, keyinfo)` 的策略是：
    - 切换到目标目录
    - `os.listdir(".")` 扫描该目录第一层所有普通文件
    - 逐个读全文，查找固定关键字 `Atomic-orbital Based Ab-initio`
    - 命中后立刻返回该文件路径
  - 关键特征：
    - 不依赖文件名
    - 不递归
    - 不显式排序
    - 若有多个命中文件，返回值受 `os.listdir()` 顺序影响
- 文件：`repo/abacus-test/abacustest/lib_collectdata/resultAbacus.py`
  - `self.LOGf` 仍固定为 `OUT.{suffix}/running_{calculation}.log`
  - 说明 `collectdata` 对 stdout 输出文件与主运行日志是两套语义：
    - `OUTPUTf`：屏幕输出，名称可变，靠内容发现
    - `LOGf`：主运行日志，名称固定，靠 `INPUT.calculation + suffix` 推导
- 文件：`repo/abacus-test/abacustest/lib_collectdata/abacus/abacus.py`
  - `GetTimeFromOutput()`、`GetDenergy()` 等指标明确依赖 `self.OUTPUT`
  - `GetLogResult()`、`GetForceFromLog()`、`GetStessFromLog()` 等指标明确依赖 `self.LOG`
  - 说明 stdout 发现问题在 `collectdata` 里是真实需求，不是辅助能力。

### 2. Forge 当前实现
- 文件：`deps/abacus-forge/src/abacus_forge/api.py`
  - 当前 Forge 已对主 `running_*.log` 做了更严格的选择：
    - 先根据 `inputs/INPUT` 中的 `calculation` 匹配 `running_{calculation}.log`
    - 否则唯一 `running_*.log`
    - 多个候选则标记歧义并回退到 `stdout.log` / `out.log`
  - 但对 stdout 类日志的发现仍偏硬编码：
    - 只把 `workspace/outputs/stdout.log` 与 `workspace/outputs/out.log` 当作 fallback 候选
    - 无法识别被重定向到其他名称的屏幕输出文件，如 `abacus.log`、`job.log`、`screen.out`
- 文件：`deps/abacus-forge/src/abacus_forge/workspace.py`
  - Forge 的标准布局是 `workspace/{inputs,outputs,reports}`
  - 这意味着扫描策略应优先以 `workspace/outputs/` 为核心，再兼容 `workspace/` 顶层
- 文件：`deps/abacus-forge/tests/test_api.py`
  - 当前测试只覆盖：
    - `stdout.log`
    - `out.log`
    - `running_*.log`
  - 尚未覆盖：
    - stdout 内容被重定向到任意名称文件
    - 自动内容发现
    - 用户显式指定 stdout 日志路径

### 3. 必要性评估
- 这项增强是必要的。
- 原因：
  - `abacus-test` 已证明“stdout 文件名不可预设”是现实场景。
  - Forge 当前实现虽然已经修复了主 `running_*.log` 与 fallback 的污染问题，但 fallback 仍然依赖固定文件名，鲁棒性不足。
  - 继续只依赖 `stdout.log/out.log` 会导致一部分真实工作目录在 `collect()` 中丢失 `OUTPUT` 类信息，例如 `total_time`、`denergy`、部分 SCF 表格信息。
- 同时，这项增强必须控制边界：
  - 不能因此反向弱化 `running_{calculation}.log` 的主日志定位。
  - 不能扩大为递归全目录“搜所有文件”的重扫描器。

## Assumptions & Decisions
- 总体策略：
  - 采用“内容发现 + 确定性排序”的 Forge 版本，而不是严格复刻 `abacus-test` 的 `FindOutput()`。
- 扫描范围：
  - 扫描 `workspace/` 顶层普通文件
  - 扫描 `workspace/outputs/` 顶层普通文件
  - 不递归扫描 `outputs/**`
- 发现目标：
  - 仅用于“stdout 类输出文件”发现，不用于替代 `running_{calculation}.log`
  - 也不用于选择 `stderr.log`
- 关键字策略：
  - 第一版沿用 `abacus-test` 的关键标识：`Atomic-orbital Based Ab-initio`
  - 可在实现中预留一个关键字列表常量，便于未来扩展
- 决策顺序：
  - 若用户显式传入 `output_log`，优先使用该路径
  - 否则先按现有主 `running_*.log` 选择规则选主日志
  - 对 stdout 类输出文件：
    - 先检查固定候选名 `stdout.log` / `out.log`
    - 若没有，再做内容发现
  - 自动发现找到多个候选时，采用确定性排序后取第一个，并在 diagnostics 中记录全部候选
- 确定性排序：
  - 对候选文件按“相对路径自然排序”处理，避免 `os.listdir()` 不稳定行为
- 显式覆盖入口：
  - Python API：在 `collect(..., output_log=...)` 增加参数
  - CLI：在 `abacus-forge collect` 增加 `--output-log <path>`
- 兼容性：
  - 不修改 `CollectionResult` dataclass 字段
  - 新信息全部通过 `diagnostics` 输出

## Proposed Changes

### 1. 在 Forge 中引入 stdout 输出文件发现器
- 文件：`deps/abacus-forge/src/abacus_forge/api.py`
- 变更：
  - 新增私有辅助函数，例如：
    - `_discover_output_log(...)`
    - `_candidate_output_logs(...)`
    - `_file_contains_output_banner(...)`
  - 行为：
    - 收集 `workspace/` 与 `workspace/outputs/` 顶层普通文件
    - 优先识别固定候选名 `stdout.log` / `out.log`
    - 若固定候选缺失，再逐个检查文件内容是否包含关键标识
    - 采用自然排序保证稳定输出
  - 返回值建议包括：
    - `selected_path`
    - `selected_reason`
    - `candidate_paths`
    - `ambiguous`
- 原因：
  - 这是把 `abacus-test` 的内容发现能力有边界地落地到 Forge 的核心。

### 2. 将 stdout 发现与当前主日志选择逻辑整合
- 文件：`deps/abacus-forge/src/abacus_forge/api.py`
- 变更：
  - 在现有 `_select_log_sources()` 基础上升级为“两轨选择”：
    - 主运行日志轨：继续使用 `running_{calculation}.log`
    - stdout 输出轨：新增内容发现/显式覆盖
  - 关键语义：
    - 主运行日志仍决定主 metrics，如 `converged`、`total_energy`、`force`、`stress`
    - stdout 输出文件作为 `OUTPUT` 类信息来源，用于补充依赖屏幕输出的 collect 指标
  - 若当前 collector 还未显式区分“主日志文本”和“stdout 文本”，则需要在 `collect()` 到 collector 的接口上引入区分，而不是简单继续混成一个 `text_blobs`
- 原因：
  - 否则即便找到任意名称 stdout 文件，也无法安全地把它接入后续解析。

### 3. 调整 collector 接口，使 LOG / OUTPUT 语义分离
- 文件：`deps/abacus-forge/src/abacus_forge/collectors/abacus.py`
- 变更：
  - 当前 `collect_abacus_metrics(text_blobs=...)` 仍偏向统一文本聚合
  - 应改为更明确的输入形态，例如：
    - `main_log_text`
    - `output_log_text`
    - `artifacts`
    - `workspace_root`
    - `structure_volume`
  - 解析职责细化：
    - `main_log_text` 负责 `converged`、`total_energy`、`force`、`stress`、`pressure`、`virial` 等
    - `output_log_text` 负责 stdout 类表格/时间/SCF step 时间等
  - 若某类文本缺失，相关指标返回缺失并在 diagnostics 标记
- 原因：
  - 这是从当前“统一聚合文本”平滑过渡到更接近 `abacus-test` 的 `LOG/OUTPUT` 双通道模型的关键一步。

### 4. 增加显式覆盖入口
- 文件：`deps/abacus-forge/src/abacus_forge/api.py`
- 变更：
  - 为 `collect()` 增加参数，例如：
    - `output_log: str | Path | None = None`
  - 语义：
    - 指向 stdout 输出文件
    - 可以是绝对路径，也可以是相对 workspace 的路径
    - 若路径不存在，应在 diagnostics 中明确报错/告警，并回退到自动发现或固定候选策略
- 文件：`deps/abacus-forge/src/abacus_forge/cli.py`
- 变更：
  - 在 `collect` 子命令增加：
    - `--output-log <path>`
  - 将其透传给 `collect(..., output_log=...)`
- 原因：
  - 这能覆盖自动发现无法准确判定、或用户已知真实 stdout 文件名的场景。

### 5. 增强 diagnostics，使选择过程透明
- 文件：`deps/abacus-forge/src/abacus_forge/api.py`
- 变更：
  - 在现有 diagnostics 基础上补充 stdout 发现相关字段，例如：
    - `output_log_path`
    - `output_log_reason`
    - `output_log_candidates`
    - `output_log_selection_ambiguous`
    - `output_log_override_requested`
    - `output_log_override_missing`
  - 继续保留现有：
    - `selected_log_path`
    - `selected_log_reason`
    - `running_log_candidates`
    - `fallback_log_candidates`
    - `ignored_log_paths`
- 原因：
  - 这轮增强的价值不仅在“找到文件”，还在“后续能解释为什么找到这个文件”。

### 6. 补充测试覆盖真实场景
- 文件：`deps/abacus-forge/tests/test_api.py`
- 新增测试：
  - `workspace/outputs/abacus.log` 包含 stdout 标识时，自动发现成功
  - `workspace/job.log` 位于 workspace 顶层时，自动发现成功
  - 同时存在多个匹配 stdout 内容的候选文件时，按确定性排序选中一个，并记录全部候选
  - 显式 `output_log` 覆盖成功
  - 显式 `output_log` 指向不存在路径时，诊断中标明覆盖失败并回退自动发现
  - 仅有 `running_*.log`、没有 stdout 输出文件时，collect 行为保持兼容
- 文件：`deps/abacus-forge/tests/test_collect_abacus_reference.py`
- 变更：
  - 保留当前参考样例
  - 可新增一个将 `out.log` 重命名为其他名称并写入 workspace 的构造样例，验证内容发现生效
- 原因：
  - 这能直接锁定“stdout 名称不固定”的核心需求。

### 7. 视需要补充 docstring / README
- 文件：`deps/abacus-forge/src/abacus_forge/api.py`
- 变更：
  - 为新的 `collect(..., output_log=...)` 参数补 docstring
- 文件：`deps/abacus-forge/README.md`
- 变更：
  - 若本轮执行时一并更新文档，应在 collect 用法中注明：
    - 默认会自动发现 stdout 输出文件
    - 也可通过 `--output-log` / `output_log=` 显式指定
- 原因：
  - 新接口属于用户可见行为，文档应同步。

## Implementation Notes
- 对 `abacus-test` 的复用与修正：
  - 复用点：基于内容关键字而非固定文件名识别 stdout 输出文件
  - 修正点：
    - Forge 使用稳定排序，避免 `os.listdir()` 的随机性
    - Forge 只扫描受控范围，不做全目录漫游
    - Forge 保留显式覆盖入口，避免完全依赖自动发现
- 安全边界：
  - 任何 stdout 内容发现都不能覆盖主 `running_{calculation}.log` 的主日志地位
  - `stderr.log` 继续只参与失败判定
- 相对路径解析：
  - `output_log` 若传相对路径，优先按 `workspace.root / output_log` 解析
  - diagnostics 中统一记录最终解析后的绝对路径
- 关键字发现建议：
  - 第一版至少使用：
    - `Atomic-orbital Based Ab-initio`
  - 若后续观察到新版 ABACUS banner 差异，再扩展关键字集合

## Verification Steps
- 代码级验证：
  - `python -m pytest deps/abacus-forge/tests/test_api.py -q`
  - `python -m pytest deps/abacus-forge/tests/test_collect_abacus_reference.py -q`
  - `python -m pytest deps/abacus-forge/tests -q`
- CLI 级验证：
  - `PYTHONPATH=src python -m abacus_forge.cli collect --help`
  - 验证 `--output-log` 参数存在并说明清晰
- diagnostics 检查：
  - `api.py`
  - `collectors/abacus.py`
  - 若改动 `cli.py` 或 `README.md`，也同步检查
- 手动场景验证：
  - 场景 1：`outputs/stdout.log` 存在，行为保持兼容
  - 场景 2：stdout 被写到 `outputs/abacus.log`，自动发现成功
  - 场景 3：stdout 被写到 `workspace/job.log`，自动发现成功
  - 场景 4：存在多个候选输出文件，选中结果稳定且 diagnostics 透明
  - 场景 5：显式传入 `output_log`，覆盖自动发现逻辑
