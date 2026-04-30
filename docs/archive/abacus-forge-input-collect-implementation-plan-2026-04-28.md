# ABACUS-Forge 输入读写编辑与 Collect 开发计划（2026-04-28）

## Summary

- 目标：围绕 `ABACUS-Forge` 当前 P1/P2 过渡阶段，具体补齐两条主链能力：
  - 输入读写编辑：将 `INPUT / STRU / KPT` 三件套补成完整、统一、可编辑的本地输入原语；
  - 结果 `collect`：在现有最小指标归一化器基础上，增强输出文件自动发现、输入回读与 `force / forces / stress / stresses / virial / virials / pressure / pressures` 解析能力。
- 设计约束：
  - 仅在 `deps/abacus-forge/` 子模块内开发；
  - 严格遵循 Forge 边界：只做本地输入生成、读取、编辑、结果解析，不引入批量平台任务壳、协议层、AiiDA 语义、前端逻辑；
  - 新功能点优先参考 `repo/abacus-test` 的已有实现与测试口径，但必须剥离厚封装与多任务调度语义。
- 成功标准：
  - Forge 对 `INPUT / STRU / KPT` 均提供一致的读取、写入和编辑原语；
  - Forge `collect()` 能稳定回收最后一步与历史集合口径的 `force/stress/virial/pressure`；
  - Collect 的关键测试优先锚定 `repo/abacus-test/tests/test_collectdata/abacus-scf/` 样例；
  - 子模块测试通过，且不破坏现有 `prepare/run/collect/export` 契约。

## Current State Analysis

### 1. 输入侧现状

- `deps/abacus-forge/src/abacus_forge/input_io.py`
  - 当前仅支持：
    - `read_input()`
    - `write_input()`
    - `write_kpt_mesh()`
    - `write_kpt_line_mode()`
  - 缺失：
    - `KPT` 读取解析；
    - `KPT` 编辑原语；
    - 与 `INPUT / STRU` 并行的统一读写/编辑接口。
- `deps/abacus-forge/src/abacus_forge/modify.py`
  - 当前已具备：
    - `modify_input()`
    - `modify_stru()`
  - 尚未覆盖：
    - `modify_kpt()`
    - `KPT` 语义化修改（mesh / shifts / line mode / segments / labels）。
- `deps/abacus-forge/src/abacus_forge/structure.py`
  - 已具备较完整的结构对象能力，并已补齐测试；
  - `to_stru()` 已修复为能正确保留 `abacus_move_flags`，可作为输入三件套中的 STRU 基线。

### 2. Collect 侧现状

- `deps/abacus-forge/src/abacus_forge/collectors/abacus.py`
  - 当前实现：
    - 正则提取 `total_energy` / `fermi_energy` / `band_gap` / `pressure` / `scf_steps`
    - `time.json` 回收
    - `band/dos/pdos` 文件摘要
    - `metrics_*.json` 附属报告读取
  - 当前缺失：
    - `force / forces`
    - `stress / stresses`
    - `virial / virials`
    - 与它们配套的最后一步 / 历史步数语义
    - 更接近 `abacustest` 的输出文件发现逻辑（如 `OUT.ABACUS/running_*.log`）。
- `deps/abacus-forge/src/abacus_forge/api.py`
  - `collect()` 已具备：
    - artifact 扫描；
    - log 路径发现；
    - `INPUT/KPT` snapshot；
    - `structure_snapshot` 和 `final_structure_snapshot`
  - 但当前 `KPT` snapshot 还是纯文本，没有解析语义；
  - collect 结果深度明显低于 `abacustest ResultAbacus`。

### 3. 来自参考实现的事实锚点

- `repo/abacus-test/abacustest/lib_collectdata/abacus/abacus.py`
  - `force`：最后一个 ION 步的 `3*natom` 扁平数组；
  - `forces`：所有 ION 步的历史数组，维度 `[nstep, 3*natom]`；
  - `stress`：最后一个 ION 步的 `9` 元扁平数组；
  - `stresses`：所有 ION 步的历史数组，维度 `[nstep, 9]`；
  - `pressure`：最后一步压力，取 `stress` 对角平均；
  - `pressures`：所有 ION 步压力历史；
  - `virial`：由 `stress * volume * KBAR2EVPERANGSTROM3` 推导出的最后一步 virial；
  - `virials`：所有 ION 步的 virial 历史。
- `repo/abacus-test/tests/test_collectdata/test_abacus_collectdata.py`
  - 已稳定验证上述变量的输出形态与数值；
  - 可直接作为 Forge collect 增强的回归锚点。
