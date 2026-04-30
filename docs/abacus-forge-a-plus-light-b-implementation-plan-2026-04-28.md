# ABACUS-Forge 任务 A + 轻量任务 B 落地计划（2026-04-28）

## Summary

- 目标：在不突破 `ABACUS-Forge` 设计边界的前提下，具体落地两个已确认符合方向的 P1 任务：
  - 任务 A：补强 `structure.py` 的核心测试覆盖；
  - 任务 B：新增一个严格受限的“单工作区结构扰动原语”，承载于新的 `perturbation.py`。
- 范围：
  - 仅修改 `deps/abacus-forge/` 子模块源码与测试；
  - 不触达主仓 `src/paimon/`、协议层、AiiDA 语义或前端交付逻辑；
  - 不实现 `abacus-test` 风格的批量目录生成器或平台调度壳。
- 成功标准：
  - `structure.py` 中当前未被直接验证的核心能力得到针对性测试覆盖；
  - `perturbation.py` 只提供纯结构变换原语，不引入 batch/workflow 语义；
  - 子模块测试通过，新增 API 与 `prepare/run/collect/export` 的边界不冲突。

## Current State Analysis

### 已确认的现状

- `deps/abacus-forge/src/abacus_forge/structure.py`
  - 已实现以下核心能力：
    - `AbacusStructure.from_input()`：支持 `Path`/`Atoms`/`AbacusStructure`/`Mapping`/`pymatgen Structure`
    - `metadata()`、`ensure_3d_pbc()`
    - `primitive_to_conventional()`、`conventional_to_primitive()`
    - `swap_axes()`、`make_supercell()`
    - `to_stru()`
    - `_read_stru()`：支持 `Direct` / `Cartesian` / `Cartesian_angstrom`、磁矩和 move flags 解析
- `deps/abacus-forge/tests/test_structure.py`
  - 当前仅有 2 个测试：
    - POSCAR 检测 + metadata
    - XYZ 输入 + `ensure_3d_pbc`
  - 尚未直接覆盖 `to_stru()`、`swap_axes()`、`make_supercell()`、mapping 输入、STRU round-trip、不同坐标模式等核心逻辑。
- `deps/abacus-forge/src/abacus_forge/__init__.py`
  - 当前对外导出 `AbacusStructure`，未导出任何扰动相关原语。
- `deps/abacus-forge/src/abacus_forge/`
  - 当前不存在 `perturbation.py` 或任何 `perturb_*` 原语。

### 已确认的设计边界

- `deps/abacus-forge/AGENTS.md`
  - 只允许围绕 `prepare` / `run` / `collect` / `export` 的基元能力扩展；
  - 禁止引入 Bohrium / DPDispatcher、MCP/ATP、AiiDA Group/Node、前端逻辑；
  - 从 `abacus-test` 吸纳能力时，必须剔除厚封装工作流部分。
- `docs/develop/abacus-forge-submodule-review-2026-04-25.md`
  - `STRU` 结构对象与变换能力应进入 Forge；
  - `pert_stru` 可进入 Forge，但前提是它被定义为“本地输入生成原语”，而不是批量平台任务系统。

### 本轮范围决策

- 用户已确认：
  - 本轮范围为“任务 A + 轻量任务 B”；
  - 任务 B 的承载位置采用新增 `perturbation.py`（而不是继续膨胀 `structure.py`）；
  - 目标是“具体落地”，不只是继续抽象论证。

## Proposed Changes

### 1. 补强 `structure.py` 的直接测试覆盖

- 文件：
  - `deps/abacus-forge/tests/test_structure.py`
  - 如测试组织需要，可新增 `deps/abacus-forge/tests/test_perturbation.py`，但优先保持结构相关测试收敛在对应测试文件中。
- 变更内容：
  - 为以下能力增加直接测试：
    - `AbacusStructure.from_input()` 的 mapping 输入路径；
    - `to_stru()` 输出的基本块结构与物种分组；
    - `_read_stru()` / `from_input(..., structure_format="stru")` 的 round-trip；
    - `swap_axes()` 的 cell 与 scaled positions 交换行为；
    - `make_supercell()` 的原子数与晶胞缩放行为；
    - `Direct` / `Cartesian` / `Cartesian_angstrom` 三种 STRU 坐标模式解析；
    - move flags 与 species metadata 回收；
    - `primitive_to_conventional()` / `conventional_to_primitive()` 的“缺少 pymatgen 时清晰失败”路径。
- 为什么：
  - 这些能力已经在 `structure.py` 中存在，但当前测试覆盖明显不足；
  - 该任务完全属于 Forge 输入归一化能力补强，不涉及边界争议。
- 如何做：
  - 优先使用构造最小 ASE `Atoms`、手写极小 STRU 文本和 round-trip 断言；
  - 不引入体量大的 golden 数据集；
  - 对 `pymatgen` 缺失场景使用 monkeypatch / import failure 模式测试清晰异常，而不是强依赖运行环境一定装有 `pymatgen`。

### 2. 新增轻量结构扰动原语 `perturbation.py`

