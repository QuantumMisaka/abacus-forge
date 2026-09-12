# Forge mainline integration Implementation Plan

**Goal:** 将已审查的 `forge-core-fidelity` typed capability 线与 `main` 上后续的 typed asset/runner 安全修复合并为一条可验证的 Forge 主线，不改变已批准的产品边界。

**Spec:** 复用已批准的 `docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html`、`docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html` 及各 capability 的已批准/已落地 PLAN；本次不新增公共契约。

**Authorization:** 用户持续授权端到端推进 Forge；本批次只在新建的 `forge-mainline-integration` 隔离分支中验证合并，不直接改写 `main`、不 push。

**Architecture:** 保留 `forge-core-fidelity` 的 typed service、manifest、MD/postprocess、export、ATST 和 nspin=4 能力，同时保留 `main` 在 `assets.py` 与 `runner.py` 中的路径、symlink、basename、caller-cwd 和 command-identity hardening；四个冲突测试文件取两侧有效回归的并集。除冲突解析外不引入新行为。

**Verification:** 冲突相关测试先行，再运行完整离线 pytest、architecture/forbidden-import、clean archive 与 wheel/import/console gate；独立审查整合差异。真实 ABACUS/PyATB、科学判定、工作流编排和平台调度不属于本整合证据。

## Scope and ownership

- `src/abacus_forge/assets.py`: 合并两侧资产 basename 校验与 typed materialization/path/symlink hardening。
- `src/abacus_forge/runner.py`: 合并 caller-cwd/lexical executable resolution、PATH 解析、命令身份保持与 typed runner 调用。
- `tests/test_assets.py`, `tests/test_service_status.py`: 保留两侧针对上述安全和兼容行为的回归测试。
- 其余已暂存文件：只接受两个已审查分支的内容，不在本批次重写。
- 本计划和 SDD ledger：记录整合决策、验证证据和未完成的发布门禁，不成为运行时契约。

## Task 1: Resolve the four integration seams

**Dependencies:** merge base `e7a9cc8`; source branches `main` (`b6d83ef`) and `forge-core-fidelity` (`96627f6`).

- [x] 保留两侧资产输入的显式路径、单 token basename、symlink containment、无部分写入和 falsy mapping rejection。
- [x] 保留两侧 runner 的 caller cwd、相对/绝对/PATH 解析、显式 `./` 与 lexical symlink argv[0] 语义，以及公开原始 command。
- [x] 合并四个冲突测试文件，不删除任一侧的有效安全回归。
- [x] `git diff --check` 与冲突扫描通过后提交整合结果（merge commit `7f80804`）。

## Task 2: Verify the integrated source

- [x] 运行冲突相关 owning tests，确认两类行为同时通过（`634 passed in 70.35s`）。
- [x] 运行完整离线 suite、architecture gate 和 discovery/process checks（`1218 passed, 5 skipped in 111.00s`；architecture `8 passed in 7.91s`；capabilities/schema/operation help and unknown-schema envelope checks passed）。
- [x] 从整合提交生成 clean archive 并运行 owning tests（`632 passed in 16.22s`）。
- [x] 构建 wheel，在全新 venv 中安装 declared dependencies，验证 import/console entry point 且不引入 legacy Forge 运行时依赖（wheel `d5e6adefe41ec42d7f9d6d623fd0615b379cf414428e5a5dcf5698508c16e9d3`；fresh venv import/capabilities/schema/operation help passed；`abacus_agent_tools`, `abacustest`, `aiida`, `atst_tools` absent）。

## Task 3: Review and handoff

- [x] 由独立 reviewer 检查整合差异与两份批准 SPEC，确认没有公共契约漂移或边界越界（`b6d83ef..7de2d47`；Critical/Important/Minor 均无）。
- [x] 将真实执行/科学验证明确保留为未完成的后续发布门禁，不把离线 fixture 结果晋升为成熟度证据。
- [x] 保持 `main` 和远程状态不变；只有用户另行授权时才进入合并或推送。

## Rulings

- `Ruling: union the two branches at the four concrete seams — both lines contain independently reviewed behavior; dropping either would regress a current security or compatibility guarantee. The cost if wrong is a bounded merge repair, not a public-main mutation.`
- `Ruling: treat this as integration, not a new capability contract — the approved SPECs and existing capability plans remain normative, so no new wire field, schema version, manifest enum, or scientific policy is introduced.`

## Completion record (2026-09-11)

The isolated integration branch is complete and review-ready at `09c935c` (merge `7f80804` plus the verification-plan record and close-out evidence). Focused, full offline, architecture, clean-archive, wheel/fresh-venv, discovery, and diff-hygiene gates passed; independent whole-branch review of `b6d83ef..7de2d47` returned no Critical/Important/Minor findings, and the final docs-only close-out was re-archived successfully. `main` and the remote remain untouched. This record does not promote experimental capabilities or claim real ABACUS/PyATB/scientific acceptance.
