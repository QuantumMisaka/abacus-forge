# Checklist for ABACUS-Forge 深度审查

## 审查前检查

- [ ] 工作树在 Forge 相关路径无未提交改动
- [ ] 已读取 `.trae/documents/abacus-forge-review.md` 审查框架
- [ ] 已确认 spec.md、tasks.md、checklist.md 三件套完整

## 静态核对检查点

### Forge 源码审查
- [ ] `api.py` 的 `prepare()` 实现已完整读取并理解
- [ ] `api.py` 的 `collect()` 实现已完整读取并理解
- [ ] `api.py` 的 `run()` 与 `export()` 实现已完整读取并理解
- [ ] `runner.py` 的 `LocalRunner` 实现已完整读取并理解
- [ ] `workspace.py` 的 `Workspace` 模型已完整读取并理解
- [ ] `cli.py` 的 CLI 子命令结构已完整读取并理解
- [ ] `modify.py` 的三个 `modify_*` 函数已完整读取并理解
- [ ] `structure.py` 的结构转换逻辑已完整读取并理解
- [ ] `result.py` 的 `RunResult`/`CollectionResult` 数据类已完整读取并理解
- [ ] `collectors/abacus.py` 的指标采集逻辑已完整读取并理解
- [ ] `band_data.py`、`dos_data.py` 的摘要逻辑已完整读取并理解

### 文档一致性核对
- [ ] README.md 声称的"已实现能力"与实际源码实现一致
- [ ] AGENTS.md 的"开发边界与禁止项"在代码中得到遵守
- [ ] ROADMAP.md 的"近期/中期方向"与当前实现状态区分清晰

### 主线约束核对
- [ ] Forge 未引入 Bohrium、DPDispatcher 等外部平台依赖
- [ ] Forge 未引入 MCP、ATP 等协议编解码逻辑
- [ ] Forge 未引入 AiiDA Group、Node UUID 等上层语义
- [ ] Forge 未引入前端状态管理或 UI 强耦合逻辑
- [ ] Forge 的 `prepare/run/collect/export` 职责边界清晰

## 能力分级检查点（SCF / Relax / Band / DOS）

### SCF 能力
- [ ] 已明确 SCF 在 prepare 阶段的输入生成能力（已闭合/部分实现/未开始）
- [ ] 已明确 SCF 在 run 阶段的执行能力（已闭合/部分实现/未开始）
- [ ] 已明确 SCF 在 collect 阶段的结果采集能力（已闭合/部分实现/未开始）

### Relax 能力
- [ ] 已明确 Relax 在 prepare 阶段的输入生成能力
- [ ] 已明确 Relax 在 run 阶段的执行能力
- [ ] 已明确 Relax 在 collect 阶段的结果采集能力（力、应力、virial、final_structure）

### Band 能力
- [ ] 已明确 Band 在 prepare 阶段的 KPT line-mode 输入生成能力
- [ ] 已明确 Band 在 collect 阶段的 BANDS_*.dat 摘要采集能力
- [ ] band_summary 指标已在 `collectors/abacus.py` 中实现

### DOS 能力
- [ ] 已明确 DOS 在 prepare 阶段的输入生成能力
- [ ] 已明确 DOS 在 collect 阶段的 DOS*_smearing.dat 摘要采集能力
- [ ] 已明确 PDOS 在 collect 阶段的 PDOS/TDOS 文件摘要采集能力
- [ ] dos_summary 和 pdos_summary 指标已在 `collectors/abacus.py` 中实现

## abacus-test 对照检查点

- [ ] Forge `prepare` vs `abacustest.prepare.PrepareAbacus` 对照已完成
- [ ] Forge `run/LocalRunner` vs `abacustest` 本地命令对照已完成
- [ ] Forge `collect/export` vs `abacustest` 结果采集对照已完成
- [ ] Forge band/dos/pdos 摘要 vs `abacustest` model 对照已完成
- [ ] 每项差距已标注"有意收缩"或"当前缺口"

## 集成适配性检查点

- [ ] `src/paimon/forge_adapter.py` 是主仓唯一 Forge 薄入口
- [ ] 主仓未在集成层为 Forge 私补大量私有语义
- [ ] Forge 被 `aiida_sai.py` 用作结果物料化层（非 workflow 编排层）

## 测试验证检查点

- [ ] `pytest deps/abacus-forge/tests -q` 已运行且结果已记录
- [ ] 测试覆盖了 prepare/run/collect/export 核心路径
- [ ] 测试覆盖了 modify_input/modify_stru/modify_kpt CLI 路径
- [ ] 测试覆盖了结构转换（cif/stru/poscar）
- [ ] 测试覆盖了 band/dos 数据类

## 报告输出检查点

- [ ] 章节1（项目定位与审查问题）已完成
- [ ] 章节2（实现现状）已完成
- [ ] 章节3（与 abacus-test 功能点对比）已完成
- [ ] 章节4（实现模式对比）已完成
- [ ] 章节5（PAIMON 主线合规性评估）已完成
- [ ] 章节6（双角色评估结论）已完成
- [ ] 章节7（风险点与 P0/P1/P2 开发路线）已完成
- [ ] 每条结论至少绑定一个源码证据
- [ ] 报告已输出到 `docs/develop/`
