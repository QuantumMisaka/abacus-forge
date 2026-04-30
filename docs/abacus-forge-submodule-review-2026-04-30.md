# ABACUS-Forge 子模块专项评审报告

> 日期：2026-04-30
> 审查范围：`deps/abacus-forge/` 全量源码、CLI、测试与项目元数据
> 审查依据：`.trae/documents/abacus-forge-review.md` 审查框架、`docs/architecture.md`、`docs/packages.md`、`AGENTS.md`（PAIMON 主）、`docs/contracts.md`

---

## 1. 项目定位与审查问题

### 1.1 Forge 在 PAIMON 主链中的职责

Forge 是 PAIMON 架构主链的最底层执行核心：

```
AI/Planner → 协议层(ATP/MCP/CLI/Skill) → AiiDA Workflow → ABACUS-Forge → ABACUS
```

依据：`AGENTS.md`（PAIMON 主）第 16 行、`docs/architecture.md`、`.trae/documents/abacus-forge-review.md` 第 8 行。

Forge 的设计定位是"轻量级 ABACUS 执行基座"，提供 `prepare → modify → run → collect → export` 的标准化能力，可作为 Python 库或 CLI 使用。

### 1.2 本次评审的两个核心角色目标

Forge 被期望同时承担两个角色：

| 角色 | 描述 | 期望成熟度 |
|------|------|-----------|
| AiiDA 计算单元库 | `aiida-abacus` / PAIMON 可复用的 ABACUS 计算功能单元库 | 上层可直接依赖 Forge 的清晰原语 |
| 科研用户本地 CLI | 服务器上科研用户可直接调用的本地/CLI ABACUS 计算单元 | 科研用户可直接完成 scf/relax/band/dos 单任务闭环 |

依据：`.trae/documents/abacus-forge-review.md` 第 15-20 行、`docs/abacus-forge-review.md` 第 19-21 行。

### 1.3 对 SCF / Relax / Band / DOS 的最低验收口径

| 任务类型 | 已闭合 | 部分实现 | 未开始 |
|---------|--------|---------|--------|
| SCF | collect 基础指标采集 | prepare/task CLI 专用输入生成 | 面向用户的一键闭环 |
| Relax | collect force/stress/virial | final_structure 产物关联 | relax 轨迹摘要、收敛历史 |
| Band | collect band_summary | KPT line-mode prepare | band 结构图生成 |
| DOS | collect dos_summary/pdos_summary | — | 面向用户的 DOS 图谱闭环 |

---

## 2. 实现现状

### 2.1 当前 Forge 的实际能力面

#### 核心数据模型
- **Workspace**（`workspace.py`）：单运行目录的 on-disk layout，包含 `inputs/`、`outputs/`、`reports/` 三目录和 `meta.json` 记录
- **LocalRunner**（`runner.py`）：本地进程执行基元，支持 MPI ranks 和 OMP threads，输出 stdout/stderr 到 workspace outputs 目录
- **RunResult / CollectionResult**（`result.py`）：结构化返回类型，包含 metrics、artifacts、diagnostics

#### prepare 原语
- `prepare(...)`（`api.py:23-110`）：从结构文件生成 `INPUT/KPT/STRU`，支持参数覆盖、删除、K 点设置、PP/ORB 路径、`copy/link` 资产模式、按元素共线磁矩初始化
- 支持结构格式：STRU、POSCAR、CIF、ASE Atoms、Pymatgen Structure、Mapping（cell+sites）
- 支持结构标准化：conventional/primitive 转换、layer/string 轴交换、3D PBC 强制
- `build_task_parameters`（`prepare_profiles.py`）：task-aware 参数构建（目前仅 scf 默认参数）

#### modify 原语
- `modify_input(...)`（`modify.py:17-33`）：对 INPUT 文件做轻量编辑，set/update/remove 参数
- `modify_stru(...)`（`modify.py:36-88`）：结构编辑，支持位移、轴交换、超胞、磁矩、AFM、move_flags
- `modify_kpt(...)`（`modify.py:91-123`）：KPT 文件编辑，支持 mesh 和 line 两种模式

