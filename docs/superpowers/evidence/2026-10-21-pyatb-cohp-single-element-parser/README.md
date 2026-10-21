# PyATB COHP single-uppercase-element parser blocker

日期：2026-10-21。在用真实 NiO `nspin=2` sparse HR/SR 验证 direct NAO COHP 时，
PyATB candidate `1.1.2.dev0+5f7e132` 在 `resolve_cohp_orbitals` 阶段失败：
`ValueError: atom index 2 is not present in STRU`。

根因是 `_section_lines` 用 `^[A-Z_]+$` 识别“下一个 section header”；NiO 的
`ATOMIC_POSITIONS` 中单字母元素 label `O` 也满足该 regex，因此 positions section
在 O atom 前提前终止，orbital map 只剩 Ni（27 个轨道）。

## 最小修复

[fix-single-uppercase-element.patch](fix-single-uppercase-element.patch) 将 section
终止条件改为只接受已知 ABACUS STRU section header。PyATB 分支：

- `QuantumMisaka/pyatb:fix/stru-single-letter-element`
- commit `b0012a8`

验证：

- 新 parser regression 先 RED：Ni/O 两个 atoms 只剩 Ni；
- patch 后 focused tests：**44 passed**；
- PyATB 全量当前测试：**77 passed, 1 skipped**；
- 补丁后真实 NiO `nspin=2 sum` COHP collect：**complete**，Ni–O pair factor `2.0`，
  结果见 [nio-patched-summary.json](nio-patched-summary.json)。

PyATB fork 的 `sidereus-adam` 后续出现独立 normalization/output 更新。该 fix 已重放到
新基线：`fix/stru-single-letter-new-base` commit `e1db9d2`（base `9c5ffdc`），focused
tests **44 passed**，全量 **77 passed, 1 skipped**。因此 parser 修复可绑定到最新
candidate branch，不依赖旧 snapshot。

Git tree 核查进一步确认 `b0012a8` 与 `e1db9d2` 的 `src/` tree hash 完全一致
（`97df50e…`），`src/` diff 为空；`tests/` 差异只有
`tests/fixtures/abacus-csr/provenance.json` 的 provenance metadata。因此已归档的
NiO `sum/up/down` runtime 证据可直接适用于 rebased `e1db9d2`，无需为 parser rebase
重复三条真实 COHP run。

## 边界

这是一个 dependency blocker 记录和 local patched branch 验证，不是 PyATB 上游
release，也不改变 Forge `4106f33` wheel/sdist artifact 身份；更广材料/自旋科学
验收仍另行推进。

## NiO `nspin=2` spin coverage

用补丁后的 PyATB branch `b0012a8`，对同一 retained NiO `nspin=2` sparse 矩阵和
Ni–O `s/p` disjoint pair 分别执行 `spin=sum/up/down`。三条 collect 均为
`complete`；`up` 与 `down` ICOHP 数值不同，证明确实消费了两个 spin channel，
`sum` 的 `spin_degeneracy=1` 语义也按 candidate 实现。曲线、metadata、逐 run
摘要和输入 SHA-256 见 [nspin2-spin-coverage.json](nspin2-spin-coverage.json)
与 [spin-runs/](spin-runs/)。

该证据扩展自上述 blocker 的 patched dependency smoke，仍限一个 NiO case 和一个
selection，不宣称多材料 parity、收敛、科学验收或 Paimon 平台验收。
