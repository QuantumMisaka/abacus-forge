# Forge Stage 5 Evidence and Release Gates Plan

**Goal:** 在不扩大 Forge 职责和公共契约的前提下，补齐进入稳定发布/交给 Paimon v1.3 评估所需的可复现证据，并明确尚未具备证据时的交付边界。
**Spec:** `docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html`、`docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html`；尤其是 R1/R4/R7/R10/R11、Stage 5 与“科学判断、编排、调度上移”的职责结论。
**Authorization:** 沿用已批准 SPEC 和当前 Forge 持续开发授权；本计划只定义证据与发布门禁，不授权合并、推送或把实验能力改为稳定能力。
**Architecture:** 证据按“离线契约/兼容 → 干净安装与依赖隔离 → 真实进程 smoke → 上层迁移 benchmark → 发布决策”分层。Forge 只提供单 operation 的执行事实、解析观察和 artifact；Paimon v3 adapter、科学判定、跨 operation 编排、重试/续算、平台与调度均在 Forge 外部。
**Verification:** 所有门禁统一写入 `docs/superpowers/evidence/2026-09-13-forge-stage5-evidence.md`，逐项记录候选 exact commit、精确命令、环境、结果、skip/unproven 分类和局限；缺少外部 executable/workspace 时必须明确记录 skip/unproven，不得把 fixture、skip 或 parser 通过写成科学或稳定性结论。

## Scope and ownership

本计划执行阶段只允许修改证据记录、门禁文档和必要的测试 harness 文档；不得为通过门禁新增 Forge 业务字段、状态枚举、Task-ID、workflow、scheduler 或 scientific policy。

- `tests/`: deterministic/compat/benchmark/real-smoke 门禁及其选择边界；真实 smoke 只消费调用方提供的 workspace 和 executable。
- `docs/superpowers/evidence/2026-09-13-forge-stage5-evidence.md`: 唯一 Stage 5 证据记录，保存每项门禁的 exact commit、命令、环境、结果、skip/unproven、限制和结论边界。
- `docs/`、`README.md`、`ROADMAP.md`: 记录命令、证据入口、成熟度和未完成条件；不把证据记录改写成产品契约。
- Forge runtime (`src/abacus_forge/`): 本计划默认不修改。若门禁暴露真实的输入/解析兼容缺口，另立窄 SPEC/PLAN 后再改。
- Paimon v3 adapter: 未来独立仓库/适配层负责 ATP 投影、科学标准、任务编排、资源环境、平台调度和 Paimon v1.2 benchmark parity；本计划不在 Forge 内实现。
- optional `atst-tools` adapter: 只验证显式的 `prepare`/`execute`/`postprocess` 单元边界和进程隔离；NEB 链路编排与并行执行仍由 atst-tools/上层负责，不成为 Forge 核心依赖。

## Evidence already available on the current candidate

以下是本计划的起点，不重复伪造为待完成工作；正式证据仍须按统一文件格式绑定最终候选 commit：

- typed `prepare`/`modify`/`execute`/`collect`，独立 `postprocess`/`export`，PyATB 与可选 atst-tools 边界已实现并保持 `experimental`；PBE 是默认输入策略。
- normal-end observation 已独立于 execution/collection status，并有日志来源、artifact 和 API/CLI/legacy 边界回归；最近 owning gate 为 `220 passed`，全量离线 gate 为 `1343 passed, 10 skipped`。
- architecture/contracts/workspace gate 为 `344 passed`；benchmark opt-in 为 `6 passed`；未配置外部输入时 real-smoke 选择为 `4 skipped`。
- 候选分支已有 serial-PW ABACUS、PyATB 和 atst-tools 的历史/局部兼容记录；这些记录证明的是进程、解析和 artifact 事实，不是科学正确性或稳定 maturity。
- 既有 integration plan 记录过 clean wheel/fresh-venv 与 legacy runtime absence 证据；Stage 5 必须在最终候选提交上重新确认或明确其提交范围，不能仅引用不相容的旧代码状态。

## Gates and tasks

### Task 1: Freeze the evidence manifest

