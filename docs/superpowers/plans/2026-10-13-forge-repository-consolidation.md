# Forge 文档与代码体系整理实施计划

状态：首轮已完成并独立审查，2026-10-13 用户要求进一步推进后已快进合入本地 main；后续消费者调查与收口见文末。用户已确认设计取舍并要求以 subagent-driven-development 推进；本计划承接该授权。

设计：[文档与代码体系整理](../specs/2026-10-13-forge-repository-consolidation-design.md)。目标为英文产品 README、中文详细文档、明确的内容归属，以及保留公开行为的加载、能力映射、公共算法和测试分类收敛。

隔离工作区：`/home/james/.codex/worktrees/7037/abacus-forge`；分支 `codex/forge-repository-consolidation-20261013`；实现基线 `5c978b0c88b0654dc0a03e43f93eee4e42a72441`。首轮将已审阅的设计与导航复制进隔离工作区实施；后续本地主线集成另行记录。

基线证据：同一源码/环境的默认离线回归 `1437 passed, 34 skipped in 100.60s`；收集 `1471` 项，其中 `615` 项无 portfolio marker。基线证据来自本轮审查的实际命令输出，复用而不伪造 RED。

## 实施边界与协作

- 保留公开导入路径、CLI 命令、参数默认值、能力覆盖、request/result/error、资产和 workspace 审计语义。默认依赖不在本批移除或转为 extra；候选单列。
- 多调用面按适用范围整理，不把 legacy/unit/sequence 自动改为 typed 行为，不实施 Contract System 或 BEC 草案。
- 同一隔离工作区内分配互不重叠的写入范围；子代理不提交、不操作共享 index、不再派生代理。控制器统一记录、审查、验证和提交。
- 子代理修改前均以计划建立后的干净提交为 BASE；完成后停止所辖写入，控制器检查完整 dirty diff（包含新增文件）。最终独立审查绑定控制器提交的完整基线到候选范围。

### Task 1：产品入口与使用文档

- [x] 将 README 改为简洁的英文产品入口，保留安装、最小可运行示例、能力成熟度与中文文档导航。
- [x] 建立 `docs/README.md`、`docs/guide.md`、`docs/reference.md`，分别承担导航、任务使用路径和接口/产物参考；搬迁现有有效细节，保留必要旧锚点导航，避免全文复制到多处。
- [x] 说明 typed operation、primitive、UnitSpec、task/sequence 与 packs 的差异及适用场景；示例不得提升成熟度或暗改资产/状态语义。

Ownership：文档作者仅写上述四个文件。控制器负责 architecture/governance/roadmap；测试作者负责文档示例测试。文档作者与测试作者约定 `docs/guide.md` 的 `## Agent-first CLI` 保留两份现有 execute JSON 示例，README 可使用独立的最小 smoke 示例。

验收：检查新旧 README 内容去向、相对链接和旧锚点；文档示例继续经真实 CLI 解析/执行既有 dry-run 边界，相关 `--help` 可用。纯文案不造行为 RED。

### Task 2：包加载与共享能力映射

- [x] 使基础 `abacus_forge.input_io` 导入不加载无关 service/engine/科学库；根包既有 122 项公开导出保持可获取、对象身份与导入路径兼容。
- [x] 收敛 discovery 与 machine CLI 的 capability/request 映射，保持 discovery JSON、schema、解码、错误优先级和 service 路由行为；只使用相称的静态映射，不引入插件框架。
- [x] 增加有独立保护价值的导入隔离/导出兼容回归，观察加载隔离的基线失败；已有机器面回归用于行为保持对比。

Ownership：`src/abacus_forge/__init__.py`、`discovery.py`、`machine_cli.py`、必要的小型静态映射模块与 `tests/test_imports.py`；不得写 `tests/test_architecture.py` 或 docs。测试文件自行声明 `core` marker。

验收：导入隔离在子进程中检查；全部旧导出与原对象相同，重复/并发基本导入正常；capabilities/schema 输出与基线等价；`tests/test_machine_cli.py`、`tests/test_cli_process.py`、相关 machine/contract suites 通过。源码包布局与 wheel 导入由控制器验证。

