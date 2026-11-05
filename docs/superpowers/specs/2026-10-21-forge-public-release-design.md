# Forge 首个公开发行版与用户入口设计

状态：依据用户确认的交付方向实施。2026-10-21 用户要求推进可 pip 安装、面向人类和通用 Agent 的独立交付，特别关注架构、功能完善度、使用方法与体验。

2026-11-05 文档接续：doctor、初版用户入口和发行管线已完成，状态见[原计划](../plans/2026-10-21-forge-public-release.md)。本修订将独立消费与社区维护要求纳入同一设计；接续开发仍是待实施事项，不以文档修订宣称已完成发布或改写旧制品证据。

上位规范：[契约优先](2026-09-01-forge-contract-first-rearchitecture-design.html)、[Service/Status](2026-09-02-forge-service-status-migration-design.html)、[Engine/Version](2026-09-12-forge-engine-version-policy-design.html)。本设计只补产品入口、环境诊断和发行，不改变单次 operation、workspace 或科学判定职责。

## 产品与接口

- 当前 package 为 0.1.0，首版面向 early/experimental 使用；不把首次发行等同于全部科学能力 stable。既有 v0.1.0 tag 绑定旧候选，后继版本/tag 由 owner 在发行前选择，不通过文档更新或默认移动 tag 改变发布身份。
- 人类推荐现有 prepare/execute/collect CLI 及同名 primitive Python API；通用 Agent 推荐 capabilities → schema → operation 的 typed JSON CLI，同一 typed service 可直接用于 Python。高级 unit/sequence/pack 保留，不在入门路径要求用户先理解所有历史抽象。
- 不删除有实际消费者的旧接口，不静默迁移默认行为。机器发现应准确表明实际调用面；已有 composite 任务展开先按其公开 CLI/API 消费，不能在 typed discovery 中虚报尚未实现的 operation。需要新增发现字段时在本设计补齐具体字段和调用样例，再做兼容实现；不重建平行 registry。既有 v1 envelope、退出码和 append-only events 保持。
- 向用户明确兼容承诺：0.x 中 patch 不故意破坏已文档化请求/结果；需要破坏性调整时通过 minor/schema 版本与迁移说明处理。experimental 指能力覆盖，不代表任意改变已公开契约；科学接受始终由调用者决定。

## 易用性与完整任务

- 提供安装后的自包含、免引擎入门：用户复制指南命令即可建立小结构、prepare、dry-run，检查生成文件和明确的 skipped/not-run 状态。示例不得依赖本工作区、源码 PYTHONPATH 或 SAI 路径。
- 真实 SCF 路径由用户显式提供 executable 与 PP/ORB；说明每一步产物、资源选择和常见错误。免引擎示例不能假造真实引擎结果。
- Agent 教程展示能力/schema 读取、唯一 operation_id、cwd/workspace-relative 路径、成功/partial/前置条件失败的处理；不以 exit 0 或 scientific=unassessed 代替任务完整性检查。
- 外层示例脚本只消费公共 API/CLI，不把示例的步骤编排放进 Forge core；无需新增 workflow framework、MCP、TUI 或 Paimon 适配。

## 环境诊断

现有只读 `abacus-forge doctor`（人读默认，`--json` 提供机器报告）和 `--version` 继续保留。诊断信息独立于 operation outcome，schema 为 `forge.environment/v1`。

- 检查当前 Python/发行包、默认依赖版本与可发现性；默认不要求 ABACUS/PyATB/ATST，保证离线使用成立。
- 显式 `--executable PATH_OR_NAME` 检查调用方给定程序可执行，重复 `--asset PATH` 检查文件可读；不启动程序、不下载资源、不写 workspace。
- 报告存在/缺失、已观察的路径及可操作建议。只有显式要求或核心依赖缺失使返回码为 3；参数错误为 2，正常检查为 0。
- 程序可发现不等于可运行、ABI 相容或科学输入正确，文案和字段明确这一边界。若现有 CLI 的 eager imports 阻碍缺依赖诊断，采用薄 stdlib 入口路由，保持原有 cli.main 和全部旧调用兼容。

## 发行

- 现有 CI 继续生成并测试 wheel/sdist。发布管线绑定选定 tag 与成功 CI run 的源码身份，消费其已测试制品，不在 publish job 悄悄重建。
- PyPI 使用 Trusted Publishing/OIDC，权限只给发布 job；不把 token 放进仓库。发布说明包含范围、已知限制、安装与版本说明。
- 原实现轮中用户明确“先做好别的配置，pypi稍缓”；其授权范围已经完成。当前实际上传仍需 owner 的发布授权；历史 tag/CI 不证明后继代码已验收。
- PyPI 发布后以新环境从索引安装，并复验版本、doctor、capabilities/schema、免引擎用户路径。

## 独立消费与社区维护

- Forge 自身的执行生命周期应能处理受控 launcher 子进程的超时与中断，保留真实失败状态；这不要求平台 allocation、后台服务或自动重试。当前已登记的 timeout 后代残留由接续计划修复。
- CI 区分默认安装与 optional extras，确保实际宣传的声子/弹性/振动路径在带真实科学库的安装态受测；缺依赖不能通过跳过整条专项来冒充能力验收。矩阵范围沿用项目支持声明，不另建重复门禁。
- wheel/sdist 明确包含源码、许可、必要文档、示例、测试及其实际读取的 fixture/provenance；历史过程日志和 scratch 不默认成为发行内容。收窄打包不能破坏源码构建或既有包验收。
- 外部贡献者能只 clone 本仓、安装开发依赖并完成基础检查；仓库 AGENTS、贡献指南及用户示例不以父 workplace、私人 Skill、SAI 或公司账号为前置。跨仓对拍和真实引擎测试仍按需显式启用。
- 维护简短贡献指南、问题/PR 入口与复用代码/数据来源；已有测试分类和兼容约定继续作为依据，不增设委员会、全库重写、插件框架或强制统一资源模型。
- 软件接口兼容承诺和科学验证范围分别描述。已有科学片段通过就保持其证据范围，全面 Paimon 替代与所有物性验证不阻塞有界 Forge 发行。

## 验收

1. 对项目声明支持的 Python 版本（当前 3.10/3.11/3.12/3.13），源码及安装态 CI 覆盖相应交付能力；本地单版本成功不冒充完整矩阵。
2. 人类和 Agent 两条入门不需源码 checkout，可验证行为与文档一致；缺资产/缺程序/partial 等场景有明确处理。
3. doctor 只读，JSON 可解析，缺项不被当成已就绪；对关键缺项有行为回归。
4. 原有请求、结果、默认 parser 和科学边界无回退；新文档不用内部迁移史作为使用前置。
5. 发布身份核查与拒绝错误 run/tag 的验证通过；公开发布状态按真实外部结果记录。
6. 三类任务展开能从公共说明找到正确调用面；安装态示例实际消费单元结果，包含缺失/失败处理；不依赖私人工作区。
7. 发行清单排除无关 scratch/过程材料，并保留重建及必要验收资产；贡献者能在独立 clone 中复现基础检查。

发布验证器目前拒绝 `run_attempt > 1`；是否改为精确绑定 attempt/artifact 仍为待评估改进，未实施前继续遵守现行[发行手册](../../releasing.md)。本设计不预先批准某个后继版本，也不要求为了简化流程撤掉已测试制品的来源核验。
