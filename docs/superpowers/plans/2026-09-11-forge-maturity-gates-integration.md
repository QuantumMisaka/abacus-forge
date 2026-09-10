# Forge maturity-gates candidate integration plan

**Goal:** 将已分别审查的 typed MD postprocess hardening 与 real-smoke freshness
门禁放在同一候选分支上验证，为后续正式集成提供一组不改变 Forge 运行时契约的发布证据设施。

**Normative sources:** approved Forge 2026-09-01/09-02 SPECs，以及
`2026-09-10-forge-typed-md-postprocess-design.html`、
`2026-09-11-forge-md-postprocess-review-fixes.md` 和
`2026-09-11-forge-real-smoke-freshness.md`。本文件只记录候选整合，不新增公共字段或能力。

**Authorization and isolation:** 从正式集成基线 `da1d4df` 派生的 MD 修复候选
`7d813dc` 上建立 `forge-maturity-gates`；只修改此隔离分支，不改写
`forge-mainline-integration`、`main` 或远程。

**Architecture:** 生产代码保持 MD 请求前置校验、精确斜晶胞 minimum-image、质量
fail-closed、真实绘图产物状态和 reported metric；freshness 只在
`tests/real_smoke/` 中拒绝复制源的 collector-visible 旧产物。它不引入 lineage
字段、调度、重试、workflow、科学验证或新的依赖。

## Scope

- 将已审查的 typed MD real-smoke 与 freshness 测试/文档提交叠加到 MD 修复候选。
- 运行 MD/real-smoke/architecture owning suites、完整离线门禁、显式 real-smoke
  skip/fail-fast 选择、benchmark 和 diff hygiene。
- 对整合后的完整 diff 做一次独立 review；Critical/Important 必须修复，Minor
  只在不影响契约且有明确记录时延期。

## Explicit non-goals

- 不把缺少真实 ABACUS workspace/executable 的 skip 当成真实科学证据或 maturity promotion。
- 不改变任何 `forge.request/v1`、`forge.result/v1`、错误类、状态枚举、descriptor 或
  普通 `execute`/`collect` 行为。
- 不在本候选中合入正式集成分支、`main`，也不 push。

## Verification record

- Candidate base: `7d813dc`; freshness source: `da1d4df..c18f6dc`; current candidate
  runtime/test state is checked from the resulting branch, not inferred from ancestry.
- Focused gate: `142 passed, 4 skipped`.
- Full offline gate: `1257 passed, 6 skipped`.
- Explicit real-smoke selection without supplied inputs: `4 skipped`.
- Benchmark opt-in: `2 passed, 1261 deselected`.
- Source package gate: `abacus_forge-0.1.0-py3-none-any.whl` built with `--no-deps`
  (candidate rebuild SHA-256 `818a2a1f75240e2ac8787b07138e7ef2fd9817aeac42716b9902ed425e9f3ee2`).
- Latest-candidate clean-environment gate: installed that wheel and its declared dependencies
  into a fresh Python 3.13 venv; `import abacus_forge`, the console entry point,
  `capabilities` (all nine advertised names), and `schema md postprocess` succeeded. The
  venv also confirmed `abacus_agent_tools`, `abacustest`, `aiida`, and `atst_tools` were
  absent. This validates packaging/import boundaries, not real ABACUS execution or science.
- `git diff --check` passes; real execution and scientific acceptance remain unavailable
  unless a caller supplies an external environment.

## Acceptance

- [x] Independent whole-branch review approves the exact candidate diff.
- [x] All listed gates and boundary scans pass; skips are classified as real-smoke rather
  than silently treated as success.
- [x] Candidate remains isolated and is handed off for an explicit integration decision.

## Review result

The independent whole-branch review of `da1d4df..1686eeb` found no Critical,
Important, or substantive Minor issue. It confirmed that the MD production
changes and approved MD SPEC are unchanged by the freshness commits, and that
the freshness helper remains confined to test evidence: its generated-file
scan follows collector-visible paths and Relax final-structure suffix rules,
without adding runtime constraints to `execute` or `collect`. The four
real-smoke skips are expected because no external workspace or executable is
provided; they are not maturity evidence.

The candidate is therefore ready for a separate, explicit integration
decision. `forge-mainline-integration` remains at `da1d4df`, `main` and the
remote remain untouched. The post-review documentation-only commits
`dadad05`, `3c795e4`, `25a457b`, and `5afa934` record acceptance, the latest
clean-package evidence, and the upper-layer library-family boundary; they do
not alter runtime behavior. Each was checked with `git diff --check`, and the
latest docs-only boundary was independently reviewed.
