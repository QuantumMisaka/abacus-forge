# Forge `25cd715` 上层交接候选

状态：当前 main 候选，取代 [`b4693f6`](2026-10-21-forge-main-b4693f6-candidate.md)。
这不是 release，也不声明 Paimon 已采用。

## 候选身份

- 源码：`main` `25cd7157b8f3824c7ff9e353f9e5209798bb8cc5`，工作树 clean。
- wheel SHA256：`bd86aa0f751141cb7bd3ff3eb6a79d53f11a90c959b4e6957f08dfd390d12d12`。
- sdist SHA256：`6a7b4495c8afc3b1f0bd493f3c8aac603beb53494a5547c555fce6e7825e9076`。
- wheel 内 76 个 Python 模块与源码逐字节一致；optional extra 为 `abacuslite==1.2.2`。
- 相对 `b4693f6`，collect 现在验证 PyATB COHP metadata 的 `total_orbitals`、原子
  轨道区间覆盖，以及所选轨道落在合法原子区间且不重叠。

## 验证

- 修复前新增 6 个 RED 用例；修复后聚焦 COHP/CLI/contracts 回归 **353 passed**。
- Paimon Python 3.11 环境全离线回归：**1540 passed, 35 skipped**。
- 本地安装态 package/parser/canonical parity：**55 passed**；同一 wheel 的全部
  direct NAO COHP 回归：**20 passed**。
- develop/LTS 两份真实 PyATB COHP metadata 回放均 `collection=complete`。
- 远端分支与 main CI 均成功。

## 边界

不发布 PyPI 或 GitHub release。Paimon owner 采用前必须显式重绑该 wheel/commit，
并按其 owning PLAN 重跑受影响入口；本记录不替代 Benchmark、SAI 或科学验收。
