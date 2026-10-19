# 完整 PyATB wheel 与 Forge 安装态双轨消费

本轮复用已批准的 Engine/Version Policy 和 typed PyATB manifest SPEC，落实[原计划 P0](../plans/2026-09-13-forge-engine-version-policy.md#返回-forge-主线下一执行切片)。Forge 运行代码未改动；完整候选 PyATB 的 Python 与 native extension 已从同一 commit 构建并安装，补齐此前“候选源码 + 旧 extension”回放的包验收缺口。

## 候选与安装边界

| 项目 | 本轮绑定 |
| --- | --- |
| Forge | `be1c0bc7ccf3d966288b59cafd890e8db4eb03ee`，`abacus_forge-0.1.0-py3-none-any.whl` |
| Forge wheel SHA-256 | `72ebfcd3289347822b586fc985bd425f108c160d147723400548bb6a6ba43903` |
| PyATB | 完整 `sidereus-adam@5f7e1329c93b65c527151819cda7b156097e231f`，含 CSR、正物理体积和 COHP 修复 |
| Eigen | `3147391d946bb4b6c68edd901f2add6ac1f31f8c` |
| PyATB wheel | `pyatb-1.1.2.dev0+5f7e132-cp312-cp312-manylinux_2_39_x86_64.whl` |
| PyATB wheel SHA-256 | `8f39ec01bb35ba4a473f99e85a8bc30ddbcf04e8fffa3e8f0a21e683285e6f03` |

PyATB 的 21 个 C++ translation units 全部重新编译。OpenBLAS 等依赖库复用现有库作为链接输入，经 auditwheel 打包；未复用旧 PyATB extension。构建说明、源码清单、ELF 审计和命令见[构建 provenance](2026-10-19-forge-pyatb-installed-consumption/build/PROVENANCE.md)。该 wheel 限 CPython 3.12、Linux x86_64、glibc ≥ 2.39，并要求兼容的系统 C++ ABI；不是面向所有 Linux/SAI 的发布物。

构建产物保留在 `/home/james/scratch/forge-pyatb-wheel-20261019/repaired/`；Forge wheel 与无 system-site 的消费环境保留在 `/home/james/scratch/forge-pyatb-installed-20261019/`。[安装身份](2026-10-19-forge-pyatb-installed-consumption/environment.json)记录导入、native 库和 wheel 来源，[测试命令](2026-10-19-forge-pyatb-installed-consumption/test-invocations.json)记录环境及退出码。两包均从 wheel 安装，未使用 editable/PYTHONPATH 注入候选源码，未修改共享 Conda 环境。PyATB 未加入 Forge 默认依赖；本地包未发布。

## 运行结果

复用[此前真实 ABACUS SCF](2026-10-19-forge-pyatb-dual-handoff.md)产生的 Si/LCAO/nspin=1 矩阵：develop `94576a801` 与 LTS `f71921fe8`。本轮没有重跑 ABACUS。

| 轨道 | prepare | execute | collect | 审计及数值 |
| --- | --- | --- | --- | --- |
| develop，新 CSR 名称与内容 | 成功 | completed / returncode 0 | complete | 3 条追加事件；band 数组与此前回放完全一致 |
| LTS，旧 CSR 名称与内容 | 成功 | completed / returncode 0 | complete | 3 条追加事件；band 数组与此前回放完全一致 |

[回放脚本](2026-10-19-forge-pyatb-installed-consumption/replay.py)检查了每个 `ArtifactRecord` 的 workspace 相对路径、文件大小和 SHA，manifest 的输入/输出角色与同 envelope artifact 引用，已有事件字节未被改写，源文件 hash 不变。每轨 band 数组为 6×26，最大绝对差为 0；短 G–X 路径报告 band_gap=0.5348 eV，全部操作 `scientific=unassessed`。这不是材料带隙科学结论，也不晋级 capability 成熟度。

原始六次调用、请求/响应、workspace 事件和产物保存在[回放归档](2026-10-19-forge-pyatb-installed-consumption/replay-artifacts.tar.gz)，[归档 SHA](2026-10-19-forge-pyatb-installed-consumption/archive-sha256.txt)用于完整性核对；命令/退出码及数值检查见[结果摘要](2026-10-19-forge-pyatb-installed-consumption/replay-summary.json)。Forge 安装态 owning tests 为 **539 passed**，覆盖 PyATB、contracts、workspace 和 machine CLI；[日志](2026-10-19-forge-pyatb-installed-consumption/forge-installed-tests.log)保留 10 条 ASE/NumPy 第三方 deprecation warning，未静默过滤。

PyATB 测试在不含 `src/pyatb` 的隔离测试副本上运行，预先导入真实安装的 MPI/native module，避免测试 conftest 注入替身；**[77 passed](2026-10-19-forge-pyatb-installed-consumption/pyatb-installed-tests.log)**。其中 native 光学回归仍单独编译同 commit 的 C++ harness，不应表述为 wheel 的光学端到端计算。首次测试副本缺少 Si 示例和 native harness 链接依赖，补齐测试资产及显式链接路径后通过；失败日志以 `.log.gz` 原字节压缩保留，不涉及包源码修改。

复现入口：在同等受支持宿主上，用[构建脚本](2026-10-19-forge-pyatb-installed-consumption/build/rebuild.sh)建立新的构建目录；安装上述两包和声明依赖到 fresh venv。用该环境 Python 执行回放脚本，传 `--forge-wheel` 与 `--pyatb-wheel` 指向对应 wheel，`--saved` 指向原回放输入/请求/基准 band 所在目录、`--output` 指向新目录、`--venv` 指向候选环境。准确参数以脚本 `--help` 为准；历史输入与基准记录仍由前轮 evidence 保存。

## Paimon v1.3 交接与剩余工作

只读核对 `app-tools-forge@9eedd082d` 后确认：当前 kit 的 Forge pin 是 `20dc2eb`，Python 为 3.13，未安装 PyATB；`pyatb-band.default_env=null` 是 explicit-only 政策。因此不能把本轮 cp312 wheel 直接装入该解释器，也不能把默认路由 14/15 的 PARTIAL 改写成失败或通过。先建立匹配 Python/宿主的 W3 候选，再验收现有显式路径。

Paimon 的真实 Tool 交接还有两个具体适配缺口（以下路径均相对其 `toolbox/ABACUS/`）：

- `abacus_scf.py:314–316` 在 Forge 路径拒绝 `matrix_output != "none"`；需要按既有输出契约支持请求并检查实际 inventory/readiness。
- `toolkits/pyatb_runtime.py:427–465` 仅发现旧矩阵名；develop 的 `hrs1_nao.csr` / `sr_nao.csr` / `rr.csr` 需要绑定已通过的 PyATB 格式兼容证据接入。

已有真实 Forge SCF workspace 不具备 Paimon 的完整 `abacus_worker_scf` producer、`consumer_ready=passed`、`output_profile_actual_*` inventory 和根目录交付视图。`forge_operation_to_result_evidence` 只是投影，不能补造这些事实；现有 `run_forge_scf_for_atp` 则会重新执行 SCF，没有受支持的无执行补证入口。

这些 W2 工作已由 Paimon `docs/superpowers/specs/2026-08-25-electronic-state-output-pyatb-l2-design.html` 和 `docs/superpowers/plans/2026-09-13-paimon-v1.3-forge-migration.md` 承接。下一步先同步最新 v2 基线到 v3，再补适配并从真实 Paimon SCF work_dir 验收显式 Tool 路径；本轮未修改 v1.2/v1.3 仓库、默认策略或平台环境。

本轮关闭的是本机完整包与 Forge 两轨 Si/nspin=1 消费。真实 nspin=2/4、更广材料、PyATB COHP 真实计算的安装态回放、Paimon 全链路/成对 Benchmark、其它 Python/系统和发布验收仍分别开放。Forge `cohp` 继续为 IAO typed postprocess，本轮未增加 NAO-COHP capability。

独立终审通过：Forge/PyATB wheel 内 Python 文件分别与上述 commit 一致，构建输入与 21 次 native 编译记录匹配，安装身份及回放归档无阻断问题。控制代理另核对全部 24 个 ArtifactRecord 的路径/大小/hash、6 条事件和摘要状态；文档本地目标与脚本语法检查通过。P0 与本轮执行分工关闭，P1 保持开放。
