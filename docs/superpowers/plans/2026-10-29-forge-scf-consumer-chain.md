# Forge SCF 消费链垂直切片

- Owner：ABACUS-Forge；Paimon v3 消费面在 migration checkout 内单独落地。
- Status：In progress。初版离线实现已交付；复审 P1/P2 及独立复核修复已在 Paimon `a05448c7e` 和 Forge `d9eb12a` 完成，默认安装态消费已用 wheel `a4bba28e…` 验证；远端 CI 与合入确认尚未完成，暂不具备合入条件。
- Design source：[算筹工场目标设计](../specs/2026-10-29-forge-computation-factory-target-architecture-design.md)。
- Forge baseline：`QuantumMisaka/abacus-forge`，branch `feat/forge-scf-consumer-chain-20261029`，commit `f02588c`（已包含用户确认的设计收缩）。
- Paimon planning baseline：`app-tools-forge-latest-main-sync`，branch `integration/paimon-v3-baseline-1.2.84-20261029`，commit `7cd73eeb3`（toolbox `1.2.84` 来源）。
- 授权与边界：本切片只做离线可验证的 Forge/Paimon v3 代码与契约；不修改 Paimon v2、不新增平台发布/上传、不申请真实 SAI 作业、不宣称 Benchmark parity。
- 本次接续：用户要求检查设计并细化计划；本文记录修复与验收工作，未将待办写成已完成。安装依赖、推送、合并、真实计算和发布按各 owning repo 及会话授权执行，本文不新增外部操作授权。

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

JSON launcher 只接受字符串数组；Python 构造保留合法 list/tuple。object、字符串或无序集合不得经 iterable 转换静默进入 runner。请求缺省行为保持；`env_overrides` 的空字符串值原样传递，不等同于删除环境变量。

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

## 复审接续任务（待完成）

复审对象：Forge `feat/forge-scf-consumer-chain-20261029@8496e7e`（package `0.1.0`）与 `app-tools-forge-latest-main-sync` 中的 `feat/paimon-v3-forge-scf-consumer-chain-20261029@be95cd86e`（toolbox `1.2.84`，显式 `backend=forge`，默认仍为 legacy）。2026-10-29 读取的 Paimon `origin/main@181c4b7ac` 相对原 `38c0f9073` 仅增加发布报告内容；接续开发按工作区规则同步最新 main，相关实现未变的既有证据继续可用。

### Task 6: 保留 Forge 收敛事实（P1，Paimon owner）

- 入口：Paimon `toolbox/ABACUS/toolkits/forge_scf_consumer.py::_converge`；消费点为 `abacus_scf.py` 和 `utils/scf_result_policy.py`。优先在 adapter 修正投影，复用既有事实与结果策略。
- 反例：真实 collector 读取 `SCF CONVERGED`、`SCF NOT CONVERGED`、能量和结束标记后，`collection=complete`、`converge=false`；当前 adapter 却给出 `true`，下游 `charge_density_convergence=passed`。
- 交付：消费 Forge 收敛 metric 或等价的既有否定优先语义，保留 unknown；不因采集完整推导科学接受。完整 outcome 原样保留。
- 验证：在 `tests/test_forge_scf_consumer_chain.py` 补真实 collector/envelope 到 Paimon facts 的回归，混合标记应保持未收敛，不能发布为收敛所需的 restart/cube/matrix ready；同时覆盖纯正、纯负和缺失标记。记录修复前失败、修复后通过，并运行 SCF output-profile / evidence 邻近测试。

### Task 7: 对齐 runtime-K 输入语法（P2，Forge owner）

- 入口：`src/abacus_forge/services.py::_input_has_runtime_k_source` 与 `input_io.py`；复用输入解析，不另建参数语言或全局 schema。
- 依据：工作区 ABACUS `v3.10.1:source/module_io/read_input.cpp` 的布尔解析与 `read_information(..., "#!")`。有效 true token 为 `true/1/t/yes/y/on/.true.`；`1.0` 不是有效布尔 token。
- 验证：无 KPT 时，`gamma_only .true.`、`gamma_only 1 ! Gamma sampling`、`kspacing 0.5 ! reciprocal spacing` 应能进入 SCF 执行；`gamma_only 1.0` 且无其他有效 K 源应被拒绝。保留 kspacing 单值/三值、有限正数与已有 KPT 路径行为。
- 在 `tests/test_service_status.py` 通过真实 INPUT 读取验证 runner 是否被调用；若修改共享 `read_input`，补 `tests/test_input_io.py` 及其受影响消费者检查。Relax/MD 的既有 KPT 准入不随此任务扩展。合法语法误拒先修复；非法值的错误文案可沿用当前类别。

