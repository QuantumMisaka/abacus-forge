# ABACUS-Forge 日志选择与 Collect 增强开发计划

## Summary
- 目标：基于 `repo/ABACUS-agent-tools`、`repo/aiida-abacus`、`repo/abacus-test` 的现有实现重新评估后，对 `ABACUS-Forge` 的 `collect` 做“最小必要增强”。
- 本轮结论：
  - 不做通用“多 `running_*.log` 顺序聚合”。
  - 优先修正主日志选择策略，避免 `stdout.log/out.log` 与 `running_*.log` 的混合污染。
  - 当检测到多个 `running_*.log` 时，不把它们当作一个步骤序列，而是尽量依据当前 `INPUT.calculation` 选择唯一主日志；若仍不唯一，则明确给出“歧义” diagnostics，而不是猜测性聚合。
- 本轮范围：
  - 改进 `collect()` 的主日志选择规则。
  - 增强 diagnostics，完整暴露候选日志、选择依据、歧义状态与回退策略。
  - 保持顶层 `metrics/status` 兼容，不引入步骤级 `step_results` 结构。
- 不在本轮范围：
  - 不做多步骤聚合模型。
  - 不把 `running_relax.log -> running_scf.log -> running_nscf.log` 视为一个 collect 单元内的顺序步骤。
  - 不引入 workflow 编排语义或 AiiDA 子任务聚合语义。

## Current State Analysis

### 1. Forge 当前实现
- `deps/abacus-forge/src/abacus_forge/api.py` 中：
  - `collect()` 先 `_collect_artifacts()`，再 `_log_paths()`，然后把全部日志文本读成 `text_blobs` 交给 `collect_abacus_metrics()`。
  - `_log_paths()` 当前策略是：
    - 总是先加入 `outputs/stdout.log` 和 `outputs/stderr.log`
    - 再追加所有 `running_*.log`
    - 若没有 `running_*.log`，才回退到 `outputs/out.log`
  - 这意味着当前 collect 仍是“多日志拼接后整体解析”，没有主日志选择模型。
- `deps/abacus-forge/src/abacus_forge/collectors/abacus.py` 中：
  - `collect_abacus_metrics()` 将 `text_blobs` 全部拼接为 `combined`
  - force/stress/pressure/virial 等也是跨 `text_blobs` 顺序追加
  - diagnostics 已有增强，但仍是聚合日志口径，不区分“主日志”和“辅助日志”
- 当前测试：
  - `deps/abacus-forge/tests/test_api.py` 覆盖单日志 collect 与基础 diagnostics
  - `deps/abacus-forge/tests/test_collect_abacus_reference.py` 覆盖 `running_scf.log + out.log` 共存
  - 尚未覆盖“多个 `running_*.log` 候选”时的主日志选择/歧义策略

### 2. 参考实现交叉审阅结论
- `repo/abacus-test`
  - `collectdata` 是“单任务目录、单主日志”模型
  - `running_{calculation}.log` 路径由 `INPUT.calculation` 推导，不扫描多个 `running_*.log`
  - `OUTPUT` 只取任务目录下首个命中的输出文件，也不是多文件聚合
  - 多任务通过外部传入多个 job 目录逐个 collect，而不是在一个目录内做多日志聚合
- `repo/aiida-abacus`
  - `AbacusCalculation` / `AbacusParser` 也是“单 CalcJob、单主日志”模型
  - retrieved 中的主日志来自 `running_{calc_type}.log`
  - WorkChain 的 relax/scf/nscf/band/dos 是多个子 CalcJob，不会在 parser 中把多个 `running_*.log` 聚合成一个 collect 对象
- `repo/ABACUS-agent-tools`
  - 结果收集核心仍是单 job 目录调用 collectdata
  - 多子任务由上层 workflow 在多个子目录中逐个运行、逐个收集，不提供统一多日志聚合层

