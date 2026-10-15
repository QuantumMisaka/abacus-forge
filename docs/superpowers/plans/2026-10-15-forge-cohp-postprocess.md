# Forge COHP postprocess implementation plan

Spec: [2026-10-15-forge-cohp-postprocess-design.md](../specs/2026-10-15-forge-cohp-postprocess-design.md)

## Task 1: Add typed cohp postprocess contract

- Add `CohpPostprocessRequest` to `postprocess_contracts.py`.
- Register `{"postprocess": CohpPostprocessRequest}` under capability `cohp`
  in `request_registry.py`.
- Validate canonical directory paths, positive 1-based atom indices, the
  `iao` method, and the default `all` orbital selectors.
- Contract tests cover strict round trip, immutability, unknown fields,
  invalid paths/indices/method, discovery schema, and registry isolation.

## Task 2: Migrate the IAO kernel behind Forge modules

- Move the Paimon v1.2 pure-Python IAO implementation into Forge as
  `cohp_iao.py`, `cohp_iao_reader.py`, and `cohp_iao_shells.py`.
- Preserve algorithms, constants, guards, warning codes, output formats, and
  public numeric behavior; only change package imports.
- Copy the small real Si fixture used by the Paimon kernel tests.
- Add focused kernel tests for shell rules, reader identities, explicit
  projector reference, Fermi-shift invariance, selector validation, missing
  overlap-R, gamma-only rejection, and artifact writing.

## Task 3: Add service, discovery and machine adapter

- Add `CohpPostprocessService` and include it in `PostprocessServiceSet`.
- Reuse operation guard, workspace path admission, changed-output admission,
  artifact records, outcome persistence, and error classification.
- Advertise `cohp` as experimental with operation `postprocess`; schema
  discovery must round-trip the typed request.
- Extend machine CLI routing so direct service and `operation postprocess`
  runs produce equivalent envelopes.

## Task 4: Own regression and evidence

- Run owning suites plus default offline regression in `abacus-env`.
- Record branch, commit, candidate identity, commands, and boundaries in
  `docs/superpowers/evidence/2026-10-15-forge-cohp-postprocess.md`.
- Explicitly state that legacy bridge, Paimon migration, parity, clean-install,
  benchmark, and release are not accepted by this slice.

## Authorized follow-up: installed consumption and W2 closeout

2026-10-15 用户在工作状态核查后要求“推进相关事项完成”。沿用 W1 SPEC 与
Paimon W0–W4 迁移计划，执行本地 COHP 交接和安装验收，不改变默认方法或能力成熟度。
Forge 工作区为 `.worktrees/cohp-install-closeout`；上层复用 `app-tools-forge`。
已 fetch app-tools origin，v3 包含最新 v2 `52798406d`，merge 检查为 already up to date。

- [x] 修复 Paimon 治理检查的实际 12 项违规；补实 COHP artifact corruption
  测试，使其从真实文件触发对应校验；若暴露缺陷，先记录 RED 再修复。
- [x] 构建 Forge wheel 和当前 Paimon ZIP，在无 system-site 的隔离环境验证
  installed runtime/default routes，并以 Si fixture 执行真实 COHP 后处理交接。
- [x] 核对迁移前 Paimon IAO 与 Forge IAO 的同输入数值结果；只声明该 fixture 的
  IAO 迁移等价，不将其称为 legacy `abacus-cohp-lcao` parity。
- [x] 运行 owning suites、治理和文档检查，独立复核改动，更新路线图和双方证据。

Ruling: 本轮优先闭合最新切片的本地验收 — 现有 W3 历史 kit 不含最新 COHP —
不能以历史安装证据替代当前候选，也不能以本轮结果关闭完整专业依赖、Benchmark、
平台或发布门禁。真实 ABACUS/SAI 运行和外部发布继续按对应授权单独处理。

完成记录：Forge wheel suites 16 passed；Paimon owning 195 passed / 3 skipped，最终 COHP 23 passed，完整 unit 7550 passed / 9 skipped / 57 deselected，本地治理通过。独立 GPT reviewer 未发现实现阻断问题；证据日志改用可跟踪扩展名并补充回放前置条件。结果与边界见[安装消费证据](../evidence/2026-10-15-forge-cohp-installed-consumption.md)。Forge 本轮仅修改文档，保留隔离分支；Paimon 实现已提交 `bab7d380d`，本地 kit 未传输或发布。
