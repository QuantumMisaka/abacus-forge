# 已有分支与文档收口

授权：2026-10-19 用户确认保留 dpdata，按优先级逐一推进，先收口已有分支和文档。本轮只做本地 main 集成；不推送、发布、删除历史工作树或启动真实计算。

依据：既有契约优先/Service-Status SPEC、COHP W1、仓库整理与 Engine/Version Policy PLAN。使用已有 `docs/forge-integration-reference-review` 隔离工作树。

## 执行清单

- [x] 核对本地 main `cc8dc43`、参考分支 `b40499b`、ATST 默认值复核 `e7fdf60`；两个分支工作树均干净，增量无运行算法或默认依赖变更。
- [x] 在参考分支合入 ATST 复核；保留 IAO 与直接 NAO 方法区别、abacustools 参考定位以及 CLI discovery 说明。
- [x] dpdata 保留默认依赖；更新当前入口及版本政策，关闭已完成的 exact extra/fresh-install 待办，历史证据保留。
- [x] 运行相关回归、文档链接与 CLI 检查；独立同族 reviewer 无阻断发现。
- [ ] 验证后本地 main 快进到集成结果，核对两条分支已吸收；工作树和分支保留以便追溯。

## 范围裁决

- dpdata：用户明确选择保留，取消移除候选，不要求上层迁移作为保留条件。
- COHP：本轮只有方法说明与 discovery description；method enum、schema 字段、默认值和算法保持不变。直接 NAO 后端仍需独立设计。
- 真实验收：ATST 2.3.0 默认值复核不冒充真实 NEB；发布 parser fixture parity 不冒充 develop/LTS 八格真实执行。
- Draft BEC、Contract System、property manifest 的批准状态不变；Paimon/SIF 工作不混入 Forge 本轮交付。

## 验证与集成结果

- 相关回归：`conda run --no-capture-output -n abacus-env python -m pytest -q tests/test_contracts.py tests/test_workspace.py tests/test_postprocess_services.py tests/test_postprocess_machine_cli.py tests/test_machine_cli.py tests/test_architecture.py tests/test_atst_neb.py tests/test_cohp_iao.py` → **513 passed**，18.72s，exit 0。原始输出 `/tmp/forge-closeout-tests.log`。首次命令误列不存在的 `test_postprocess_contracts.py`，未运行任何测试；核对测试文件后以上完整选集通过。
- 修改范围内 Markdown 本地文件链接：176 个目标，0 缺失（不包含网页与页内锚点验证）；`git diff --check` 通过。
- `conda run --no-capture-output -n abacus-env env PYTHONPATH=src python -m abacus_forge.cli --help` → exit 0；指南中的机器 CLI 示例由上述 architecture tests 覆盖。
- 未运行全量、真实引擎或 Benchmark，不据此宣称能力晋级。
- 独立同族 reviewer 已审查 `cc8dc43..1c23425` 及本轮文档差异，无阻断发现。main 集成结果待回填。