#### run 原语
- `run(...)`（`api.py:113-117`）：通过 LocalRunner 执行本地 ABACUS 进程
- `LocalRunner.run()`（`runner.py:50-91`）：subprocess 调用，默认 abacus 可执行文件，支持 MPI/OMP 参数

#### collect/export 原语
- `collect(...)`（`api.py:125-184`）：解析 metrics、structures、artifacts from workspace
  - 日志自动发现：`running_{calculation}.log` 优先匹配，fallback 到 stdout.log/out.log，基于 ABACUS banner 的内容发现
  - 显式 output_log 支持：`--output-log` 参数或 `output_log=` 参数
  - `collect_abacus_metrics()`（`collectors/abacus.py:53-140`）：正则提取基础指标 + band/dos/pdos 摘要 + force/stress/virial + 时间指标
- `export(...)`（`api.py:187-194`）：JSON 序列化与落盘

#### CLI 子命令
`cli.py` 提供 7 个子命令：`prepare`、`modify-input`、`modify-stru`、`modify-kpt`、`run`、`collect`、`export`

### 2.2 当前新增改动实际补了什么

本次审查周期的主要新增是 `collect` 对 Band/DOS/PDOS 的摘要采集能力：

**Band**（`collectors/abacus.py:104-110`）：
```python
band_files = _artifact_paths_matching(artifacts, "BANDS_", ".dat")
if band_files:
    metrics["band_summary"] = BandData.from_paths(band_files).summary()
    metrics["band_artifacts"] = [str(path) for path in band_files]
```
- `BandData.summary()`（`band_data.py:39-47`）：返回 `num_points`、`num_bands`、`num_columns` 等计数信息
- **注意**：仅返回文件路径和计数，**不包含**能带色散数据或 VBM/CBM/Fermi level 对齐

**DOS**（`collectors/abacus.py:112-118`）：
```python
dos_files = _artifact_paths_matching(artifacts, "DOS", "_smearing.dat")
if dos_files:
    metrics["dos_summary"] = DOSData.from_paths(dos_files).summary()
    metrics["dos_artifacts"] = [str(path) for path in dos_files]
```
- `DOSData.summary()`（`dos_data.py:40-47`）：返回 `points`、`energy_min`、`energy_max`
- **注意**：仅返回能量范围和点数，**不包含**积分面积或费米能级处 DOS 值

**PDOS**（`collectors/abacus.py:120-127`）：
```python
metrics["pdos_summary"] = PDOSData(pdos_path=pdos_file, tdos_path=tdos_file).summary()
metrics["pdos_artifacts"] = [...]
```
- `PDOSData.summary()`（`dos_data.py:55-59`）：仅返回文件路径，**不包含**投影分析结果

**Relax 产物**（`collectors/abacus.py:129-131`）：
- 支持读取 `metrics_relax.json` 报告文件，但未实现 ABACUS 原生 relax 轨迹解析

### 2.3 当前测试覆盖了什么、没有覆盖什么

运行 `pytest deps/abacus-forge/tests -q`：**53 passed in 0.95s**

测试覆盖了：
- INPUT/KPT/STRU 三件套的读写
- `prepare/run/collect/export` 核心 API 路径
- `modify_input/modify_stru/modify-kpt` CLI 路径
- 结构转换（cif/stru/poscar）
- BandData/DOSData/PDOSData 数据类

测试缺失：
- **无 task-oriented golden workspace 测试**：所有测试均为单元级 mock 文本提取，未用真实 ABACUS 输出建立 golden 标准
- **无 relax 轨迹摘要测试**：`metrics_relax.json` 解析路径未被测试覆盖
- **无 output_log 自动发现完整路径测试**：仅少量覆盖
- **无 ABACUS 失败模式测试**：stderr 非空判断逻辑无独立测试保护

---

## 3. 与 abacus-test 的功能点对比

### 3.1 功能对照矩阵

