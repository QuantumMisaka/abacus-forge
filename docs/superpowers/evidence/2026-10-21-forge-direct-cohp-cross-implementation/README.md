# Direct NAO COHP 跨实现对照（同一 Si SCF）

日期：2026-10-21。范围：复用 SAI job `1760372` 的 LTS ABACUS v3.10.1 完整 Si SCF，
不新跑 ABACUS；在同一 STRU、ORB、36 k 点和权重上分别运行两个 direct NAO 实现。
选择为 Si1 `s/p`，nspin=1。目的是完成 2026-10-15 COHP PLAN 中的方法对照，不是
科学验收、多材料评估或 Paimon 平台验收。

## 实现与输入

| 实现 | commit/version | 输入路径 |
| --- | --- | --- |
| `abacus-cohp-lcao` | `78b3628aa4bb137bb75f465b2b4ecc9aac8f9fb1` | WFC 与完整 `H(k)/S(k)` |
| Forge → PyATB | PyATB `1.1.2.dev0+5f7e132`；Forge `39413ee` | sparse `H(R)/S(R)` 重建求解 |

两边的 STRU、ORB、HR、SR 和 k points 来源文件逐字节一致；SHA-256 见
[summary](summary.json)。两者均使用 eV、nspin=1 `sum`（简并因子 2）、36 个 ABACUS
k 点权重、Si1 `s/p` disjoint orbital-set pair（factor 2）、绝对能量窗口
`[-15,25] eV` 和 `de=0.05 eV`。

## 结果

| 实现 | discrete ICOHP / eV |
| --- | ---: |
| `abacus-cohp-lcao` | -0.8790256696459798 |
| Forge → PyATB | -0.880434861336741 |
| absolute difference | 0.0014091916907611 |
| relative difference | 0.1603% |

对照特意使用展宽前的离散占据态求和；两条展宽曲线已保留在
[abacus-lcao/cohp.dat](abacus-lcao/cohp.dat) 和
[pyatb/minus-cohp.dat](pyatb/minus-cohp.dat)。两者展宽核不同——lcao 用标准
Gaussian convolution，PyATB 用 `exp(-(dE/sigma)^2)/(sqrt(pi)*sigma)`——因此展宽后
曲线不作为 parity gate。

同一 SCF 的既有 IAO `s/p` ICOHP 为 `-0.6040196341992011 eV`。IAO 与 direct NAO 是
不同轨道表示，该差异按方法差异报告；不要求曲线或 ICOHP 相等。

## 归档与复现

- 输入/产物摘要、版本、边界：[summary.json](summary.json)
- 命令：[commands.json](commands.json)
- Forge→PyATB 回放脚本：[scripts/replay_forge_pyatb.py](scripts/replay_forge_pyatb.py)
- 展宽敏感性记录：[broadening-sensitivity.json](broadening-sensitivity.json)

本轮不改写原始 ABACUS 输出，不宣称跨材料 parity、稳定能力、科学正确性或
Paimon/SAI 验收。
