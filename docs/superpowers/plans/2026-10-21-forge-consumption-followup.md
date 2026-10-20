# Forge 消费能力接续：完成情况核查与实施计划

状态：本轮有限实施与审查完成；后续 BEC 设计裁决与有界实现也已完成，安装态及真实材料验证由接续计划跟踪。基线 `f590367`，隔离工作树
`forge-integration-reference-review` / `codex/forge-pyatb-installed-consumption`。

本计划中的 BEC 范围反映本轮交付时的状态。之后用户确认有界实现契约，完成 typed 能力与离线验证；当前 wheel 与 MgO 单列验证见[安装/实算接续计划](2026-10-21-forge-installed-bec-validation.md)及[验证证据](../evidence/2026-10-21-forge-installed-bec-validation.md)。此接续不扩展为完整张量、科学收敛或 Paimon/SAI 验收。

## 目标与授权

2026-10-21 用户确认直接 NAO-COHP 有必要，要求具体考察 v2 兼容的必要性、
Contract System、Property manifest 与 BEC 的 Forge 集成价值；随后要求按
brainstorming、writing-plans、subagent-driven-development 推进，并先确认
既有 SPEC/PLAN 和完成情况。

本计划接续既有工作，不重建迁移验收体系。当前实施范围是 Forge 独立消费：
直接 NAO/PyATB 接口、有限能力元数据、现有 manifest 的实际消费示例和验证；
BEC 先修订设计，未决极化分支策略不自动进入生产实现。Paimon 的并行 Benchmark
工作保持原 owner，本计划只记录有证据的交接问题，不改写其在途文件。
本轮不发布、推送、不启动新的 ABACUS/SAI 计算。

上位规范仍为 [契约优先 SPEC](../specs/2026-09-01-forge-contract-first-rearchitecture-design.html)
与 [Service/Status SPEC](../specs/2026-09-02-forge-service-status-migration-design.html)。
各能力仍是 experimental；离线调用、原始数据回放、完整科学/平台验收分别记账。

## 实施前已有内容核查（2026-10-21）

| 主题与 owning 文档 | 已核实完成 | 实际剩余 |
| --- | --- | --- |
| [IAO-COHP SPEC](../specs/2026-10-15-forge-cohp-postprocess-design.md) / [PLAN](2026-10-15-forge-cohp-postprocess.md) | `cohp/postprocess`、`method=iao`、Python/CLI、路径准入、安装消费及真实 Si 五组后处理有代码和证据 | 尚无直接 NAO typed 路径；同输入 NAO 实现间的比较不能由 IAO 回放替代 |
| [Engine/Version PLAN](2026-09-13-forge-engine-version-policy.md) | abacuslite 1.2.0 exact-extra；四类安装消费；限定双轨矩阵；完整 PyATB wheel 的两轨 Si band 消费 | 更广输入覆盖、后续版本采用各自验收；不重新要求已经通过的八格实算 |
| [Property manifest PLAN](2026-09-10-forge-property-manifest.md) / [旧 SPEC](../specs/2026-09-10-forge-property-manifest-design.html) | `property_manifest.py` 与 charge/spin/charge-diff post 投影已实现，PLAN 有 provisional 回归和复核记录 | 规范仍标 Draft；未找到 Paimon runtime 读取此字段的消费者；应先闭合可运行消费示例，而不是再次实现 builder |
| [Contract System Draft](../specs/2026-09-29-forge-contract-system-design.html) | 既有 `discovery.py`、request registry、typed metrics/artifacts 可复用 | M1–M4 尚未实施；草案有关覆盖/单位的部分断言已落后，不复制 JSON 默认值/正则目录 |
| [旧 BEC Draft](../specs/2026-09-29-forge-typed-bec-design.html) | legacy pack 有位移准备、通用执行、读取外部 `polarization.json` 的差分路径 | 不是完整原生极化链；单位、模量、坐标、分支与执行 owner 必须修订，尚无实施 PLAN |
| Paimon 迁移原 SPEC/PLAN | 最新 v2 能力、输入策略/ATP 归 Paimon，Forge 提供基元；W0 盘点完成，多项 W2/W3 局部消费已有记录 | W3/W4 整体未关闭；局部固定输入对比不代替原始任务入口的 demo/Benchmark |

