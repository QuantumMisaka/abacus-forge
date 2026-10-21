# Forge `4106f33` 上层交接候选

状态：当前 runtime/main 交接候选，取代
[`01fbb2a`](2026-10-21-forge-main-01fbb2a-candidate.md)。这不是 release，也不声明
Paimon 已采用。

## 候选身份

- 源码：`main` `4106f33505b552f1dee837c6f2e6bf24e514cf83`，工作树 clean。
- wheel SHA256：`ae3705aa8d801a969f80ae7b3c418ec546e7fa66ba46a65094b80140cc393ad1`。
- sdist SHA256：`489cb160f375b1e720360cbee6773bb36f173f64126bedfb0067b4fc3830cfdb`。
- wheel 内 76 个 Python 模块与源码逐字节一致；optional extra 为 `abacuslite==1.2.2`。
- 相对 `01fbb2a`，`capabilities.contracts["pyatb-cohp"].result` 现在显式暴露
  PyATB pair convention/factor 规则，供 Agent 在发请求和读结果前消费。
- `main` 后续的 `36633b9` / `c93d793` 只增加 relax stress 交接、COHP 跨实现对照
  和矩阵核查文档/证据；`src/`、`tests/`、`pyproject.toml` 与 CI workflow 相对本候选
  无变化，因此 wheel/sdist 身份保持有效。

## 验证

- 新 discovery 断言先在 main discovery 上 RED，修复后 GREEN。
- 聚焦 COHP/CLI/contracts 回归：**360 passed**。
- Paimon Python 3.11 环境全离线回归：**1547 passed, 35 skipped**。
- 本地安装态 package/parser/canonical parity：**55 passed**；同一 wheel 的 direct NAO
  COHP 回归：**27 passed**。
- 分支和 main hosted CI 均成功。

## 边界

不发布 PyPI 或 GitHub release。Paimon owner 采用前必须显式重绑该 wheel/commit，并按
owning PLAN 重跑受影响入口；本记录不替代 Benchmark、SAI 或科学验收。