### Task 3：公共 band 后处理归属

- [x] 将 typed 与 legacy 共享的表格输出/绘图及能带前缀识别归入中立模块，两个调用面复用同一实现。
- [x] 保留 legacy 私有入口必要转发、函数签名与默认行为；显式 typed 路径不再从 legacy unit 模块借用实现。
- [x] 复用现有后处理、API/unit 回归建立基线/候选等价；必要时补混合列布局和默认输出的独立行为断言。

Ownership：`src/abacus_forge/band_data.py`、`unit_postprocess.py`、`postprocess_algorithms.py`、必要的中立 band 输出模块及 `tests/test_postprocess_algorithms.py`。不得修改 CLI、包入口和其他测试作者所辖文件。

验收：`tests/test_postprocess_algorithms.py tests/test_postprocess_services.py tests/test_postprocess_machine_cli.py tests/test_units.py tests/test_tasks.py` 通过；能量列、默认文件内容与可选图行为保持。不以删除测试或放宽预期获得通过。

### Task 4：测试分类与验收入口

- [x] 补齐 portfolio marker 归类；已有保护保留，默认仍隔离 benchmark/real_smoke，新增未归类文件应能暴露而非静默遗漏。
- [x] 更新 `tests/test_architecture.py` 的文档行为测试读取位置，保留真实 CLI 校验；配合 Task 1 的示例搬迁。
- [x] 整理中文 `tests/README.md` 与 `tests/real_smoke/README.md`，保留有效命令/环境/证据范围，纠正旧版本问题归因并链接证据。

Ownership：`tests/conftest.py`、`tests/test_architecture.py`、上述两个测试 README；确需验证选择行为时可新增小型 owning test。不删除或合并原测试。

验收：收集的每项适用测试有 portfolio marker；正向 marker 选择覆盖对应文件，默认 real_smoke/benchmark 仍跳过。旧示例行为验证继续通过；执行无真实集群访问。

### Task 5：架构、文档治理与最终集成（控制器）

- [x] 建立中文 `docs/architecture.md`，映射现行职责/代码/参考/扩展与测试定位。
- [x] 收敛 AGENTS、ROADMAP、`docs/superpowers/README.md`：Markdown 新规范、有效设计/草案/历史导航、当前专项入口及独立可废弃候选；保留上位规范地位和历史证据。
- [x] 检查已知本仓和跨仓 README 链接，保留兼容锚点；标明旧 I/O Draft 与 Contract System Draft 的关系，不把独立草案修成批准设计。
- [x] 统一检查各包完整 diff、文档链接和示例、架构与契约/workspace 门禁、默认全量离线回归、wheel/公开导入检查。
- [x] 冻结候选，独立整体审查，处理真实发现并复验；记录结果和剩余候选，保留工作区交付。

当前环境可用 `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider`。全量测试统一由控制器在包集成后执行；各包先运行上述 focused suites，日志路径与实际结果回报控制器。文档验证按现有可执行检查或直接链接/锚点检查进行，不增设文档框架。

## Rulings 与进展

- Ruling：保留默认依赖和所有现有调用面，仅列出可废弃候选 — 本轮批准的是兼容收敛 — 若遗漏实际安装/调用依赖，会破坏上层消费。
- Ruling：先完成可独立验证的加载、映射和 band 共享代码整理，不批量重排全部生产目录 — 以降低实际耦合为目标 — 大范围移动会增加导入路径与跨仓迁移成本。
- 初始化：原工作区已有设计未提交，复制到隔离工作区纳入本任务；子代理分配前由控制器建立干净恢复点。

## 验收记录

实现与测试候选为 `edf3f3c1d15fafa3e9314b86519ffd711c80d8d4`。独立终审绑定 `5c978b0c88b0654dc0a03e43f93eee4e42a72441 → edf3f3c1d15fafa3e9314b86519ffd711c80d8d4` 的完整 24 文件 diff，结论：未发现重要问题。后续收尾提交仅更新本计划及导航/路线图状态。

