# 0.1.0 发行操作手册

状态：发行流程已准备。GitHub `pypi` environment 已配置，PyPI Trusted Publisher 尚待配置；尚未创建 tag、触发发布流程或上传 PyPI。本文供维护者在账户配置完成后执行。

## 发行边界

`publish.yml` 是手动入口。它仅从指定的成功 CI `push` run 下载已测试的 Python 3.12 wheel 和 sdist，核对 tag、commit、四个必需矩阵 job、artifact 摘要与两个包的元数据，然后由单独的 `pypi` job 上传。发布流程不重新构建。首次版本沿用 `pyproject.toml` 中的 `0.1.0`。

发布验证器要求：

- `tag=v0.1.0`，且手动 workflow 的 **ref 同为 `v0.1.0`**；签出代码、tag 指向的 commit、CI run 的 `head_sha` 三者一致。main 后续可以继续前进。
- CI run 来自 `QuantumMisaka/abacus-forge` 的 `.github/workflows/ci.yml`，事件为 `push`，首次运行成功；`test` 和 `installed-package` 的 Python 3.10、3.12 四个 job 均成功。
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
2. 等待该 commit 的 CI `push` run 完成。记录 run ID，核对四个必需 job 及 artifact。CI 可以由 tag push 或相同 commit 的分支 push 产生。
3. 当 PyPI/GitHub environment 配置完成、且已准备上传时执行：

   ```bash
   gh workflow run publish.yml --repo QuantumMisaka/abacus-forge --ref v0.1.0 -f tag=v0.1.0 -f run_id=<CI_RUN_ID>
   ```

   网页启动时也要在分支/tag 下拉框选择 `v0.1.0`，并填写相同 tag。错误 ref 或 run 会在取得 OIDC 权限前被验证 job 拒绝。
4. 核对 `verify` 和 `pypi` job 成功及 [PyPI 页面](https://pypi.org/project/abacus-forge/0.1.0/)。建立新虚拟环境，从公开索引执行 `python -m pip install abacus-forge==0.1.0` 与 `python -m pip check`；按 README 的 `--version`、`doctor --json`、capabilities/schema 和免引擎示例再验收。保留运行链接和安装结果作为发行证据。

OIDC 或项目权限错误应先核对 PyPI publisher 四元组和 GitHub environment 名称。已上传文件的版本不能原地覆盖；不得以重跑发布工作流代替查明实际 PyPI 状态。发行证据只记录已观察结果，不能把准备就绪写作已发布。