### 3. 必要性评估
- “把同一 workspace 下多个 `running_*.log` 建模成统一步骤序列”的必要性，经审阅后明显下降。
- 风险点：
  - `running_relax.log`、`running_scf.log`、`running_nscf.log` 更可能对应不同计算任务，虽然可能基于同一体系或同一结构演化，但并不天然属于一个 collect 原子单元。
  - 若强行按顺序聚合，容易把不同任务的状态、能量、力应力、收敛标记混在一起，产生错误顶层结果。
- 当前真正需要修复的问题更像是：
  - 有主日志时，不应再被 `stdout.log` 或 `out.log` 污染
  - 多个 `running_*.log` 同时存在时，需要有清晰的“选择唯一主日志 / 标记歧义”的策略

## Assumptions & Decisions
- 口径：
  - 采用“最小必要增强”。
  - 主日志优先级以 `running_*.log` 为先，但仅在能够唯一确定时使用。
- 主日志选择规则：
  - 优先读取 `inputs/INPUT` 的 `calculation`
  - 若存在与之匹配的 `running_{calculation}.log`，且唯一，则将其选为主日志
  - 若没有匹配主日志：
    - 若 `running_*.log` 只有一个，则选它
    - 若有多个 `running_*.log` 且无法唯一匹配，则不做猜测性聚合
  - 无法唯一确定主日志时：
    - 若有 `stdout.log` 或 `out.log`，回退到单兜底日志继续 collect
    - 同时在 diagnostics 中明确标记“存在多个 running 候选、未做聚合”
    - 若既无可唯一确定主日志，也无可用兜底日志，则返回 `missing-output` 或保留空 metrics，并给出歧义 diagnostics
- `stdout.log/out.log` 角色：
  - 在已选择主 `running_*.log` 时，不再参与 metrics 解析，只作为 diagnostics 记录
  - 仅在没有可用主 `running_*.log` 时作为兜底日志来源
- `stderr.log` 角色：
  - 继续只参与顶层失败判定与 diagnostics，不参与 metrics 提取
- 兼容性：
  - 不修改 `CollectionResult` dataclass 字段
  - 不引入 `step_results`
  - 保持现有顶层 `metrics/status` 格式

## Proposed Changes

### 1. 在 `api.py` 中建立“主日志选择”而不是“多日志拼接”模型
- 文件：`deps/abacus-forge/src/abacus_forge/api.py`
- 变更：
  - 将 `_log_paths()` 重构为更明确的日志选择逻辑，例如：
    - 收集 `running_*.log` 候选
    - 读取 `inputs/INPUT` 中的 `calculation`
    - 按 `running_{calculation}.log` 精确匹配主日志
    - 若无精确匹配则处理“唯一候选”或“歧义候选”
    - 独立记录 `stdout.log` / `out.log` 作为 fallback 候选
  - `collect()` 改为只把“被选中的主日志文本”传入 metrics 解析
  - `stdout.log/out.log` 不再与主日志一起拼接
  - 新增 diagnostics：
    - `log_strategy`
    - `selected_log_path`
    - `selected_log_reason`
    - `running_log_candidates`
    - `fallback_log_candidates`
    - `ignored_log_paths`
    - `log_selection_ambiguous`
    - `stderr_nonempty`
- 原因：
  - 当前核心问题不是“没有顺序模型”，而是“缺乏唯一主日志选择规则”

### 2. 在 `collectors/abacus.py` 中保持单日志解析边界，并增强 diagnostics
- 文件：`deps/abacus-forge/src/abacus_forge/collectors/abacus.py`
- 变更：
  - 保持当前单日志 / 单文本解析模型，不引入步骤级聚合
  - `collect_abacus_metrics()` 继续接受选中的主日志文本列表，但实现上默认只解析主日志来源
  - diagnostics 保持现有增强项，同时允许由 `api.collect()` 注入新的日志选择 diagnostics
  - 如需要，补充轻量 warning：
    - 检测到多个 `running_*.log` 但只选择其中一个
    - 使用 fallback 日志而非主 `running_*.log`
- 原因：
  - 参考实现普遍采用单主日志解析；Forge 不应在本轮越过这一边界