| 检查 | 实际结果与范围 |
| --- | --- |
| 导入隔离基线 | 原实现运行新用例有 2 项预期失败；候选 4 项导入用例通过。原 122 个根包导出名称/顺序/对象来源、26 份 request schema、capabilities 与冻结基线等价。 |
| 导入/发现 owning suites | 497 passed；涉及 machine/CLI process、各 typed decoder 与 contract。静态映射归入 `request_registry.py`，未引入插件框架。 |
| Band owning suites | 原测试基线 53 passed；新增混合前缀/legacy 默认/typed 能量轴刻画在原实现也通过，候选 54 passed。公共实现归入 `band_postprocess.py`；补充架构检查，禁止 typed/shared 后处理依赖 legacy unit。 |
| 测试组合 | 收集 1476 项，正向 portfolio marker 并集覆盖相同 nodeid 集合，缺口为 0。未归类 probe 按预期 collection error；选定真实/benchmark 测试默认 12 skipped；双轨发布显式环境门禁在缺矩阵时按预期失败。未删除/合并测试。 |
| 默认全量离线回归 | `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider` → **1442 passed, 34 skipped in 105.44s**。包含 contracts/workspace、架构、API/CLI/result 与新增导入回归。 |
| wheel 元数据 | 本地 `pip wheel --no-deps --no-build-isolation` 构建；提供 `ABACUS_FORGE_WHEEL` 后 package contract/metadata drift suites → **16 passed**。默认依赖与 optional extra 未改。 |
| 安装后消费 | 新 venv 无依赖安装 wheel 后基础 I/O 可导入、未加载科学库；另一隔离 venv 复用 paimon 的科学依赖，122 项公开导出和 console capabilities/operation help 通过，确认导入来自该 venv。此项不声称重新安装了全部第三方依赖或验收 abacuslite extra。 |
| 文档与导航 | 独立文档复核修正了遗漏示例、详细说明语言及 cwd/workspace 两级路径。相对链接/锚点检查通过；AGENTS 的工作区上级入口按原工作区解析。未发现已知 app-tools-forge 文档对旧 Forge README 锚点的引用。 |

运行日志保存在执行机 `/tmp/forge-consolidation-full.log`、`/tmp/forge-consolidation-install.json`、`/tmp/forge_task2_{red,owning,final_imports}.log`、`/tmp/forge_task2_{baseline,candidate}.json`、`/tmp/forge-task3-{baseline,newtest-baseline,candidate-final}.log`。这些临时日志不是永久发布工件；上表记录本批范围与实际结果，历史 real-smoke 证据不被改写成当前候选的真实运行验收。

本批没有执行真实 ABACUS/集群任务，也没有晋升 capability 成熟度。可安装 parser extra、真实 NEB、BEC/Contract System 草案与 Paimon 全链路迁移仍由原 owner 文档维护；它们不阻断本次兼容整理。


### 最终冻结与复验

- 独立文档 reviewer 复核了中文正文、补回的 CLI/Python 示例、两级路径与规范状态；独立 final reviewer 复核了公开导入兼容、映射/错误顺序、band 输出、测试门禁与整体边界。无未解决的重要发现。
- 最终文档检查：13 份改动文档、153 个相对链接/锚点，0 错误；10 个 Python 代码块语法通过；`tests/test_architecture.py` 在最终示例上 **8 passed in 6.05s**。
- 在冻结候选重新构建 wheel：`abacus_forge-0.1.0-py3-none-any.whl`，SHA-256 `e43f34889409f9814327bd4acba9d831edac9e1df532112eef1b04a35e4120fb`。该最终 wheel 的 package suites 再次 **16 passed in 0.10s**，无依赖 I/O 和复用科学依赖的独立 venv 安装检查再次通过。命令/原始输出见 `/tmp/forge-consolidation-wheel.log`、`/tmp/forge-consolidation-wheel-tests.log`、`/tmp/forge-consolidation-install.json`。
- 首轮验证后的代码、测试和示例未再修改，收尾提交只更新完成记录；当时保留原工作区设计草稿，尚未合并。后续合入状态以下节为准。

### 后续推进：本地主线集成与候选调查