- 文件：
  - 新增 `deps/abacus-forge/src/abacus_forge/perturbation.py`
  - 更新 `deps/abacus-forge/src/abacus_forge/__init__.py`
  - 新增或更新测试文件：
    - `deps/abacus-forge/tests/test_perturbation.py`
    - 如需最小集成验证，可补 `deps/abacus-forge/tests/test_api.py`
- 变更内容：
  - 在 `perturbation.py` 中新增一个单结构原语函数，建议接口：
    - `perturb_structure(structure, *, displacements, copy=True, preserve_source_format=True) -> AbacusStructure`
  - 输入允许：
    - `Atoms`
    - `AbacusStructure`
    - 兼容 `AbacusStructure.from_input()` 可接受的轻量输入之一，但实现时应优先收敛到 `Atoms | AbacusStructure`
  - 输出：
    - 单个 `AbacusStructure`
  - 行为：
    - 仅对原子坐标施加位移；
    - 不创建目录树、不写多个 case、不注入 task/workflow 参数；
    - 默认复制输入对象，不原地修改。
- 为什么：
  - 这满足审查文档对 `pert_stru`“可进入 Forge”的条件；
  - 通过独立 `perturbation.py`，可以避免把 `structure.py` 继续做厚，也防止未来滑向 `PrepareAbacus` 风格的大类。
- 如何做：
  - 第一版只支持最小、清晰、可验证的位移模式：
    - 传入 shape 为 `(n_atoms, 3)` 的显式位移数组/列表；
  - 本轮不做：
    - 随机扰动种子系统；
    - 多样本批量生成；
    - 多目录输出；
    - 与 `prepare()` 自动绑定；
    - 参数扫描 (`mix_*`) 组合壳。

### 3. 最小导出与可发现性调整

- 文件：
  - `deps/abacus-forge/src/abacus_forge/__init__.py`
- 变更内容：
  - 若确定该原语是面向 Forge 用户的稳定轻接口，则将 `perturb_structure` 导出到包顶层；
  - 若实现后判断仍偏内部工具，则保留仅模块内可导入，不进入 `__all__`。
- 决策：
  - 本轮计划采用**导出到包顶层**，因为：
    - 它是一个独立、边界清晰的输入原语；
    - 用户已经明确要求“具体落地”；
    - 其定位与 `AbacusStructure` 一样，属于底层输入处理能力。

### 4. 测试与验收

- 文件：
  - `deps/abacus-forge/tests/test_structure.py`
  - `deps/abacus-forge/tests/test_perturbation.py`
  - 按需更新 `deps/abacus-forge/tests/test_api.py`
- 变更内容：
  - 对任务 A 与 B 各自建立清晰的单元测试；
  - 如果 `test_api.py` 已适合作为最小集成入口，则增加“扰动后结构可被 `prepare()` 接收并写出 STRU”的一条轻集成测试；
  - 不将扰动原语耦合到 `prepare()` 默认流程，只验证兼容性。

## Assumptions & Decisions

- 决定：本轮实现包含两个任务，但 B 严格限定为“轻量扰动原语”。
- 决定：B 的承载文件为新建 `perturbation.py`，不并入 `structure.py`。
- 决定：B 第一版接口只支持**单结构 + 显式位移矩阵**，不引入随机批量生成和多 case 输出。
- 决定：不实现 `abacus-test PrepareAbacus` 风格的 `pert_stru` 厚封装，更不实现与平台目录生成、提交说明、Bohrium/dispatcher 相关的逻辑。
- 决定：本轮若需要 `pymatgen` 相关测试，只测试“缺失依赖时的清晰失败”以及在现环境可稳定验证的路径，不强求跨环境不稳定测试。
- 假设：当前 `deps/abacus-forge` 相关文件没有新的外部并发改动；若实施前发现意外变化，应先停止并重新确认。

## Verification Steps

- 代码级验证：
  - `structure.py` 的关键现有能力均有直接测试，不再只靠 `test_api.py` 间接覆盖；
  - `perturbation.py` 仅暴露单结构变换能力，不包含目录、workspace、批量生成、workflow 语义；
  - 若 `perturb_structure` 导出到包顶层，`__init__.py` 中导出项与实现一致。
- 测试验证：
  - `python -m pytest deps/abacus-forge/tests/test_structure.py -q`
  - `python -m pytest deps/abacus-forge/tests/test_perturbation.py -q`
  - `python -m pytest deps/abacus-forge/tests/test_api.py -q`
  - 如有必要，再跑：
    - `python -m pytest deps/abacus-forge/tests -q`
- 行为验证：
  - `AbacusStructure.to_stru()` 生成文本可被 `from_input(..., structure_format="stru")` 重新读回；
  - `swap_axes()` 与 `make_supercell()` 对 cell / positions / atom count 的影响符合预期；
  - `perturb_structure()` 返回的是单个 `AbacusStructure`，且默认不修改输入对象；
  - 扰动后的结构可以直接被 `prepare()` 接收并写出合规 `STRU`。
- 边界自检：
  - 没有新增 Bohrium、dispatcher、MCP/ATP、AiiDA Group/Node 相关代码；
  - 没有实现批量目录生成器、平台任务壳或前端结果摘要逻辑；
  - `perturbation.py` 的 I/O 保持在“结构输入 -> 结构输出”层面。
