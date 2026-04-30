# ABACUS-Forge 诊断增强与磁矩语义补强实施计划（2026-04-29）

## Summary

- 目标：基于最新审阅结论，对 `deps/abacus-forge/` 继续推进两项开发：
  - A. `collect`/`diagnostics` 鲁棒性增强，重点补齐更可信的收敛判定与缺失信息诊断；
  - B. `STRU` 磁矩语义补强，重点支持共线磁矩下的逐原子磁矩写出/回读、`modify_stru()` 里的 AFM 交错磁设置，以及 `prepare()` 中按元素的简单磁矩设置。
- 边界约束：
  - 仅在 Forge 子模块内开发，不下沉 workflow、多步任务编排、站点策略或 AiiDA provenance 语义；
  - 本轮不做多日志顺序解析，不实现 `Relax -> Band -> DOS` 链式日志拼装；
  - 本轮磁矩范围限定为**共线磁矩**，不引入非共线 `angle1/angle2` 或三分量磁矩向量接口。
- 参考基线：
  - `repo/abacus-test/abacustest/lib_prepare/stru.py`：确认 ABACUS STRU 原生支持 species 级 `magmom` 与原子行 `mag` 覆盖；
  - `repo/ADAM-ABACUS/abacus_input.py` 与 `repo/ADAM-ABACUS/abacus_editor.py`：确认 `site_magmoms` 与逐原子补丁写入的工程口径；
  - `repo/ABACUS-agent-tools/src/abacusagent/modules/abacus.py` 与 `tests/test_abacus.py`：确认“按原子初始磁矩编辑”与 AFM 初猜属于上游已有稳定需求。

## Current State Analysis

### 1. diagnostics / collect 当前状态

- `deps/abacus-forge/src/abacus_forge/collectors/abacus.py`
  - 当前 `_regex_metrics()` 仅基于全文关键词判断收敛：
    - 正向：`"converged"`、`"charge density convergence is achieved"`
    - 负向：`"not converged"`
  - 该实现简单可用，但仍可能对非目标上下文中的 `converged` 文本过度宽松。
  - `collect_abacus_metrics()` 已产出 `diagnostics["log_sources"]` 与 `diagnostics["structure_volume"]`，但对以下情况没有明确标记：
    - `time.json` 缺失；
    - 报告 JSON 缺失；
    - 未从日志中匹配到任何正向收敛信号；
    - 解析过程中触发的“弱失败/跳过”。
- `deps/abacus-forge/src/abacus_forge/api.py`
  - `_log_paths()` 当前优先收集 `stdout.log` / `stderr.log`，并在 artifact 中附加所有 `running_*.log`，若无则回退到 `out.log`；
  - 当前逻辑仍偏向“最小发现”，不承担多步骤任务链的顺序合并职责；
  - 但 `collect()` 的调用方目前仍缺少更细粒度的“本次实际使用了哪些日志源”的可观测信息。

### 2. STRU 磁矩语义当前状态

- `deps/abacus-forge/src/abacus_forge/structure.py`
  - `to_stru()` 当前对每个 species 仅写一行 type-level 磁矩：
    - `lines.append(f"{float(np.mean([magmoms[idx] for idx in idxs])):.8f}" if idxs else "0.0")`
  - 这意味着同一元素下若存在不一致的逐原子磁矩，Forge 会静默平均，信息被丢失。
  - `_read_stru()` 当前只读取 species 级磁矩行，并将其复制给该 species 的全部原子；不会解析原子坐标行中的 `mag`/`magmom` 覆盖。
- `deps/abacus-forge/src/abacus_forge/modify.py`
  - `modify_stru()` 当前支持 `magmoms`，但其语义只是把一组标量磁矩塞回 `ASE Atoms.initial_magmoms`；
  - 尚无：
    - AFM 交错磁设置；
    - 逐原子磁矩优先级控制；
    - 按元素默认磁矩与逐原子覆盖的组合策略。
- `deps/abacus-forge/src/abacus_forge/api.py`
  - `prepare()` 当前不提供任何磁矩入口，只能依赖用户传入一个已带 `initial_magmoms` 的结构对象。

