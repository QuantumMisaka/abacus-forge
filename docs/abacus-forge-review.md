---
level: P2
type: review
status: active
owners:
  - project-lead
source_of_truth: deps/abacus-forge
related:
---

# ABACUS-Forge 深度审查与报告交付计划

## Summary

产出一份正式审查报告，建议落在 `docs/develop/`，定位为“子项目专项评审文档”，结论必须同时覆盖：

- `ABACUS-Forge` 是否遵循 PAIMON 主线与包边界
- 它与 `abacus-test` 在功能点和实现模式上的差异
- 它是否已经同时满足两种角色：
  - 服务器上科研用户可直接调用的本地/CLI ABACUS 计算单元
  - `aiida-abacus` / PAIMON 可复用的 ABACUS 计算功能单元库
- 对 `SCF / Relax / Band / DOS` 至少给出“已闭合 / 部分实现 / 未开始”的明确分级
- 给出后续开发路线，按 P0/P1/P2 排优先级，并明确哪些能力应进入 Forge、哪些必须留在 AiiDA/PAIMON 上层

报告的总判断口径预设为：

- **边界遵循度**：整体遵循主线，当前没有明显吸入协议层、前端或 AiiDA provenance 语义
- **角色完成度**：更接近“轻量计算基元库”，还不是“对标 abacustest 的开箱即用 CLI 工具链”
- **功能闭合度**：`collect/export` 对 `band/dos/pdos` 的摘要能力已有最小落地，但 `prepare/run/CLI` 对
  `SCF / Relax / Band / DOS` 的本地完整任务单元能力仍明显不足
- **后续方向**：应优先补齐单任务原语闭环和 task-oriented local UX，而不是把厚工作流或站点策略下沉到 Forge

## Key Changes

### 1. 报告的证据基线与比较口径

报告只使用仓库内可验证事实，并明确区分“直接源码证据”和“仓库内分析文档证据”：

- Forge 直接证据：`deps/abacus-forge` 的源码、README、AGENTS、tests、当前工作树 diff
- 主线边界证据：`docs/architecture.md`、`docs/contracts.md`、`docs/development.md`、`docs/develop/legacy-
    to-forge-capability-map.md`
- `abacus-test` 对比证据：`docs/repo_analysis_vault/10_Repos/abacus-test/*` 与 `docs/aiida-abacus-sai-
    work-docs/*` 中的实践记录
- 集成使用证据：`src/paimon/forge_adapter.py`、`src/paimon/aiida_sai.py`

报告中必须显式声明：

- 仓库内没有 `abacus-test` 源码子模块
- 本次对 `abacus-test` 的对比基于仓库内已有分析沉淀和实践记录，而不是直接对其源码逐文件 diff

### 2. 审查框架与必写章节

报告按以下结构写，避免只写泛泛结论：

1. **项目定位与审查问题**
   - Forge 在 PAIMON 主链中的职责
   - 本次评审的两个核心角色目标
   - 对 `SCF / Relax / Band / DOS` 的最低验收口径
2. **实现现状**
   - 当前 Forge 的实际能力面：`Workspace`、`LocalRunner`、`prepare/run/collect/export`、CLI
   - 当前新增改动实际补了什么：`band/dos/pdos` 摘要采集
   - 当前测试覆盖了什么、没有覆盖什么
3. **与** **`abacus-test`** **的功能点对比**
   - 输入准备：结构格式支持、参数模板化、K 点、PP/ORB 组织、批量/目录生成
   - 执行：单任务运行、MPI/OMP、本机/HPC 调用、失败模式
   - 结果：基础指标、Band/DOS/PDOS、筛选/导出、报告
   - 工作流：单任务原子操作 vs 厚封装多步流程
   - CLI 面：薄原语 CLI vs 工具链 CLI
4. **实现模式对比**
   - Forge：单工作区原语、极薄依赖、无平台编排、无上层语义
   - `abacustest`：prepare/submit/collect/report/model/workflow 全栈工程化工具链
   - 明确哪些差异是“有意收缩”，哪些差异是“当前缺口”
5. **按 PAIMON 主线的合规性评估**
   - 哪些地方符合“基元化、轻量化、不吸上层语义”
   - 哪些地方虽然不违规，但尚不足以支撑既定双角色目标
6. **双角色评估结论**
   - 作为 AiiDA 计算单元库：给出明确分级和理由
   - 作为科研用户本地 CLI 计算单元：给出明确分级和理由
   - 对 `SCF / Relax / Band / DOS` 分别给出完成度评级
