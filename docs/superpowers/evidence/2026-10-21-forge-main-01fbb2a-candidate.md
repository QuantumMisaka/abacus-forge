# Forge `01fbb2a` 上层交接候选

状态：**已由 [`4106f33`](2026-10-21-forge-main-4106f33-candidate.md) 取代**。保留当时的
候选身份；不要把它当作当前 `main` 交付候选。

## 候选身份

- 源码：`main` `01fbb2ac0414cf9c40d753901f2f03c21c3c229b`，工作树 clean。
- wheel SHA256：`4c82db574167a46efe7cf62518fe27732e9cea541a1df8aa254155e0ee1feaef`。
- sdist SHA256：`db4ccad1cbc689224a2a74085b1572620c01b5adbaa7a581fe3e1e62b0c05190`。
- wheel 内 76 个 Python 模块与源码逐字节一致；optional extra 为 `abacuslite==1.2.2`。
- 相对 `03b4957`，collect 校验 PyATB `pair_convention`，并要求 orbital selection 只能是
  identical（factor 1）或 disjoint（factor 2）；部分重叠 fail-closed。

## 验证

- 5 个新增非法 pair/factor 用例在旧实现上 RED；修复后通过。
- 聚焦 COHP/CLI/contracts 回归：**360 passed**。
- Paimon Python 3.11 环境全离线回归：**1547 passed, 35 skipped**。
- 本地安装态 package/parser/canonical parity：**55 passed**；同一 wheel 的 direct NAO
  COHP 回归：**27 passed**。
- develop/LTS 真实 PyATB metadata 回放均 `collection=complete`。
- 分支和 main hosted CI 均成功。

## 边界

不发布 PyPI 或 GitHub release。Paimon owner 采用前必须显式重绑该 wheel/commit，并按
owning PLAN 重跑受影响入口；本记录不替代 Benchmark、SAI 或科学验收。
