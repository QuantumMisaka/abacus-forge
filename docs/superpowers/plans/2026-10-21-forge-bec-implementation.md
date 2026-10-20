# Forge polarization / BEC 实施计划

状态：本轮有界本地实现、验证与审查完成；工作流 L3，继续既有 brainstorming / writing-plans / SDD。
用户已确认“有条件分支处理＋显式覆盖；允许请求子集、缺项明确报告”，并要求继续。
规范源：[BEC SPEC](../specs/2026-10-21-forge-polarization-bec-design.md)。

继续隔离工作树 `forge-integration-reference-review`，HEAD f590367。前轮 NAO/manifest
已审查 dirty 改动保持；本轮开始前全部 dirty 文件归档于
`/home/james/scratch/forge-bec-20261021/before-bec.tar.gz`，状态见同目录 before-status.txt。
不改 Paimon 并行工作、不提交/发布、不启动新 ABACUS/SAI 计算。

### Task 1：依据与契约冻结

- [x] 审查现有 SPEC/PLAN、legacy BEC 和 ABACUS producer；确认旧 pack 不能充当新数值路径。
- [x] 用户确认后冻结 conditional auto/explicit、子集和缺项语义。
- [x] 核实 generic 准备/位移/单次执行复用，保留可执行示例（recipe test 1 passed；假进程，不是 ABACUS 实算）。

### Task 2：原生事实与数值算法

- [x] 新 polarization parser/fact producer：保留三种单位、七位小数模量、gdir/phase，关联 STRU/INPUT。
- [x] 新 BEC pure algorithm：固定晶胞/几何/配置检查；三 gdir、显式/条件式分支、±δ差分。
- [x] 源格式 fixture/已知斜晶胞张量/歧义与缺项回归先 RED 后 GREEN；不冒充实算。

### Task 3：请求、服务和机器消费

- [x] 严格 collect/postprocess 请求、路径准入、只追加事件、标准 artifacts 和部分结果。
- [x] CLI/schema/discovery/Python 接线；复用已有协议，不增加 workflow。
- [x] Python/CLI 等价、路径逃逸/覆盖/缺失/重复与旧能力回归。

### Task 4：文档、集成与审查

- [x] 更新使用示例、当前导航/ROADMAP、前轮计划的后继状态。
- [x] 独立审查数值与边界，修复有效发现；主控验收实际 diff/原始日志。
- [x] 相称离线回归与完成记录，明确尚无真实 BEC 科学验收。

分工：数值 worker 只写 polarization.py / bec.py 与对应算法测试、fixture；
接口 worker 只写新 contracts/services 及注册/CLI/discovery/root exports、接口测试/portfolio。
主控拥有 SPEC/PLAN/docs/example，跨 worker 接口先约定；没有共享文件并发写入。
普通实现选择可裁决推进；范围/科学能力变化回到对应设计。

Ruling：新 typed 能力先覆盖 polarization/collect 与 bec/postprocess；准备/位移/单次
执行复用现有通用原语和明确 recipe，避免复制旧 BEC workflow。不能假借 typed SCF
execute 运行 NSCF。若通用复用不可行，先修正有界技术方案再开工。

## 完成记录

- 新增 `polarization/collect` 与 `bec/postprocess`，注册请求、Python、CLI/schema 与
  discovery；准备/位移/单进程执行复用现有原语。legacy pack 未替换。
- 条件式 auto 要求可信的相邻真实变化界和零参考；explicit 保留每 sample/gdir
  的整数 offsets。未知分支、缺数据、无效数据都不会伪造完整张量。
- 数值/解析 owning 初次 RED（缺模块）后 **18 passed**；recipe RED（缺示例文件）
  后 **1 passed**，验证指定原子位移和仅一次假进程。
- 接口定向 **442 passed**；含真实 source-shaped 日志收集→fact→BEC 链、
  good/invalid 列并存、source artifacts、路径/目标保护、schema 与注册旧行为。
- 全量离线 **1532 passed、35 skipped、176 warnings**，exit 0，139.36 s。
  既有可选/真实计算门禁保持跳过，第三方 warning 未屏蔽。
- 主控额外运行机器 CLI/API 等价回放：九个 collect 加 CLI/Python 两个 BEC
  postprocess，JSON 完全一致，11 个 append-only events；已知合成列为
  `[0.2,0,0] e`，requested_complete=true / full_tensor_complete=false。
- 独立科学复核未发现分支/单位/笛卡尔合成实质错误；完整 reviewer 已关闭
  malformed fact 被误标 missing 的问题，确认列级 invalid 与有效列可并存。
  无未解决的实质发现。
- 246 个相对文件链接可解析，`git diff --check` 通过。原始日志、CLI requests/
  responses、facts、结果和脚本见[本轮证据](../evidence/2026-10-21-forge-bec.md)。
- 在全套通过后，发现 parser-only 测试 STRU 的 Å/bohr 与合成日志设定不一致；
  仅修正测试 lattice constant（串联fixture已正确），生产代码不变；最后定向 **18 passed**，exit 0（algorithm-fixture-final.log）。

## 保留边界与后续

- 截至本实施轮结束，尚未取得真实材料 Berry 日志或运行原生 BEC 科学验收；本轮
  支持是源格式与数值/交接验证。其后 fresh wheel 安装及 MgO 单列真实计算进入
  [安装/实算接续计划](2026-10-21-forge-installed-bec-validation.md)，对应状态与证据
  由该计划及[验证记录](../evidence/2026-10-21-forge-installed-bec-validation.md)维护。
  当前单列结果不代表完整张量或收敛；能力仍 experimental。位移步长、k 网格和
  分支条件敏感性仍按接续计划评估，不重复在此记账。
- INPUT 除 gdir 外严格比较；PP/ORB 仅比较引用，实际字节一致性和绝缘性由调用方保证。
- 本轮没有 Paimon 平台接线、Benchmark 宣告、main 合入、提交、推送或发布。
  代码保留在隔离工作树；本地实现完成不等于上述外部验收完成。
