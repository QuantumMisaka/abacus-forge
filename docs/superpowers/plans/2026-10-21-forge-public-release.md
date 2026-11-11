# Forge 独立公开交付与工程化收口计划

状态（2026-11-11）：Task 1–9 已完成实现与验收；Task 6 和候选 `c65931d` 的远端四版本矩阵通过。Task 10 剩余主分支集成、owner 版本/tag 决策与授权发布；实际 PyPI 发行未执行。证据见[工程化切片记录](../evidence/2026-11-11-forge-public-engineering-slices/README.md)。

规范为[公开交付设计](../specs/2026-10-21-forge-public-release-design.md)与[收缩设计](../specs/2026-10-29-forge-computation-factory-target-architecture-design.md)。工程化候选基线：`QuantumMisaka/abacus-forge` branch `codex/forge-public-engineering-20261111@c65931d`，package `0.1.0`。本地新 wheel 与三类展开验收见[证据](../evidence/2026-11-05-forge-task-expansion/README.md)。

## 初版交付记录（已完成）

原来源：用户要求按首版建议推进，强调架构、完整性、方法和体验。原基线 `42c23a4`；分支 `codex/forge-public-release-010`，工作树 `forge-integration-reference-review`。这些路径和分工仅记录当时实施，不作为接续工作的 checkout 指令。

### Task 1：诊断和版本入口
- [x] 实现独立只读 doctor / --version 与人读、JSON 输出，缺程序/文件可操作提示。
- [x] 行为回归先验证缺口，覆盖无引擎正常、显式缺项、只读和安装态 CLI；保留既有调用行为。

### Task 2：人类与 Agent 上手
- [x] 用公共 API/CLI 提供自包含免引擎路径、真实 SCF 操作方法和 Agent 消费示例。
- [x] README/指南明确推荐入口、资产、状态和支持范围；补公开兼容说明。
- [x] clean wheel 环境实际跑文档/示例；验证错误与 partial，不依赖本机绝对路径或 PYTHONPATH。

### Task 3：发行管线
- [x] tag/成功 CI run/制品身份验证与 PyPI OIDC 发布工作流；发布说明和维护者 runbook。
- [x] 构建与 metadata 校验、发布验证器负向回归、CI 检查；查询外部配置，先完成本地可审阅结果。

### Task 4：整体交付
- [x] 完整离线回归、两版安装态与用户路径，独立审查并解决实质问题。
- [x] 集成与远端 CI，形成具体发行候选；不覆盖并行 owner 状态。
- 延后（用户本轮明确要求）：PyPI 账户配置与实际发布、发布后 fresh index install。本轮完成其余配置、实现与验收，不以此声称 PyPI 已上线。

任务分工：诊断 worker 仅 doctor/CLI 与 owning tests；用户路径 worker 仅用户文档/示例/用户路径 tests；发布 worker 仅 release workflow/验证器/发布文档与测试。主控维护规范、计划、索引、项目元数据及 CI 集成，并负责审查、构建和发布动作。共享 Git index 仅主控操作。

验收记录见[本轮证据](../evidence/2026-10-21-forge-public-release.md)。独立终审已完成，legacy/typed 状态说明差异已修正。GitHub `pypi` environment 与 `v*` tag policy 已配置；不触发发行。