### 3. 参考实现事实锚点

- `repo/abacus-test/abacustest/lib_prepare/stru.py`
  - STRU 写出同时支持：
    - species 级 `magmom_global`
    - atom 级 `magmom`，最终在原子行以 `mag ...` 写入；
  - 说明 Forge 采用“species 行 + 原子行覆盖”的写出模式与 ABACUS 语义相容。
- `repo/ADAM-ABACUS/abacus_input.py`
  - `_patch_stru_magmoms()` 对 `site_magmoms` 的处理是：优先按 1-based 原子索引覆盖，必要时回退到元素顺序补丁；
  - 该实现说明“写后补丁原子行 `mag`”是现实可行且稳定的技术路线。
- `repo/ABACUS-agent-tools/tests/test_abacus.py`
  - 已存在按原子编辑 `initial_magmoms` 的测试，覆盖共线和非共线两类场景；
  - 本轮 Forge 只吸收其中的**共线按原子编辑**能力，不扩展到非共线向量与角度。

## Proposed Changes

### 1. 收紧 `converged` 判定并补齐 collect 诊断信息

- 文件：
  - `deps/abacus-forge/src/abacus_forge/collectors/abacus.py`
  - `deps/abacus-forge/src/abacus_forge/api.py`
  - `deps/abacus-forge/tests/test_api.py`
  - 视测试组织情况新增 `deps/abacus-forge/tests/test_collect_diagnostics.py`，否则并入 `test_api.py`
- 变更内容：
  - 将 `_regex_metrics()` 的收敛逻辑从“全文泛搜关键词”收紧为“明确正向模式 + 明确负向模式”：
    - 正向最小集合：
      - `SCF CONVERGED`
      - `charge density convergence is achieved`
      - 保留大小写不敏感；
    - 负向集合：
      - `not converged`
      - `SCF NOT CONVERGED`
      - 其他已知直接否定表达；
    - 保持最小收紧，不进入完整段落解析。
  - 为 `collect_abacus_metrics()` 增加更明确的 diagnostics：
    - `matched_converged_markers`
    - `matched_nonconverged_markers`
    - `time_json_absent`
    - `report_json_absent`
    - `warnings`（轻量字符串列表，用于记录跳过或缺失情况）
  - 在 `api.collect()` / `_log_paths()` 路径上增加日志源诊断字段，例如：
    - `diagnostics["log_paths"]`
    - `diagnostics["stderr_nonempty"]`
- 为什么：
  - 这能直接提升 `collect()` 结果的可信度与调试可观测性；
  - 属于审阅结论中的高收益低风险补强，不改变 Forge 职责边界。
- 如何做：
  - 诊断字段采用“增量新增、向后兼容”策略，不替换现有字段；
  - 若未匹配到收敛或失败关键词，不抛异常，只通过 `status` 与 `diagnostics` 反映。

### 2. 在 `structure.py` 中补齐逐原子共线磁矩的写出与回读

- 文件：
  - `deps/abacus-forge/src/abacus_forge/structure.py`
  - `deps/abacus-forge/tests/test_structure.py`
- 变更内容：
  - `to_stru()` 调整为以下规则：
    - 若某 species 下所有原子磁矩相同，则继续沿用 species 级磁矩行，且原子行不额外写 `mag`；
    - 若某 species 下存在不同的逐原子共线磁矩，则：
      - species 级磁矩行写保守基线值 `0.0`；
      - 该 species 的每个原子行都显式写 `mag <value>`，避免静默平均；
    - 继续保留 `m` 运动约束写法；
    - 本轮只支持标量 `mag`，不写三分量 `mag x y z`，不写 `angle1/angle2`。
  - `_read_stru()` 补齐对原子行 `mag`/`magmom` token 的解析：
    - 若原子行存在标量 `mag`，则该值覆盖 species 级磁矩；
    - 若不存在，回退到 species 级磁矩；
    - 若遇到三分量 `mag` 或 angle token，本轮可选择：
      - 明确忽略并保留 species 值，或
      - 抛出清晰错误；
    - 计划采用前者只读兼容、后者写接口不支持的方案，以避免非共线历史文件直接读崩。