授权来源：用户在首轮交付后要求“进一步推进”。本步完成本地主线收口与可废弃候选的证据核对，沿用公开行为和默认依赖保持的设计。远程发布、改变安装依赖、删除兼容 API、实施独立草案均不在此步内。

- [x] 确认原工作区 main 仍为 `5c978b0`，两份未提交设计材料与 `84a46a1` 中的版本逐字一致。将原文件、tracked patch 和恢复说明保存在 `~/scratch/abacus-forge-pre-integration-5lk08tx1/`，再快进至 `1503d0b484d4a382a0c8701f74c37ebeb7b83ba5`。没有覆盖未识别的用户变更。
- [x] 在原 main checkout 执行 `tests/test_imports.py tests/test_architecture.py tests/test_contracts.py tests/test_workspace.py`：**350 passed in 12.07s**，命令前缀为 `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider`，原始输出见 `/tmp/forge-consolidation-main-integration.log`。相对链接/锚点检查仍为 153 项、0 错误。
- [x] 确认集成后的生产代码、测试、包声明、README/用户示例相对完整验证候选 `edf3f3c` 无 diff，复用 1442/34 的全量离线及最终 wheel 证据，不将 focused 回归称作新一次全量运行。
- [x] 核对默认依赖和两个兼容 API 的已知消费者，在 ROADMAP 中写明处置及下一步触发条件。
- [x] 独立复核后续三个文档的完整 delta：无重要问题；完成记录随本次收尾提交快进合入 main。调查补充后本地链接/锚点检查为 160 项、0 错误。

隔离分支与受管理的 worktree 继续保留；不清理其他历史工作区，不推送远程。