### 3. 明确歧义场景的降级与状态口径
- 文件：`deps/abacus-forge/src/abacus_forge/api.py`
- 变更：
  - `_determine_status()` 保持现有顶层状态词汇：
    - `failed`
    - `missing-output`
    - `unfinished`
    - `completed`
  - 但状态依据改为“被选中的主日志”而不是全部日志拼接后的 metrics
  - 当多个 `running_*.log` 存在且无法唯一选择时：
    - 不做顺序聚合
    - 如果 fallback 日志可用，则按 fallback 的 collect 结果给出状态，同时在 diagnostics 中显式标记不确定性
    - 如果 fallback 也不可用，则顶层返回 `missing-output`
- 原因：
  - 与“最小必要增强”口径一致，避免用不可靠的多日志聚合结果覆盖状态

### 4. 增加针对主日志选择与歧义诊断的测试
- 文件：`deps/abacus-forge/tests/test_api.py`
- 新增测试：
  - 存在 `running_scf.log + out.log` 时，只解析 `running_scf.log`，`out.log` 仅入 diagnostics
  - 存在多个 `running_*.log`，且 `INPUT.calculation = scf` 时，优先选择 `running_scf.log`
  - 存在多个 `running_*.log`，但无匹配 `running_{calculation}.log` 时，标记 `log_selection_ambiguous`
  - 歧义场景下若有 `stdout.log` 或 `out.log`，则走 fallback，并记录 `selected_log_reason`
  - 仅存在 `stdout.log` / `out.log` 时，单日志兜底行为保持不变
- 文件：`deps/abacus-forge/tests/test_collect_abacus_reference.py`
- 新增/调整测试：
  - 保留 `running_scf.log + out.log` 的参考样例
  - 显式断言：
    - `selected_log_path` 指向 `running_scf.log`
    - `out.log` 被记录为 fallback 或 ignored，而不是参与主 metrics 解析
- 原因：
  - 这能锁定真正必要的行为，并防止回归到“全量拼接污染”的实现

### 5. 视需要补充 `result.py` 注释
- 文件：`deps/abacus-forge/src/abacus_forge/result.py`
- 变更：
  - 若实施中需要，可补充 `CollectionResult` docstring，说明日志选择与歧义信息通过 `diagnostics` 承载
  - 不新增字段
- 原因：
  - 帮助后续维护者理解“为什么没有多日志聚合结果结构”

## Implementation Notes
- 关键原则：
  - 一个 collect 结果只对应一个主日志解析来源
  - 检测到多个 `running_*.log` 时，先做“分类与选择”，而不是“排序与聚合”
  - `INPUT.calculation` 是最重要的主日志选择依据
- 文件名推断规则：
  - `running_{calculation}.log` 为精确主日志候选
  - 例如：
    - `calculation = scf` -> `running_scf.log`
    - `calculation = nscf` -> `running_nscf.log`
    - `calculation = cell-relax` -> `running_cell-relax.log`
- 歧义处理建议：
  - diagnostics 中追加可读 warning，例如：
    - `Multiple running logs detected; no unique match for calculation=scf`
    - `Falling back to stdout.log because running log selection is ambiguous`

## Verification Steps
- 单元测试：
  - `python -m pytest deps/abacus-forge/tests/test_api.py -q`
  - `python -m pytest deps/abacus-forge/tests/test_collect_abacus_reference.py -q`
  - `python -m pytest deps/abacus-forge/tests -q`
- diagnostics 检查：
  - `api.py`
  - `collectors/abacus.py`
  - 如改动 `result.py` 则一并检查
- 手动行为核对：
  - 构造同时存在 `running_scf.log` 与 `out.log` 的 workspace，确认顶层 metrics 仅来自 `running_scf.log`
  - 构造存在 `running_relax.log`、`running_scf.log`、`running_nscf.log` 的 workspace，确认不会把三者聚合；若 `INPUT.calculation=scf`，只选择 `running_scf.log`
  - 构造多个 `running_*.log` 且无唯一匹配的 workspace，确认 diagnostics 标记歧义，并按 fallback 或 `missing-output` 处理
