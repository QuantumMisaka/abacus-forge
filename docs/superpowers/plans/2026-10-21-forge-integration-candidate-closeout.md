# Forge 本地集成、候选范围与实际消费收口

状态：本轮收口完成，独立审查通过。用户确认按“集成 main → 明确候选依赖/交付范围 → 实际 demo/Benchmark 缺口”顺序推进。
工作流 L3，复用既有三份已完成计划与 SPEC；不重新设计已审查实现。

依据：[消费接续](2026-10-21-forge-consumption-followup.md)、
[BEC 实现](2026-10-21-forge-bec-implementation.md)、
[安装与实算](2026-10-21-forge-installed-bec-validation.md)。
公共契约沿用契约优先与 Service/Status SPEC，不扩大 Forge 的平台/工作流责任。

## Task 1：本地 main 集成

- [x] 核对 origin/main、干净 main 与当前工作树；复用当前候选的测试和审查证据。
- [x] 提交本轮 NAO/元数据/manifest/BEC 代码、测试、规范与必要证据，完整保留被通用 ignore 排除的验证日志。
- [x] 合入本地 main，运行集成后离线回归，保留工作树和历史实验恢复路径。

授权范围是本地提交与 main 集成；本轮不推送远程、不发布 PyPI、不改 Paimon owner 工作树。
远程核对：fetch 后 origin/main 为本地 main 的祖先（main 领先12提交，未落后）；
当前开发分支 f590367 为 main 416153d 的后继，预期可 fast-forward。
已有安装候选 c70e71a… 的76个Python文件与本轮源码逐字节一致；1532离线与520安装态
回归、真实NAO/BEC证据及独立审查用于集成前验收。集成后检查实际结果，不重新跑实算。

## Task 2：候选依赖与交付范围

- [x] 核查 abacuslite 1.2.0→1.2.2 发布内容与 Forge 消费契约，决定本候选采用版本。
- [x] 若升级，先跑已有 parser 安装/parity 与保留真实输出消费检查；不足时保留已验证pin并明确后续，不冒用旧版本验收。
- [x] 构建本地候选 wheel/sdist，给出安装方式、依赖与平台验证范围；不将本地候选当作已发布版本。

## Task 3：实际 demo/Benchmark 交接

- [x] 只读核查并行 Paimon owner 当前代码与实际结果，区分新问题、已修复问题和非Forge职责。
- [x] 对有复现证据的 Forge 缺口做最小修复与 owning 回归；无新缺口则记录已验证交接和具体上层剩余，不制造泛化兼容任务。
- [x] 更新路线图/导航及候选交付记录，核对本地main/工作树状态。

Paimon工作树当前有owner未提交内容，不在此修改。若后续确需v3实质开发，须先按工作区
规则同步合并最新v2 origin/main；只读消费核查不冒充完成该基线同步或平台验收。

## 执行记录与裁决

Ruling：原生和测试日志按原始字节提交（包括固定宽度空格），用三份证据目录的精确 `.log`/`.info` attributes 排除 whitespace 格式检查；不修改原始证据。补全现行 architecture 中新增服务/数值模块归属。


- 实现 `5f38349` 已提交并 fast-forward 合入 main。main全量离线1532 passed/35 skipped，exit0。
- sdist及从sdist构建wheel成功；wheel c70e71a…与前轮已验证候选相同；76模块与main/安装态一致。
- Ruling：保留optional abacuslite==1.2.0。1.2.1/1.2.2未改当前Forge消费的三项日志reader，
  当前demo无新字段需求；采用新版本由实际需要触发，不扩大本候选验证范围。
- fresh candidate环境安装[dev,abacuslite]，30项package/canonical检查通过；2个初始
  wheel环境变量门禁跳过随后补验通过，pip check通过。无PyATB原生新安装声明。
- 只读检查app-tools-forge@89fe8edc5：旧executor/band-edge问题已修复，没有证实的
  Forge库级阻断。Paimon kit存在旧d7与新4f ZIP绑定并存，交给原owner统一并继续
  实际canary/完整Benchmark；不改其在途工作树或授权锁。
- 产物、实际命令和交接依据见[交付记录](../evidence/2026-10-21-forge-integration-candidate-closeout.md)。
  证据保存原始.log；源码包按既有ignore不携带这些日志，完整日志已跟踪在main。

独立终审确认main集成、构建/安装原始证据、依赖选择与Paimon交接结论，无实质问题。
本轮文档相对文件链接164项均可解析，diff格式检查通过。收口文档随后与main同步；
保留开发分支/工作树及scratch候选环境，不进行远程推送或发布。
