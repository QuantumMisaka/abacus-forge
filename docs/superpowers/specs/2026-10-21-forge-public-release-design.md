# Forge 首个公开发行版与用户入口设计

状态：依据用户确认的交付方向实施。2026-10-21 用户要求推进可 pip 安装、面向人类和通用 Agent 的独立交付，特别关注架构、功能完善度、使用方法与体验。

上位规范：[契约优先](2026-09-01-forge-contract-first-rearchitecture-design.html)、[Service/Status](2026-09-02-forge-service-status-migration-design.html)、[Engine/Version](2026-09-12-forge-engine-version-policy-design.html)。本设计只补产品入口、环境诊断和发行，不改变单次 operation、workspace 或科学判定职责。

## 产品与接口

- 首个公开版本沿用项目 0.1.0，明确为 early/experimental；不把首次发行等同于全部科学能力 stable。
- 人类推荐现有 prepare/execute/collect CLI 及同名 primitive Python API；通用 Agent 推荐 capabilities → schema → operation 的 typed JSON CLI，同一 typed service 可直接用于 Python。高级 unit/sequence/pack 保留，不在入门路径要求用户先理解所有历史抽象。
- 不删除旧接口，不静默迁移默认行为；新增能力用 capability discovery 暴露。既有 v1 envelope、退出码和 append-only events 保持。
- 向用户明确兼容承诺：0.x 中 patch 不故意破坏已文档化请求/结果；需要破坏性调整时通过 minor/schema 版本与迁移说明处理。experimental 指能力覆盖，不代表任意改变已公开契约；科学接受始终由调用者决定。

## 易用性与完整任务

- 提供安装后的自包含、免引擎入门：用户复制指南命令即可建立小结构、prepare、dry-run，检查生成文件和明确的 skipped/not-run 状态。示例不得依赖本工作区、源码 PYTHONPATH 或 SAI 路径。
- 真实 SCF 路径由用户显式提供 executable 与 PP/ORB；说明每一步产物、资源选择和常见错误。免引擎示例不能假造真实引擎结果。
- Agent 教程展示能力/schema 读取、唯一 operation_id、cwd/workspace-relative 路径、成功/partial/前置条件失败的处理；不以 exit 0 或 scientific=unassessed 代替任务完整性检查。
- 外层示例脚本只消费公共 API/CLI，不把示例的步骤编排放进 Forge core；无需新增 workflow framework、MCP、TUI 或 Paimon 适配。

## 环境诊断

新增只读 `abacus-forge doctor`（人读默认，`--json` 提供机器报告）和 `--version`。诊断信息独立于 operation outcome，schema 为 `forge.environment/v1`。

- 检查当前 Python/发行包、默认依赖版本与可发现性；默认不要求 ABACUS/PyATB/ATST，保证离线使用成立。
- 显式 `--executable PATH_OR_NAME` 检查调用方给定程序可执行，重复 `--asset PATH` 检查文件可读；不启动程序、不下载资源、不写 workspace。
- 报告存在/缺失、已观察的路径及可操作建议。只有显式要求或核心依赖缺失使返回码为 3；参数错误为 2，正常检查为 0。
- 程序可发现不等于可运行、ABI 相容或科学输入正确，文案和字段明确这一边界。若现有 CLI 的 eager imports 阻碍缺依赖诊断，采用薄 stdlib 入口路由，保持原有 cli.main 和全部旧调用兼容。

## 发行

- 现有 CI 继续生成并测试 wheel/sdist。发布管线绑定选定 tag 与成功 CI run 的源码身份，消费其已测试制品，不在 publish job 悄悄重建。
- PyPI 使用 Trusted Publishing/OIDC，权限只给发布 job；不把 token 放进仓库。发布说明包含范围、已知限制、安装与版本说明。
- 用户随后明确“先做好别的配置，pypi稍缓”：本轮完成可审查代码、制品和发布操作说明，PyPI 账户配置和实际发布延后，不建发行 tag 或触发发布，不宣称发布成功。
- PyPI 发布后以新环境从索引安装，并复验版本、doctor、capabilities/schema、免引擎用户路径。

## 验收

1. Linux Python 3.10/3.12 clean wheel 安装和既有源码回归通过。
2. 人类和 Agent 两条入门不需源码 checkout，可验证行为与文档一致；缺资产/缺程序/partial 等场景有明确处理。
3. doctor 只读，JSON 可解析，缺项不被当成已就绪；对关键缺项有行为回归。
4. 原有请求、结果、默认 parser 和科学边界无回退；新文档不用内部迁移史作为使用前置。
5. 发布身份核查与拒绝错误 run/tag 的验证通过；公开发布状态按真实外部结果记录。