7. **风险点与后续开发路线**
   - 必须按 P0/P1/P2 排序
   - 每项明确“应进入 Forge / 应留在上层”

### 3. 报告中的核心判断标准

对每个能力点，不用“有没有一点代码”判断，而用以下标准：

- **已闭合**：科研用户或上层调用方能直接完成该类任务，输入、执行、采集、导出链路完整，且接口语义稳定
- **部分实现**：已有底层原语或部分结果采集，但无法独立完成该类任务闭环
- **未开始**：缺少关键原语或缺少任何可复用实现

基于当前仓库事实，报告应按下列口径评估：

- `prepare`
  - 已有：生成最小 `INPUT/KPT/STRU`、meta 记录
  - 缺失：`cif/POSCAR` 转换、PP/ORB 组织、task-aware 输入准备、模板/覆盖策略、Relax/Band/DOS 专用输入生成
- `run`
  - 已有：本地进程执行、MPI/OMP 最小参数
  - 缺失：HPC runner 抽象、错误分类、作业级资源模型、与 task 类型关联的执行辅助
- `collect`
  - 已有：基础能量/费米能级/带隙/收敛、Band/DOS/PDOS 最小摘要
  - 缺失：Relax 关键产物摘要、ABACUS 更完整解析、对真实输出命名和失败模式的更强鲁棒性
- `CLI`
  - 已有：原语级 `prepare/run/collect/export`
  - 缺失：面向科研用户的 task CLI，如“直接完成 scf/relax/band/dos 单任务闭环”的用户体验
  - 为 `Relax` 增加 `final_structure / convergence / trajectory summary`
  - 为 `Band / DOS` 增加更稳定的 canonical artifact 识别
  - 保持返回结构仍是 Forge 自己的 metrics/artifacts，不引入 AiiDA/PAIMON 语义
- 强化测试
  - 不再只测 mock 文本提取，增加 task-oriented golden workspace 测试

#### P1：把 Forge 做成“科研用户可直接使用的轻量 CLI”

- 在现有原语 CLI 之外增加 task CLI，但仍复用 `prepare/run/collect/export`
- 推荐接口形态：
  - `abacus-forge scf ...`
  - `abacus-forge relax ...`
  - `abacus-forge band ...`
  - `abacus-forge dos ...`
- 这些 task CLI 只负责单任务闭环，不引入厚工作流、平台提交、远程追踪或 HTML 报告系统

#### P2：把 Forge 做成“更稳的 AiiDA 计算基元库”

- 明确 Python API 的稳定入口，保证 AiiDA/PAIMON 只依赖少量清晰原语
- 让 `retrieved -> workspace -> collect/export` 成为正式支持路径
- 如需新增 runner，优先加“本地/HPC 命令抽象”，不要把 Slurm/QOS/站点策略塞进 Forge

### 5. 明确哪些能力不应进入 Forge

报告必须明确排除以下方向，防止后续开发跑偏：

- 不把 `abacustest` 的 `submit/status/download/report/model/remote/dflow` 整体迁入 Forge
- 不把 `Relax -> Band -> DOS` 这类多步物理流程编排下沉到 Forge
- 不把 SAI/Slurm 的 `partition/qos/nodes/gpus-per-node` 等站点策略下沉到 Forge
- 不把 PAIMON 的 `RunResult / Group / provenance / case/archive/tutorial` 语义塞入 Forge
- 不把 ATP/MCP/前端消费字段放进 Forge 的返回结构

## Test Plan

执行该审查并写报告时，必须附带以下验证动作和对应结论来源：

- 运行 `pytest deps/abacus-forge/tests -q`
  - 明确本轮子模块改动只补了 `collect` 的 band/dos/pdos 摘要
- 检查 `src/paimon/forge_adapter.py`
  - 证明 Forge 当前在 PAIMON 中主要承担 mock/local primitives 与 artifact/metrics 归一化角色
- 检查 `src/paimon/aiida_sai.py`
  - 证明真实 AiiDA 路径已把 Forge 用作结果物料化与收集层，而不是 workflow 编排层
- 用表格列出 `abacustest` 与 Forge 的能力映射
  - 至少覆盖：输入准备、执行、结果采集、导出、CLI 面、工作流/平台能力、依赖模型

## Assumptions

- 报告交付位置默认选 `docs/develop/`，因为它属于“实现状态、评审和下一步方向”的过程文档目录。
  按“已有部分 mock 解析”判断。
- 对 Forge 的目标解释采用 PAIMON 主线口径：它应成为“轻量任务单元库 + 轻量 CLI”，而不是“另一个 abacustest
  平台化工具链”。

