# 双轨真实矩阵到 PyATB 的交接验收

2026-10-19；Forge 基线 `a072413`。按 Engine/Version Policy 的 A 阶段推进真实矩阵消费。生产源码未改；同一隔离 venv 已安装 wheel 的 69 个 Python 文件与当前源码逐一 SHA 相同。沿用上一轮安装身份，不宣称新发布。

## 结果与范围

| 来源 | 矩阵生成 | Forge → PyATB 1.1.2 | 当前结论 |
| --- | --- | --- | --- |
| develop `94576a801` / 日志 v3.11.0-beta8 | Si LCAO，nspin=1；1 passed / 16.54s；`hrs1_nao.csr`、`sr_nao.csr`、`rr.csr` | prepare 成功；execute 返回 failed / not_collected / unassessed，returncode=1 | 新 CSR 内容格式不被当前 PyATB reader 支持；双轨门继续开放 |
| LTS `f71921fe8` / v3.10.1 | 相同 Si 输入；1 passed / 14.12s；`data-HR-sparse_SPIN0.csr`、`data-SR-sparse_SPIN0.csr`、`data-rR-sparse.csr` | prepare → execute → collect 完整通过；3 条事件；收集 3 个输出产物 | 当前组合的 nspin=1 交接通过；band_gap=0.5348 eV 仅为短 G–X 路径上的解析观测 |

ABACUS executable 与日志 SHA、失败状态核验见 [provenance.json](2026-10-19-forge-pyatb-dual-handoff/provenance.json)。这些是指定历史构建，不是最新 develop。两次新计算仅生成本地 Si 矩阵，无集群作业。所有操作保持 `scientific=unassessed`；未验证科学带隙、更多材料、nspin=2/4 的双轨实算或 PyATB properties。

[消费脚本](2026-10-19-forge-pyatb-dual-handoff/replay.py)通过 `python -I -m abacus_forge.cli` 调用已安装 Forge，显式提供同一 workspace 中的原名矩阵和 SCF collect 的 eV 费米能。PyATB 使用独立的现有 Conda executable，不代表 PyATB 已安装进 Forge venv。LTS 每个操作核验 artifact 的相对路径、实际文件、SHA、大小、事件 payload 和 artifact refs，并核验源矩阵不变；见 [LTS 摘要](2026-10-19-forge-pyatb-dual-handoff/lts-summary.json)。develop 失败的两个事件及已返回 artifact 哈希另行核验，没有执行后续 collect 或将失败转成成功。

## 缺口定位及推进办法

安装的 `pyatb.io.abacus_read_xr.abacus_readHR` 扫描以 `Matrix` 开头的旧头部，在新格式头部中的空行访问 `line[0]` 抛出 `IndexError`。新文件还包含结构头、CSR 注释与分行数值，因此只跳过空行或重命名不足以完成格式适配。

[独立 reader 复现](2026-10-19-forge-pyatb-dual-handoff/diagnose_reader.py)绕过 Forge，将两轨 HR 分别复制为相同旧文件名；LTS 可读，develop 仍抛出同一异常。[诊断结果](2026-10-19-forge-pyatb-dual-handoff/reader-diagnosis.json)绑定 PyATB 1.1.2 reader SHA。只读核对本地 `pyatb@80f7c2d` 的同一 reader 也保留此扫描逻辑；不据此断言所有上游版本都未修复。

Ruling：本轮关闭 LTS nspin=1 消费项，将 develop 项具体化为 PyATB reader 格式兼容缺口。修复归 PyATB owner：用本归档的新旧 HR/SR/rR 建立直接 reader 回归，按格式解析完整矩阵并保持单位、spin 和数据完整性；修复后用新 executable 重放同一矩阵，无需重跑 ABACUS。Forge 继续薄交接，暂不内置 CSR 转换器或隐式格式降级。此裁决不关闭 develop 门，也不新增公共 API。

## 回归、原始记录与复现

- `conda run --no-capture-output -n abacus-env python -m pytest -q -m pyatb`：**101 passed、1424 deselected、10 warnings，5.77s**，原始输出见 [boundary-tests.log](2026-10-19-forge-pyatb-dual-handoff/boundary-tests.log)。这是离线边界回归，不能覆盖上述真实格式缺口。
- 两轨 producer 都使用现有 `test_typed_lcao_matrices_machine_execute_and_collect`，installed-only 模式，输入源 `abacus-packages/smoke-sources/lcao-scf-si-matrices`；各自 source 对应 toolchain/install/setup，OMP/OPENBLAS threads=1。原始测试输出见 [develop.log](2026-10-19-forge-pyatb-dual-handoff/develop.log) 和 [lts.log](2026-10-19-forge-pyatb-dual-handoff/lts.log)。
- [原始归档](2026-10-19-forge-pyatb-dual-handoff/real-handoff.tar.gz)含两轨 producer 输入、PP/ORB、实际日志、矩阵、事件及 PyATB 成功/失败 workspace；[归档 SHA](2026-10-19-forge-pyatb-dual-handoff/archive-sha256.txt)。解包后可直接作为 replay 的 sources，无需重算。
- 复现 LTS：隔离环境 Python `-I replay.py --sources /absolute/extracted-root --output /absolute/new-directory --track lts --pyatb /absolute/pyatb`。去掉 `--track lts` 时当前 PyATB 会在 develop execute 断言失败，这是未关闭的真实缺口，不能当作通过门禁。
- reader 定位：在对应 PyATB 环境运行 `diagnose_reader.py --develop-hr /absolute/hrs1_nao.csr --lts-hr /absolute/data-HR-sparse_SPIN0.csr`；该脚本断言当前已知差异，修复后应改用正向兼容回归，不能用它作为双轨成功门。

本机证据位于 `/home/james/scratch/forge-pyatb-dual-handoff-20261019/`。首次脚本预检因 pytest current 符号链接重复计数退出，排除别名后重放；该预检未调用 PyATB。所有失败目录保留。本轮不修改共享环境，不修改上游仓库，不推送或发布。

独立终审通过，无阻断问题：归档 SHA、两轨日志 SHA、reader SHA、21 个 ArtifactRecord 与 5 个事件 payload 均核对一致。131 个本地文档链接有效，两个脚本语法检查及 staged diff whitespace 检查通过。develop 失败项继续开放。
