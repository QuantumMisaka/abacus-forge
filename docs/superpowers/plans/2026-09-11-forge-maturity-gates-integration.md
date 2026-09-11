# Forge maturity-gates candidate integration plan

**Goal:** 将已分别审查的 typed MD postprocess hardening、real-smoke freshness
门禁和当前 ABACUS 原生输出兼容修复放在同一候选分支上验证，为后续正式集成提供
一组不改变 Forge 版本化运行时契约的发布证据。

**Normative sources:** approved Forge 2026-09-01/09-02 SPECs，以及
`2026-09-10-forge-typed-md-postprocess-design.html`、
`2026-09-11-forge-md-postprocess-review-fixes.md` 和
`2026-09-11-forge-real-smoke-freshness.md`。本文件只记录候选整合，不新增公共字段或能力。

**Authorization and isolation:** 从正式集成基线 `da1d4df` 派生的 MD 修复候选
`7d813dc` 上建立 `forge-maturity-gates`；只修改此隔离分支，不改写
`forge-mainline-integration`、`main` 或远程。

**Architecture:** 生产代码保持 MD 请求前置校验、精确斜晶胞 minimum-image、质量
fail-closed、真实绘图产物状态和 reported metric；collector 仅补齐当前 ABACUS 原生
SCF 收敛标记、Relax 的 `STRU_FINAL`/`STRU_NOW` 结构名与 `inputs/OUT.*` 域路径、MD
原生日志的 `inputs/OUT.*` 域路径，以及原生结构头部注释。freshness 只在
`tests/real_smoke/` 中拒绝复制源的已知 collector-visible 旧产物，保留非生成 handoff。
这些兼容修复不引入 lineage 字段、调度、重试、workflow、科学验证或新的运行时依赖。

## Scope

- 将已审查的 typed MD real-smoke 与 freshness 测试/文档提交叠加到 MD 修复候选。
- 对照当前 `abacus-develop` 原生输出，补齐上述格式/路径兼容并覆盖 Relax→后续
  nscf/band/dos 的显式结构 handoff。
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
- Initial integration full offline gate: `1257 passed, 6 deselected`.
- Latest candidate full offline gate after native-output follow-up:
  `1277 passed, 6 deselected`.
- Explicit real-smoke selection without supplied inputs: `4 skipped`.
- With a locally built serial PW ABACUS from `abacus-develop@94576a801` and
  prepared PBE/H workspaces, legacy SCF plus typed SCF/Relax/MD machine gates:
  `4 passed`; the same Relax gate with `capability=cell-relax`: `1 passed`.
  These are parser/artifact integration evidence only; all typed capabilities
  remain experimental and `scientific=unassessed`.
- Benchmark opt-in: `2 passed`.
- Latest-candidate clean-environment/package gate: rebuilt after the native-output follow-up
  (SHA-256 `d4eeae4ee37bdfa4fd6df793498f8269cb7720b8ca2a3b60cc2283d18f847988`),
  reinstalled that wheel and its declared dependencies
  into the isolated Python 3.13 venv; `import abacus_forge`, the console entry point,
  `capabilities` (all nine advertised names), and `schema md postprocess` succeeded. The
  venv also confirmed `abacus_agent_tools`, `abacustest`, `aiida`, and `atst_tools` were
  absent. This validates packaging/import boundaries, not real ABACUS execution or science.
- `git diff --check` passes; any supplied real execution remains an opt-in
  integration evidence gate and never becomes scientific acceptance.

## Native-output follow-up

The post-review follow-up commits `c88624f`, `7314e57`, `ff452ec`, `b3b939e`,
`0c1095d`, and `b0beea9` are a same-schema compatibility correction, not a new
capability or status contract. They were driven by the native ABACUS checkout
(`94576a801`): `#SCF IS CONVERGED#`, `STRU_FINAL`/`STRU_NOW` (including CIF and
`inputs/OUT.*` execution layout), annotated structure headers, and native MD
logs are now parsed as factual inputs. The freshness helper rejects only these
known generated names in `inputs/OUT.*`; arbitrary handoff files remain allowed.
All typed results retain `scientific=unassessed` and existing `forge.result/v1`
records.

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
without adding runtime constraints to `execute` or `collect`. The earlier
input-free real-smoke selection skipped four tests; those skips are not
maturity evidence.

The candidate is therefore ready for a separate, explicit integration
decision. `forge-mainline-integration` remains at `da1d4df`, `main` and the
remote remain untouched. The independent review of the native-output follow-up
range `da1d4df..b0beea9` found no Critical or Important issue; its only Minor
notes were stale freshness wording, now corrected above. The post-review
documentation-only commits `dadad05`, `3c795e4`, `25a457b`, and `5afa934`
record earlier acceptance and package/boundary evidence; the present docs-only
corrections record the native-output follow-up and do not alter runtime behavior.

## Post-review closeout (2026-09-11)