**Files:** `docs/superpowers/evidence/2026-09-13-forge-stage5-evidence.md` and this plan.
**Behavior:** 为每个 capability/operation 记录当前 descriptor、maturity、输入输出 artifact 角色和适用 engine；记录证据对应的 exact commit。只核对已存在的 contract，不新增 contract。
**Dependencies:** 当前候选分支和两份批准 SPEC。
**Verification:** capability/schema/discovery、architecture/forbidden-import、全量离线 pytest；结果包含 exact counts、skip 分类和 `git diff --check`。

- [ ] 只冻结当前九个 typed/discovery capability：`scf`、`relax`、`cell-relax`、`md`、`band`、`dos`、`pyatb-band`、`export`、`atst-neb`；确认其实际 descriptor 与实现一致。
- [ ] 明确所有能力在独立发布决策前仍为 `experimental`；不以 fixture 或 benchmark 单独晋升。
- [ ] 将 property packs 明确标记为 deferred/experimental，不纳入本次 stable manifest 或 Paimon v1.3 稳定面。
- [ ] 检查结果 envelope 只表达 execution/collection 与 observations/artifacts；不得出现科学接受、任务关系或平台状态。

### Task 2: Re-run clean package and dependency-isolation gate

**Files:** packaging/test documentation and the gate harness only。
**Behavior:** 在全新 Python 环境构建并安装最终候选 wheel，验证 `import abacus_forge`、console entry point、capability/schema discovery 和最小 typed operation 解码；环境不安装 `abacus-agent-tools`、`abacustest`、AiiDA、ATP/MCP、atst-tools 或 scheduler。
**Dependencies:** Task 1 的候选 commit；可用 build backend 和 Python 版本。
**Verification:** fresh-venv install/import/process 命令成功；`pip show`/import probe 证明禁止运行时包不存在；源码 AST/依赖扫描通过。若缺 build backend，记录阻塞原因并提供可复现的环境准备方式，不声称 gate 通过。

- [ ] 将 wheel hash、Python/platform、安装命令和 import/process 输出写入证据记录。
- [ ] 确认 atst-tools 只可作为显式外部进程/可选 adapter 使用，不进入 Forge core 安装依赖。
- [ ] 确认 clean gate 只证明安装和边界，不证明 ABACUS 运行或科学结果。

### Task 3: Run opt-in real process smoke gates

**Files:** `tests/real_smoke/` and `docs/superpowers/evidence/2026-09-13-forge-stage5-evidence.md`。
**Behavior:** 以 machine CLI 为主，使用人类提供的、无历史 generated output 的 prepared workspace，验证 Forge operation 的 process invocation、workspace containment、native parser facts、event 和 artifact refs。API parity 不在 real-smoke 中另造一条运行面，由离线 owning tests 覆盖。没有输入时精确 skip；输入无效时 fail。
**Dependencies:** Task 2；ABACUS executable and prepared workspaces supplied outside Forge. PyATB/ATST executable evidence is separately opt-in.
**Verification:** SCF、Relax/cell-relax、MD、必要的 PyATB/ATST machine-CLI smoke commands with exact pass/skip output；API/CLI 等价性引用离线 owning tests。`normal_end` 只作为日志 observation 检查，不转换为 scientific status。

- [ ] 按能力分别运行现有 real-smoke；不把一次 serial-PW run 当作物理正确性、收敛性或 capability promotion。
- [ ] 对 atst-tools 使用已确认版本（当前外部仓库记录为 2.2.4）做安装/API/process boundary smoke；不启动 Slurm，不把 atst 的 NEB 编排复制到 Forge。
- [ ] 对 generated-output freshness、symlink/path containment、stdout/stderr 和 artifact provenance 保留失败证据。

### Task 4: Establish Paimon v1.2 migration/benchmark evidence outside Forge policy

