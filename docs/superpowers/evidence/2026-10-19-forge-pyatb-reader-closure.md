# PyATB CSR 修复候选与 Forge 双轨回放

2026-10-19，用户在上一轮定位后授权继续修复。Forge 基线 `01f724c`；PyATB 修复提交 **`cfa5fb1`**，基于 `80f7c2d`，保留在本地 `codex/csr-reader-compat` 分支及 `/home/james/scratch/pyatb-csr-reader-20261019` 工作树。Forge 生产代码、共享环境和已发布 PyATB 均未修改。

## 修复与行为证据

PyATB `io/abacus_read_xr.py` 的共同 H/S reader 识别旧头部和带注释的新 HContainer 头部，按声明数量读取分行实数/复数 CSR 数组，处理新旧空块差异，校验长度、列范围、行指针和有限值；保持单位换算及三角存储。rR reader 保持原实现，当前 develop 的 rr.csr 仍采用其可读的旧内容格式。

真实进程随后暴露 H/S 的 R 列表不同：新 S 省略 30 个全零块，旧 solver 要求相同列表。因此在 PyATB 的 ABACUS 输入汇合处新增有序 R 并集与稀疏行重排，供 `main.py` 和 `init_tb.py` 使用；保留 H↑/H↓、S-only、rR-only 的非零值，不修改输入对象，不改变 solver 或 WANNIER90 路径。这是稀疏数据表示对齐，不修改矩阵数值或 Forge 公共契约。

- Reader 回归：[基线 11 failed / 7 passed](2026-10-19-forge-pyatb-reader-closure/reader-red.txt)；修复后初版 18 passed。
- 输入汇合回归：[基线 6 failed](2026-10-19-forge-pyatb-reader-closure/alignment-red.txt)，覆盖 nspin=1/2/4 × dense/sparse。
- 最终 PyATB 仓库测试：**[39 passed，0.95s](2026-10-19-forge-pyatb-reader-closure/tests.txt)**；包含真实压缩 Si fixture、新旧格式、复数、空块、截断/损坏、前导空白、对齐的输入不变与错误边界。测试配置使用 MPI/native 接口替身，不冒充真实引擎执行。
- [数值核对](2026-10-19-forge-pyatb-reader-closure/numerical-parity.json)：旧格式 H/S/rR 修复前后逐值完全相同；新旧真实 H/S 按 R 并集对齐后逐值完全相同。H 均有 93 个 R；S 为 develop 63 / LTS 93，多出的 LTS 块全零。

## 实际消费结果与运行身份

复用[前轮实际 ABACUS 矩阵](2026-10-19-forge-pyatb-dual-handoff.md)，**没有重跑 ABACUS**。使用同一已安装 Forge wheel，实际执行候选 PyATB：

| 来源 | prepare | execute | collect |
| --- | --- | --- | --- |
| develop / Si LCAO / nspin=1 | 成功，原名 H/S/rR 交接 | completed，returncode=0 | complete，3 个输出产物，3 条总事件 |
| LTS / Si LCAO / nspin=1 | 成功，旧名 H/S/rR 交接 | completed，returncode=0 | complete，3 个输出产物，3 条总事件 |

每个操作核对 artifact 相对路径、大小、SHA、事件 payload/ref；源文件保持不变。两条 band.dat 与前轮原版 PyATB 的 LTS band.dat 字节相同，SHA256 为 `3a41219dfb67c40ebe97b3d38153cff63cc2f9654b9e56ddb7c80483218451a3`。三者解析观测 band_gap=0.5348 eV，仅是短 G–X 路径的结果，不是完整带隙科学验收。全部 `scientific=unassessed`。

[运行绑定](2026-10-19-forge-pyatb-reader-closure/runtime-binding.json)记录候选 **79 个 Python 文件**、复用的既有 PyATB 1.1.2 native extension 及 bundled libraries 的 SHA。实际载体是隔离候选源码加既有二进制依赖，**不是重新构建/发布的 wheel，也不是对当前已安装包的升级**。真实 nspin=2/4、更多材料/性质及候选打包发布仍需各自验收。

[结果摘要](2026-10-19-forge-pyatb-reader-closure/replay-summary.json)、[请求/响应/审计/工件归档](2026-10-19-forge-pyatb-reader-closure/replay-artifacts.tar.gz)与[归档 SHA](2026-10-19-forge-pyatb-reader-closure/archive-sha256.txt)保留消费证据。最初隔离复制漏带 pyatb.libs，产生动态库导入失败；补齐后暴露 R 列表不一致，修复后才通过。本机所有失败和成功目录均保留在 `/home/james/scratch/pyatb-csr-validation-20261019`。

## 复现及下一步

1. 在 PyATB 依赖环境中运行 [stage_runtime.py](2026-10-19-forge-pyatb-reader-closure/stage_runtime.py)，传 `--source /path/to/pyatb-cfa5fb1/src/pyatb --output /absolute/new-runtime`；脚本复制候选源码、现有 native extension 和 pyatb.libs，不修改共享环境。脚本实际生成载体后的全部源码、native 和 library SHA 已与本轮运行绑定核对一致。
2. 用已安装 Forge 的 Python `-I` 运行前轮 `replay.py --sources /absolute/extracted-producer-root --output /absolute/new-workspaces --pyatb /absolute/new-runtime/pyatb-candidate`。两轨输入直接使用前轮归档，无需计算。
3. PyATB owner 后续构建并验收候选 wheel，再决定上游提交/发布及消费端版本绑定。当前源代码修复已通过局部和真实消费验证；已安装/发布的旧 reader 仍有原缺口，不能将候选成功写成发布组合已修复。

独立代码审查发现的旧头部前导空白回退已修复，并补 H/S 回归；reader 与新增 R 对齐复核均无阻断问题。本轮不推送或发布；PyATB 修复分支保留，Forge 仅收录交接与版本边界证据。

最终独立交付复核通过：79 个候选 Python 文件、native extension 与 bundled libraries 身份一致；6 个事件、24 个 ArtifactRecord 与归档匹配；三方 band.dat 字节一致。131 个本地文档链接、复现脚本语法及 staged diff 检查通过。
