# Forge “算筹工场”目标架构与 Paimon v3 单一来源后端设计

- Status: Draft; product name confirmed by owner on 2026-10-29
- Date: 2026-10-29
- Owner: ABACUS-Forge
- Supersedes: 无；本 SPEC 是既有 Contract-First / Service-Status / Capability SPEC 的目标架构附录
- 上位规范:
  - `2026-09-01-forge-contract-first-rearchitecture-design.html`
  - `2026-09-02-forge-service-status-migration-design.html`
  - `2026-09-12-forge-engine-version-policy-design.html`
  - `2026-09-29-forge-contract-system-design.html`（只采纳其问题定义；M1–M4 仍不整体批准）

## 1. 定位裁决

**Forge 是 ABACUS 科学计算的单一来源后端，也是人类研发者与 AI Agent 共用的“算筹工场”。**

Forge 不是 Paimon 的内部工具，也不是只服务 ATP 的私有函数库。它对外提供稳定、版本化、协议无关的：

- typed Python API；
- non-interactive machine CLI；
- request / result / artifact / event contracts；
- workspace 与 provenance；
- capability、engine、resource、diagnostic、output 元数据。

**Paimon 承载 ATP Tool 与其他辅助组件。**

Paimon 是 Forge 的消费者和平台适配层，负责：

- ATP Tool 生命周期；
- `@tool_io` 声明；
- platform protocol；
- Agent session、报告和辅助组件；
- Slurm / SAI / 站点调度适配；
- 用户可见的诊断包装和恢复策略。

Paimon 不得复制 Forge 的执行、收集、artifact、schema 或 output contract 逻辑。Paimon 的 Tool 契约应由 Forge capability registry 驱动、生成或校验。

### 非目标

Forge 仍然不做：

- MCP / ATP / 平台协议编解码；
- Slurm、SAI、Bohrium、DPDispatcher 调度；
- workflow 编排、自动重试、跨 workspace 任务链；
- 数字 Task-ID 协议；
- 交互式前端；
- 科学接受判断；
- 用户项目管理、权限、报告发布。

“ProjectContext”只表达调用方显式给出的本地目录组织意图，不表达平台项目、权限或任务队列。

## 2. 产品身份与调用模型

Forge 对两类一等调用者保持同一契约：

| Caller | 使用方式 | 典型形态 |
| --- | --- | --- |
| 人类研发者 | Python API / CLI / 后续可选 TUI | 准备输入、执行、收集、后处理、导出 |
| AI Agent / 上层 adapter | machine CLI / typed Python API / JSON contracts | 非交互、结构化、可审计、可重放 |

“算筹工场”的目标是让调用方不必理解旧 `abacus-agent-tools` / `abacustest` 的内部结构，只需选择 capability、operation、engine、workspace 和 evidence 要求。

### 调用模型

```text
Human / Agent / Paimon ATP Tool
        ↓ explicit request
Forge capability API / machine CLI
        ↓ capability contract
Prepare / Modify / Execute / Collect / Postprocess / Export
        ↓ engine adapter
ABACUS / PyATB / ATST / optional parser backend
        ↓ local process + evidence
Workspace manifest, events, artifacts, metrics, diagnostics
        ↓ consumer projection
Human report / Agent evidence / Paimon Tool outputs
```

## 3. 核心架构原则

1. **单一来源**：capability、operation、request schema、output contract、diagnostic class、engine identity、maturity 都以 Forge registry 为规范源。
2. **契约先行**：所有新行为先进入版本化 schema，再进入实现。
3. **单元操作优先**： Forge 提供单元 operation；多 operation 编排由 caller 显式执行。
4. **Artifact 是一等公民**：任何跨 operation 边界的文件必须有 `ArtifactRecord` 与 workspace-relative path。
5. **科学状态不判定**：执行成功、解析完整、科学可接受是三类事实，Forge 只表达前两类。
6. **平台无关**：Forge 不理解站点、账号、队列、项目权限或平台 Task-ID。
7. **可审计优先**：workspace manifest 和 events append-only；不使用 mutable last-result 作为规范事实。
8. **薄 adapter**：Paimon 只做投影，不复制后端逻辑。
9. **显式降级**：缺失依赖、未知 schema、非法资源、engine identity mismatch、diagnostic unknown 都 fail closed。
10. **人类与 Agent 对等**：CLI 的输出应能由 Agent 消费；Python API 的语义应能由人类审阅。

## 4. 目标架构分层

### L0 Contract Kernel

稳定基础类型：

- `OperationRef`
- `OperationStatus`
- `ForgeResultEnvelope`
- `ArtifactRecord`
- `MetricRecord`
- `CheckRecord`
- `Observation`
- `ForgeErrorEnvelope`
- `OperationOutcome`