**Files:** Forge benchmark harness/evidence docs and the external Paimon adapter acceptance workspace。
**Behavior:** 对相同输入和明确 operation 交接，比较 v1.2 既有实现与 Forge 的可观察事实、artifact handoff、CLI/API envelope 和上层 Agent 可消费结果。Paimon adapter 是 Forge 外部的上层依赖与 handoff consumer，不是 Forge 内待完成的实现；比较只用于迁移工程证据，Forge 不接收 scientific policy 或 workflow object。
**Dependencies:** Tasks 1–3；由上层提供 Paimon v1.2 reference runner/fixtures 和 acceptance harness。
**Verification:** benchmark 必须显式 opt-in；报告 compare scope、expected differences、环境和失败归因。不能以 benchmark 通过替代 real-smoke、clean-env 或人类/Agent 的科学验收。

- [ ] 保持默认 pytest 不运行 benchmark；记录当前 `6 passed` 事实矩阵仅覆盖已有 fixture/collection 兼容范围。
- [ ] 为需要的 prepare/execute parity 补上真实输入和 process evidence；不能把 collect-only matrix 扩写成全链路等价。
- [ ] 将“是否进入 Paimon v1.3 稳定面”的决定留给上层维护者，不在 Forge descriptor 中自动改变 maturity；若 adapter 尚未在外部仓库具备证据，记录为上层 handoff unproven，不把它写成 Forge 缺陷或 Forge 待开发任务。

### Task 5: Make the release decision and hand off

**Files:** `ROADMAP.md`、发布/集成 evidence record；未来 Paimon v3 仓库由其维护者负责。
**Behavior:** 只有各自所需证据齐全且审查通过，才可由维护者决定某一 capability 的 maturity；否则保持 `experimental`，同时发布可用的事实型 CLI/API。发布决定按 capability 分开，不要求一次性把所有 property pack 变成稳定能力。
**Dependencies:** Tasks 1–4 and independent review of the exact candidate diff.
**Verification:** full offline + architecture/import + clean package + applicable real-smoke + benchmark outputs are attached; boundary review confirms no scientific judgment, orchestration or scheduling has moved into Forge.

- [ ] 明确 Forge 合并与发布是独立决定；本计划不自动 merge/push。
- [ ] 若需要 Paimon v3，另建独立 adapter/repository，消费 Forge facts 并拥有 ATP、资源/平台、编排、科学标准和 v1.2 parity；不得在 Forge 追加厚适配层。
- [ ] 将缺失的真实 ABACUS/PyATB/ATST workspace、上层 Agent benchmark 或 clean-env 证据列为 `unproven`，而不是以 skip 充数。

## Non-goals and boundary rulings

- 科学验证、收敛/质量阈值、接受/拒绝结论由人类或 Agent 负责；Forge 只返回事实、观察和产物。
- 多 operation 链路、重试/恢复、任务编排、队列、资源选择、Slurm/Bohrium/DPDispatcher 和平台调度不进入 Forge。
- Prepare/collect 等轻量 operation 不提供从中途恢复的 Forge 语义；是否重复执行或另起模块由人类/Agent 决定。`execute` 的运行事实也不构成恢复 workflow。
- PBE 默认仅是 ABACUS 输入生成默认值，不是科学判断。
- 本计划不新增 TUI；未来 TUI 只能是 Python API/结构化 CLI 的薄壳。

## Exit criteria

Stage 5 只有在以下条件全部满足时，才能称为“证据齐全”：统一证据文件已绑定最终候选 exact commit；离线契约/架构门禁通过；clean package/dependency gate 通过；适用的真实进程 smoke 有明确 pass；Paimon v1.2 parity 已由 Forge 外部的上层 adapter/acceptance harness 记录；独立 review 无未处理的 Critical/Important；文档仍明确 Forge 不做科学判断、编排和平台调度。

如果缺少真实 ABACUS/PyATB/ATST executable、prepared workspace、clean build environment 或上层 benchmark，必须在统一证据文件中标记对应 gate 为 `unproven`（并保留精确 skip/失败原因）；此时不得称 Stage 5 证据齐全，不得把任何 capability 改为 stable，也不得宣称 Forge 已是 Paimon v1.3 stable backend。Forge 仍可作为 `experimental` 的事实型 CLI/Python API 交付，待外部条件满足后重新运行适用门禁。
