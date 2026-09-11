# Forge typed PyATB nspin=4 交接 Implementation Plan

**Goal:** 在不扩大 Forge 职责的前提下，让实验性的 typed `pyatb-band` 正确支持 PyATB 的 `nspin=1|2|4` 与 HR 路由数量 `1|2|1`。

**Spec:** `docs/superpowers/specs/2026-09-10-forge-typed-pyatb-nspin4-design.html`；上位约束来自 `2026-09-01-forge-contract-first-rearchitecture-design.html` 与 `2026-09-02-forge-service-status-migration-design.html`。

**Authorization:** 用户已授权沿 Forge 已批准 SPEC 主线持续推进；本批次是 ROADMAP 中已登记、但尚未落地的 typed PyATB nspin=4 handoff 小切片。设计依据为本地 `pyatb` revision `80f7c2d` 的 `operate_HR_route` 和 ABACUS reader。

**Architecture:** 在 `pyatb_contracts.py` 集中定义允许的 spin mode 与 HR cardinality；discovery 复用同一允许值公布 schema；现有 `pyatb_typed.py` staging/input renderer 和 `pyatb_manifest.py` 只消费已验证的显式路径，因此 nspin=4 仅需通过正确的单 HR contract。nspin=4 的唯一 HR 在既有 manifest v1 中保持 `matrix_hr/shared`。不增加 property selector、矩阵解析、编排、调度或科学判断。

**Verification:** TDD RED→GREEN；contracts/discovery、typed prepare/manifest、machine/API parity、legacy PyATB regression；随后完整离线 pytest、architecture/import/clean-wheel 门禁与 `git diff --check`。不启动真实 PyATB/ABACUS，不把离线 fixture 当科学或 real-smoke 证据。

## Global constraints

- 保持 `forge.request/v1`、`forge.result/v1`、`forge.pyatb-manifest/v1`、event、artifact ref、错误类和 exit mapping 不变。
- `pyatb-band` 仍只声明 `prepare|execute|collect`，成熟度仍为 `experimental`；旧 nspin=1/2 wire 形式和所有 legacy helper 不变。
- nspin=1/4 恰好一个 HR；nspin=2 恰好两个 HR；SR 恰好一个，rR 可选且最多一个。只校验显式 workspace-relative 文件、生成输入和 provenance。
- nspin=4 的 HR/SR 以及供给时的 rR 内容不在 Forge 解析范围；实际 PyATB 进程自行报告输入内容错误。Forge 不返回 property、spin-texture、接受/拒绝或科学质量判断。
- 不修改 main，不合并、不 push；只在当前隔离 worktree 形成可审查提交。

## 文件责任

- `src/abacus_forge/pyatb_contracts.py`: allowed nspin 与 HR cardinality 的唯一运行时契约。
- `src/abacus_forge/discovery.py`: 将同一允许值和 HR cardinality conditional 公布到 typed prepare schema。
- `tests/test_contracts.py`, `tests/test_machine_cli.py`, `tests/test_cli_process.py`: request/cardinality/decoder/discovery/process 契约。
- `tests/test_pyatb_typed.py`: nspin=4 prepare、Input route、manifest 和 service/API 事实。
- `README.md`, `ROADMAP.md`, 本 SPEC 关联说明: 仅更新当前能力与明确延后项，不重写历史计划证据。

## Task 1: Add RED tests for nspin/cardinality and discovery

**Files:** `tests/test_contracts.py`, `tests/test_machine_cli.py`, `tests/test_cli_process.py`, `tests/test_pyatb_typed.py`（只新增测试，不修改生产代码）。

**Behavior:**

- request constructor/JSON decoder accepts nspin 1, 2 and 4;
- nspin=4 requires exactly one HR; zero/two HR are rejected before staging;
- nspin=1 still requires one HR; nspin=2 still requires two HR;
- discovery schema publishes enum `[1, 2, 4]` and conditional HR cardinality (`nspin=2` → 2; omitted/1/4 → 1), decoder routes nspin=4 without silently defaulting to 1;
- JSON schema integer/type and runtime constructor both reject boolean nspin;
- typed prepare with one nspin=4 HR produces `nspin 4`, one `HR_route`, shared SR, and a shared rR only when supplied; the manifest always contains `matrix_hr/shared` and only conditionally contains `matrix_rr/shared`.
- an isolated machine-process nspin=4 prepare produces the same envelope facts as the direct service API.

**RED verification:** 先在当前 baseline（nspin=4 尚未实现）运行新增 focused tests；预期仅因现有 `nspin must be 1 or 2` 或 cardinality/schema 不符而失败，不接受 setup/import failure 作为 RED。

- [x] Add the smallest contract, discovery and typed integration tests.
- [x] Run the focused tests and retain the exact RED output in the SDD ledger.
- [x] Commit the test-only package so the implementation package can consume a stable failing snapshot.

## Task 2: Implement the minimal contract/discovery change

**Files:** `src/abacus_forge/pyatb_contracts.py`, `src/abacus_forge/discovery.py` only.

**Dependencies:** Task 1 test snapshot.

**Behavior:**

- define one internal allowed-value/cardinality mapping (`1→1`, `2→2`, `4→1`);
- reject bool and unsupported integers with the existing request error behavior;
- validate HR list length against the mapping, with a mode/cardinality-specific message;
- make discovery’s nspin enum derive from the contract constant and add a JSON Schema `if/then/else` for HR cardinality (nspin=2 → exactly 2; omitted/1/4 → exactly 1);
- do not alter `to_dict()` field names, schema version, manifest schema, renderer or legacy code.