### Task 8: 拒绝非数组 launcher（P2，Forge owner）

- 入口：`src/abacus_forge/contracts.py::ScfExecuteRequest`、现有 machine decoder 与 discovery。
- 反例：`launcher={"env":"-i"}` 当前被转成 `["env"]`，静默丢失参数。
- 交付与验证：合法 argv 保持顺序与内容；错误类型在 constructor/from_dict/CLI 边界拒绝。CLI 返回既有 `request.schema` 错误，runner 不被调用。邻近用例放在 `tests/test_contracts.py`、`tests/test_machine_cli.py`；同步核对 schema，兼顾共享 helper 的其他调用者，避免扩大无关行为变更。

### Task 9: 默认安装态消费链（两侧修复完成后）

- 从修复后的明确 Forge commit 构建 wheel，在隔离环境安装；使用项目认可的 Python 环境，不覆盖日常 `abacus-env`。记录 wheel SHA、实际解释器、package 导入位置及 Paimon commit；确认非 editable，Forge 源码不通过 cwd/PYTHONPATH 注入。
- Paimon 使用真实 `run_forge_scf_consumer()` 默认 service/request factories，底层执行传入可控 stub executable；不 monkeypatch `_default_services` 或 request 构造器。现有 doubles 测试继续验证局部行为，不能替代这条安装态交接。
- 输入包含有效 INPUT/STRU、PP/ORB 与相对依赖树。覆盖一次成功 execute→collect→legacy projection，检查 resolved command、资源观测 unknown、两次 operation 的 outcome record 与完整依赖树；另覆盖一次执行失败，确认不 collect、不 retry，原错误事实可读。
- 将可复跑集成检查接到 Paimon 现有测试或 evidence 脚本入口，避免仅留不可重复的临时命令。重跑既有 focused suite；记录实际测试范围与排除项。该项证明包和消费者交接，不证明真实 GPU/ABACUS 运行。

### Task 10: 当前切片集成与合入

- 依赖 Task 6–9。Forge 按 `tests/README.md` 执行受影响契约、workspace、service/result 检查及最终默认离线回归；Paimon 执行本计划的 focused 范围。记录两侧修复后的提交和差异复审结论。
- 获得推送授权后提交两侧分支并建立相应 PR/MR；Forge CI 对 Python 3.10/3.11/3.12/3.13 的 `test` 与 `installed-package` 共八个 job 通过。安装态 CI 的现有用例不包含 Paimon 默认 adapter，Task 9 仍需独立证据。
- 确认 Paimon candidate 的部署依赖将使用支持 launcher/env_overrides 的 Forge 包；保留默认 legacy 路由。先让 Forge 修复提交可被消费，再集成依赖它的 Paimon 修复，避免只合 adapter 而仍部署旧 Forge。
- reviewer/owner 在相应仓库完成合入确认。当前切片完成声明只覆盖已验收的 SCF 链路；失败 durable evidence、真实平台运行和完整替代按下节推进。

## 后续交付边界

| 交付 | 前置与验收 | 计划详度 |
| --- | --- | --- |
| Forge 0.1.0 | Forge 修复合入后的发布 commit，成功 push CI 的八个 job 与同次 `forge-distributions-3.12` 制品；记录 wheel/sdist 各自 SHA、run ID/head SHA；按发行手册 tag、owner 发布与干净安装回验。发布上传已受测制品，不本地重建另一份替代。 | 复用[发行手册](../../releasing.md)与[发布计划](2026-10-21-forge-public-release.md)，重新生成当前 candidate；Paimon 全量替代不作为独立 Forge 发布前置。 |
| Paimon v3 替代 | 按正确 gitlink/环境补齐依赖并重跑 full suite，逐项归因剩余失败；逐批接续 Relax/cell-relax/MD、CPU 后处理及 ASE/CP/NEB，复用原有 route 中仍适用的实现；候选最终解除旧依赖并通过对应 Benchmark parity。 | 先完成 SCF，再为下一实际能力批次细化计划；不预写全部 Tool 的统一接口或固定开发顺序。 |
| 真实资源与失败交接 | Paimon 请求→平台 allocation→launcher→resolved command→实际 GPU→输出交接；覆盖所选启动方式。失败信息优先接入已有 outcome/event 与 Paimon 报告出口。 | 各档映射先离线验收；真实单卡/多卡案例按启动差异选取，额外档位按实际差异补证。失败出口按真实消费者缺口扩展，不另建诊断框架。 |

旧 full-suite 的 `73 failed` 是修复前观察，不能全部预归因于环境；按正确依赖重跑后再处理剩余问题。候选清单沿用已有 evidence，记录所验证的源码、wheel、引擎/镜像、依赖和 Benchmark 工件即可，不建立 ExecutionIdentity 子系统。真实平台验收与外部发布仍按既有授权边界执行。