调查绑定：Forge `1503d0b`；只读 Paimon `app-tools-forge@da25adf2127a92139436f26075e0f4f937b185c6` 的 `toolbox/ABACUS`。两位子代理分别核对依赖和兼容接口，控制器复读实现、调用测试与 W3 安装记录。最终处置统一维护在 [ROADMAP 候选表](../../../ROADMAP.md#可废弃与依赖调整候选)。

- `suppress_legacy_events` 无本仓调用，但有可观察的 prepare/modify 事件抑制行为；`claim_v1_operation` 是少量代码的兼容转发。保留两者，避免用接口破坏换取有限的行数减少。
- `dpdata` 在 Forge 生产源码未发现静态/动态使用，上层有真实使用。Paimon v1.2 的 abacustest 安装链与依赖声明不能证明 v1.3 W3 已独立承接它。已核对 W3 报告中的 Forge wheel 等解析入口和历史 clean-route lock；锁中存在 dpdata 只能证明该历史环境安装了它，不能证明依赖所有权或当前 kit 安装闭合。
- Ruling：下一批优先解决 dpdata 的安装责任与候选验证，再决定 Forge 默认依赖调整；matplotlib/pymatgen 的 extra 拆分须有明确使用需求 — 当前绘图默认值和结构元数据会受影响 — 静默拆分会改变用户安装后的能力。
- 后续只变更三个文档的状态与调查结论，生产代码、测试和包声明保持冻结候选一致。

### 推送前收尾（用户确认继续，2026-10-13）

工作流：L3，沿用既有隔离分支，起点 `c2f83c1`。用户确认此前建议的前三项，并顺带整理包简介。范围为历史材料、通用测试与 Python 3.10 测试兼容、示例说明及包元数据；CI 仍为后续事项，本步不推送远端。

- [x] 历史材料：将 Git 跟踪的 27 份 SDD 记录、3 份 Trae 审查材料及旧 AiiDA 评审归入 docs/archive，保留原始证据/原路径线索；修复已知导航和引用，忽略今后的工具临时状态。已批准 SPEC 的地位不变。
- [x] 测试与包：补通用 venv / dev 安装与测试入口；对 Python 3.10 无 tomllib 的收集失败建立真实基线，再以条件 dev 依赖和兼容读取修复；保留运行时最低版本及默认科学依赖。包简介改用当前操作名称并补官方仓库链接。
- [x] 示例：说明 NiO 输入、外部 PP/ORB 及 SAI Slurm 脚本边界；补可执行的本地 prepare/dry-run 路径，保留被结构测试使用的 STRU。
- [x] 控制器完成导航整合、历史材料完整性与链接检查、Python 3.10/当前 Python 的相称测试及包构建验证、独立复核和本地主线收口。

分工：历史材料作者仅改原始历史文件、docs/archive、.gitignore 和必要历史引用；测试作者仅改 pyproject.toml、tests/test_package_contract.py、tests/README.md；示例作者仅改 examples 下说明及 docs/guide.md 的示例导航。控制器拥有 AGENTS、README、docs/README、docs/superpowers/README、本计划和统一提交。所有作者不得提交、操作共享 index 或再派生代理；共享工作区内不覆盖其他人的修改。


#### 本批验收记录

- 归档：控制器以 `git show 15ab407:<原路径>` 对照新路径文件，31/31 逐字节一致；三份原始 NiO 文件同样一致。归档索引保留旧路径到新路径的映射，历史命令和报告不重写；工具临时目录忽略规则有效。
- Python 3.10：在全新 Python 3.10.20 venv 中，修复前 package 测试收集以 `ModuleNotFoundError: No module named 'tomllib'` 失败（exit 2）。补条件 `tomli` dev 依赖与兼容导入后，`pip install -e '.[dev]'` 成功，`pip check` 无冲突。直接使用的 `packaging` 同时纳入 dev 声明，默认运行依赖和 Python 最低版本保持原样。
- 默认全量：该 Python 3.10 环境执行 `python -m pytest -q`，**1442 passed, 34 skipped in 97.27s**（exit 0）。跳过项仍是显式门控的 benchmark/real_smoke 与未提供 wheel 的检查；没有运行真实 ABACUS 或集群任务。
- wheel：隔离构建生成 `abacus_forge-0.1.0-py3-none-any.whl`，SHA-256 `2ae609f7045cce5885ca3594e3e08e4e49e836dd099caa131f3e737c5b8d4eee`；以 `ABACUS_FORGE_WHEEL` 指向该文件，Python 3.10 的 package contract/metadata drift 为 **16 passed**，现用 paimon Python 的相同检查加 architecture 为 **24 passed**。额外核对 wheel URL 及 dev marker：仅 Python <3.11 引入 tomli，运行依赖未改变。
- 示例：文档中的 prepare 返回 `prepared`，typed execute dry-run 返回 `execution=skipped`、`scientific=unassessed`，exit 0；原结构 owning suite 为 **57 passed**。示例明确资源占位符、原始 INPUT 不被自动复制，以及 SAI 脚本的站点边界。
- 导航：本轮累计改动的 15 份当前文档检查 173 个本地链接/锚点，0 错误；31 份原文归档按完整性验收，不将其历史路径改写成当前上下文。`git diff --check` 通过。

证据位于执行机 `/tmp/forge_package_py310_{red,editable,green,pipcheck}.log`、`/tmp/forge_package_current_green.log`、`/tmp/forge-prepush-py310-full.log`、`/tmp/forge-prepush-wheel.log`、`/tmp/forge-prepush-wheel-py310.log`、`/tmp/forge-prepush-current.log` 及 `/tmp/forge-archive-move-manifest.json`。示例与 structure 的原始输出由作者工具返回并交给控制器复读，未额外落盘；临时日志不是永久发布工件。本批不新增持续集成服务或文档框架，后续依赖调整仍按 ROADMAP 候选独立处理。

独立终审绑定 `c2f83c1ebcef2afbaff38323d8f4b5f8aac5a7fd → a68728c49cd61c9ee5cd8825fdf540fad29ba7a4` 的完整 42 文件变更，结论为无重要问题。原工作区 main 已从 `c2f83c1` 快进至 `a68728c`；工作树干净，与已验收候选树一致，主线文档检查仍为 173 个链接/锚点、0 错误。复用同一代码/测试/包声明的全量与 wheel 证据，不重复运行无变化的回归。后续提交仅补记本段完成状态并快进合入；隔离分支及受管理工作区保留，未推送远端。