- 为什么：
  - 这是 Forge 支持“逐原子编辑磁矩”的基础；
  - 同时修复当前 species 平均导致的信息丢失问题。
- 如何做：
  - 以 ABACUS 原生 STRU 语义为准；
  - 回读/写出都只做共线标量闭环，不扩展到非共线。

### 3. 扩展 `modify_stru()`：支持 AFM 交错与逐原子磁矩优先级

- 文件：
  - `deps/abacus-forge/src/abacus_forge/modify.py`
  - `deps/abacus-forge/src/abacus_forge/__init__.py`
  - `deps/abacus-forge/tests/test_modify.py`
- 变更内容：
  - 在 `modify_stru()` 中补充共线磁矩编辑参数，保持它作为主入口：
    - 保留现有 `magmoms`：表示逐原子标量磁矩列表，长度必须等于 `natom`；
    - 新增 `magmom_by_element: dict[str, float] | None = None`：按元素设置默认磁矩；
    - 新增 `afm: bool = False`；
    - 新增 `afm_elements: Iterable[str] | None = None`：限定哪些元素参与 AFM 交错，未提供时默认作用于 `magmom_by_element` 中磁矩非零的元素。
  - 明确磁矩优先级：
    - `magmoms`（逐原子）最高；
    - `afm` 在 `magmom_by_element` 生成的 species 默认值基础上施加交错符号；
    - 未命中的原子保留现有 `initial_magmoms` 或回退为 `0.0`。
  - AFM 交错规则（本轮固定为最小实现）：
    - 按 species 内原子出现顺序交替赋值 `+m, -m, +m, -m, ...`；
    - 不尝试根据空间邻接、子晶格识别或反铁磁拓扑自动分组。
  - `destination` 写回继续通过 `to_stru()`，从而自然落到 species 行 + 原子行 `mag` 覆盖模式。
- 为什么：
  - 这与用户确认的“主要放在 `modify_stru`”完全一致；
  - 同时吸收了 `ABACUS-agent-tools` / `ADAM-ABACUS` 中已经证明有价值的 AFM 与 site-level 编辑场景。
- 如何做：
  - 将磁矩组合逻辑封装为私有 helper，避免 `modify_stru()` 主体膨胀；
  - 对非法输入给出明确错误：
    - `magmoms` 长度错误；
    - `magmom_by_element` 含非数值；
    - `afm=True` 但没有可作用的元素时，可给出 warning 或直接无操作，优先选择无操作并在测试中锁定。

### 4. 为 `prepare()` 增加“按元素简单磁矩设置”入口

- 文件：
  - `deps/abacus-forge/src/abacus_forge/api.py`
  - `deps/abacus-forge/tests/test_api.py`
  - 若 CLI 同步暴露，则改 `deps/abacus-forge/src/abacus_forge/cli.py` 与 `tests/test_cli.py`
- 变更内容：
  - 在 `prepare()` 增加一个**简单、收敛的**按元素磁矩入口：
    - `magmom_by_element: dict[str, float] | None = None`
  - 该入口只做均匀 species 级初始化：
    - 对结构中命中的元素设置对应初始磁矩；
    - 不做 AFM；
    - 不做逐原子覆盖；
    - 生成的 STRU 应由 `to_stru()` 写为 species 级磁矩行。
  - 若本轮时间允许，可同步给 CLI `prepare` 增加重复参数入口；若范围控制更紧，则只在 Python API 暴露。
- 为什么：
  - 用户已明确：`prepare` 只需要“简单的按元素种类的磁矩设置”；
  - 这样既能满足主线轻量输入准备，也不把高级磁矩编辑全部下沉到 `prepare`。
- 如何做：
  - 在 `prepare()` 内、`structure_payload.to_stru()` 之前对 `Atoms` 设置 `initial_magmoms`；
  - 若结构来自文件且未显式要求磁矩，则保持现状不改写。