实现 `cc68920` 已通过四矩阵远端 CI，并由 [PR #8](https://github.com/QuantumMisaka/abacus-forge/pull/8) 合入 `main@93cd2cc`。源码与安装态结果见[验收记录](../evidence/2026-10-21-forge-public-release.md#远端集成)。本轮实现及其余配置已完成；PyPI 延后项保持开放。

<a id="工程化接续待实施"></a>

## 工程化接续（Task 10 待完成）

### Task 5：执行生命周期

- [x] 在既有 `runner.py` 内修复已复现的 timeout 后 launcher 后代残留，并核对中断退出；限定受控执行树，不误杀无关进程，不引入调度或自动重试。
- [x] 用会派生子进程的受控 executable 验证：失败状态及日志可读、操作返回后旧子进程不再写结果，原执行清理后才允许后续消费/重试；覆盖直接 runner 和新单元入口。
- 验证入口：runner、workspace、service 和 composite plan 的 owning tests；真实 Slurm allocation 不作为此项前置。原始问题见[架构审查 F1](../evidence/2026-11-05-forge-architecture-replacement-audit/README.md#本轮发现与处置)。

### Task 6：把新增消费面纳入持续验证

- [x] 修正默认 `[dev]` 安装时 optional phonopy 测试的缺依赖处理；已发现 `test_phonon_cli_and_python_preserve_angstrom_geometry_and_harmonic_response` 在 `importorskip` 前导入 optional 模块。
- [x] 在现有 `.github/workflows/ci.yml` 中覆盖默认安装及含 phonon extra 的真实科学库路径；installed-package 加入三类展开和共享单元消费测试，保留现有 parser/包/上手验收。
- [x] 对当前声明的 Python 矩阵验证实际可安装组合及调用行为；不能用源码 job 跳过 phonopy、安装态 job 不选择展开测试的组合宣称声子已通过 CI。
- 验证入口：三类 expansion tests、`test_composite_plan.py`、既有安装态包/CLI 与 release matrix tests。本地先重放变更的安装组合，远端 CI 在 Task 10 对正式集成候选运行。

### Task 7：外部 Agent 能找到并消费任务展开

- [x] 将 `docs/agents.md`、compatibility 和已有 CLI/discovery 说明对齐：typed operation 与 composite 单元入口分别准确描述，不把新增能力藏在“legacy 不推荐”之后。
- [x] 提供一个只消费公开 API/CLI 的声子或振动展开示例，包含独立执行/采集、乱序汇总、缺失项和指定单元重试；免引擎版本明确使用受控 executable。
- [x] 核对现有机器发现是否足以指向真实入口。若需要扩展发现字段，先在原公开交付 SPEC 写明兼容字段与可运行调用样例，再实现；不预设新 schema/registry，也不伪报 typed operation 已支持。
- 验收：新 wheel、独立工作目录中，按公开说明完成清单→单元→显式汇总→CPU 分析；旧机器请求/结果和 CLI 退出语义不回退。

### Task 8：收窄发行内容

- [x] 在 `pyproject.toml` 及必要构建配置中明确 wheel/sdist 内容。当前 `82af7d5` sdist 带入 1202 个 evidence 文件和 10 个 `.scratch` 文件；排除无关历史过程材料，不删除仓库中的验收记录。
- [x] 保留源码构建、包契约检查与公开示例实际读取的文件，尤其 optional parser provenance、测试 fixture 和用户文档；不能整体排除 evidence 后破坏现有 package tests。
- [x] 从 sdist 重建 wheel，在新 venv 验证 metadata、`pip check`、公共导入、文档示例及新增单元消费；检查压缩包实际清单。
- 范围：不趁打包收口移除 dpdata 等既有默认依赖，也不自动升级已验收的 optional pin。

### Task 9：独立贡献入口

- [x] 增补简短 `CONTRIBUTING.md`、issue/PR 模板；复用 `tests/README.md` 解释按变更选择测试、失败复现和审查证据。
- [x] 仓库 `AGENTS.md`、开发命令和示例在独立 clone 中成立，不要求私人 Skill 或父 workplace；跨仓对拍与真实引擎按需启用。`c65931d` clean clone 使用公开依赖完成 focused 测试、composite 示例、CLI discovery 和 `pip check`，见工程化切片记录。
- [x] 核对复用实现、示例与 fixture 的来源/许可记录，修正实际缺失；不凭 legacy 名称删除已有功能，不引入无实际维护需求的治理层。
- 验收：仅本仓与公开可安装依赖完成基础开发和用户示例；文档链接、CLI 示例与当前接口一致。

### Task 10：候选集成与实际发行

- [ ] Task 5–9 完成后做相称回归与一次整体独立审查，经仓库协作流程集成并跑完整远端 CI；记录实际 commit/run/artifact。
- [ ] Owner 决定既有 `v0.1.0` 之后的发行版本/tag；选择后再更新版本和发行手册，不默认改指已有 tag。
- [ ] 复用已测试制品的发布管线；当前拒绝 rerun 的行为继续生效。只有确认需要支持正常 rerun 时，才实现并验证 attempt/artifact 的准确归属，不能单纯删除校验。
- [ ] 在明确发布授权和账户配置具备后上传 PyPI，再从公开索引新建环境安装、验收并保存发布证据。

Task 5–9 可按独立写集安排，但 Task 7 的安装消费需覆盖 Task 6/8 的实际包；Task 10 依赖前述完成。Paimon 接线、全量 Benchmark 与真实平台资源不是这份 Forge 工程化计划的完成条件，也不由本计划宣称已完成。

## 参考仓与外部责任

参考更新按需 fetch/比较后再采用，不批量 pull 或覆盖冻结验收提交。Paimon 开发前先同步其最新 v2 基线，在 migration checkout 合并；引擎参考区分发布线与 develop，浅克隆先查历史完整性。abacuslite/PyATB/ATST 的参考刷新与 runtime pin 升级分别验收；abacus-agent-tools/abacus-test 保留旧对照提交；历史 AiiDA 原型不恢复为活动依赖。参考刷新不新增全工作区 lock、统一 identity 或自动升级策略。

Paimon 后续优先以声子接通 CPU 准备→独立计算单元→CPU 汇总，再复用到振动与弹性；Forge 13 单元弹性与 Paimon 25 单元方法不能默认等价。平台 allocation、算法对拍及 Benchmark 由其 owner 在最新候选上验收。

## 2026-11-05 文档收口记录

本轮按用户要求修订两份现行 SPEC，沿用本 PLAN 承接工程化事项；SCF、任务展开、Phase A 撤回、矩阵修复及已有基础实施明确结项。导航和 ROADMAP 删除过时的当前候选/Paimon 分数；三份退役 HTML 移入历史归档并保留旧路径指引，property manifest 的实际行为继续保留。

同家族独立文档审查未发现架构或契约阻断，指出两项轻微问题：旧章节链接失效、13/25 单元主语歧义；已恢复旧锚点并明确 Forge/Paimon 归属。Markdown 链接检查 2 passed；6 个迁移 HTML 的 60 个本地链接/锚点通过，归档正文与原版本比对一致（仅增加状态提示、重定位链接）。运行代码、测试、依赖、CI 和既有运行证据未改；Task 5–10 的实施状态保持未完成。
