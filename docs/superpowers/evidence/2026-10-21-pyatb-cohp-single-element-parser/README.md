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

## 边界

这是一个 dependency blocker 记录和 local patched branch 验证，不是 PyATB 上游
release，也不改变 Forge `4106f33` wheel/sdist artifact 身份；更广材料/自旋科学
验收仍另行推进。
