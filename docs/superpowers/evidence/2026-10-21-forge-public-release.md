# Forge 0.1.0 公开消费准备验收

规范：[SPEC](../specs/2026-10-21-forge-public-release-design.md)；执行：[PLAN](../plans/2026-10-21-forge-public-release.md)。本轮基线 `42c23a4`，分支 `codex/forge-public-release-010`。本地候选已通过独立终审，远端集成/CI 见下文；PyPI 账户配置、正式发布及发布后 index install 按用户要求延后。

## 本轮范围

- 增加 `doctor` 的人读和 `forge.environment/v1` 输出、`--version`，顶层帮助可发现；缺核心依赖时仍可启动诊断，机器 CLI 无需先加载 legacy 依赖。
- 完成当前 Git/wheel 安装、人类免引擎上手、显式资产真实 SCF 操作方法、通用 Agent 发现/请求/状态/错误指南及 0.x 兼容承诺。
- 保持现有原语、typed service、workspace 与科学判断边界。入门编排仅在外部示例；没有新增调度/平台协议层，也没有更改默认依赖或实验性成熟度。
- 发布流程手动选择 tag 与成功 CI run，校验同仓、同 commit、四矩阵、artifact 摘要及包元数据，只提升测试过的制品；OIDC 仅给最终发布 job。

## 本地实测

原始日志根：`/home/james/scratch/forge-public-release-20261021/`；最终集成测试位于 `final/`。两个新建 venv 分别使用 CPython 3.10.20 和 3.12.13，不共享 system-site-packages。

| 检查 | 观察结果 |
| --- | --- |
| 完整默认离线回归 | 两版各 `1582 passed, 35 skipped`；3.12 有 176 个 ASE 对 NumPy 2.5 的弃用警告，未过滤新增警告。 |
| fresh wheel 安装与 parser parity/doctor/用户路径 | 两版各 `64 passed`；启用 installed-only、`python -I`、空 PYTHONPATH，abacuslite 为 1.2.2。 |
| 仅核心依赖安装 | `core-only` venv 安装默认 wheel，仓库外执行入门脚本成功；dry-run 为 skipped/not_collected，缺程序和输入为 precondition.missing，无输出 collect 为 missing_output。未启动 ABACUS。 |
| 无第三方依赖安装 | `doctor/final-no-deps-venv` 中 doctor/--version/--help 退出码为 3/0/0，doctor 列出五个缺失核心依赖；不会先因 numpy import 崩溃。 |
| 依赖完整性 | 两个 full venv 的 `uv pip check` 均通过。 |
| 发布验证 | 正负向来源/版本/摘要回归通过；旧成功 run `39572951484` 的真实 API 和 artifact ZIP 也已实际读取与校验，仅作验证器实测，未作为本轮发行制品。 |
| 独立终审 | 代码/架构/发布来源审查通过；唯一实质文档问题为真实 SCF 的 legacy/typed 状态混淆，已修复并复核。 |

完整测试命令为各环境 `python -m pytest -q`，日志 `final/full-310.log`、`final/full-312.log`。安装态命令与 `.github/workflows/ci.yml` 的六文件范围一致，增加 `python -I`；fixture 来自此前按 abacuslite 1.2.2 provenance checkout 的 `tests/fixtures/io/testfiles`，只提供日志，parser 从已安装的 PyPI 包导入。安装态日志为 `final/installed-310.log`、`final/installed-312.log`。

本轮不声称新增真实科学收敛或 Paimon Benchmark 验收。35 个跳过属于现有 opt-in/可选覆盖边界；真实科学计算证据仍沿既有双轨和有界 capability 记录。

审查修正文案后重新构建，最终本地 wheel SHA-256 为 `f40cf487163cae048ef7f2900713cffe6e6326821718a2f6e51fc64c79a82a7e`；两版重新安装并运行上述 64 项及文档链接检查，各 `66 passed`（`final/reviewed-installed-310.log`、`final/reviewed-installed-312.log`）。构建包保存在 `final/reviewed-dist/`；远端最终提交的 sdist 由 CI 重建并单独绑定。

## GitHub 配置

已创建 `pypi` environment（ID `24906209635`），仅选定 deployment tag policy `v*`（ID `63821738`）；没有分支发布许可，也没有新增人员审批和仓库级 tag ruleset。读回结果保存在 `final/github-environment-policies.json`。PyPI Pending Trusted Publisher 尚未配置；没有创建 release tag、触发 publish workflow 或上传 PyPI。实际发行操作见[维护手册](../../releasing.md)。

## 远端集成

实现提交 `cc689202dad573b138ae677bd92e3967c5a6f8ce` 的 [push CI](https://github.com/QuantumMisaka/abacus-forge/actions/runs/39583395220) 和 [PR CI](https://github.com/QuantumMisaka/abacus-forge/actions/runs/39583476961) 均全部通过。原始 push 日志保存于 `final/ci-39583395220.log`：两版源码各 `1582 passed, 35 skipped`，两版安装态各 `64 passed`。

已实际下载 `forge-distributions-3.12` 并运行发行 metadata 验证器。CI wheel SHA-256 为 `f40cf487163cae048ef7f2900713cffe6e6326821718a2f6e51fc64c79a82a7e`，与本地终审 wheel 一致；CI sdist SHA-256 为 `4b4f4c0da4b84fefc109c02cab65a6aeda27ce55fb924ea09ab261fc83457cb6`。该制品用于当前候选复核，未上传 PyPI。

[PR #8](https://github.com/QuantumMisaka/abacus-forge/pull/8) 已合入 `main@93cd2cc19af593b3d9a4d7dadfc00ceab30ec4a4`。后续收口提交仅更新本计划/证据/索引；最终发布时仍需选择届时 tag 对应的成功 push CI 及未过期制品，不直接复用过期 run。主 checkout 的 `docs/elastic-al-fcc-raw-attribution@79ad5e1` 保持原状，Paimon owner 工作区未修改。