Paimon owner 路径（相对本仓 canonical 根目录）：
`../app-tools-forge/toolbox/ABACUS/docs/superpowers/plans/2026-09-13-paimon-v1.3-forge-migration.md`
及 `2026-10-19-paimon-v1.3-benchmark-parity-plan.md`。
2026-10-21 核查至 `13c377d2d`：SCF/relax CoF3 固定输入能量对比通过；
Si band gap 实算通过，Fermi/VBM/CBM 事实仍 partial。旧“band canary blocked”
和“执行器尚未接线”只保留为历史，不重复列为待实现。

## 本轮裁决

- Ruling：兼容面按真实科学请求、下游产物和当前消费者判断；保留现有 demo/
  Benchmark 验收，不要求复刻两个旧包的全部内部接口。
- Ruling：历史 benchmark 调用、当前 v2 产品、当前 v3 是不同基线。当前 v2 已将
  `extra_input` 归属 modifier；回放历史 prepare 参数应转换到现有 modifier，
  不能仅删除科学控制，也不必为每组参数新建 profile。
- Ruling：CoF3 首轮重准备的输入差异只证明配置不同，尚未证明 Forge 的因果责任。
  固定输入可定位后端问题；包含 prepare 的最终任务仍须走实际任务入口。
- Ruling：直接 NAO 作为独立 `pyatb-cohp` capability，复用显式外部引擎交接，
  不改变 `cohp` 的 IAO 默认，也不把 PyATB 重建本征态说成读取原始 WFC。
- Ruling：Contract 元数据先落在现有 discovery；Property manifest 沿用现有
  diagnostics 增量。两者不引入 workflow、第二套 artifact identity 或查询 operation。

## 实施包

### Task 1：规范与完成情况核对

- [x] 主控读取上位 SPEC、owning PLAN 和源码，子代理独立核查迁移与 Forge 扩展。
- [x] 记录已完成、历史局限、当前缺口和并行 owner，避免按旧 checkbox 重做。
- [x] 更新导航，将原 Draft 与本轮有限授权/仍未决内容明确分开。

### Task 2：直接 NAO-COHP 的独立消费

设计见 [PyATB COHP 扩展](../specs/2026-10-21-forge-pyatb-cohp-design.md)。
实现复用 `OperationRef`、`ServiceContext`、workspace guard、LocalRunner、已有
PyATB 显式 handoff；允许按代码实际职责选择新模块，不复制科学算法。

- [x] 请求/准备：显式 STRU、HR/SR、ORB、k 点/权重、EF、选择器；冻结方法与单位；
  拒绝不支持的自旋、非法数值、路径越界、文件碰撞和不明确的 orbital 映射。
- [x] 执行/收集：一次本地进程，保留 stdout/stderr 和审计；拒绝覆盖已有 PyATB
  输出；显式收集 spectrum/meta，缺失/无效数据不能报告 complete。
- [x] Python/机器 CLI/schema/discovery 接线，保持 IAO 与 band 已有行为。
- [x] owning 回归、CLI parity、错误状态与不破坏源文件的验证；在可用时以既有
  矩阵和已构建 PyATB 包做本地消费回放，真实计算/安装证据不足时如实保留范围。

### Task 3：有限元数据与 manifest 消费

有限规范见 [metadata 与 manifest 消费 SPEC](../specs/2026-10-21-forge-consumption-metadata-design.md)。

- [x] 在现有能力发现中补直接 NAO 与 IAO 的方法/输入/结果约定，元数据引用现有
  request/default 定义；不实施旧 Contract System 的全量正则目录/M4 服务。
- [x] 沿现有 Property manifest PLAN 补一条可运行的 Python/CLI 消费示例，按
  `role/origin/spin` 与同结果 source refs 选择实际产物，并验证缺失路径处理。
- [x] 修订 Contract/manifest 文档状态和用户入口；不宣称 Paimon 已消费，不强迫
  当前 Benchmark 改用新的字段。

### Task 4：BEC 设计修订与上层交接

- [x] 新 Markdown 取代旧 HTML Draft 的活跃设计地位，保留历史正文与后继指针。
  明确 Å/Bohr、体积归一化、浮点极化量子、晶格/笛卡尔坐标、分支歧义与不完整张量。
- [x] 区分 Forge 可复用单元操作与调用方多阶段执行；保留需要用户判断的分支策略。
- [x] 在当前计划中交接 Paimon 参数映射/prepare 覆盖问题，不并发编辑其 runner。