| 能力域 | Forge 当前 | abacus-test 当前 | 差距性质 |
|--------|-----------|-----------------|---------|
| **输入准备：结构格式** | STRU/POSCAR/CIF/ASE Atoms/Pymatgen | STRU/POSCAR/CIF + 完整元素周期表 PP 自动匹配 | **当前缺口**：Forge 缺少自动 PP 路径解析和组织 |
| **输入准备：参数模板** | `build_task_parameters` 极简 scf 默认参数 | `lib_prepare/abacus.py` 完整 task-aware 参数模板（scf/relax/band/dos/md/phonon） | **当前缺口**：Forge 的 task profile 仅覆盖 scf |
| **输入准备：PP/ORB 组织** | `collect_assets`/`stage_assets` 仅支持 copy/link，无元素匹配策略 | `PrepareAbacus` 完整 PP/ORB 路径推断 + 文件名到元素映射 | **当前缺口**：Forge 需要调用方自行管理 PP/ORB 布局 |
| **执行：单任务运行** | `LocalRunner` 本地 subprocess，无 runner 抽象层 | `PrepBand.run_abacus()`、`run_command()` 完整执行封装 | **有意收缩**：Forge 不承担 HPC runner 抽象 |
| **执行：MPI/OMP** | 仅 `mpirun -np` 硬编码，`OMP_NUM_THREADS` 环境变量 | `run_command()` 支持 launcher 自定义、batch 脚本生成 | **有意收缩**：Forge 不承担站点 batch 脚本策略 |
| **结果：基础指标** | 正则提取 total_energy/fermi_energy/band_gap/pressure + force/stress/virial | `ResultAbacus` 正则 + 结构化解析双轨 | **当前缺口**：Forge 的正则脆弱，对非标准输出格式无降级 |
| **结果：Band/DOS/PDOS** | `BandData`/`DOSData`/`PDOSData` 仅计数和范围，**无色散/积分数据** | `model_012_band.py`/`model_021_dos_pdos.py` 完整色散读取 + Fermi 对齐 | **当前缺口**：Forge 的 band_summary/dos_summary 是元数据级，不是分析级 |
| **工作流编排** | **无**：Forge 明文禁止工作流编排 | `submit/poll/download/report` 完整批量工作流 | **有意收缩**：此能力不在 Forge 边界内 |
| **CLI 面** | 7 个原语级子命令，无 task 闭环 | `main.py` 的 `band`/`dos`/`relax` 等 task CLI 完整闭环 | **当前缺口**：Forge CLI 是基元，不是工具链 |

### 3.2 abacus-test 源码关键对照

以下对照基于仓库内 `repo/abacus-test/` 可直接读取的源码（依据审查计划第 70-88 行的对照矩阵）：

**Forge `api.py::prepare` vs `abacustest/lib_prepare/abacus.py`**：
- Forge：单结构 → 单 workspace，`build_task_parameters` 仅提供 `ecutwfc` 等极少数默认参数
- abacustest：`PrepareAbacus.gen_stru()` 包含完整 STRU 写入 + `AbacusStru` 元素特定 PP 选择策略
- **差距**：Forge 的 `prepare` 是"最简输入准备"，abacustest 的 prepare 是"完整工程化输入准备"

**Forge `collectors/abacus.py` vs `abacustest/lib_collectdata/resultAbacus.py`**：
- Forge：正则 + 固定后缀文件发现，`band_summary`/`dos_summary` 仅计数
- abacustest：`ResultAbacus` 有更完整的指标解析，包括 `ethr`、`nelec`、`basis_threshold` 等 ABACUS 特有指标

**Forge `LocalRunner` vs `abacustest/lib_model/comm.py::run_command()`**：
- Forge：`subprocess.run` 单一封装，无错误分类、无重试、无作业状态建模
- abacustest：`run_command` 返回结构化 `RunResult`，包含 stdout/stderr/returncode 的更细粒度处理

---

## 4. 实现模式对比

### 4.1 Forge：单工作区原语、极薄依赖、无平台编排

Forge 的实现哲学：
- **单一职责**：每个原语（`prepare`/`modify_*`/`run`/`collect`/`export`）只做一件事
- **无状态**：workspace 是纯数据容器，无执行状态建模
- **无平台感知**：LocalRunner 不处理 Slurm/PBS/QOS，仅转发本地命令
- **零协议耦合**：无 AiiDA/ATP/MCP/前端语义

源码证据：
- `workspace.py:11-54`：纯数据类，无执行状态
- `runner.py:50-91`：subprocess.run 直连，无 runner 抽象接口
- `api.py:23-110`：`prepare` 函数内部不引用任何外部平台服务

