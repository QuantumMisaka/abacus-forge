# 真实进程 smoke 门禁

这些测试显式调用外部可执行文件，并将调用方准备的源目录复制到临时 Forge workspace；不会改动源目录。ABACUS 输入须有有效的 `inputs/INPUT`、`inputs/STRU`、`inputs/KPT`，以及 INPUT 所需全部 PP/ORB 资产。默认回归跳过本目录；运行前设置对应环境变量并传入 `--run-real-smoke`。变量缺失会跳过相应测试，已提供但无效的路径、可执行文件、capability 或输入会失败。测试只证明选定的进程、解析、产物与审计交接，不判断物理收敛、轨迹质量、调度器或科学结果。

## ABACUS：SCF、Relax 与 MD

legacy SCF 使用 `execute_unit`/`collect_unit` Python 兼容入口，只检查 legacy 结果。typed SCF 使用 machine CLI 的独立 `execute` 和 `collect` 请求及不同 UUIDv4 operation ID，检查序列化 envelope、事实、event、manifest 引用和工作区内 artifact；只有后者证明 typed machine path。两者共享以下输入：

```bash
export ABACUS_FORGE_REAL_SMOKE_WORKSPACE=/absolute/path/to/prepared-forge-workspace
export ABACUS_FORGE_ABACUS_EXECUTABLE=/absolute/path/to/abacus
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-real-smoke \
  tests/real_smoke/test_abacus_smoke.py -k typed_scf
```

不传 `--run-real-smoke` 且没有外部输入时，上述定向选择为 `1 skipped, 2 deselected`，不构成执行证据。typed SCF 要求源 INPUT 声明 `calculation=scf`。

typed Relax 是独立的实验性 machine CLI 门禁；源目录与 SCF 分开，`ABACUS_FORGE_RELAX_SMOKE_CAPABILITY` 默认为 `relax`，也可取 `cell-relax`。一次 execute 后一次 collect，检查状态、能量、final-structure 事实和审计；不施加物理阈值。

```bash
export ABACUS_FORGE_RELAX_SMOKE_WORKSPACE=/absolute/path/to/prepared-relax-workspace
export ABACUS_FORGE_ABACUS_EXECUTABLE=/absolute/path/to/abacus
export ABACUS_FORGE_RELAX_SMOKE_CAPABILITY=relax
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-real-smoke \
  tests/real_smoke/test_abacus_smoke.py -k typed_relax
```

typed MD 也是独立的实验性门禁；源 INPUT 必须声明 `calculation=md`。测试检查 `running_md.log` 的末步热力学标量、状态、审计与 contained artifact，`MD_dump` 是单独的事实投影。

```bash
export ABACUS_FORGE_MD_SMOKE_WORKSPACE=/absolute/path/to/prepared-md-workspace
export ABACUS_FORGE_ABACUS_EXECUTABLE=/absolute/path/to/abacus
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-real-smoke \
  tests/real_smoke/test_abacus_smoke.py -k typed_md
```

源目录不得含 collector 可见位置中的旧 `running_*.log`、Forge fallback `out.log` 或 MD 的 `MD_dump`，包括 `inputs/OUT.*` 布局；Relax 还拒绝这些位置中已有的 final-structure 输出（`STRU_FINAL`、`STRU_FINAL.cif`、`STRU_ION_D`、`STRU_NOW`、`STRU_NOW.cif`、`STRU.cif`、`STRU`）。非生成的 `inputs/OUT.*` restart/handoff 资产允许保留。该 freshness guard 仅约束 smoke 输入，不改变 Forge 通常的 execute/collect 行为。

## LCAO 稀疏矩阵与版本证据

typed LCAO SCF 三种门禁使用相同 machine path，要求 `basis_type=lcao`。nspin2 还要求 `nspin=2`；matrices 还要求 `out_mat_hs2=1`、`out_mat_r=1`，并检查 `inputs/OUT.ABACUS/` 的 HR/SR/rR 矩阵。

```bash
export ABACUS_FORGE_ABACUS_EXECUTABLE=/absolute/path/to/abacus
export ABACUS_FORGE_LCAO_SMOKE_WORKSPACE=/absolute/path/to/si-lcao-scf-source
export ABACUS_FORGE_LCAO_NSPIN2_SMOKE_WORKSPACE=/absolute/path/to/fe-lcao-nspin2-source
export ABACUS_FORGE_LCAO_MATRICES_SMOKE_WORKSPACE=/absolute/path/to/si-lcao-matrices-source
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-real-smoke \
  tests/real_smoke/test_abacus_smoke.py -k lcao
```

