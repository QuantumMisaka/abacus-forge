# Forge 候选安装包与真实 MgO BEC 验证

本记录承接 [执行计划](../plans/2026-10-21-forge-installed-bec-validation.md)；
算法/API 仍按 [BEC SPEC](../specs/2026-10-21-forge-polarization-bec-design.md)。
候选为 HEAD `f590367` 加前两轮已审查的 dirty 实现；本轮没有修改生产源码。
安装包已通过指定回归，真实 MgO 单列和有限位移/网格敏感性检查通过；
独立最终审查通过，无阻断问题。

## 安装消费

全新 CPython 3.12.13 venv，`include-system-site-packages=false`，安装本地构建
`abacus_forge-0.1.0-py3-none-any.whl`，SHA256
`c70e71a698ea6fc6d697495845e45c8cb9a95876636e54705074ce2967a02180`。
76 个 Python 文件与工作树源码及 site-packages 逐字节一致，含本轮新增的
NAO COHP、polarization、BEC 模块。三项新 capability 的 CLI schema 可用；
指定 8 文件回归 **520 passed，1 条 ASE/NumPy warning**，`pip check` 通过。

运行时清除 PYTHONPATH，并启用 `ABACUS_FORGE_INSTALLED_PACKAGE_ONLY=1`；
真实计算与分析脚本均用该 venv 的 `python -I`，CLI 子进程也使用 `-I`。
新 venv 未安装 PyATB；本项不证明其原生执行或其他 Python/平台安装成功。
[安装收据](2026-10-21-forge-installed-bec-validation/installed/summary.json)、
[测试原始输出](2026-10-21-forge-installed-bec-validation/installed/installed-pytest.log)、
[实际测试命令](2026-10-21-forge-installed-bec-validation/installed/commands.json)。
pytest 主进程未使用 `-I`，通过 installed-only 开关禁止 conftest 注入源码；
另行的 CLI 验证和真实运行使用 `-I`。

## 真实计算条件

- ABACUS develop 既有本机二进制，原生日志显示 **v3.11.0-beta8 / 94576a801**；
  二进制 SHA256 `7ca5a99e0d68cfb4a65707db57ef5992caa989679421800d3fa6191f053f5ed5`。
- 岩盐 MgO 两原子原胞，a=4.24584 Å，三个晶格矢量为
  `(0,a/2,a/2)`、`(a/2,0,a/2)`、`(a/2,a/2,0)`，固定晶胞，仅移动 O 的 Cartesian x。
- NC/PBE `Mg.PD04.PBE.UPF`（2 价电子）、`O.upf`（6 价电子），PW 80 Ry，
  nspin=1、fixed occupations、nbands=4、symmetry=-1，SCF 1e-10，NSCF 对角化 1e-11。
- SCF 4³；三个 Berry NSCF 分别为 8×4×4、4×8×4、4×4×8，
  `berry_phase=1`、`gdir=1..3`、`init_chg=file`。0/±0.01 Å 各自独立 SCF，
  对应 NSCF 使用该位移 SCF 的 restart，绝不将零位移电荷用于正负位移。
- 每个引擎进程 1 MPI rank / 1 OMP、OpenBLAS thread，timeout 300 秒。
  首组 12 个引擎阶段、9 次原生日志 collect 均成功。nbands 仅含占据态，
  日志的零 gap 不提供绝缘性测量；本轮以 MgO 绝缘性为材料前提。

原始 ASE 顺序 Mg/O 中位移的是第 2 原子；prepare 按 species 重排后 STRU
是 O/Mg，BEC 必须请求 **atom_index=1**。该转换已由 fact 几何独立核对。

电荷收据记录执行前源/目标摘要一致；NSCF 会改写自己的目标 restart，
因此另记执行后摘要并验证 SCF 源未变。原始日志也确认从文件读入电子密度。
初始调用方脚本对完成标记的拼写与原生格式不同；核对后修正脚本并复用已
成功结束的 SCF，未改日志或产品代码。

## 分支与数值核对

所有事实文件来自安装态 `polarization/collect`。每份保留对应 INPUT、STRU、
KPT、原生日志和收据；不是 source-shaped fixture。九份打印模量均为
11.3469068，与 `2|R_i|` 相符；三单位行与矢量方向在显示精度内一致。

`auto` 使用调用方声明的每步变化界 0.25 个量子。独立脚本从原始 scalar 和
modulus 相对零点选最近分支，得到显式 offsets，未从 auto 结果复制：