### Task 5：集成检查与交付

- [x] 检查实际 diff、定向原始测试输出、文档链接；运行与变化相称的离线回归。
- [x] 对公共接口、路径/外部进程及数值 metadata 做独立终审，修复实质发现。
- [x] 更新本计划的完成记录和剩余工作，保留隔离工作树，不推送或发布。

## 分工、验证与恢复

主控拥有本计划、导航、设计裁决和最终验收。NAO executor 拥有新增能力实现及
对应注册/测试；文档 executor 拥有 BEC 设计及随后明确委派的历史文档/导航更新。共用文件/索引修改串行，子代理
不自行启动新的 reviewer 或提交。所有改动与基线 `f590367` 对照，已有用户改动
为零；Paimon 同期改动不是本轮作者资产。

Forge 测试使用 `conda run -n abacus-env env PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=src python -m pytest ... -p no:cacheprovider`。默认离线；
新增代码先有观察到目标失败的回归，再验证实现。源文件、CLI/schema 与
workspace/event 的关联覆盖按 `tests/README.md` 执行。

初始检查曾引用不存在的 `tests/test_pyatb_services.py`，pytest exit 4、未运行
测试；这是命令定位错误，不是基线代码失败。后续改用实际 owning 文件
`tests/test_pyatb_typed.py`。

## 完成记录

- 已实现 `pyatb-cohp` 严格请求、prepare/execute/collect、CLI/schema/discovery，
  保留现有 `cohp` 的 IAO 语义。新增 contracts map 限两个方法。
- manifest 消费示例已串起真实 legacy CLI post JSON 与 cube 读取，并覆盖
  source refs、缺失、移走和摘要变化，owning suites **43 passed**。
- 两轨 Si/nspin=1 源码 Forge + 已安装 PyATB 回放通过：各 801 谱点与既有
  原生基线最大差为 0，ICOHP 在 1e-10 对比容差内，三事件/输入摘要检查通过。
  详细范围、原始 requests/responses 和回放脚本见[本轮证据](../evidence/2026-10-21-forge-consumption.md)。
- BEC [后继设计](../specs/2026-10-21-forge-polarization-bec-design.md) 修正了原生输出、
  单位/体积与晶格方向解释；按本计划完成时仍是 Draft、尚无 typed 实现。该 SPEC
  后经确认并完成有界实现，结果见[BEC 实施计划](2026-10-21-forge-bec-implementation.md)。
- 独立审查发现 execute 日志路径父目录 symlink 越界及 nspin 浮点误接纳，
  均已修复；两项先观察到目标 RED，最终定向 **15 passed**。reviewer 已复核关闭，
  无未解决的实质发现。discovery operation 元数据改为引用 descriptor。
- 完整离线回归（上述两项修复前快照）**1503 passed、35 skipped、173 warnings**，
  exit 0；修复后的 15 项定向回归覆盖其变更面。35 skipped 为既有可选/显式门禁，
  不记作真实验收。未过滤第三方 warnings。
- 主控检查实际 diff、原始 RED/GREEN、CLI --help、两轨 response/metadata；
  217 个相对文件链接均可解析，`git diff --check` 通过。
  [源文件摘要](../evidence/2026-10-21-forge-consumption/candidate-source-sha256.json)
  绑定本轮 src/tests/example dirty 内容；原始测试日志随证据保存。
- 实施留在现有隔离工作树，未提交、合入 main、推送或发布；当前完成声明只覆盖
  本轮有界本地实现，不关闭下列后续事项。

### 仍开放的后续边界

1. BEC：有界设计与本地实现已完成；当前 fresh wheel 与 MgO 单列验证、敏感性和
   未覆盖范围由[安装/实算接续计划](2026-10-21-forge-installed-bec-validation.md)
   及[证据](../evidence/2026-10-21-forge-installed-bec-validation.md)维护。
2. Paimon owner：保持 demo/Benchmark 作为验收；历史 extra_input 等价转换、
   prepare 原始入口覆盖、band 边缘事实和 W3/W4 未完成项继续在原计划推进。
3. 新 NAO 能力当前 experimental；真实 nspin=2、更广材料、目标平台与新 NAO 原生组合的
   安装执行尚未覆盖；当前 Forge wheel 的安装态接口回归已由后继计划补齐。abacuslite 1.2.2 pin adoption 是独立版本更新任务，本轮未修改。
