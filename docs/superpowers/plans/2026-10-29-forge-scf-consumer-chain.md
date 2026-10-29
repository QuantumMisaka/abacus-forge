# Forge SCF 消费链垂直切片

- Owner：ABACUS-Forge；Paimon v3 消费面在 migration checkout 内单独落地。
- Status：Approved for implementation（2026-10-29 用户确认收缩后的目标 SPEC，并要求按此推进）。
- Design source：[算筹工场目标设计](../specs/2026-10-29-forge-computation-factory-target-architecture-design.md)。
- Forge baseline：`QuantumMisaka/abacus-forge`，branch `feat/forge-scf-consumer-chain-20261029`，commit `f02588c`（已包含用户确认的设计收缩）。
- Paimon planning baseline：`app-tools-forge-latest-main-sync`，branch `integration/paimon-v3-baseline-1.2.84-20261029`，commit `7cd73eeb3`（toolbox `1.2.84` 来源）。
- 授权与边界：本切片只做离线可验证的 Forge/Paimon v3 代码与契约；不修改 Paimon v2、不新增平台发布/上传、不申请真实 SAI 作业、不宣称 Benchmark parity。

## Goal

完成第一条真实消费者链路：Paimon SCF Tool 的显式 Forge 后端可以把已准备输入交给 Forge 执行与收集，读取 `OperationOutcome` 中的实际启动、结果、artifact 和 metric 事实，并映射到既有 Paimon Tool 输出契约。科学接受、资源申请、重试和平台发布仍由 Paimon/调用方决定。

## Rulings

- Ruling：不为本次切片发布通用 `ResourceSpec`。Forge 只在 SCF execute request 中暴露本次执行需要的现有 runner 能力：显式 `launcher` 与 `env_overrides`；GPU/CPU 申请和档位仍由 Paimon adapter 持有。错了的代价是其他 operation 不能复用这些字段，需在各自实际消费时再扩展。
- Ruling：Paimon 保留现有 `@tool_io` 输出与 result-evidence 合同，把 Forge canonical workspace/artifact 映射为该合同的输入；不自动生成新 Tool 契约、不新建 capability/output registry。错了的代价是 Forge 输出扩展时 adapter 必须显式跟进，而不是被全局投影掩盖。
- Ruling：请求资源、实际分配、实际启动分别记录；缺少平台分配观测时记录 unknown，不把 GPU 数写成零。Forge 记录 requested launch 与 resolved command；Paimon evidence 记录 adapter request 和可获得的 allocation observation。错了的代价是失败诊断会把“未观测”伪装成“零资源”。

## Interface contract

SCF execute request 增加可选字段（既有字段与 v1 envelope 不变）：

```text
launcher: list[non-empty string]      # default absent/empty；完整站点 launcher argv
env_overrides: object[string,string]  # default empty；仅显式传给 runner
```

`LocalRunner` 已支持二者。Paimon 可从 `ABACUS_COMMAND_ARGV` 生成 launcher，但不得把 `ABACUS_COMMAND_ARGV` 本身变成 Forge 传输协议。执行事实必须保留：

- requested：`launcher`、`mpi_ranks`、`omp_threads`、`timeout_seconds`、`env_overrides`。
- actual start：runner 解析后的完整命令；找不到可执行文件时保持 unknown，不用空数组冒充。
- outcome：returncode/status、stdout/stderr artifact、normal-end 事实和 Forge/parser diagnostics。

## Tasks

### Task 1: Forge SCF execute handoff

在当前 Forge worktree 内实现 request→runner 的 launcher/env handoff，并让执行结果区分 requested 与 actual start。

- 扩展 `ScfExecuteRequest`、discovery schema 和 typed machine decoder；省略新字段时 payload round-trip 与 CLI discovery 保持兼容。
- 把新字段传给 runner；执行成功或启动后失败时记录 resolved command。保留既有 requested command。
- 为新增 schema、runner handoff、resolved-command 事实和缺失可执行文件分支添加邻近回归。
- Checks：`tests/test_contracts.py`、`tests/test_machine_cli.py`、`tests/test_service_status.py`、`tests/test_cli_process.py`，随后全量默认离线 pytest。记录 TDD 失败→通过证据。

### Task 2: Paimon Forge SCF adapter

在 Paimon v3 migration checkout 新建执行分支，只修改 `toolbox/ABACUS` 内的 Forge adapter、必要 runtime wiring 和 tests。

- 新增纯 Python adapter，从 Paimon 的完整输入目录创建显式 Forge workspace，调用 Forge SCF execute/collect，再把结果投影回 legacy backend 形状（`scf_work_dir`、`normal_end`、`converge`、`energy`、`total_time`）。
- Projection 必须保留 Forge execute 与 collect 两个 outcome 的 operation_id、metrics、artifact references 和 diagnostics；不把 artifact 复制成 mutable last-result。
- 从 Tool runtime 参数生成 requested resource facts，allocation observation 缺失时显式 unknown；实际启动来自 Forge resolved command。
- 不得 import ATP/MCP 协议或 Slurm；不得自动重试、CPU 降级或判定科学收敛。
- Checks：adapter focused tests，覆盖成功、失败 envelope、路径逃逸拒绝、launcher/env 映射、artifact/result evidence 映射、unknown allocation。

### Task 3: Paimon Tool 消费与输出合同

将 adapter 接到 `abacus_worker_scf` 的显式 Forge backend，默认保持现役 legacy 行为。

- 新请求字段可用 `execution_backend: Literal["legacy", "forge"] = "legacy"` 表达；选择 Forge 时必须经过既有 handoff/preflight/output-profile staging。
- Forge 路径使用既有 declared outputs、runtime log、raw artifact manifest、result evidence 和 report 生成逻辑；`provenance.runtime.backend="forge"`。
- Forge workspace 与 legacy layout 的差异必须在 adapter 显式映射，成功输出的 declared ports 全部存在且可发布。
- Checks：SCF declared-output focused tests、output contract gates、tool integrity focused tests、Forge adapter tests；未改动行为用 focused regression 保护。

### Task 4: Integration and evidence

- 汇总 Forge 与 Paimon 的 repo/branch/commit、package/toolbox identity、focused 和 full offline 命令结果。
- 用一个 fake/stub engine 集成测试验证 prepare-handoff→Forge execute→collect→Paimon evidence 的顺序与失败传播；该测试不冒充真实 ABACUS 证据。
- 明确记录未完成的真实 SAI/GPU smoke、installed-wheel/打包和 Benchmark 验收；不声明 v1.2.84 替代完成。

### Task 5: Independent review and closeout

- 在两个 checkout 的最终 diff 上做同家族独立审查，重点检查契约兼容、资源事实、输出映射、离线/真实证据边界和未消费抽象回潮。
- 修复 Critical/Important 发现并复跑受影响检查；Minor 可记录延后。
- 完成声明只能覆盖本切片的离线消费链，不扩大到 Relax/MD、CPU postprocess、多节点或发布。

## Verification policy

- 行为变化用 TDD；契约变更同时检查 Python decoder、machine CLI 和 discovery schema。
- 已有未改动行为的证据可复用；修复后只补受影响回归。
- 真实 ABACUS、GPU allocation、安装态和 Benchmark 属于显式后续授权，不在本计划内推断通过。

## Progress

- [x] 2026-10-29：确认并提交收缩后的 SPEC（`f02588c`）。
- [ ] Task 1: Forge SCF execute handoff
- [ ] Task 2: Paimon Forge SCF adapter
- [ ] Task 3: Paimon Tool 消费与输出合同
- [ ] Task 4: Integration and evidence
- [ ] Task 5: Independent review and closeout