已有 `forge.request/v1`、`forge.result/v1`、`forge.workspace/v1` 保持兼容。

### L1 Capability Registry

将现有分散在 `discovery.py`、contracts、collector、service 中的事实收敛为单一 capability registry。

每个 capability 的规范记录：

```json
{
  "schema_version": "forge.capability-contract/v1",
  "capability": "relax",
  "engine": "abacus",
  "driver": "native|ase|cp",
  "operations": ["prepare", "modify", "execute", "collect"],
  "maturity": "experimental",
  "request_schema_ref": "forge.schema.relax.execute/v1",
  "canonical_outputs": [
    {
      "name": "work_dir",
      "kind": "directory",
      "required": true,
      "availability": "always",
      "artifact_role": "output"
    },
    {
      "name": "relaxed_structure_file",
      "kind": "file",
      "required": false,
      "availability": "converged",
      "artifact_role": "primary_structure"
    },
    {
      "name": "relaxed_inputs_dir",
      "kind": "directory",
      "required": false,
      "availability": "converged_or_partial_resume",
      "artifact_role": "input_handoff"
    }
  ],
  "metrics": [
    {
      "name": "total_energy",
      "unit": "eV",
      "kind": "reported|derived",
      "source_marker_ref": "abacus.marker.final_etot"
    }
  ],
  "diagnostic_classes": [
    "missing_output",
    "unparseable_output",
    "resource_oom",
    "resource_timeout",
    "engine_nonzero_exit",
    "identity_mismatch"
  ],
  "maturity_evidence": {
    "offline": true,
    "installed": false,
    "real_smoke": false,
    "parity": false
  }
}
```

该 registry 是 Paimon Tool 契约的规范来源。Paimon 可以生成 `@tool_io` 声明，或至少用 CI 校验其声明与 Forge registry 一致。

不得把 ATP `tool_data`、platform report、Slurm shape 或用户报告文案放进 Forge registry。

### L2 Workspace and Project Runtime

保持单 workspace 审计边界，新增显式 project 组织层。

```json
{
  "schema_version": "forge.workspace-plan/v1",
  "project_root": "GaN",
  "workspace_rel": "relax/prime-run",
  "role": "run",
  "strategy": "explicit",
  "contained_paths": true,
  "allow_existing": false
}
```

`ProjectContext` 不表示平台项目，只表示本地目录组织：

```text
GaN/
  inputs/
    prime/
    next/
  runs/
    prime/
    restart-a/
  analysis/
    band/
    dos/
  reports/
    forge-projects.json
```

`WorkspaceAllocator` 只做确定性路径解析、containment 检查、冲突检测和 allocator evidence；不做任务链、不自动 retry、不自动复用旧目录。

`ProjectManifest` 追加记录：

- project root；
- declared workspace roles；
- operation outcome refs；
- artifact refs；
- allocator decisions；
- engine identity；
- diagnostic refs。

它不改变单 workspace manifest 语义，而是跨 workspace 的只读审计索引。

### L3 Engine and Driver Adapter

Forge 的引擎面继续与平台解耦。

| Adapter | 职责 | 不做 |
| --- | --- | --- |
| ABACUS native | prepare INPUT/STRU/KPT；execute；collect native output | 不自动判断收敛为科学成功 |
| ASE relax/MD driver | 构造 driver 输入、启动本地优化/MD、收集轨迹与 endpoint | 不做 CP 逻辑硬编码、不做科学收敛判定 |
| CP / ATST driver adapter | 显式接收 compensated/FCP 配置和 runner 结果 | 不隐藏 workflow 状态 |
| PyATB | 显式矩阵/结构 handoff、postprocess/collect | 不扫描 latest、不推断上游 |
| ATST NEB / transition | 显式文件交接与本地执行 | 不做站点调度 |
| Optional parser | abacuslite 等 collect backend | 不改变 native 默认 |

`ResourceSpec` 是显式请求，不是调度器：

```json
{
  "schema_version": "forge.resource-spec/v1",
  "mpi_ranks": 4,
  "omp_threads": 4,
  "gpu_count": 1,
  "gpu_shape": "1gpu",
  "expected_locality": "single-node",
  "environment_ref": "reports/environment.json",
  "timeout_seconds": 3600,
  "dry_run": false
}
```

Forge 只校验、传递、执行并记录 evidence。Slurm / SAI adapter 决定如何满足该 spec。

### L4 Execution Identity and Provenance

每次真实 execute/collect 都携带可核对 identity：

```json
{
  "schema_version": "forge.execution-identity/v1",
  "engine": "abacus",
  "engine_version": "v3.10.1",
  "engine_build": "LTS3.10.1",
  "executable_sha256": "...",
  "container_image": "abacus:1.1.1",
  "container_digest": "sha256:...",
  "forge_version": "0.1.0",
  "forge_commit": "...",
  "parser_backend": "native",
  "python_lock_ref": "reports/python-lock.json",
  "resource_spec_ref": "reports/resource-spec.json"
}
```

