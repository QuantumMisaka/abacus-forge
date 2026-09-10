# Forge Typed MD Real-Smoke Evidence Plan

**Goal:** 为现有 typed `md` capability 增加一个显式、可选的真实 ABACUS 执行/收集门禁，只证明 Forge 的本地 operation path，不把 fixture 或一次运行解释成科学结论。
**Spec:** `docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html` 的 status/boundary/testing/rollout 条款，以及已完成 `docs/superpowers/plans/2026-09-10-forge-typed-md-operations.md` 的 typed MD 约束；本批次不新增公共 schema。
**Authorization:** 用户已持续授权在 Forge 主线内按批准 SPEC/PLAN 推进；本批次从已验收 `forge-mainline-integration` 分支建立隔离工作树，只提交测试与文档，不修改 `main`、不 push。
**Architecture:** 复用既有 `run_cli`、real-smoke pytest 选项、typed machine `operation execute/collect` 和 workspace 复制模式。由调用方通过环境变量提供一个已准备的 MD workspace 与 ABACUS executable；测试复制到临时目录后使用两个 UUIDv4 operation ID 执行一次 `md`，再收集 factual envelope、artifact 和 audit event。旧 SCF/Relax smoke 保持不变。
**Verification:** 默认离线套件仍将该测试跳过；显式 `--run-real-smoke` 且缺少输入时精确跳过，错误输入失败。运行新增测试的 focused selection、machine/MD owning suites、完整离线套件、benchmark/real-smoke 选择边界和 `git diff --check`。无 supplied executable/workspace 时不声称真实 ABACUS 证据。

## Scope and ownership

- `tests/real_smoke/test_abacus_smoke.py`: 新增一个 typed MD execute/collect smoke；不改变现有 SCF/Relax 测试。
- `tests/conftest.py`: 为新测试注册 MD workspace/executable 环境变量映射。
- `tests/real_smoke/README.md`, `tests/README.md`, `README.md`, `ROADMAP.md`: 记录 MD smoke 的入口、事实边界和当前未证明状态。
- 本 PLAN：记录执行与审查证据；不成为运行时契约。

## Global constraints

- `md` 仍为 `experimental`；不得因为 smoke 通过就修改 discovery maturity 或宣称 Paimon v1.3 稳定面。
- 使用已存在的 `forge.request/v1` 字段和 `capability="md"`；不得添加 scheduler、job ID、retry/resume、monitor、trajectory conversion 或科学阈值字段。
- 执行只调用一个已配置的本地 ABACUS executable；不引入 Slurm、Bohrium、DPDispatcher、AiiDA、`abacus-agent-tools`、`abacustest` 或 `atst-tools` 运行时依赖。
- source workspace 只能复制到 `tmp_path` 后执行，不能修改调用方目录；返回的 artifact/event path 必须是 workspace-relative 且 contained。
- 为避免旧结果冒充本次执行证据，复制源的根目录或 `outputs/` 下不得已有生成的 `running_md.log` 或 `MD_dump`；测试发现时直接失败。
- 断言只覆盖 operation status、parser facts 是否存在、artifact/audit 事实和 `scientific="unassessed"`；不检查收敛阈值、温度是否物理正确或轨迹是否科学可接受。
- 缺少环境变量时 skip；已提供但不是目录/可执行文件时 fail，不能把坏输入转换为 pass。

## Task 1: Add the typed MD smoke

**Files:** `tests/real_smoke/test_abacus_smoke.py`, `tests/conftest.py`
**Dependencies:** existing typed MD contracts/services/machine CLI on this branch.
**Behavior:** copy a supplied prepared MD workspace, run typed `execute` and `collect` through the subprocess CLI, and assert factual/audit invariants.