## Verification policy

- 行为变化用 TDD；契约变更同时检查 Python decoder、machine CLI 和 discovery schema。
- 已有未改动行为的证据可复用；修复后只补受影响回归。
- Task 6–8 的源码修复可分别验收，Task 9 验证组合后的安装态交接，Task 10 汇总集成结果。安装依赖、真实 ABACUS/GPU、推送和发布按授权执行；计划中的步骤不构成通过证据。

## Progress

- [x] 2026-10-29：确认并提交收缩后的 SPEC（`f02588c`）。
- [x] Task 1: Forge SCF execute handoff
- [x] Task 2: Paimon Forge SCF adapter
- [x] Task 3: Paimon Tool 消费与输出合同
- [x] Task 4: 源码态 stub probe 与初版 evidence；未覆盖安装态。
- [x] Task 5: 初版独立审查；其后复审发现转入 Task 6–8。
- [x] Task 6: Paimon 收敛事实保真。
- [x] Task 7: Forge runtime-K 语法一致性。
- [x] Task 8: Forge launcher 类型验证。
- [x] Task 9: 默认安装态消费链。
- [ ] Task 10: 集成 CI、差异复审与两侧合入。

## Execution record

- Forge implementation：`QuantumMisaka/abacus-forge`，branch `feat/forge-scf-consumer-chain-20261029`，初版验收记录提交 `5ac3e72`，复审文档 HEAD `8496e7e`，Task 7–8 修复 HEAD `baee443`，独立复核修复 HEAD `d9eb12a`。覆盖 SCF-only `launcher` / `env_overrides`、requested vs resolved launch、ABACUS token-style runtime-K comments、launcher ordered-array admission、capability sequence compatibility、服务错误 envelope 事实和文档。修复后默认离线回归 1658 passed / 35 skipped。
- Paimon v3 implementation：`app-tools-forge-latest-main-sync`，branch `feat/paimon-v3-forge-scf-consumer-chain-20261029`，初版 final HEAD `be95cd86e`，Task 6 修复 HEAD `9cac98d85`。覆盖显式 Forge backend、immutable consumer outcome record、完整 legacy dependency-tree projection、runtime launcher mapping、negative-priority convergence projection、unknown allocation observation 和既有 output/evidence 合同。Task 6 focused consumer tests 14 passed；SCF focused suite 366 passed / 2 deselected。
- 控制器跨源 stub probe 用 Forge branch 的真实 `ScfServiceSet` 驱动 Paimon adapter：无 KPT + `gamma_only=1` 的 execute/collect 成功，normal-end/converge/energy 与 resolved command 可读，allocation 保持 unknown。
- 初版独立审查后修复：完整 PP/ORB legacy projection、SCF-only 契约 fence、三分量 `kspacing`、空环境值和 docs；当时发现已关闭。2026-10-29 后续复审在上述 HEAD 复现 Task 6 的 P1 与 Task 7/8 的两项 P2，三项均待修复；不能继续沿用“全部 closed”作为当前合入结论。
- 本轮复审：Paimon 真实 collector/envelope 反例先复现 `false → true → passed`；修复后混合标记保持 `false` 且 `charge_density_convergence=failed`。Forge 反例复现 launcher object 丢值与合法 runtime-K 输入误拒；修复后 focused 和全量回归通过。复审时远端两条 feature 分支尚不存在，Forge 无对应 HEAD 的 CI；日常 `abacus-env` 仍导入 canonical main 的旧 editable Forge，因此 Task 9 使用独立隔离 venv，而不是覆盖日常环境。
- Task 9：从 Forge `d9eb12a` 构建 wheel `abacus_forge-0.1.0-py3-none-any.whl`（SHA-256 `a4bba28e3a4379a6079a0968a865c4bb5752eb9a31db1ad6158a029b8baa8ae5`），装入隔离 venv 后用真实 default request/service factories、stub engine、完整 PP/ORB 依赖树和失败 envelope 执行 `toolbox/ABACUS/scripts/verify_forge_scf_installed_consumer.py`，exit 0。隔离环境 focused suite 366 passed / 2 deselected。Paimon evidence entry HEAD `a05448c7e`。
- Deferred：malformed runtime-K source 的诊断仍保守折叠为缺 KPT；Paimon Forge 失败 outcome 目前随 exception 保留，尚不生成 durable failure evidence；installed-wheel end-to-end、真实 ABACUS/SAI/GPU 和 Benchmark parity 仍未执行，不作为本切片验收声明。
