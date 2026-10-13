# ABACUS-Forge 深度审查 Spec

## Why

PAIMON 主项目已进入"一致性加固"阶段，需要对 `deps/abacus-forge` 子模块开展一次以"边界合规 + 能力成熟度 + 集成适配性 + 文档真实性"为核心的细致审查，确保 Forge 遵循主线架构约束并具备支撑双角色目标的能力。

## What Changes

本次审查不对 `deps/abacus-forge` 源码做任何修复，交付物为：
1. **正式评审报告**（`docs/develop/abacus-forge-submodule-review-<date>.md`）：按 `.trae/documents/abacus-forge-review.md` 既定框架输出
2. **对话内 findings 摘要**：按严重级别排序的关键发现

## Impact

- 受影响 specs：`docs/develop/abacus-forge-submodule-review-2026-04-25.md` 的审查框架
- 受影响代码：`deps/abacus-forge/src/` 全量源码、`src/paimon/forge_adapter.py`、`src/paimon/aiida_sai.py`

## 审查范围

### 主审对象
- `deps/abacus-forge/` 子模块全部源码、CLI、测试和项目元数据

### 证据读取范围（不做主审）
- `src/paimon/forge_adapter.py`、`src/paimon/aiida_sai.py`、`src/paimon/execution.py`
- `docs/develop/legacy-to-forge-capability-map.md` 等过程文档
- `repo/abacus-test/` 同功能源码对照

### 不在范围
- 主仓核心包（`src/paimon/` 自身逻辑）
- `deps/aiida-abacus/` 深度源码
- Legacy 仓库整体

## ADDED Requirements

### Requirement: 项目定位与边界合规性审查

#### Scenario: 审查 Forge 是否遵循主线三层架构约束
- **WHEN** 对 Forge 源码与 `docs/architecture.md`、`docs/packages.md`、`AGENTS.md` 进行对照审查
- **THEN** 必须明确给出"边界遵循度"结论，区分"已闭合"、"部分实现"、"未开始"三级

### Requirement: 双角色能力成熟度评估

#### Scenario: 评估 Forge 作为"科研用户 CLI 工具链"和"AiiDA 计算基元库"的双重角色
- **WHEN** 审查 `prepare/run/collect/export` 全链路实现
- **THEN** 必须对 `SCF / Relax / Band / DOS` 四类任务给出明确完成度分级（已闭合 / 部分实现 / 未开始）

### Requirement: 与 abacus-test 功能对照

#### Scenario: 使用仓库内 `repo/abacus-test/` 源码做同功能对照
- **WHEN** 对 Forge 和 `abacus-test` 的输入准备、执行、结果采集、CLI 面进行同功能映射
- **THEN** 必须明确标注每项差距为"有意收缩"还是"当前缺口"

### Requirement: 测试与文档一致性

#### Scenario: 验证 README/AGENTS/ROADMAP 声称能力与实际代码实现的一致性
- **WHEN** 读取文档与对应源码实现
- **THEN** 每项声称必须绑定至少一个源码证据，不以路线图代替已实现事实

## 审查框架与必写章节

1. **项目定位与审查问题**：Forge 在 PAIMON 主链中的职责、本次评审双角色目标、对 SCF/Relax/Band/DOS 最低验收口径
2. **实现现状**：当前 Forge 实际能力面（Workspace、LocalRunner、prepare/run/collect/export、CLI）、新增 band/dos/pdos 摘要采集、测试覆盖情况
3. **与 abacus-test 的功能点对比**：输入准备、执行、结果采集、CLI 面、工作流/平台能力、依赖模型
4. **实现模式对比**：Forge 单工作区原语 vs abacustest 全栈工具链，明确哪些差异是"有意收缩"哪些是"当前缺口"
5. **按 PAIMON 主线的合规性评估**：符合轻量化、不吸上层语义的方面；尚不足以支撑双角色目标的方面
6. **双角色评估结论**：作为 AiiDA 计算单元库和科研用户 CLI 的分级评估
7. **风险点与后续开发路线**：按 P0/P1/P2 排序，明确每项"应进入 Forge"还是"必须留在上层"

## 证据基线与比较口径

- Forge 直接证据：`deps/abacus-forge/` 的源码、README、AGENTS、tests、pyproject.toml
- 主线边界证据：`docs/architecture.md`、`docs/contracts.md`、`docs/packages.md`、`AGENTS.md`
- abacus-test 对比证据：`repo/abacus-test/` 可直接读取的同功能源码

## 报告判断口径

- **边界遵循度**：整体遵循主线，当前没有明显吸入协议层、前端或 AiiDA provenance 语义
- **角色完成度**：更接近"轻量计算基元库"，还不是"对标 abacustest 的开箱即用 CLI 工具链"
- **功能闭合度**：`collect/export` 对 `band/dos/pdos` 有最小落地，但 `prepare/run/CLI` 对 SCF/Relax/Band/DOS 本地完整任务单元能力仍明显不足
- **后续方向**：应优先补齐单任务原语闭环和 task-oriented local UX