- [x] 先写 focused test：环境缺失时 skip；workspace/executable 无效时 fail；输入 `calculation=md` 缺失或不匹配时 fail。
- [x] 使用 `ABACUS_FORGE_MD_SMOKE_WORKSPACE`、`ABACUS_FORGE_ABACUS_EXECUTABLE`，复制 workspace 时 `symlinks=False`；拒绝复制源已有的根目录/`outputs/` MD 生成物；使用两个不同 UUIDv4 IDs。
- [x] execute 请求使用 `capability=md`、`dry_run=false` 和显式 bounded timeout；断言一个 JSON stdout、空 stderr、`execution=completed`、`scientific=unassessed`。
- [x] collect 请求使用同一 workspace 和另一个 ID；断言 `collection=complete`、`execution=not_run`、`scientific=unassessed`，并要求四个原生 MD parser facts（总能、势能、动能、温度）为有限 scalar，不做科学判断。
- [x] 核对每个 event payload 等于 CLI envelope，manifest 记录两个 event，artifact/event path 相对且 contained；在 `_REAL_SMOKE_ENV_BY_TEST` 注册精确环境变量。
- [x] 运行 focused selection 与默认 skip/fail-fast 检查，确认 legacy SCF/Relax smoke 行为未变。

## Task 2: Document and verify the gate

**Files:** `tests/real_smoke/README.md`, `tests/README.md`, `README.md`, `ROADMAP.md`, this plan.
**Dependencies:** Task 1.
**Behavior:** consumers can discover how to opt in to the MD smoke and understand that it is operation evidence, not scientific validation.

- [x] 文档说明 MD workspace 必须已含 `inputs/INPUT`、`inputs/STRU`、`inputs/KPT` 和可执行所需资产，变量名和命令与测试一致。
- [x] 文档明确 typed MD smoke 与 legacy SCF/Relax smoke 分开，`MD_dump`/`running_md.log` 只作为 parser fact 来源；Forge 不判断轨迹质量、温度/能量物理正确性或任务编排。
- [x] 文档保留 `experimental` 与后续 real-smoke/benchmark/上层科学验收待办，不将本批次结果写成稳定发布证据。
- [x] 运行 MD/CLI/architecture owning suites、完整离线套件、显式 real-smoke 选择（无外部输入应 skip）以及 `git diff --check`。

## Task 3: Independent review and handoff

- [x] 请求独立 reviewer 检查本计划范围、既有 SPEC 和测试/文档差异；上一轮 Important 已修复并通过针对性复审。
- [x] 记录确切 HEAD、focused/full/skip 输出和 review verdict；没有 supplied real workspace/executable 时明确记录 real evidence unavailable。
- [x] 保持本工作树隔离、`main`/remote 不变；不在本批次合并或推送。

## Completion evidence

- Implementation commits: `0d24b53` (typed MD smoke) and `965e874` (require native parser facts).
- Task-scoped review of `0d24b53..965e874`: **Ready**, no Critical/Important/Minor findings. The reviewer confirmed the four required names match the native parser and that no scientific thresholds were introduced.
- Default real-smoke selection with `--run-real-smoke`: `4 skipped in 0.55s`; no real MD workspace or ABACUS executable is available locally, so no real execution evidence is claimed.
- Supplied invalid workspace: `1 failed, 3 deselected in 0.66s`, with a direct invalid-workspace diagnostic.
- MD/CLI owning suite: `160 passed in 61.20s`.
- Architecture gate: `8 passed in 5.51s`.
- Full offline gate (`not real_smoke and not benchmark`): `1218 passed, 6 deselected in 105.99s`.
- Benchmark opt-in gate: `2 passed, 1222 deselected in 1.25s`.
- `git diff --check`: passed.
- The branch remains isolated at the final implementation/documentation state; `main` and the remote were not modified.

## Rulings

- `Ruling: add a test-only MD release gate instead of weakening the typed service or adding a new operation — the roadmap explicitly defers per-capability real evidence, while the service contract is already settled. If the test harness proves too brittle for a supplied ABACUS build, the cost is a bounded evidence-test repair; no production wire contract changes.`
- `Ruling: require collection=complete but no scientific thresholds — complete means the existing MD parser saw its declared native domain output; scientific acceptance stays with the human/Agent boundary.`