### 4.2 abacustest：prepare/submit/collect/report/model/workflow 全栈工程化工具链

abacustest 的实现哲学：
- **多层级抽象**：prepare（输入工程化）→ model（执行脚本生成）→ collectdata（结果结构化）→ report（可视化）
- **平台感知**：submit 支持 Slurm/交互式多种模式
- **错误建模**：失败模式分类、重试策略
- **批量工作流**：dflow 风格的 DAG 编排

**有意收缩 vs 当前缺口汇总**：

| 差异项 | 性质 | 说明 |
|--------|------|------|
| 无 task profile 模板 | **当前缺口** | `build_task_parameters` 仅 scf 有默认值 |
| 无自动 PP 路径解析 | **当前缺口** | 调用方需自行管理 PP/ORB 布局 |
| 无 HPC runner 抽象 | **有意收缩** | 边界明确：不处理 Slurm/QOS |
| 无 band/DOS 分析级摘要 | **当前缺口** | 仅元数据级计数，无 Fermi 对齐 |
| 无 relax 轨迹解析 | **当前缺口** | `metrics_relax.json` 读取未测试 |
| 无 CLI task 闭环 | **当前缺口** | 用户需自行组合原语 |
| 无工作流编排 | **有意收缩** | 边界明确：不承担多步编排 |
| 无 AiiDA/ATP 语义 | **有意收缩** | 边界明确：不吸上层语义 |

---

## 5. 按 PAIMON 主线的合规性评估

### 5.1 符合"基元化、轻量化、不吸上层语义"的方面

✅ **边界约束得到遵守**：
- `AGENTS.md` 第 23-29 行的禁止项在 Forge 源码中均无违反：
  - 无 Bohrium/DPDispatcher 依赖（`pyproject.toml` 仅有标准库 + ase + numpy）
  - 无 MCP/ATP 协议逻辑
  - 无 AiiDA Group/Node UUID
  - 无前端状态管理
- `docs/packages.md` 第 7 行定义的 Forge 职责边界（输入归一化、工作目录准备、提交/本地运行、结果收集与导出）在源码中有对应实现

✅ **核心契约 I/O 清晰**：
- `prepare`（`api.py:23-110`）的输入输出契约明确
- `collect`（`api.py:125-184`）返回 `CollectionResult` dataclass，字段稳定
- `export`（`api.py:187-194`）仅 JSON 序列化，不承担展示或平台交付

✅ **主仓集成薄入口**：
- `src/paimon/forge_adapter.py` 作为主仓唯一 Forge 调用入口，未私补大量 Forge 语义
- Forge 被 `aiida_sai.py` 用作结果物料化层（非 workflow 编排层）

### 5.2 尚不足以支撑既定双角色目标的方面

⚠️ **作为 AiiDA 计算单元库**：
- `band_summary`/`dos_summary` 仅返回计数和范围，无法支撑上层做 Fermi 能级对齐或带隙判断
- `collect_abacus_metrics` 的正则提取无降级策略，当 ABACUS 输出格式变化时整体失效
- 无 ABACUS 特有指标（如 `ethr`、`nelec`、`basis_threshold`）的采集

⚠️ **作为科研用户本地 CLI**：
- 用户需自行理解 `prepare → modify-* → run → collect → export` 的原语组合方式
- 无面向 task 的闭环 CLI（如 `abacus-forge scf ...` / `abacus-forge relax ...`）
- 磁矩初始化支持已实现（`magmom_by_element` 参数），但 STRU 文件中元素特定 PP 文件名需要用户自行管理

---

## 6. 双角色评估结论

### 6.1 作为 AiiDA 计算单元库

| 能力域 | 完成度 | 理由 |
|--------|--------|------|
| 输入准备（通用结构） | ★★★☆☆ | 已支持 STRU/POSCAR/CIF，但缺 task-specific 参数模板和自动 PP 匹配 |
| 输入准备（磁矩/AFM） | ★★★★☆ | `magmom_by_element`、`afm` 参数已完整实现 |
| 执行（本地） | ★★★☆☆ | LocalRunner 可用，但无 runner 抽象接口，无错误分类 |
| 结果采集（基础指标） | ★★★☆☆ | 正则提取脆弱，无降级，缺 ABACUS 特有指标 |
| 结果采集（Band） | ★★☆☆☆ | 仅计数，无色散数据，无法支撑上层 Fermi 对齐 |
| 结果采集（DOS/PDOS） | ★★☆☆☆ | 仅能量范围，无积分分析 |
| 结果采集（Relax） | ★★☆☆☆ | 支持 force/stress/virial，但 final_structure 关联弱，无轨迹摘要 |