- `docs/develop/abacus-forge-submodule-review-2026-04-25.md`
  - 明确 `modify_input / modify_stru` 应进入 Forge；
  - 明确 `INPUT/KPT/STRU` 的稳定读写能力应进入 Forge；
  - 明确 `SCF/Relax 基础指标`、`力/应力/virial/pressure` 等属于应进入 Forge 的 collect 能力。

### 4. 本轮范围决策

- 用户已确认：
  - 输入侧按三件套完整收口；
  - collect 侧推进到 `force/stress/virial/pressure` 解析；
  - 优先参考 `repo/abacus-test` 的算法与样例；
  - 在 collect 变量语义上，先以 `abacustest` 实际意义为准再做设计。

## Proposed Changes

### 1. 补齐 `KPT` 的读写与编辑三件套

- 文件：
  - `deps/abacus-forge/src/abacus_forge/input_io.py`
  - `deps/abacus-forge/src/abacus_forge/modify.py`
  - `deps/abacus-forge/src/abacus_forge/__init__.py`
  - `deps/abacus-forge/tests/test_input_io.py`
  - 视组织情况新增 `deps/abacus-forge/tests/test_modify_kpt.py`，否则并入 `test_input_io.py`
- 变更内容：
  - 在 `input_io.py` 中新增 `read_kpt()`，统一解析至少两类现有写出格式：
    - mesh 模式：`K_POINTS / 0 / Gamma / mesh shifts`
    - line 模式：`K_POINTS / segments / Line / coords [#label]`
  - 返回统一结构化 payload，例如：
    - `{"mode": "mesh", "mesh": [..], "shifts": [..]}`
    - `{"mode": "line", "segments": n, "points": [{"coords": [...], "label": "..."}]}`
  - 在 `modify.py` 中新增 `modify_kpt()`：
    - 支持从 `KPT` 文件路径或结构化 KPT payload 读取；
    - 支持更新 mesh / shifts / line points / segments；
    - 支持可选写回到 `destination`。
- 为什么：
  - 这样 Forge 才真正形成 `INPUT / STRU / KPT` 三件套输入原语；
  - 与现有 `modify_input / modify_stru` 形成一致接口；
  - 只做单文件/单对象输入编辑，不触碰批量调度边界。
- 如何做：
  - 第一版只支持 Forge 现已写出的 `mesh` 与 `line` 两种模式；
  - 暂不扩展到所有 ABACUS `KPT` 变体；
  - 不引入上层 task/workflow 自动推导。

### 2. 统一输入快照语义，增强 `collect()` 的输入回读

- 文件：
  - `deps/abacus-forge/src/abacus_forge/api.py`
  - `deps/abacus-forge/src/abacus_forge/input_io.py`
  - `deps/abacus-forge/tests/test_api.py`
- 变更内容：
  - `_inputs_snapshot()` 中当前 `KPT` 仅回读纯文本，计划改为：
    - 保留原始文本；
    - 同时增加结构化解析结果（来自 `read_kpt()`）。
  - `INPUT` 回读保持现状；
  - 不对 `STRU` 做额外字段膨胀，继续依赖 `structure_snapshot`。
- 为什么：
  - 输入侧“三件套”补齐后，collect 中也应稳定看到结构化 `KPT`；
  - 这能提升主仓与下游 AiiDA 层对输入快照的复用价值。
- 如何做：
  - `inputs_snapshot["KPT"]` 可升级为包含 `raw` + `parsed` 的对象，或平滑新增 `KPT_PARSED`；
  - 为避免破坏现有调用，优先采用**向后兼容**方案：保留 `KPT` 纯文本，再新增一个解析字段。

### 3. 增强 collect 的输出文件发现与日志入口

- 文件：
  - `deps/abacus-forge/src/abacus_forge/api.py`
  - `deps/abacus-forge/src/abacus_forge/collectors/abacus.py`
  - `deps/abacus-forge/tests/test_api.py`
  - 复用 `repo/abacus-test/tests/test_collectdata/abacus-scf/` 做新增回归锚点
- 变更内容：
  - 保留当前对 `outputs/stdout.log` / `stderr.log` / `running_*.log` 的发现逻辑；
  - 明确支持 `OUT.ABACUS/running_*.log` 这类 `abacustest` 样例路径；
  - `time.json` 发现逻辑继续保留，但支持 `abacustest` 样例中的路径布局。
- 为什么：
  - 这是 collect 深化前的必要地基；
  - 也是将 `abacustest` 样例直接复用于 Forge 回归的前提。

### 4. 在 `collectors/abacus.py` 中补 `force / stress / virial / pressure` 语义

