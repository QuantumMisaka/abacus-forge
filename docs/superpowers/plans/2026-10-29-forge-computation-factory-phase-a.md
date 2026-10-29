# Forge Phase A 原型撤回与设计收缩

- Owner：ABACUS-Forge。
- 状态：收缩完成，离线验证与独立审查通过；原 Phase A contract-only foundation 由本次收缩取代。
- 日期：2026-10-29。
- 设计源：[算筹工场设计](../specs/2026-10-29-forge-computation-factory-target-architecture-design.md)。
- 授权：用户确认“收缩聚焦，消融掉所有过度锁定和不必要设计”，并确认 ABACUS 默认 GPU、其他任务 CPU 的分工。

## 裁决与范围

Ruling：撤回 `3d3ae52` 新增但未被运行链消费的 Phase A 原型，复用已有 discovery、request/result、runner 与 provenance。原因是平行 registry 已发生事实漂移，identity/resource/projection 等新类型只有自测而没有实际执行消费者。代价是曾采用该源码原型的调用方需迁移回 `capabilities` / `schema`；明确记录撤回，不制造第二套兼容元数据。

范围为 `QuantumMisaka/abacus-forge`，基线 `main@3d3ae52c8908149ae6f1f9f140444a3a805b69ca`、package `0.1.0`，执行分支 `refactor/forge-design-contraction-20261029`。本次不修改 Paimon、ABACUS、PyATB 或 ATST 代码，不改变现有操作、运行后端和依赖。

本地消费调查覆盖 Forge 源码/测试，以及 `app-tools-forge`、`app-tools-forge-latest-main-sync` 的 ABACUS runtime 和 abacuslite/atst-tools 源码；只找到新模块自己的测试与机器 CLI 路由。此结论不宣称不存在工作区外消费者。首次公开发布尚未执行，撤回说明进入 compatibility 与 changelog；原设计与实现保留在 Git 历史。

## 本次工作

- [x] 将目标 SPEC 收缩为实际能力、轻量来源、资源分工和消费交接；撤回七层框架及固定 Phase A–F 门禁。
- [x] 移除未消费的 `capability_registry.py`、对应 CLI 命令与专用测试；保留既有 v1 操作契约。
- [x] 更新 reference、architecture、兼容说明、changelog 和规范导航。
- [x] 核对保留 discovery/API/CLI 与基线一致，完成相称回归和独立审查。

## 测试消融依据

原 `test_capability_registry.py` 的 22 项测试只验证被撤回的 records/seed/CLI，不作为现有运行能力的唯一证据。保留的 `test_contracts.py`、`test_machine_cli.py`、`test_cli_process.py`、workspace/result/service tests 继续保护请求解码、JSON、路径、操作、退出语义和审计。此次不为证明某个类名不再存在增加永久源码扫描测试。

删除前已做具名 production mutation：临时移除 `ScfExecuteRequest` 的 timeout 有限性判断，保留测试 `test_scf_execute_request_rejects_invalid_runner_configuration` 对 Infinity、NaN 两项失败，其余 15 项通过。已恢复源码；此变异证明仍保留真实运行参数的保护，不把过度锁定消融成取消有效输入校验。

修改前保存 13 个 capability 与 32 个 operation schema 的 discovery 输出，修改后比较完整内容；不靠重新冻结 hash 代替行为等价。

## 验证记录

所用解释器：`abacus-env` 的 Python 3.12；沿用本会话已完成的环境预检。开发态测试从本 worktree 的 `src/` 导入。

| 检查 | 当前结果 |
| --- | --- |
| 保留接口的完整基线比较 | 13 个 capability、32 个 operation schema 与基线一致；33 个 CLI 查询全部与 API 一致，退出成功且 stderr 为空。[比较记录](../evidence/2026-10-29-forge-design-contraction/discovery-comparison.txt) |
| 删除测试前的保护能力核验 | timeout 有限性 mutation 被保留测试检出：2 failed、15 passed；源码已恢复。[原始输出](../evidence/2026-10-29-forge-design-contraction/timeout-mutation.txt) |
| 全量默认离线回归 | `conda run --no-capture-output -n abacus-env env PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider`：1584 passed、35 skipped，退出 0；176 条 warning 为 ASE/NumPy 弃用提示。[原始输出](../evidence/2026-10-29-forge-design-contraction/offline-tests.txt) |
| 独立终审 | 同家族独立 reviewer 检查未提交 diff 和消费者，无阻断项；确认实际运行代码未变、撤回与兼容边界明确，无新全局门禁。 |
| 格式与来源 | `git diff --check` 通过；当前原型撤回之外的请求、结果、runner、workspace 与基线一致。 |

真实 ABACUS/SAI、平台发布和 Benchmark 不属于此次元数据原型撤回的验证范围。改动留在上述隔离分支的工作树，尚未提交、合入 main 或推送；删除文件的本地恢复副本位于 `~/scratch/forge-design-contraction-20261029-3d3ae52/`。后续资源执行接入与 Paimon 1.2.84 迁移仍按各自能力推进，本次不宣称完成它们。