结果 envelope 不直接内嵌大文件，而是引用 identity artifact。identity mismatch 属于 diagnostic class，不由 Forge 决定是否重试。

### L5 Evidence, Collector and Diagnostics

Collector 从单一事实源扩展为 typed collector registry：

| Collector class | 输出 |
| --- | --- |
| `engine_exit` | returncode、stdout/stderr ref、start/end |
| `running_log` | SCF/Relax/MD markers、迭代、能量、收敛观察 |
| `structure_evidence` | source/final structure、species order、atom mapping |
| `matrix_fact` | SCF matrix / density / Hamiltonian artifacts |
| `trajectory_evidence` | frames、steps、units、dataset manifest |
| `resource_evidence` | launch shape、GPU、OOM、timeout、host observation |
| `handoff_evidence` | editable/published、containment、manifest digest |
| `identity_evidence` | engine、container、forge、parser backend |

统一 `DiagnosticRecord`：

```json
{
  "schema_version": "forge.diagnostic/v1",
  "stage": "collect",
  "error_class": "resource_oom",
  "severity": "error",
  "message": "Slurm evidence reports OOM",
  "observed_facts": {
    "oom_kind": "host_memory",
    "slurm_event_ref": "reports/events/slurm-oom.json"
  },
  "workdir_ref": "runs/prime",
  "artifact_refs": ["running_log", "raw_artifacts_manifest"],
  "resource_evidence_ref": "reports/resource-evidence.json",
  "safe_next_actions": [
    "inspect_resource_evidence",
    "choose_larger_shape"
  ],
  "scientific_interpretation": "unassessed"
}
```

`safe_next_actions` 只是语义枚举，不自动执行。

### L6 Consumer Projection

Forge 不实现 ATP Tool，但提供 projection contract：

```json
{
  "schema_version": "forge.tool-projection/v1",
  "capability": "relax",
  "operation": "collect",
  "target": "paimon.tool/v1",
  "tool_name": "abacus_worker_relax",
  "declared_outputs": {
    "work_dir": {"source": "canonical_output:work_dir"},
    "final_structure_file": {"source": "artifact:relaxed_structure"},
    "result_evidence_file": {"source": "artifact:result_evidence"}
  },
  "diagnostics_mapping": {
    "resource_oom": "platform.resource.retry_candidate"
  }
}
```

Paimon 可由 registry 生成 Tool 描述，最低要求是 CI 校验：

- Paimon Tool outputs ⊆ Forge canonical outputs；
- required / optional 与 Forge registry 一致；
- metric units/kinds 一致；
- diagnostic classes 有 adapter 处理或显式 unsupported；
- missing registry contract 阻断 Tool 发布。

## 5. 与 1.2.84 缺口的映射

| 1.2.84 能力 | 本 SPEC 对应设计 |
| --- | --- |
| project output parent、semantic stages | `forge.workspace-plan/v1` + `ProjectContext` |
| directory roles、editable/published handoff | workspace role + handoff evidence |
| multi-GPU ASE relax/MD、GPU shape | `forge.resource-spec/v1` |
| OOM/resource recovery evidence | `resource_evidence` collector + `DiagnosticRecord` |
| strict declared-output publisher | capability output contract + consumer projection |
| Tool SIF 全量切 `abacus:1.1.1` | execution identity |
| 修复 L2 误载旧 `abacusagent` | Forge runtime closure + retired path neutrality |
| IDPP failure actionable | transition diagnostic class |
| SCF matrix facts、MD result evidence | matrix/trajectory evidence collectors |
| IRC / property analysis root | project analysis role + workspace allocator |

## 6. 渐进迁移策略

不做一次性 giant merge。按 capability vertical slice 推进：

### Phase A — Contract-only foundation

新增：

- capability contract registry schema；
- workspace plan schema；
- resource spec schema；
- execution identity schema；
- diagnostic schema；
- consumer projection schema。

本阶段只引入 registry、validator、fixture 和 round-trip tests，不改现有 runtime。

验收：

- schema/API/CLI round-trip；
- unknown field fail closed；
-现有 Forge full offline suite 不回退；
- Paimon focused suite 可继续运行。

### Phase B — Project placement

实现：

- `ProjectContext`；
- `WorkspaceAllocator`；
- `ProjectManifest`；
- allocator event/evidence；
- contained path checks。

先接 SCF，再接 Relax / MD，再接 Band / DOS。

验收：

- 同一请求使用显式 project root 后，输出位置稳定；
- 不同 role 不冲突；
- no cwd side effect；
- artifact 均在允许 root 下；
- old single-workspace path 保持兼容。

### Phase C — Resource and identity evidence

实现：

