# Forge 安装态 CI 与独立包交付

用户确认本会话继续 Forge 独立交付，Paimon Benchmark 由另一会话负责。
原有 GitHub CI 仅做 editable 源码全离线测试，未检查构建包和可选解析器安装。
本轮在同一 workflow 新增 `installed-package`，复用现有安装/解析测试。

## 行为与验证

- Python 3.10/3.12 分别运行 `python -m build`，从 sdist 生成 wheel，再安装该 wheel 的 `[dev,abacuslite]` extra，执行 `pip check`。
- abacuslite fixture 的提交由 exact pin 对应 provenance 解析；checkout 只提供测试日志，解析器仍来自 PyPI 安装。不存在 fixture 目录或 parser 无法导入时直接失败。
- 使用 `ABACUS_FORGE_INSTALLED_PACKAGE_ONLY=1` 和显式 wheel 路径运行包元数据、parser backend、四 capability canonical parity，禁止 editable/source 冒充已安装包。
- 成功后以 `forge-distributions-3.10` / `forge-distributions-3.12` 保存 wheel/sdist，保留 14 天。只保留 CI 产物，不执行 PyPI 发布。

两套 fresh venv 重放 YAML 中的实际 shell/Python run blocks，构建、安装、`pip check` 均通过。
最终包含显式导入检查的命令分别 **55 passed、无跳过、exit 0**；测试夹具取自
`f8c8b045fa3a76ad4c2fdd92c828fda5155f6f34`。两版构建的 wheel 均为
`516fcbda179964e652ba44dade698604c03b021b7c2080c7820fc0710c215441`，
与[1.2.2 升级候选](2026-10-21-forge-abacuslite-1.2.2-rebind.md)相同。

[机器摘要](2026-10-21-forge-installed-package-ci/summary.json)、
[Python 3.10 最终日志](2026-10-21-forge-installed-package-ci/py310/final-check.log)、
[Python 3.12 最终日志](2026-10-21-forge-installed-package-ci/py312/final-check.log)。
同目录保留实际命令、构建/安装日志、依赖清单与本地重放脚本。

本地 checkout/setup-python 由对应解释器和本地 Git archive 提供，未声称 GitHub
托管 Actions 或 artifact 上传已经成功；后者须推送后验证。原有源码全离线 job 保留，
本轮未改运行代码，不重复既有 1534 项完整回归或真实计算。

独立审查发现 canonical fixture 在 ImportError 时可能 skip；已在 CI test step
增加实际导入与发行版本读取，关闭这一假绿入口，并在两版环境重验。

独立终审通过，无未关闭实质问题；本轮交付到本地 main，开发 worktree 保留。