The remaining Stage 3 coverage note was closed by `4bb8b41`, which directly
exercises `ScfServiceSet.modify` (not the legacy `ForgeServices` shim); its
focused service suite passed `153` tests. The candidate-wide offline gate at
`3e46946` passed `1295` tests with `6` opt-in skips. Documentation checks
(`git diff --check`, HTML parsing, and placeholder scan) pass, and the merge
tree against `forge-mainline-integration@da1d4df` remains conflict-free. The
property-manifest plan status wording was clarified in `f5c3bbc`; its SPEC is
still Draft/provisional and no normative or stable-release decision is implied.

## Fresh serial-PW runtime confirmation (2026-09-11)

A fresh, generated-output-free copy of the local Si PBE fixtures was used for each
run. The executable was rebuilt from `abacus-develop@94576a801` as a serial PW
binary (MPI/OpenMP/LCAO disabled) against the temporary OpenBLAS/FFTW dependency
prefix. With `--run-real-smoke`, the following gates passed:

- legacy API SCF execute/collect: `1 passed`;
- typed SCF machine execute/collect: `1 passed`;
- typed Relax machine execute/collect with `capability=relax`: `1 passed`;
- typed Relax machine execute/collect with `capability=cell-relax`: `1 passed`;
- typed native-MD machine execute/collect: `1 passed`.

The Relax and cell-relax inputs use the standard `suffix=ABACUS`, so the observed
`inputs/OUT.ABACUS` output domain and `STRU_FINAL`/`STRU_NOW` handoff are the same
paths asserted by the smoke contract. The MD input uses the native `running_md.log`
and `MD_dump` outputs. These runs verify Forge process invocation, workspace
containment, native parsing, artifact references, and persisted event payloads;
they do not assert convergence quality, physical correctness, benchmark parity, or
stable capability maturity. Typed capabilities therefore remain experimental and
their reported scientific state remains `unassessed`.

## Native STRU comment and convergence smoke follow-up (2026-09-11)

The follow-up fix `c73a2f0` makes the existing STRU reader accept native ABACUS
inline `#` and `//` comments. The regression test first reproduced the failure
against an ABACUS test STRU (`Si // Element type`). Independent review then
found that the initial unbounded truncation would corrupt valid asset tokens
such as `pp//Si.upf` and `Si#test.orb`; `ee03c41` narrows recognition to fields
after the expected inputs, with a regression covering both tokens. The targeted
comment suite now passes `4` tests, the owning structure/maturation/API suites
pass `90` tests, and the pre-label-slice full offline gate passed `1298` tests
with `6` opt-in skips. After the native species-label slice, the current full
offline gate passes `1313` tests with `6` opt-in skips.
This is an input-fidelity correction only: it does not add a schema, capability,
status, orchestration, scheduler, or scientific-judgement contract.

After the fix, a fresh generated-output-free Si PBE workspace completed the
experimental `convergence` pack with `key=ecutwfc` and values `[20, 30]`: two
local serial-PW ABACUS executions completed and `post` returned two parsed energy
points. The smoke records prepare/execute/post process and parser compatibility;
it does not establish cutoff convergence, physical correctness, benchmark parity,
or maturity. Property packs therefore remain experimental and outside the
stable Paimon v1.3 capability surface.

## Native spin-density smoke follow-up (2026-09-11)

The current serial-PW ABACUS binary emitted `chgs1.cube` and `chgs2.cube` for a
fresh `nspin=2` property run. Forge initially returned `degraded` because the
legacy property matcher only listed `SPIN1_CHG.cube`/`SPIN2_CHG.cube`; `8ba64b1`
adds the exact current names ahead of the existing compatibility globs and keeps
the older names supported. A regression test covers both native names and the
derived cube manifest. Re-running `post_spin_density` on the fresh ABACUS output
now returns `completed`, records both contained source cubes, and writes
`reports/spin_density.cube`.

This is a filename/parser compatibility correction within the existing legacy
property pack. It adds no typed capability, schema, status, orchestration,
scheduling, or scientific-interpretation contract; spin-density remains
experimental and is not evidence for Paimon v1.3 stable exposure.

## Native ABACUS species-label smoke follow-up (2026-09-11)

The ABACUS Fe spin example uses distinct atom-type labels `Fe1` and `Fe2` for
one chemical element. Before `483ac13`, the Forge STRU reader passed those labels
to ASE as chemical symbols and failed with `KeyError`; the fix stores the
original per-atom labels separately, maps them to canonical ASE elements, and
keeps label-keyed species blocks/resources through STRU writing, supercell and
vacancy edits. Element-keyed asset maps remain the public input convention.
`2af077a` and `77ce4b9` make prefix inference case-sensitive and fail closed for
unknown two-letter prefixes and lowercase labels; standardization rejects
non-element labels rather than silently dropping them. The implementation does
not introduce an `X`/`empty` pseudo-element conversion.

The original Fe1/Fe2 `nspin=2` example was then prepared in a fresh workspace
with the local serial-PW binary built from `abacus-develop@94576a801`. The
property pack completed `prepare`, one `run` subtask, and `post`; native
`chgs1.cube`/`chgs2.cube` were found as contained inputs and
`reports/spin_density.cube` was produced. The owning structure/modify/API gate
passes `96` tests. This smoke confirms input, process, and parser compatibility
only; it does not assert spin-density quality, physical correctness, benchmark
parity, scientific acceptance, or maturity promotion.