| 位移 | gdir 1 | gdir 2 | gdir 3 |
| --- | ---: | ---: | ---: |
| −0.01 Å | 1 | 0 | 0 |
| 0 | 0 | 0 | 0 |
| +0.01 Å | 0 | 1 | 1 |

再调用 `explicit`，并用 NumPy 对修正后的三个 Cartesian dipole contribution
求和、做中心差分。三条路径一致：O 的 x 列为
**[-1.954825926723525, 0, 0] e**，最大差为 0。
`requested_complete=true`、`full_tensor_complete=false`、`scientific=unassessed`。
独立指定 offsets 与 auto 一致，不消除两者共同的连续性前提；离散样本不能
证明不存在隐藏绕圈。

[首组摘要](2026-10-21-forge-installed-bec-validation/real/analysis-mesh4-002/summary.json)、
[原始分支表](2026-10-21-forge-installed-bec-validation/real/analysis-mesh4-002/raw-branch-table.json)、
[独立中心差分](2026-10-21-forge-installed-bec-validation/real/analysis-mesh4-002/manual-endpoint-difference.json)。

[VASP 官方 MgO 示例](https://vasp.at/tutorials/latest/electron-phonon/part1/)给出
O 约 −1.976 e；[Posternak 等原始研究](https://arxiv.org/pdf/cond-mat/9702086)给出
约 −2.07 e。这里只作符号和数量级对照，不能把不同 PP/XC/晶胞的结果当严格 oracle。
SCF→三方向 NSCF 的流程来自 [ABACUS 官方 Berry 文档](https://abacus-rtd.readthedocs.io/en/latest/advanced/elec_properties/Berry_phase.html)。

## 敏感性与审查

全部 **32 次引擎运行、24 次真实极化 collect** 正常完成；最终三组分析共
6 次 BEC CLI 调用。每个 SCF 收敛，全部阶段使用的 PP 摘要与统一资产相同，
电荷交接执行前一致且 SCF 源未变，日志摘要与成功收据一致。

| SCF / NSCF 网格 | 位移幅度（Å） | O 的 Zxx（e） | 与首组差值（e） |
| --- | ---: | ---: | ---: |
| 4³ / 8×4×4（按 gdir 置换） | 0.010 | -1.9548259267 | 0 |
| 4³ / 8×4×4（按 gdir 置换） | 0.005 | -1.9548500693 | 0.0000241426 |
| 5³ / 10×5×5（按 gdir 置换） | 0.010 | -1.9553974381 | 0.0005715114 |

三个条件均为 auto=explicit=独立 NumPy，横向分量为显示精度内的 0。
两项差异均低于计算前声明的工程参考界 0.1 e。这只说明这两个改动下结果
变化很小；奇偶网格不同、仅一次加密、固定截断能，不构成完整收敛证明。
原预估的 6³ 加密改为 5³ 以控制首轮成本，裁决已在运行前写入 PLAN。
[汇总与逐阶段收据](2026-10-21-forge-installed-bec-validation/real/validation-summary.json)、
[半幅位移](2026-10-21-forge-installed-bec-validation/real/analysis-mesh4-half/summary.json)、
[网格加密](2026-10-21-forge-installed-bec-validation/real/analysis-mesh5-001/summary.json)。

独立 reviewer 已从首组九份原生日志逐值核对 facts，并独立复算 BEC，
与安装态相差约 9.4e-14 e；36 个 analysis 复制源摘要均一致。
独立最终审查还核对全部 8 个 SCF、24 个 NSCF 与归档摘要；从两组敏感性
原生日志重算的 Zxx 与安装态相差均小于 2e-13 e。实际 KPT、安装命令与完整性
标记相符。无阻断发现，见[审查记录](2026-10-21-forge-installed-bec-validation/real/final-review.md)。

## 复现范围和保留材料

完整运行目录：`/home/james/scratch/forge-real-bec-20261021/`。
隔离安装目录：`/home/james/scratch/forge-release-validation-20261021/`。
本记录附件保留调用方脚本、输入/原生日志/facts/CLI 请求响应与必要运行收据；
体积较大的 restart 和环境留在 scratch，其摘要进入收据。引擎与工具链沿用本机路径。
脚本从其所在目录取数据；离线分析可在有相同 Forge 安装环境时对保留 facts 重跑，
需更新 provenance 中 Python 路径并指定新的分析输出目录。

此项不覆盖完整 2 原子×3 位移轴张量、声学求和规则、其他材料/自旋/引擎版本、
截断能和完整 K 网格收敛，也不是 Paimon Benchmark、SAI 或发布验收。