- `ResourceSpec` validation；
- `LocalRunner` evidence；
- execution identity artifact；
- OOM / timeout / nonzero exit diagnostics；
- identity mismatch diagnostics。

验收：

- synthetic local runner 可复现 OOM、timeout、nonzero、identity mismatch；
- real smoke 记录完整 identity；
- Forge 不做重试决策。

### Phase D — Capability output registry

按顺序：

1. SCF；
2. Relax / cell-relax；
3. MD；
4. Band / DOS；
5. EOS / Bader / charge-diff；
6. Phonon / spin / vibration；
7. COHP / PyATB；
8. Transition / IRC / property。

每个 capability 提供：

- canonical output contract；
- metric contract；
- diagnostic classes；
- Paimon projection fixture；
- normal 与 disabled-compatibility sweep；
- real smoke 或冻结 replay。

### Phase E — Paimon projection hardening

Paimon 改为由 Forge registry 校验 Tool outputs：

- Tool 生成或 CI 校验；
- missing contract 阻断发布；
- tool integrity gate 增加 Forge registry consistency；
- release inventory 记录 Forge wheel、SIF digest、Python lock、capability contract hash。

### Phase F — Benchmark and release

完成：

- 全 capability parity；
- Agent Benchmark 同等或更好验证；
- clean install；
- SAI real smoke；
- production-ready release inventory。

在此之前不得宣称 v3 完全替代 v2。

## 7. 兼容与迁移规则

1. v1 request/result 保持兼容，新增字段必须是 optional 且 schema 化。
2. 新 schema 使用独立 `schema_version`，不悄悄改变旧 payload。
3. legacy API 可以继续存在，但不得成为新 capability 的规范路径。
4. retired systems 可在 docs/fixtures/guards 中出现，但 runtime 不产生路径或 import 特例。
5. Paimon 的 Tool outputs 只能引用 Forge canonical outputs 或显式 diagnostic projection。
6. 任何 capability 没有完成 registry contract 时，Paimon Tool 必须标记 experimental 或 blocked。
7. Forge 不因 Paimon 暂缺某 projection 而拒绝提供人类/Agent CLI。

## 8. 验收总纲

### Forge local gates

- full offline suite；
- schema/API/CLI parity；
- workspace/project allocator tests；
- resource/diagnostic mutation tests；
- identity mismatch tests；
- collector fixture tests；
- installed wheel tests；
- boundary purpose map tests。

### Paimon integration gates

- Forge registry → Tool projection consistency；
- legacy disabled sweep；
- candidate package build；
- package runtime；
- package default routes；
- focused capability suite；
- SAI real smoke；
- release inventory。

### Evidence requirements

每个 capability slice 记录：

- Forge commit；
- Paimon commit；
- Forge wheel SHA；
- SIF / engine digest；
- Python lock；
- v2 replay input；
- Forge normal result；
- disabled compatibility result；
- focused test result；
- real smoke or frozen replay result。

## 9. 开放取舍

以下不阻塞本 SPEC 的架构方向，但进入实施前需逐项裁决：

| 问题 | 推荐 | 说明 |
| --- | --- | --- |
| Project root 是否进入每个 typed request | 推荐 optional `workspace_plan` 字段 | 保持单 workspace 请求兼容 |
| `n_gpu` 是否加入 v1 execute request | 推荐包进 optional `resource_spec` | 避免把 GPU shape 泄漏为所有 capability 的顶层概念 |
| Paimon Tool outputs 是生成还是 CI 校验 | 短期 CI 校验，长期生成 | 生成减少漂移，但需要稳定代码生成协议 |
| capability registry 存 JSON、Python 还是两者 | 推荐 Python source of truth + deterministic JSON export | 便于类型校验，同时给 Agent/CI 消费 |
| Contract System M1–M4 是否并入 | 暂不整体并入 | 只吸收 capability/output/diagnostic 子集 |
| “算筹工场”是否进入 README 产品名 | 已采纳 | owner confirmed on 2026-10-29; README uses “ABACUS-Forge · 算筹工场” |

## 10. 成功标准

目标架构完成后，应满足：

1. Forge 是 capability、schema、execution、evidence 和 provenance 的单一来源。
2. Paimon 没有复制的 Forge 执行/收集/output contract 逻辑。
3. 人类与 Agent 使用同一套 contracts，不需第二套私有路径。
4. 1.2.84 的 project placement、resource evidence、strict output、diagnostic identity 都有 Forge-native 表达。
5. 每个 capability 的 maturity 和证据等级机器可查。
6. v2 replay、Forge normal、disabled compatibility 三类结果可比对。
7. Forge wheel、SIF、Python lock、capability contract hash 进入 release inventory。
8. 不再依赖“代码看起来没有旧 import”推断替代完成，而是有 capability-level parity 和 release inventory。