**Verification:** focused `tests/test_contracts.py tests/test_machine_cli.py tests/test_pyatb_typed.py tests/test_cli_process.py`; the Task 1 RED tests must turn GREEN, and all pre-existing assertions remain green.

- [x] Implement the smallest production change.
- [x] Run the focused suites and inspect the exact diff for no unrelated API changes.
- [x] Commit the implementation package.

## Task 3: Documentation and approved-SPEC alignment

**Files:** `README.md`, `ROADMAP.md`, `docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html`, `docs/superpowers/specs/2026-09-10-forge-typed-pyatb-artifact-manifest-design.html` only where an explicit nspin=4 deferral now contradicts the approved current status; do not edit completed historical plan evidence except by adding a short follow-up pointer if needed.

**Behavior:**

- README states nspin 1/2/4, HR cardinality 1/2/1, and nspin=4 shared manifest semantics;
- ROADMAP marks only this experimental handoff as implemented and keeps PyATB properties, real-smoke, scientific interpretation, aggregation and orchestration outside scope;
- approved status text no longer says nspin=4 is globally unsupported, while it continues to state that properties/real execution need separate evidence;
- no text implies Forge owns scientific validation, workflow orchestration, scheduling or DeePMD.

**Verification:** HTML parse/placeholder scan, `rg` contradiction scan, `git diff --check`; documentation changes do not require synthetic RED/GREEN.

- [x] Update the smallest set of current-status paragraphs.
- [x] Re-read all changed passages against the new SPEC and ROADMAP boundaries.
- [x] Commit docs separately from behavior code.

## Task 4: Final gates and independent review

**Files:** current branch only; update `.superpowers/sdd/2026-09-10-forge-typed-pyatb-nspin4/progress.md` (ignored ledger) with exact evidence.

**Verification:**

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_contracts.py tests/test_machine_cli.py tests/test_cli_process.py \
  tests/test_pyatb_typed.py tests/test_pyatb.py tests/test_workspace.py

env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q -p no:cacheprovider

git diff --check
```

Also run the repository’s architecture/forbidden-import, discovery, clean archive and wheel/import gates for this public contract change; if an environment-specific gate cannot run, record the exact narrower boundary and failure rather than implying it passed. No command may be described as real PyATB/ABACUS or scientific evidence.

- [x] Bind focused and full outputs to the final revision.
- [x] Obtain an independent task/whole-branch review appropriate to the public request/schema change.
- [x] Repair every Critical/Important finding, or record evidence disproving it; leave only bounded Minor follow-up items.
- [x] Mark this plan complete only after current worktree status and `git diff --check` are clean.

## Plan self-review and rulings

- The scope is one public field’s accepted values plus a derived HR cardinality; a single implementation plan can cover it without a new engine or persistence layer.
- The existing typed renderer already emits one route for a one-element HR list, and the existing manifest builder maps a single HR to `shared`; no production changes are planned in those modules unless tests expose an actual defect.
- `Ruling: use an internal `(nspin, expected_hr_count)` mapping, derive discovery's enum from it, and express its two cardinality branches with JSON Schema if/then/else — runtime and machine-readable validation then reject the same malformed request without adding wire fields.`
- `Ruling: keep nspin=4 HR as manifest `shared` — the manifest describes the one explicit route, not a complete spinor physics taxonomy; adding a new enum would expand v1 without a consumer need.`
- `Ruling: do not add a real-smoke gate to this implementation plan — real process validation is a later release gate, while this batch proves only typed handoff and facts.`

## Follow-up correction (2026-09-11)

The local PyATB input contract confirms that `BAND_STRUCTURE` consumes HR/SR and does not require an rR route. The typed request therefore keeps `rr_path_rel` nullable/optional: supplied rR files remain strict workspace-relative handoffs with manifest provenance, while omitted rR produces no route or `matrix_rr` entry. This correction narrows an unnecessary input requirement without changing the nspin cardinality or Forge's facts-only boundary.

## Execution evidence (2026-09-11)

- Test-only RED commits: `23d9951`, `743d211`; the expected baseline failures are recorded in the SDD ledger. Production contract/discovery commit: `b51728c`; docs alignment commits: `836e293`, `e588cd6`, `e184769`; complete process/API parity strengthening: `1af88c2`.
- Focused nspin4 boundary after implementation: `8 passed, 457 deselected`; owning contract/CLI/PyATB/workspace suites: `506 passed`; full offline suite: `1218 passed, 5 skipped`.
- Architecture/forbidden-import gate: `8 passed`; discovery process gate exposes `pyatb-band` as `experimental`, operations `prepare|execute|collect`, nspin enum `[1, 2, 4]`, and conditional HR cardinality `2→2`, `1/4/default→1`; `operation --help` exposes both `--request` and `--stdin`.
- Behavior/doc implementation closeout revision: `ace93b7`; this evidence-only update completes the plan. Clean archive owning suite: `506 passed in 71.03s`; wheel build produced `abacus_forge-0.1.0-py3-none-any.whl` (sha256 `a2f1bcdb8ab55e7379cd1e2204d336e6183a4ab92f863490324f100ffafd1cf7`), fresh venv import/console checks passed, and `abacus_agent_tools`, `abacustest`, `aiida`, and `atst_tools` were absent.
- HTML gate: `xmllint --html --noout` passed for both changed SPEC files; placeholder scan and `git diff --check` passed. Independent whole-branch review of the implementation/doc diff found no Critical, Important, or substantive Minor findings. No real PyATB/ABACUS process or scientific validation is claimed by this plan.