- 文件：
  - `deps/abacus-forge/src/abacus_forge/collectors/abacus.py`
  - `deps/abacus-forge/tests/test_api.py`
  - 新增 `deps/abacus-forge/tests/test_collect_abacus_reference.py` 或类似文件
- 变更内容：
  - 参考 `abacustest/lib_collectdata/abacus/abacus.py`：
    - 从日志中解析 `TOTAL-FORCE (eV/Angstrom)` 区块；
    - 输出：
      - `force`: 最后一步扁平数组 `[3*natom]`
      - `forces`: 历史数组 `[nstep, 3*natom]`
    - 从日志中解析 `TOTAL-STRESS (KBAR)` 区块；
    - 输出：
      - `stress`: 最后一步扁平数组 `[9]`
      - `stresses`: 历史数组 `[nstep, 9]`
      - `pressure`: 最后一步压力，对角平均
      - `pressures`: 历史压力数组
      - `virial`: 最后一步 virial
      - `virials`: 历史 virial 数组
  - `virial` 的换算公式与单位按 `abacustest` 口径对齐：基于 `volume` 和 `KBAR2EVPERANGSTROM3`。
- 为什么：
  - 这是当前 collect 侧与 `abacustest` 的关键差距；
  - 同时属于 review doc 已明确应进入 Forge 的结果解析能力。
- 如何做：
  - 第一版只解析**最终日志中明确可识别的标准 ABACUS 输出块**；
  - 不追求立即覆盖所有异常日志排版；
  - 解析失败时返回 `None` 或省略字段，而不是将 `collect()` 整体判失败。

### 5. 测试策略：优先复用 `abacustest` 样例

- 文件：
  - Forge 自身测试文件
  - 只读引用 `repo/abacus-test/tests/test_collectdata/abacus-scf/`
- 变更内容：
  - collect 核心回归优先基于：
    - `repo/abacus-test/tests/test_collectdata/abacus-scf/OUT.ABACUS/running_scf.log`
    - `repo/abacus-test/tests/test_collectdata/abacus-scf/time.json`
    - 同目录下必要的 `INPUT` / `OUT.ABACUS/INPUT`
  - Forge 测试中验证：
    - `force / forces`
    - `stress / stresses`
    - `virial / virials`
    - `pressure / pressures`
    - 输入回读与结构 snapshot 不被破坏
  - 输入三件套侧继续以 Forge 自造最小样例为主，因为 `KPT` 编辑原语接口是 Forge 自身设计。
- 为什么：
  - 这样可以让 collect 的数值口径直接对齐参考仓库，而不是重新发明一套测试基准。

## Assumptions & Decisions

- 决定：本轮输入侧目标是完整补齐三件套，重点新增 `KPT` 读取/编辑，而不是继续扩展 `INPUT/STRU` 大接口。
- 决定：本轮 collect 输出口径优先向 `abacustest` 靠拢。
- 决定：`force/stress/virial/pressure` 采用双层口径：
  - 单数形式 = 最后一步；
  - 复数形式 = 历史集合。
- 决定：测试优先复用 `repo/abacus-test/tests/test_collectdata/abacus-scf/` 样例。
- 决定：本轮不扩展到更深的 `atom_mag`、`drho/denergy`、DOS/PDOS 结构化大对象重做等额外 collect 能力。
- 决定：本轮不新增上层 workflow 或批量输入组合壳，只做本地输入原语与结果解析。
- 假设：Forge 当前现有测试与输入输出路径约定不会在执行前被并行修改；若发现意外改动，应先停止并重新核对。

## Verification Steps

- 输入侧验证：
  - `python -m pytest deps/abacus-forge/tests/test_input_io.py -q`
  - `python -m pytest deps/abacus-forge/tests/test_modify.py -q`
  - 验证 `read_kpt()` 对 mesh / line 模式都能返回稳定结构化结果；
  - 验证 `modify_kpt()` 可更新并写回 KPT，且不破坏现有写出格式。
- collect 侧验证：
  - 新增基于 `abacustest` 样例的 collect 测试；
  - 验证 `collect()` 可正确回收：
    - `force / forces`
    - `stress / stresses`
    - `virial / virials`
    - `pressure / pressures`
  - 验证最后一步与历史集合的语义与 `abacustest` 一致。
- 回归验证：
  - `python -m pytest deps/abacus-forge/tests/test_api.py -q`
  - `python -m pytest deps/abacus-forge/tests -q`
- 边界自检：
  - 没有引入 Bohrium / dispatcher / MCP / ATP / AiiDA / 前端逻辑；
  - 没有将输入编辑原语膨胀成批量目录生成器；
  - collect 仍保持“本地目录 -> 结构化内存结果”的职责边界。
