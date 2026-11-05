# Forge 发行操作手册

状态（2026-11-05 核对）：GitHub `pypi` environment 已配置，`v0.1.0` tag 已指向 `d5585f5`；发布 workflow 尚无运行，PyPI 的 `abacus-forge/0.1.0` 查询返回 404。Trusted Publisher 配置与实际上传仍由 owner 确认。该 tag 不含 11 月 5 日的 runtime-K 大小写和 capability 序列修复；当前本地代码需重新取得同提交 CI 与制品，不能沿用旧 candidate 宣称包含这些修复。已有 tag 的处置或版本选择由 owner 决定，不自动改指 tag。

当前还包括 `82af7d5` 的三类任务展开，见[本地候选](superpowers/evidence/2026-11-05-forge-task-expansion/README.md)。执行生命周期、CI 专项覆盖和发行内容等先按[公开交付接续](superpowers/plans/2026-10-21-forge-public-release.md#工程化接续待实施)收口。下面保留 package 0.1.0 对应的现行管线说明；后继版本尚未选择，不能直接用这些命令宣称新代码已经准备好上传。

## 发行边界

`publish.yml` 是手动入口。它仅从指定的成功 CI `push` run 下载已测试的 Python 3.12 wheel 和 sdist，核对 tag、commit、全部必需矩阵 job、artifact 摘要与两个包的元数据，然后由单独的 `pypi` job 上传。必需 job 由 `test`/`installed-package` 与 pyproject 声明的 Python 版本派生，当前共八个。发布流程不重新构建。首次版本沿用 `pyproject.toml` 中的 `0.1.0`。

发布验证器要求：

- `tag=v0.1.0`，且手动 workflow 的 **ref 同为 `v0.1.0`**；签出代码、tag 指向的 commit、CI run 的 `head_sha` 三者一致。main 后续可以继续前进。
- CI run 来自 `QuantumMisaka/abacus-forge` 的 `.github/workflows/ci.yml`，事件为 `push`，首次运行成功；`test` 和 `installed-package` 对 pyproject 声明的每个 Python 版本（当前为 3.10、3.11、3.12、3.13）各有成功 job，共八个。
- `forge-distributions-3.12` artifact 未过期，归属该 run 和 commit；下载的 ZIP 的 SHA-256 与 GitHub API 中的 digest 一致；内部恰好是 `abacus-forge` 0.1.0 的 wheel 与 sdist，二者名称、版本、Python 要求、摘要一致。

若 CI 首次运行失败后重跑成功，请为同一 commit 产生新的完整 `push` CI run，再使用新 run ID。当前验证器有意拒绝 `run_attempt > 1`，避免从重跑之前选到同名旧 artifact。CI artifact 保留 14 天，过期需重新触发完整 CI。

## 外部配置

首次 PyPI 发布前，由拥有 PyPI 项目权限的维护者配置 [Pending Trusted Publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)（如果项目已存在，则配置 [Trusted Publisher](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)）：

| 字段 | 值 |
| --- | --- |
| PyPI 项目 | `abacus-forge` |
| GitHub owner | `QuantumMisaka` |
| GitHub repository | `abacus-forge` |
| Workflow filename | `publish.yml` |
| Environment | `pypi` |

GitHub 侧已建立 `pypi` environment（ID `24906209635`），deployment tag policy 为 `v*`（ID `63821738`）；目前未设置额外人员审批或仓库 tag ruleset。发布 job 有 `id-token: write`，其他 job 无此权限；无需长期 PyPI token。Pending Publisher 不会预留项目名，正式上传前应复核名称可用性和项目权限。PyPI 账户配置和实际发行留给维护者完成。

## 执行顺序

1. 确认 release commit 的 `pyproject.toml` 版本、`CHANGELOG.md`、入门文档及干净安装验收。按维护者流程将该 commit 合入远端，再在该 commit 建立 `v0.1.0` tag 并推送；勿将 tag 指向未经验证的提交。
2. 等待该 commit 的 CI `push` run 完成。记录 run ID，核对由 pyproject Python 支持矩阵派生的全部必需 job（当前八个）及 artifact。CI 可以由 tag push 或相同 commit 的分支 push 产生。
3. 当 PyPI/GitHub environment 配置完成、且已准备上传时执行：

   ```bash
   gh workflow run publish.yml --repo QuantumMisaka/abacus-forge --ref v0.1.0 -f tag=v0.1.0 -f run_id=<CI_RUN_ID>
   ```

   网页启动时也要在分支/tag 下拉框选择 `v0.1.0`，并填写相同 tag。错误 ref 或 run 会在取得 OIDC 权限前被验证 job 拒绝。
4. 核对 `verify` 和 `pypi` job 成功及 [PyPI 页面](https://pypi.org/project/abacus-forge/0.1.0/)。建立新虚拟环境，从公开索引执行 `python -m pip install abacus-forge==0.1.0` 与 `python -m pip check`；按 README 的 `--version`、`doctor --json`、capabilities/schema 和免引擎示例再验收。保留运行链接和安装结果作为发行证据。

OIDC 或项目权限错误应先核对 PyPI publisher 四元组和 GitHub environment 名称。已上传文件的版本不能原地覆盖；不得以重跑发布工作流代替查明实际 PyPI 状态。发行证据只记录已观察结果，不能把准备就绪写作已发布。
