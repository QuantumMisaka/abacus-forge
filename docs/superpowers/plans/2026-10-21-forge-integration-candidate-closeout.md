# Forge 本地集成、候选范围与实际消费收口

状态：执行中。用户确认按“集成 main → 明确候选依赖/交付范围 → 实际 demo/Benchmark 缺口”顺序推进。
工作流 L3，复用既有三份已完成计划与 SPEC；不重新设计已审查实现。

依据：[消费接续](2026-10-21-forge-consumption-followup.md)、
[BEC 实现](2026-10-21-forge-bec-implementation.md)、
[安装与实算](2026-10-21-forge-installed-bec-validation.md)。
公共契约沿用契约优先与 Service/Status SPEC，不扩大 Forge 的平台/工作流责任。

## Task 1：本地 main 集成

- [x] 核对 origin/main、干净 main 与当前工作树；复用当前候选的测试和审查证据。
- [ ] 提交本轮 NAO/元数据/manifest/BEC 代码、测试、规范与必要证据，完整保留被通用 ignore 排除的验证日志。
- [ ] 合入本地 main，运行集成后离线回归，保留工作树和历史实验恢复路径。

授权范围是本地提交与 main 集成；本轮不推送远程、不发布 PyPI、不改 Paimon owner 工作树。
远程核对：fetch 后 origin/main 为本地 main 的祖先（main 领先12提交，未落后）；
当前开发分支 f590367 为 main 416153d 的后继，预期可 fast-forward。
已有安装候选 c70e71a… 的76个Python文件与本轮源码逐字节一致；1532离线与520安装态
回归、真实NAO/BEC证据及独立审查用于集成前验收。集成后检查实际结果，不重新跑实算。

## Task 2：候选依赖与交付范围

- [ ] 核查 abacuslite 1.2.0→1.2.2 发布内容与 Forge 消费契约，决定本候选采用版本。
- [ ] 若升级，先跑已有 parser 安装/parity 与保留真实输出消费检查；不足时保留已验证pin并明确后续，不冒用旧版本验收。
- [ ] 构建本地候选 wheel/sdist，给出安装方式、依赖与平台验证范围；不将本地候选当作已发布版本。

## Task 3：实际 demo/Benchmark 交接

- [ ] 只读核查并行 Paimon owner 当前代码与实际结果，区分新问题、已修复问题和非Forge职责。
- [ ] 对有复现证据的 Forge 缺口做最小修复与 owning 回归；无新缺口则记录已验证交接和具体上层剩余，不制造泛化兼容任务。
- [ ] 更新路线图/导航及候选交付记录，核对本地main/工作树状态。

Paimon工作树当前有owner未提交内容，不在此修改。若后续确需v3实质开发，须先按工作区
规则同步合并最新v2 origin/main；只读消费核查不冒充完成该基线同步或平台验收。

## 执行记录与裁决

Ruling：原生和测试日志按原始字节提交（包括固定宽度空格），用三份证据目录的精确 `.log`/`.info` attributes 排除 whitespace 格式检查；不修改原始证据。补全现行 architecture 中新增服务/数值模块归属。
