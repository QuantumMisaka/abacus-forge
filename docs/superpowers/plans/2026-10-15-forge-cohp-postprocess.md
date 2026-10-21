# Forge COHP postprocess implementation plan

Spec: [2026-10-15-forge-cohp-postprocess-design.md](../specs/2026-10-15-forge-cohp-postprocess-design.md)

Follow-on pointer (2026-10-21): direct NAO/PyATB COHP is a separate capability,
not an extension of this IAO-only W1 implementation. See the [bounded NAO
SPEC](../specs/2026-10-21-forge-pyatb-cohp-design.md) and [current
implementation/verification plan](2026-10-21-forge-consumption-followup.md).
This historical plan remains the record for W1 and its stated follow-up evidence.

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

后续真实输入验收（2026-10-15）：用户确认继续后，以同一 wheel 对 SAI job `1760372` 的完整 Si SCF 输入执行五组 IAO postprocess；总曲线与原始完整数据结果最大差 `4.77e-15`，s/p 分解 ICOHP 求和残差 `0.0 eV`。产物与 audit 均通过核对，详见[真实输入证据](../evidence/2026-10-15-forge-real-evidence.md#完整-si-scf-上的-cohp)。这是既有真实 SCF 输入的本轮后处理，不是新 SCF、legacy parity 或多材料科学验收。


## 已确认的方法口径与后续对照（2026-10-19）

用户确认按直接 NAO-COHP / IAO-COHP 区分。此次落实术语、机器 schema 描述和参考
记录；不改变 W1 的 `cohp` capability、`method="iao"`、默认值、算法或成熟度。

- [x] README、guide/reference、请求说明与 schema 明示当前交付 IAO-COHP；直接
  NAO-COHP 未作为 typed 方法提供，避免将 `cohp` 名称误解为方法全集。
- [x] 核对直接 NAO 路径：`abacus-cohp-lcao::cal_COHPmatskIJ_e_ij`、
  `abacustools::_pair_value`、PyATB `cohp_values_one_k` 均采用原轨道块收缩；
  相同公式不视为代码继承或完整数值 parity。源码与快照见[参考记录](2026-09-09-forge-core-fidelity-references.md#cohp-provenance-20261019)。
- [x] 选择同一完整 SCF 数据，固定 producer 版本、PP/ORB、结构、H/S/C、k 权重、
  spin 与 Fermi 信息，分别运行可消费该输入的实现。PyATB 如从 H(R)/S(R) 重建并
  求解，应独立核对本征值和矩阵，而不能假定与原始 WFC 完全等价。
  2026-10-21 已以 LTS v3.10.1 Si SCF 和 36 k 点完成 `abacus-cohp-lcao` 与
  Forge→PyATB 对照，见[跨实现证据](../evidence/2026-10-21-forge-direct-cohp-cross-implementation/README.md)。
- [x] 直接 NAO 实现间先对齐单位、spin 简并、单/双序、能量参考、展宽、积分
  与周期像定义；明确保存原始输出与归一化步骤，再报告差异，不能调整科学默认值
  只为让数值通过。同证据对齐 eV、nspin=1 sum、disjoint pair factor 2、绝对能量、
  36 k 点权重和展宽前离散积分；两条展宽输出保留，展宽核差异不当 parity gate。
- [x] IAO 与直接 NAO 的对比独立报告方法差异，不要求不同轨道表示的曲线/ICOHP
  相等；检查能量参考平移、周期像与基组选择的影响，保留已知方法局限。
  同证据报告 IAO s/p 为 -0.6040196342 eV，direct NAO 两实现为 -0.8790256696 /
  -0.8804348613 eV；方法差异保留，不作等值门禁。
- [x] 如确定需要新增直接 NAO typed 方法，先补其输入/方法标识、产物、外部依赖
  与版本边界设计，并取得相应确认后实现；此次术语确认不自动批准 legacy bridge。
  2026-10-21 已按独立 SPEC 确认并实现 `pyatb-cohp`，legacy bridge 未批准。

这些待办归属现有 COHP 计划，验收产物应包含版本/输入来源、方法约定表、原始和
归一化数值、差异归因与未覆盖项；不以化学方向看似合理替代方法验证。

### 当前状态（2026-10-21）

“新增直接 NAO typed 方法”的设计前置已由用户批准，并经
[NAO/PyATB SPEC](../specs/2026-10-21-forge-pyatb-cohp-design.md) 与
[消费接续计划](2026-10-21-forge-consumption-followup.md)完成。2026-10-21 的跨实现
对照进一步闭合了上列方法对照项：同一 LTS Si SCF 上 `abacus-cohp-lcao` 与
Forge→PyATB 的离散 ICOHP 差为 `1.409e-3 eV`（相对 `0.1603%`）；IAO/direct NAO
方法差异单独保留。该证据限于一个 Si nspin=1 `s/p` case，不关闭更广材料、自旋、
安装平台或科学验收。

本轮验证：`paimon` 环境下运行 `tests/test_architecture.py`、`tests/test_cohp_iao.py`、
`tests/test_postprocess_services.py`、`tests/test_postprocess_machine_cli.py`，53 passed；
真实 CLI `schema cohp postprocess` exit 0，返回 `enum=["iao"]` 及 IAO-COHP 描述。
154 个本地文档链接/锚点检查与 `git diff --check` 通过。本轮未执行新的 ABACUS 计算
或跨方法数值对照，不将上述待办标记为已验收。