### 5. 测试与验收方案

- 文件：
  - `deps/abacus-forge/tests/test_structure.py`
  - `deps/abacus-forge/tests/test_modify.py`
  - `deps/abacus-forge/tests/test_api.py`
  - 可选新增 `deps/abacus-forge/tests/test_collect_diagnostics.py`
- 变更内容：
  - `test_structure.py`
    - 新增 heterogeneous species 磁矩 roundtrip：
      - 同一元素多个原子磁矩不同；
      - 写出 STRU 后应出现原子行 `mag`；
      - 读回后 `initial_magmoms` 保持逐原子值。
    - 新增 homogeneous species 磁矩 roundtrip：
      - 仅写 species 级磁矩，不额外写 atom-level `mag`。
  - `test_modify.py`
    - 新增 `modify_stru(..., magmom_by_element=...)` 的 species 默认设置测试；
    - 新增 `afm=True` 的交错磁测试；
    - 新增“逐原子 `magmoms` 覆盖 AFM/element 默认值”的优先级测试。
  - `test_api.py`
    - 新增 `prepare(..., magmom_by_element={"Fe": 3.0})` 的输出验证；
    - 新增 collect diagnostics 覆盖：
      - 有 `time.json`；
      - 无 `time.json`；
      - 有明确 SCF CONVERGED；
      - 有明确 non-converged 文本。
- 为什么：
  - 新增能力跨越了结构读写、编辑和 collect 判定三层，必须用针对性测试锁定行为；
  - 这些测试都可在 Forge 子模块内自足完成，不需要引入上层环境依赖。

## Assumptions & Decisions

- 决定：本轮开发范围固定为 `A+B`，不纳入多日志顺序解析 `C`。
- 决定：收敛判定只做“最小收紧”，不引入完整 SCF/ION 段落状态机。
- 决定：Forge 的高级磁矩入口放在 `modify_stru()`，而 `prepare()` 只补“按元素简单设置”。
- 决定：本轮磁矩范围只覆盖**共线标量磁矩**。
- 决定：AFM 的实现口径为“按 species 内原子出现顺序做正负交替”，不做空间拓扑推断。
- 决定：当某 species 下存在异构逐原子磁矩时，`to_stru()` 不再平均，而是采用：
  - species 行 `0.0`
  - atom 行逐个写 `mag`
- 决定：`_read_stru()` 读取 atom-level `mag` 标量覆盖，但不把非共线三分量/角度纳入本轮正式支持。
- 决定：功能设计与测试必须显式参考以下已有实现，但不整体搬运厚封装：
  - `repo/abacus-test/abacustest/lib_prepare/stru.py`
  - `repo/ADAM-ABACUS/abacus_input.py`
  - `repo/ADAM-ABACUS/abacus_editor.py`
  - `repo/ABACUS-agent-tools/src/abacusagent/modules/abacus.py`
  - `repo/ABACUS-agent-tools/tests/test_abacus.py`

## Verification Steps

- 单测分层验证：
  - `python -m pytest deps/abacus-forge/tests/test_structure.py -q`
  - `python -m pytest deps/abacus-forge/tests/test_modify.py -q`
  - `python -m pytest deps/abacus-forge/tests/test_api.py -q`
- 全量回归：
  - `python -m pytest deps/abacus-forge/tests -q`
- 语义验收：
  - heterogeneous species 磁矩写出后，STRU 原子行出现 `mag`，读回不丢失；
  - `modify_stru(afm=True, magmom_by_element=...)` 能产出交错正负磁矩；
  - `prepare(magmom_by_element=...)` 仅生成简单按元素初始磁矩，不携带 AFM 或 site-level 编辑；
  - `collect()` 在 `time.json` 缺失、收敛关键词缺失、stderr 非空等场景下，`diagnostics` 有明确标记。
- 边界自检：
  - 不引入 AiiDA、Slurm、站点资源参数；
  - 不新增多步工作流编排；
  - 不将 Forge 返回结构扩展为上层 provenance/case 语义对象。
