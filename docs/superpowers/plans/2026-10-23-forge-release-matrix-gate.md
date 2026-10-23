# Forge release matrix gate

依据：2026-10-23 用户确认优先完成 release gate 修复与新候选回归/构建。基线为
`main@8524075`；本计划只处理首版发布门禁的版本矩阵一致性和本地候选验收，
不改变运行时契约、依赖版本或科学能力边界。

## Scope

- CI 的 `test` 与 `installed-package` 矩阵补齐 Python 3.11。
- 发布验证器不再维护硬编码的四 job 清单，而是按 pyproject 声明的 Python
  classifier 派生 `test` 和 `installed-package` 必需 job；发布 run 缺任一版本
  即拒绝。
- 增加 owning regression，检查声明的 Python 版本、两条 CI 矩阵和发布必需
  job 三者一致。
- 在隔离 Python 3.11 环境执行完整默认离线回归；用 CPython 3.12 构建 wheel
  与 sdist，并做安装态候选 smoke。
- 形成新候选记录；远端 CI 未完成前不得宣称该候选已满足发布门槛。

## Non-goals

- 不发布 PyPI、不创建 release tag、不更新 abacuslite pin。
- 不修改 typed capability 契约、默认依赖或实验性成熟度。
- 不用本地候选替代远端 CI 成功 run。