### 6.2 作为科研用户本地 CLI

| 能力域 | 完成度 | 理由 |
|--------|--------|------|
| SCF 任务闭环 | ★★☆☆☆ | 需手动组合 `prepare → run → collect`，无一键闭环 |
| Relax 任务闭环 | ★☆☆☆☆ | 同上，且 final_structure 关联不足 |
| Band 任务闭环 | ★☆☆☆☆ | 需手动处理 line-mode KPT 生成 |
| DOS 任务闭环 | ★☆☆☆☆ | 需手动处理 smearing 参数 |
| CLI 可发现性 | ★★★★☆ | `--help` 覆盖完整，与 README 一致性良好 |
| 错误信息友好度 | ★★★☆☆ | diagnostics 有 log_selection 信息，但无修复建议 |

### 6.3 SCF / Relax / Band / DOS 完成度分级

| 任务 | prepare | run | collect | CLI task 闭环 |
|------|---------|-----|---------|---------------|
| **SCF** | 已闭合 | 已闭合 | 已闭合 | **未开始** |
| **Relax** | 已闭合 | 已闭合 | **部分实现**（缺 final_structure 关联、轨迹摘要） | **未开始** |
| **Band** | **部分实现**（仅 line-mode KPT 生成） | 已闭合 | **部分实现**（仅计数，无色散） | **未开始** |
| **DOS** | **部分实现**（仅 kmesh 生成） | 已闭合 | **部分实现**（仅能量范围） | **未开始** |

---

## 7. 风险点与后续开发路线

### P0（必须进入 Forge，当前明显不足）

#### P0.1 补齐 Band/DOS 分析级摘要采集
- **问题**：`band_summary`/`dos_summary` 仅计数和范围，无法支撑上层 Fermi 能级对齐、带隙判断、DOS 积分等分析需求
- **证据**：`collectors/abacus.py:104-127` 仅调用 `BandData.summary()`/`DOSData.summary()` 返回元数据
- **建议**：在 `collectors/abacus.py` 中新增 Fermi 能级对齐后的 band 数据提取（如读取 `band_gap` 指标并与 Fermi 能级组合），或在 `BandData`/`DOSData` 类中增加 `with_fermi_level()` 方法
- **应进入 Forge**：是，这是 Forge collect 能力的核心缺口

#### P0.2 增强 collect 正则提取的鲁棒性
- **问题**：当前正则（如 `TOTAL\s+ENERGY\s*=\s*([-+]?\d+(?:\.\d+)?)`）对 ABACUS 输出格式变化无降级策略
- **证据**：`collectors/abacus.py:18-24` 的 `_METRIC_PATTERNS` 硬编码 5 个正则
- **建议**：增加多模式正则匹配 + 解析失败时的 warning/diagnostic 报告
- **应进入 Forge**：是，提升基元库的可靠性

#### P0.3 Relax final_structure 关联增强
- **问题**：`final_structure_snapshot` 仅尝试固定后缀列表（`STRU_ION_D/STru_NOW.cif/STru.cif/STru`），无 ABACUS 输出中的结构追踪
- **证据**：`api.py:461-483` 的 `_final_structure_snapshot`
- **建议**：当 `calculation=relax` 时，自动从 ABACUS 输出中发现最终结构文件路径
- **应进入 Forge**：是，这是 relax collect 能力的核心缺口

### P1（把 Forge 做成科研用户可直接使用的轻量 CLI）

#### P1.1 增加 task CLI 闭环
- **问题**：当前 CLI 均为原语级，用户需手动组合才能完成单任务闭环
- **建议**：新增 `abacus-forge scf`、`abacus-forge relax`、`abacus-forge band`、`abacus-forge dos` 四个 task CLI，复用现有 `prepare/run/collect/export` 原语
- **应进入 Forge**：是，这是科研用户 CLI 角色的核心需求
- **不进入**：厚工作流、平台提交、远程追踪、HTML 报告

