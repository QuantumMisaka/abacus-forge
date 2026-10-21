# Forge `03b4957` 上层交接候选

状态：当前 main 候选，取代 [`25cd715`](2026-10-21-forge-main-25cd715-candidate.md)。
这不是 release，也不声明 Paimon 已采用。

## 候选身份

- 源码：`main` `03b49577e0021b0989f2eb1dbd778df27a1bd823`，工作树 clean。
- wheel SHA256：`831355d3867a177cc0d231f37f432c39d6afe494204d97fea73d9c0b22846acd`。
- sdist SHA256：`d19aa44d452d4d9f1243b3f47cac9aeee0b83377cf8d56801edd2973023f857d`。
- wheel 内 76 个 Python 模块与源码逐字节一致；optional extra 为 `abacuslite==1.2.2`。
- 相对 `25cd715`，collect 继续拒绝单个 selector 内重复轨道，但允许同一原子对的
  i/j 轨道重叠；这匹配 PyATB intrasite pair 语义。

## 验证

- 新增 intrasite overlap 完整性用例；恢复旧全局重叠拒绝的受控 mutation 令其失败，
  还原修复后通过。
- 聚焦 COHP/CLI/contracts 回归：**355 passed**。
- 本地安装态 package/parser/canonical parity：**55 passed**；同一 wheel 的 direct NAO
  COHP 回归：**22 passed**。
- 分支和 main hosted CI 均成功。

## 边界

不发布 PyPI 或 GitHub release。Paimon owner 采用前必须显式重绑该 wheel/commit，并按
owning PLAN 重跑受影响入口；本记录不替代 Benchmark、SAI 或科学验收。
