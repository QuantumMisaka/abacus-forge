# Tasks for ABACUS-Forge 深度审查

## Task 1: 读取 Forge 全部源码与项目元数据
- [ ] 读取 `deps/abacus-forge/src/abacus_forge/` 全部 Python 源码
- [ ] 读取 `deps/abacus-forge/README.md`、`AGENTS.md`、`ROADMAP.md`
- [ ] 读取 `deps/abacus-forge/pyproject.toml` 了解依赖和入口配置
- [ ] 读取 `deps/abacus-forge/tests/` 全部测试文件

## Task 2: 读取主项目约束文档
- [ ] 读取 `docs/architecture.md` 架构主链约束
- [ ] 读取 `docs/packages.md` 包边界约束
- [ ] 读取 `AGENTS.md`（PAIMON 主）核心契约
- [ ] 读取 `docs/contracts.md` 接口契约

## Task 3: 读取已有审查计划与过程文档
- [ ] 读取 `.trae/documents/abacus-forge-review.md` 审查框架
- [ ] 读取 `docs/abacus-forge-submodule-code-review-plan-2026-04-25.md` 审查计划
- [ ] 读取 `docs/abacus-forge-review.md` 报告交付计划
- [ ] 读取 `docs/develop/legacy-to-forge-capability-map.md` 能力映射
- [ ] 读取 `docs/develop/practice-informed-status-review-and-next-plan.md` 实践状态

## Task 4: 审查 Forge 与主仓集成证据
- [ ] 读取 `src/paimon/forge_adapter.py` 主仓唯一 Forge 薄入口
- [ ] 读取 `src/paimon/aiida_sai.py` AiiDA 路径调用关系
- [ ] 核对集成是否遵循"薄入口、无 Forge 语义私补"原则

## Task 5: 运行 pytest 验证测试覆盖
- [ ] 运行 `python -m pytest deps/abacus-forge/tests -q` 获取测试结果
- [ ] 分析测试覆盖哪些能力、缺失哪些能力
- [ ] 运行 `python -m pytest tests/test_forge_adapter.py tests/test_router_and_execution.py -q`（如存在）

## Task 6: 按审查框架撰写正式报告
- [ ] 撰写章节1：项目定位与审查问题（Forge 在 PAIMON 主链职责、双角色目标、SCF/Relax/Band/DOS 验收口径）
- [ ] 撰写章节2：实现现状（Workspace、LocalRunner、prepare/run/collect/export、CLI、新增 band/dos/pdos 摘要、测试覆盖）
- [ ] 撰写章节3：与 abacus-test 功能点对比（输入准备、执行、结果采集、CLI 面、工作流/平台能力、依赖模型）
- [ ] 撰写章节4：实现模式对比（有意收缩 vs 当前缺口）
- [ ] 撰写章节5：PAIMON 主线合规性评估
- [ ] 撰写章节6：双角色评估结论（AiiDA 计算单元库 vs 科研用户 CLI 的分级）
- [ ] 撰写章节7：风险点与后续 P0/P1/P2 开发路线
- [ ] 输出最终报告到 `docs/develop/abacus-forge-submodule-review-<date>.md`

## Task 7: 对话内 findings 摘要
- [ ] 汇总按严重级别排序的关键 findings
- [ ] 每条 findings 绑定源码证据

## Task Dependencies
- Task 2-4 依赖 Task 1 的源码阅读结果
- Task 5 依赖 Task 1-4 的信息收集
- Task 6 依赖 Task 2-5 的全部输入
- Task 7 依赖 Task 6 的报告完成