#### P1.2 补齐 Relax 收敛轨迹摘要
- **问题**：relax 过程的中原胞变化历史无法从当前 collect 能力中获取
- **建议**：在 `collectors/abacus.py` 中新增 `relax_convergence_trajectory` 指标，读取 ABACUS 输出中的结构优化历史
- **应进入 Forge**：是，relax collect 能力的自然延伸

#### P1.3 补齐 task-aware 参数模板
- **问题**：`build_task_parameters`（`prepare_profiles.py`）仅有 scf 默认参数，无 relax/band/dos 的专用参数集
- **建议**：在 `prepare_profiles.py` 中为 relax/band/dos 分别建立参数模板
- **应进入 Forge**：是，这是 prepare 能力闭合 relax/band/dos 的前提

### P2（把 Forge 做成更稳的 AiiDA 计算基元库）

#### P2.1 明确 Python API 的稳定入口
- **问题**：当前 API 无版本承诺，上层依赖存在脆弱性
- **建议**：在 `api.py` 中显式标注 stable/internals，明确哪些是 stable API
- **应进入 Forge**：是

#### P2.2 ABACUS 特有指标补齐
- **问题**：缺少 `ethr`、`nelec`、`basis_threshold`、`latname` 等 ABACUS 特有指标的采集
- **建议**：在 `_METRIC_PATTERNS` 中新增这些指标的正则
- **应进入 Forge**：是

#### P2.3 runner 抽象层（不涉及 Slurm/QOS）
- **问题**：`LocalRunner` 无接口抽象，上层定制执行策略困难
- **建议**：定义 `Runner` 抽象接口（`run(workspace) -> RunResult`），但不实现 Slurm/QOS 等站点策略
- **应进入 Forge**：是（轻量 runner 接口），否（站点策略）

### 明确不应进入 Forge 的方向

以下方向已在 `docs/packages.md` 第 130-137 行和审查计划第 128-137 行明确排除：

- ❌ `abacustest` 的 `submit/status/download/report/model/remote/dflow` 全栈能力迁入
- ❌ `Relax → Band → DOS` 多步物理流程编排下沉
- ❌ SAI/Slurm 的 `partition/qos/nodes/gpus-per-node` 等站点策略
- ❌ PAIMON 的 `RunResult/Group/provenance/case/archive/tutorial` 语义
- ❌ ATP/MCP/前端消费字段放入 Forge 返回结构

---

## 附录：证据索引

### Forge 源码证据
- `api.py:23-110`：`prepare` 函数完整实现
- `api.py:113-117`：`run` 函数
- `api.py:125-184`：`collect` 函数，日志发现逻辑
- `api.py:187-194`：`export` 函数
- `runner.py:16-91`：`LocalRunner` 类
- `workspace.py:11-54`：`Workspace` 类
- `cli.py:16-252`：CLI 解析器与 7 个子命令
- `modify.py:17-123`：三个 `modify_*` 函数
- `structure.py:26-64`：`AbacusStructure.from_input`
- `result.py:10-56`：`RunResult`/`CollectionResult`
- `collectors/abacus.py:53-140`：`collect_abacus_metrics`
- `collectors/abacus.py:18-47`：正则指标模式
- `band_data.py:26-47`：`BandData.summary`
- `dos_data.py:27-59`：`DOSData.summary`/`PDOSData.summary`

### 主线文档证据
- `AGENTS.md`（PAIMON 主）第 16 行：架构主链定义
- `docs/packages.md` 第 7 行：Forge 职责边界
- `docs/packages.md` 第 28-33 行：`deps/abacus-forge` 归属原则
- `AGENTS.md`（Forge 子）第 8 行：主链定位
- `AGENTS.md`（Forge 子）第 23-29 行：禁止项红线

### 审查框架证据
- `.trae/documents/abacus-forge-review.md`：审查说明文档
- `docs/abacus-forge-review.md`（审查计划文件）：报告交付计划
- `docs/abacus-forge-submodule-code-review-plan-2026-04-25.md`：细致审查计划
- `docs/abacus-forge-review.md`（报告）：预设立场口径