matrices 门禁接受 LTS 旧名 `data-HR-sparse_SPIN0.csr`、`data-SR-sparse_SPIN0.csr`、`data-rR-sparse.csr`，也接受 develop 新名 `hrs1_nao.csr`、`sr_nao.csr`、`rr.csr`。当前 typed `pyatb-band` handoff 已支持新 CSR 名称及对应角色顺序，不要求调用方预先 rename；这项兼容由 [Engine/Version Policy 计划](../../docs/superpowers/plans/2026-09-13-forge-engine-version-policy.md) 的 A 阶段及 owning tests 约束。记录中的 LCAO 源 PP/ORB 来自 Paimon v1.2 `abacus-pp-orb` 系列；门禁只检查进程、parser 和产物事实。

[2026-09-13 native real-smoke 复核](../../docs/superpowers/plans/2026-09-13-forge-engine-version-policy.md#c-阶段-native-real-smoke-证据2026-09-13)记录：develop `94576a801` 为 `7 passed`；LTS `f71921fe8` 为 `6 passed, 1 failed`。LTS typed cell-relax 同时产生 `STRU_ION_D`、`STRU_NOW.cif`、`STRU.cif` 三个 contained final 候选，`final_structure_selection_ambiguous=true`，因此 collection 为 `partial`。这不是“仅因缺少 `STRU_FINAL`”的故障，也不能记为 pass。原始运行身份与诊断见[复核证据](../../docs/superpowers/evidence/2026-09-13-forge-engine-version-policy-review.md#10-native-real-smoke-双轨复核2026-09-13)。这组 native 结果不证明 optional `abacuslite` 四 capability 真实 parity。

## PyATB、ATST 与 vacancy

typed PyATB band 输入源结构为 `source/STRU` 和 `source/data-HR-sparse_SPIN0.csr`、`source/data-HR-sparse_SPIN1.csr`、`source/data-SR-sparse_SPIN0.csr`；`source/data-rR-sparse.csr` 在请求中可选，本门禁输入包含它。源目录不可已有 `inputs/Out/Band_Structure/` 下生成的 band 文件。测试依次执行一次 typed prepare、execute、collect，检查 handoff、原生 band 产物、parser 的 `band_gap`、event、artifact 引用及 `scientific=unassessed`；band gap 是观测值，不是科学验收。缺少变量会跳过，非法值会失败。

```bash
export ABACUS_FORGE_PYATB_SMOKE_WORKSPACE=/absolute/path/to/pyatb-source-root
export ABACUS_FORGE_PYATB_EXECUTABLE=/absolute/path/to/pyatb
export ABACUS_FORGE_PYATB_SMOKE_FERMI_ENERGY=15.5241312077
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-real-smoke \
  tests/real_smoke/test_pyatb_smoke.py
```

ATST-tools NEB 门禁选择 ATST 2.2.4，执行 `atst neb make`、`atst run --dry-run`、`atst neb summary/post`，不启动 ABACUS。它只检查 process envelope、状态、contained summary/CIF artifact 与审计，不证明真实 NEB 执行或物理有效性。

```bash
export ABACUS_FORGE_ATST_EXECUTABLE=/absolute/path/to/atst
conda run -n atst-dev env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-real-smoke \
  tests/real_smoke/test_atst_smoke.py
```

vacancy property-pack 门禁从完整 ABACUS 源 workspace 经 `prepare_vacancy` 建 pristine/defect 子目录，以 `run_vacancy` 分别执行，再用 `post_vacancy` 投影形成能事实。可选 `vacancy/ref_energy.txt` 每行 `<element> <energy_eV>`；有参考能时形成能有限并报告 `completed`，无参考能时为 `degraded` 且形成能为 `null`，两者均可作为进程证据。

```bash
export ABACUS_FORGE_VACANCY_SMOKE_WORKSPACE=/absolute/path/to/prepared-vacancy-source
export ABACUS_FORGE_ABACUS_EXECUTABLE=/absolute/path/to/abacus
# 可选：从 1 开始的移除原子序号，默认 1。
export ABACUS_FORGE_VACANCY_SMOKE_INDEX=1
conda run -n abacus-env env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-real-smoke \
  tests/real_smoke/test_vacancy_smoke.py
```

这些 smoke 不能替代平台、workflow、调度器、完整 Paimon Benchmark 或科学有效性验证。各能力在各自真实门禁和 Stage 4 剩余发布条件满足前仍标为实验性。
