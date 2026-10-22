# Al-FCC historical SCF elastic replay

状态：root cause 已闭环。2025-08-20 历史 elastic 模式精确复现 evalset baseline；candidate 是后来 relax 模式。

## 结论

`elastic/Al-FCC` 的 baseline 与 candidate 差异不是 candidate 侧 fit/stress/strain bug，而是两个 elastic 科学口径不同：

| 口径 | historical evalset baseline | current candidate |
| --- | --- | --- |
| deformed structure 计算 | `scf` | `relax` |
| force threshold | 未设置 | `0.01 eV/angstrom` |
| KPT | prepared INPUT `kspacing=0.14` → `20x20x20` | effective v1.2 replay → `34x34x34` |
| shear modulus | `23.727388 GPa` | `24.868832 GPa` |

历史模式由 `abacus-agent-tools@e81c5d1` 还原。该版本在 2025-08-20 使用 deformed structure SCF；`2025-10-31` 的 `7409d2a` 才改为 relax 并加入 force threshold。

## Replay 证据

- SAI job：`1900782`
- account / partition / QOS：`pku-jianghong` / `8V100V0` / `improper-gpu`
- node：`8v100v0n02`
- elapsed：`00:06:28`
- work root：`/org/pku-jianghong/liuzhaoqing/paimon-bench-20261020/runs/v12-equivalent-elastic-Al-FCC-20261022`
- completed work dir：`/org/.../20261022225825.abacus_cal_elastic.1b584e94`
- parsed result：[historical-scf-replay-parsed.json](historical-scf-replay-parsed.json)
- scalar comparison：[summary.json](summary.json)
- postprocess script：[postprocess_historical.py](postprocess_historical.py)
- Slurm script：[run_historical_scf_pku_py312.sh](run_historical_scf_pku_py312.sh)
- wrapper log / compatibility patch：[wrapper-and-compatibility.tar.gz](wrapper-and-compatibility.tar.gz)

SHA-256：

```text
historical-scf-replay-parsed.json = 351557efbf287ac44d72f71f9e0258214d170cb6c7a93f661798886c569224a7
postprocess_historical.py        = 50446c26f719c8a7ac1c4402073e2eff5f93414ddd4315d9b60065e5840e66ee
run_historical_scf_pku_py312.sh  = 2e523963c641d08d1e0c8ff8ba1830d90a02aa2b0b27f9da06a445b943268e50
wrapper-and-compatibility.tar.gz = 2aa9d600cbccfb6153d5bb56d628f4cc23e17be9374d43b78b57ef33ff6e883a
```

25 个 job（1 pristine + 24 deformed）全部 `normal_end=true`、`converge=true`。Slurm batch 的 exit code 是 1，原因是旧函数返回的 `elastic_cal_dir` 为 `Path`，当前 JSON encoder 不能直接序列化；ABACUS 计算和后续独立 postprocess 已完成，不影响科学结果。

## 与 evalset baseline 对比

| 指标 | historical replay | evalset baseline | difference |
| --- | ---: | ---: | ---: |
| bulk | `75.38306491906677` | `75.38299506884455` | `6.99e-5` |
| shear | `23.72738793618004` | `23.72735569302671` | `3.22e-5` |
| Young | `64.42295973820733` | `64.4228748383505` | `8.49e-5` |
| Poisson | `0.357565356782779` | `0.357565412509998` | `-5.57e-8` |

replay tensor 与 evalset rounded tensor 的最大绝对差是 `0.004084 GPa`，一致于 evalset tensor 的两位小数舍入。异常分量也逐项复现：

```text
C14: replay  9.6498 vs evalset  9.65
C24: replay -9.2707 vs evalset -9.27
C44: replay 18.8104 vs evalset 18.81
C55: replay 18.8366 vs evalset 18.84
C56: replay  9.3920 vs evalset  9.39
C65: replay 10.2341 vs evalset 10.23
C66: replay 24.9805 vs evalset 24.98
```

## 兼容性 patch 边界

`e81c5d1` 中 `Structure.to(..., fmt='vasp/poscar')` 在可获得的 2024/2025/2026 pymatgen 版本中都不被接受。为让历史代码在本机运行，只做了 serialization patch：

```diff
- fmt='vasp/poscar'
+ fmt="poscar"
```

该 patch 不改变 SCF/relax 选择、KPT、strain generation、stress conversion 或 elastic fit。

## 最终归因

candidate-side raw 证据见[2026-10-21 raw attribution](../2026-10-21-elastic-al-fcc-raw-attribution/README.md)。结合本轮历史 replay：

```text
baseline evalset = SCF + 20^3 口径
candidate        = relax + force threshold + 34^3 口径
```

因此 `elastic/Al-FCC` 应按 owner 流程裁决为 baseline defect fixed / scientific-mode upgrade，而不是 candidate fail。容差不需要修改。
