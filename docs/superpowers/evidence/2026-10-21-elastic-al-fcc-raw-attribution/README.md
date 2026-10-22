# Al-FCC elastic raw strain/stress attribution

状态：candidate-side 归因已闭合；后继 historical replay 已定位 baseline 口径为 SCF + `20^3`。见[2026-10-22 historical replay](../2026-10-22-elastic-al-fcc-historical-scf-replay/README.md)。

2026-10-21，用户明确要求访问 SAI job `1886152` 的原始输出。本次只读取远端数据并取回轻量工件；未修改 `app-tools-forge` owner worktree，未重跑 candidate。

## 源与工件

| 项 | 值 |
| --- | --- |
| SAI job / Slurm ID | `1886152` |
| run ID | `bm-20261021-044215-1886152` |
| parity case | `elastic/Al-FCC` |
| work root | `/org/pku-jianghong/liuzhaoqing/paimon-bench-20261020/runs/elastic_Al-FCC/work/elastic_al-fcc_step1-005` |
| 选中 raw 工件 | [raw-selected.tar.gz](raw-selected.tar.gz) |
| run provenance | [sai-run-selected.tar.gz](sai-run-selected.tar.gz)（内含 `job.log`、`result.json`、`stdout.log`）、[result.json](result.json) |
| 逐 strain 解析 | [per-strain.json](per-strain.json) |
| 张量级对比 | [summary.json](summary.json) |
| 复现脚本 | [reconstruct_fit.py](reconstruct_fit.py) |

关键 SHA-256：

- `raw-selected.tar.gz`: `0d802c38852f839170c1b5f4cdebf79b90bb2b2401ff73b9badde81f4b9ce443`
- `sai-run-selected.tar.gz`: `94923b66066c120a14891971e20081d6f1590df7c639ee3d361f02fb60ae64fc`
- `per-strain.json`: `8d71748784b008d726d3552758bc3918c2ead4b1da0cf9079873ba4385bcc0f6`
- `summary.json`: `8a5c9faceb9d9e0fe8db28a0eebd1d6e306ce6ced526959ab5dd8d6b9f354f57`

`raw-selected.tar.gz` 保留 25 个 job（1 pristine + 24 deformed）的 `INPUT / KPT / STRU`、final `STRU_ION_D`、collect event 和 stdout/stderr，另含顶层 `elastic_fit.json` 与 `elastic_tensor.json`。为避免复制 315 MB 全量输出，未包含 pseudopotential/orbital、charge density、k-point dump 和约 190 MB `running_relax.log`；远端原始 work root 仍保留。

## Candidate-side 闭环

1. 25 个 job 的 `KPT` 全部是 `34x34x34`，证明实际执行使用的是 v1.2 effective dense grid，而不是 prepared INPUT 的 `18x18x18`。
2. 25 个 Forge collect 事件都报告 `converged=true`；单原子位于原点，1 个 relax step 后位置未变。
3. Forge collect 的 9-component stress 是 kbar row-major。脚本按 `Stress(-0.1 * matrix)` 转为 pymatgen GPa stress。
4. 用 24 个 raw stress、raw strain provenance 和 candidate 的同一 `DeformedStructureSet` 顺序重建，结果逐位复现顶层 candidate 结果：
   - bulk: `76.07318366257788 GPa`
   - shear: `24.86883186282004 GPa`
   - Young: `67.27555303880061 GPa`
   - Poisson: `0.3526078227136277`

因此 candidate 侧可排除：strain-set 顺序错误、KPT 选择错误、stress row-major 解析错误、kbar/GPa 转换错误、equilibrium-stress 漏传和本地 fit 错误。每个 raw collect 的 stress 3×3 矩阵也严格对称。

复现命令：

```bash
mkdir raw
tar -xzf raw-selected.tar.gz -C raw
python reconstruct_fit.py --root raw --output raw/per-strain.reproduced.json
```

本次在 CPython 3.13 / pymatgen 环境重放时，`per-strain.reproduced.json` 与归档的 [per-strain.json](per-strain.json) 字节一致。

## 与 baseline final tensor 的张量级对比

`elastic.evalset.json` 保留的 v1.2 final tensor 可重算出其上报模量（如 shear `23.728 GPa`），因此该 tensor 是可信的历史响应记录，而不是抄录错误。当前可用数据中没有 v1.2 的 24 条 per-strain stress。

关键差异：

| Voigt 分量 | baseline | candidate raw | candidate - baseline |
| --- | ---: | ---: | ---: |
| C33 | 118.19 | 110.842 | -7.348 |
| C13 | 54.26 | 58.337 | +4.077 |
| C23 | 54.15 | 58.613 | +4.463 |
| C44 | 18.81 | 23.856 | +5.046 |
| C55 | 18.84 | 23.899 | +5.059 |
| C66 | 24.98 | 25.670 | +0.690 |
| C14 | 10.81 | 2.479 | -8.331 |
| C24 | -11.00 | -2.448 | +8.552 |
| C56 | 9.39 | 2.580 | -6.810 |

candidate 的六阶 Voigt 张量最大不对称量为 `0.476 GPa`；baseline final tensor 为 `1.730 GPa`。baseline 还带有 candidate 中基本消失的大额 `C14/C24/C56` shear coupling。这些异常和低 `C44/C55` 共同降低其 Voigt shear modulus，是当前 +4.8% residual 的直接张量级来源。

## 当前结论与边界

- 已闭合：candidate raw 执行、stress conversion、strain mapping 和 fit 可完整复现；本轮 fail 不是 candidate-side 的 parser/order/unit bug。
- 张量级发现：baseline final tensor 本身有明显 shear coupling 和 `C44/C55` 异常，可解释汇总模量差异。
- 历史根因已由后继 replay 闭合：2025-08-20 的 `abacus-agent-tools@e81c5d1` 使用 `calculation=scf` 和 prepared INPUT `kspacing=0.14`（`20x20x20`），精确复现 evalset baseline tensor 与模量；candidate 使用 relax、`0.01 eV/angstrom` force threshold 和 `34x34x34`。见[historical replay](../2026-10-22-elastic-al-fcc-historical-scf-replay/README.md)。
- 剩余动作由 owner 签字：将 `elastic/Al-FCC` 按科学口径升级记为 baseline defect fixed；不需要修改 1% threshold。
