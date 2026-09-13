# Forge Stage 5 evidence record

**状态：** provisional / candidate evidence；不构成稳定能力或 Paimon v1.3
backend 发布决定。

**代码候选提交：** `7b8d4c9`（包含生产代码归因修复、回归测试、已复审的
ATST adapter 死状态清理，以及 typed PyATB real-process smoke harness；后两项不改变
既有业务契约）。Stage 5 ATST smoke harness follow-ups：`c11fc6e`、`7458110`；这些提交
仅增加测试/门禁文档，不改变生产代码候选。

**证据文档基线提交：** `87eda1fe6b3e59da73965d4dee92cf2e876d5054`；后续
`5806d1c`、`5930607`、`939f666` 及后续文档校正均不改变候选代码；`e32fda1` 是之后
单独复审的行为保持型 adapter 清理。

**规范源：**
`docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html`
与 `docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html`。

**2026-09-13 归因校正：** 后文历史运行数字保留。当前 typed PyATB handoff 接受显式路径，不能由旧名称分类表推断它拒绝新名；typed Relax 已兼容唯一有效的 STRU_NOW/STRU_ION_D 等旧候选，不能仅凭没有 STRU_FINAL 解释 LTS partial。具体原因须核对原始 diagnostics 或后续 fresh evidence。现行政策见 [Engine/Version SPEC](../specs/2026-09-12-forge-engine-version-policy-design.html)。

## 1. 当前 typed capability manifest

以下内容由候选提交的 `capabilities_document()` 直接输出；九项均保持
`experimental`。artifact role 只记录实际 descriptor，不推断未实现的角色。

| capability | operations | engine | artifact roles |
| --- | --- | --- | --- |
| `scf` | `prepare`, `modify`, `execute`, `collect` | `abacus` | `input`, `provenance_manifest`, `output` |
| `relax` | `prepare`, `modify`, `execute`, `collect` | `abacus` | `input`, `provenance_manifest`, `output` |
| `cell-relax` | `prepare`, `modify`, `execute`, `collect` | `abacus` | `input`, `provenance_manifest`, `output` |
| `md` | `prepare`, `modify`, `execute`, `collect`, `postprocess` | `abacus` | `input`, `provenance_manifest`, `output` |
| `band` | `postprocess` | `abacus` | `input`, `output` |
| `dos` | `postprocess` | `abacus` | `input`, `output` |
| `pyatb-band` | `prepare`, `execute`, `collect` | `pyatb` | `input`, `provenance_manifest`, `output` |
| `export` | `export` | `forge` | `output` |
| `atst-neb` | `prepare`, `execute`, `postprocess` | `atst-tools` | `input`, `output` |

Legacy property packs（包括 `convergence`、cube、BEC、Bader、workfunc、vacancy
等）不纳入本 typed manifest，继续保持 `experimental`；它们需要各自的
SPEC/PLAN 和真实操作证据后，才能由上层评估是否消费。

## 2. Deterministic and migration gates

执行环境为 conda `paimon`（Python 3.11.15），工作目录为候选 worktree。

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider
1346 passed, 12 skipped in 118.96s (0:01:58)

conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider \
  tests/test_architecture.py tests/test_contracts.py tests/test_workspace.py
344 passed in 8.20s

conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-benchmark -m benchmark
6 passed, 1351 deselected in 3.64s

git diff --check
passed (no output)
```

本证据/计划提交自身的 `git diff --check` 通过，placeholder scan 无匹配。

`benchmark` 当前是既有 fixture/collection 事实矩阵；它不是全链路执行等价、
科学正确性或稳定 maturity 证据。

代码候选提交的 discovery/import 检查输出为：

```text
0.1.0
['scf', 'relax', 'cell-relax', 'atst-neb', 'md', 'band', 'dos', 'pyatb-band', 'export']
```

architecture gate 同时覆盖生产 import 边界和禁止运行时依赖的 AST 检查。

## 3. Clean package and dependency isolation

环境：Linux 6.18.33.2-microsoft-standard-WSL2 x86_64、Python 3.13.13；以下是实际
执行的最小重现命令（`stage5_tmp` 是临时目录）：

```bash
stage5_tmp=$(mktemp -d /tmp/forge-stage5-build-XXXXXX)
python -m venv "$stage5_tmp/venv"
"$stage5_tmp/venv/bin/python" -m pip install --quiet hatchling
"$stage5_tmp/venv/bin/python" -m pip wheel --no-deps --no-build-isolation \
  --wheel-dir "$stage5_tmp/wheels" .
"$stage5_tmp/venv/bin/python" -m pip install --no-deps \
  "$stage5_tmp/wheels/abacus_forge-0.1.0-py3-none-any.whl"
"$stage5_tmp/venv/bin/python" -m pip install ase dpdata matplotlib numpy pymatgen

"$stage5_tmp/venv/bin/abacus-forge" schema scf execute \
  | "$stage5_tmp/venv/bin/python" -c \
  'import json,sys; d=json.load(sys.stdin); print("schema_ok", d["schema_version"], d["capability"], d["operation"])'
"$stage5_tmp/venv/bin/python" -c \
  'from abacus_forge.machine_cli import decode_operation_request; r=decode_operation_request("execute", {"schema_version":"forge.request/v1","operation":"execute","operation_id":"123e4567-e89b-42d3-a456-426614174123","workspace_rel":"fixture","dry_run":True}); print("decode_ok", type(r).__name__, r.operation, r.workspace_rel, r.dry_run)'
```

随后执行 `import`、console、schema 和最小 typed decoder 探针。构建结果：

```text
abacus_forge-0.1.0-py3-none-any.whl
sha256=185b7d06b0a7d74d82b22c1b2328b8896947a42499562ab8136643304fe952ed
```

安装后的检查结果：

```text
import_ok 0.1.0
capabilities ['scf', 'relax', 'cell-relax', 'atst-neb', 'md', 'band', 'dos', 'pyatb-band', 'export']
cli_ok forge.capabilities/v1 9
forbidden_absent {'abacus_agent_tools': True, 'abacustest': True, 'aiida': True, 'atst_tools': True}
schema_ok forge.schema-discovery/v1 scf execute
decode_ok ScfExecuteRequest execute fixture True
```

该 gate 证明的是当前代码候选 wheel 的安装、import、console entry point、discovery 和
legacy runtime isolation；不证明 ABACUS/PyATB/ATST 的真实运行，也不包含任何
科学接受判断。

ATP/MCP、调度器和平台包不通过运行时探针判断；它们由同一候选提交的
architecture/AST forbidden-import gate 覆盖，避免把可选外部工具误写成 Forge 安装依赖。

## 4. Real-process evidence

先保留未配置外部输入时的精确 skip 基线：

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-real-smoke -m real_smoke
6 skipped, 1352 deselected in 2.14s (without external smoke inputs)
```

随后在隔离 `/tmp` 构建目录编译了 ABACUS `abacus-develop` 当前提交
`94576a80169de36e02e637edc2a0963fba9e1838` 的串行 PW 可执行文件
`abacus_pw_ser`。配置为 `ENABLE_MPI=OFF`、`ENABLE_LCAO=OFF`、
`ENABLE_OPENMP=OFF`、`USE_CUDA=OFF`，使用隔离依赖目录中的 OpenBLAS、LAPACK
和 FFTW3；可执行文件 sha256 为
`90c570c31c126d893d56c9679f9780e837d7619fc37972d04fcf01fbea88146c`。
ABACUS 本身对 Si/PBE SCF、cell-relax 和 NVE MD 输入均返回零退出码并生成
对应原生输出。

构建复现命令（`build_dir` 与 `deps_dir` 可替换为任意内容等价的临时路径）为：

```bash
build_dir=$(mktemp -d /tmp/abacus-forge-real-XXXXXX)
deps_dir=/tmp/abacus-forge-build-deps  # OpenBLAS 0.3.34 pthreads + FFTW3 3.3.11 nompi
cmake -S /home/james/work/sidereus/workplace/abacus-develop -B "$build_dir" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$build_dir/install" \
  -DENABLE_MPI=OFF -DENABLE_LCAO=OFF -DENABLE_ELPA=OFF \
  -DENABLE_PEXSI=OFF -DENABLE_OPENMP=OFF -DUSE_CUDA=OFF \
  -DBUILD_TESTING=OFF -DLAPACK_DIR="$deps_dir/lib" -DFFTW3_DIR="$deps_dir"
cmake --build "$build_dir" -j2
```

本次工具链为 CMake 3.28.3、GNU C++ 13.3.0；依赖版本来自 conda-forge
linux-64（`openblas=0.3.34`, `fftw=3.3.11`）。

为避免把旧输出当作新证据，三个 Forge smoke source 都只包含输入和伪势，
并使用 `suffix=ABACUS`：
`/tmp/abacus-forge-scf-source-29xKKl`、
`/tmp/abacus-forge-cell-relax-source-hTlmlT`、
`/tmp/abacus-forge-md-clean-MpZSVu`。精确的组合选择命令为：

三个 source 均由工作区 `paimon@5b5088160ff2e023aecf597c4e04586b5d35ed1a`
中的 `deps/aiida-abacus/tests/test_data/pw_Si2/{INPUT,STRU,KPT}` 与
`deps/aiida-abacus/tests/test_data/pseudos/Si.upf` 复制后生成；只修改了
`INPUT` 的 calculation/profile 行（SCF、cell-relax 或 NVE MD），不复制任何
原有 `OUT.*`。为让 `/tmp` 实例可核对，最终 source 文件 sha256 如下；复跑时
路径可以不同，但应与这些 hash 相同：

| source | `INPUT` | `STRU` | `KPT` | `Si.upf` |
| --- | --- | --- | --- | --- |
| SCF | `c874a7c8a3a8deca660e4cfcd1830309f88f7a1feee54bb72d40179c963a7bc0` | `6ad1d70a432384ed460679b814c0d5eef1af66f473c28bc66fcc74af99b3ee3e` | `d55726c99e0d8d0167d5e49534cd97731c4a035c5c563bd09fb72aa40d3409c7` | `39822757f53f36e3bf3bfb779356152a8d3f21199c7db9dd5a931e5d18c45282` |
| cell-relax | `5227d39ce0f5e6472e9022e299c2c6261a0734c8c8a5a16145edcdfa702a1293` | 同上 | 同上 | 同上 |
| MD | `2530be486fb1f5f8b23e921674a0bd2191a36b3aaa61382b3b588db926a2ca49` | 同上 | 同上 | 同上 |

```bash
ABACUS_FORGE_REAL_SMOKE_WORKSPACE=/tmp/abacus-forge-scf-source-29xKKl \
ABACUS_FORGE_RELAX_SMOKE_WORKSPACE=/tmp/abacus-forge-cell-relax-source-hTlmlT \
ABACUS_FORGE_RELAX_SMOKE_CAPABILITY=cell-relax \
ABACUS_FORGE_MD_SMOKE_WORKSPACE=/tmp/abacus-forge-md-clean-MpZSVu \
ABACUS_FORGE_ABACUS_EXECUTABLE=/tmp/abacus-forge-real-CpBJCH/abacus_pw_ser \
ABACUS_FORGE_ATST_EXECUTABLE=/home/james/apps/miniforge3/envs/atst-dev/bin/atst \
ABACUS_FORGE_PYATB_SMOKE_WORKSPACE=/tmp/abacus-forge-pyatb-clean-titgjN \
ABACUS_FORGE_PYATB_EXECUTABLE=/home/james/apps/miniforge3/envs/abacus-env/bin/pyatb \
ABACUS_FORGE_PYATB_SMOKE_FERMI_ENERGY=15.5241312077 \
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q \
  -p no:cacheprovider --run-real-smoke -m real_smoke
6 passed, 1352 deselected in 54.69s
```

这六项包括 legacy/typed SCF、typed cell-relax、typed MD、typed PyATB band 和 ATST
process smoke；它们证明的是 Forge 的进程调用、workspace containment、原生 parser facts、
audit event 和 artifact refs。它们不构成科学验证、收敛判断、NEB 真实执行或
稳定能力晋升。`normal_end` 仍只是独立日志 observation，不会被转换为
scientific status；当前归因规则只接受前缀未变的新增后缀 marker，旧 marker 在
截断、同尺寸改写或前缀改写中一律视为歧义并省略。

### Typed PyATB band process detail

PyATB 真实进程 gate 绑定外部仓库 `pyatb@80f7c2d89aaa8a736e4145f67a6e1d30c783be2d`
（工作区 `pyatb`，clean）和 `pyatb` 1.1.2 executable
`/home/james/apps/miniforge3/envs/abacus-env/bin/pyatb`；运行环境为 Python
3.12.13，executable sha256 为
`6ef9dc93d784bffdb3e0340c2a2523f032b9636a61bac46b22d869d0706c8944`。调用方提供的
source 是已结项 Paimon v1.2 工作区 `paimon@5b5088160ff2e023aecf597c4e04586b5d35ed1a`
下历史 `deps/abacus-forge/runs/05101055.property_calculation_scf.0218/STRU` 与
`OUT.ABACUS/{data-HR-sparse_SPIN0.csr,data-HR-sparse_SPIN1.csr,data-SR-sparse_SPIN0.csr,data-rR-sparse.csr}`；
测试只复制这五个 source 文件到临时 Forge workspace，首次执行前确认没有
`inputs/Out/Band_Structure` 生成物。它们的 sha256 如下（临时路径可变）：

| source file | sha256 |
| --- | --- |
| `source/STRU` | `d837d5654265c5f69bb8d393a0cd8d16f83d1eeb775b3aa9f43c8e68f6341490` |
| `source/data-HR-sparse_SPIN0.csr` | `78c473660cdef68588bb5933823e71c8ca1a3e3dafbf33b3ae1c5c4111f2052a` |
| `source/data-HR-sparse_SPIN1.csr` | `369241953db0501ff5a3d4179167d48cf4cf774b1a7838e32f17ab104ad895fd` |
| `source/data-SR-sparse_SPIN0.csr` | `69bd7000192312b3de95f3b6f91f8c309a4b07017dd48818575b487aa8a04a31` |
| `source/data-rR-sparse.csr` | `7439a8d613835ac2143a20abf6a693f2b3c51daf639935db425a82584c56573e` |

测试命令使用 `ABACUS_FORGE_PYATB_SMOKE_FERMI_ENERGY=15.5241312077`、nspin=2、
line-mode 十个高对称点、`line_segments=5`、`max_kpoint_num=4000` 和
`handoff_mode=copy`，执行以下三个独立 operation：

```text
prepare  -> inputs/Input + inputs/KPT_band + copied source artifacts
execute  -> one local pyatb process, returncode=0, execution=completed
collect  -> band_info.dat + band_up.dat + band_dn.dat + band.pdf, collection=complete
```

本次 `collect` 返回一个有限的 parser `band_gap=0.0097`（eV）metric；结果与三个
operation event 中的 artifact refs、workspace containment 和 `scientific=unassessed`
一致。生成的核心输出 hash 为：`band_info.dat`
`7010b0119352d4368bbd831875dcf3695976ab98d4723b81d254293a8c18c0ef`、
`band_up.dat` `d8968d9cd34decb2a03e281a3a015a430bd23ca0729390c6225fa7163924c782`、
`band_dn.dat` `0b2130388e299f02653e05ad3bd35add85c0ae188d3a618860802ab28e82ae31`、
`band.pdf` `ace9872da79ea89be2b35bdeaa8ab3e6a4069d27baacb6b57afbbf8161c1a08c`。这证明
的是 typed handoff、进程、parser 和 artifact/audit 兼容性；不证明 PyATB property
计算、物理带隙正确性、NEB workflow 或稳定 maturity。

`atst-tools` 外部仓当前记录为 `main@9318177`、版本 `2.2.4`。在
`atst-dev` 环境用 `/home/james/apps/miniforge3/envs/atst-dev/bin/atst` 运行
`tests/real_smoke/test_atst_smoke.py` 的结果为 `1 passed in 15.14s`；该门禁只
覆盖 `neb make`、`run --dry-run`、`neb summary/post` 的进程/API 与 Forge 产物
containment，不启动 ABACUS。没有提供 ATST executable 时，精确选择为 `1 skipped
in 0.02s`。真实 NEB workflow、版本/API 锁定和环境隔离仍为 `unproven`。Forge
不启动 Slurm，也不复制 atst 的链路编排。

## 5. 双版本 LCAO/版本矩阵证据（2026-09-12 增补）

本节记录把 real-smoke 从易失 `/tmp` 环境迁到持久 `abacus-packages/` 基座后的
双版本（develop + LTS）、双基组（PW + LCAO）矩阵结果。构建遵循
`abacus-develop` 仓内 toolchain（`toolchain_gnu.sh` + `build_abacus_gnu.sh`
配方），输出与源码仓隔离；复现脚本与溯源见
`abacus-packages/README.md`（工作区级目录，不属 Forge 仓）。

两轨构建均为生产级形态：MPI(OpenMPI 5.0.10/5.0.8) + LCAO + ELPA(genelpa) +
LibRI/LibComm + DFTD4 + RapidJSON + OpenMP，`BUILD_TESTING=OFF`。
`ENABLE_LIBXC=OFF` 是本地偏离：develop@`94576a801` 的 `xc_grad.cpp` 经
`xc_functional.h` 只包含 `<xc.h>`，而 libxc 7.x 将 `XC_GGA_C_LYP` 等 id 宏移入
`xc_funcs.h`，`ENABLE_LIBXC=ON` 编译失败；该不兼容属 abacus-develop 上游问题
（`libxc_abacus.h` 已示范正确包含方式），不是 Forge 缺口。LTS 轨本地另有两处
toolchain workaround（cereal 6190 补丁对 master 不适用、ELPA openmp 头文件
路径），均在 `abacus-packages/README.md` 记录且未修改任何被跟踪文件。

可执行文件与 sha256（前 24 位）：

| 轨 | commit | 可执行文件 | sha256 |
| --- | --- | --- | --- |
| develop | `94576a80169de36e02e637edc2a0963fba9e1838`（v3.11.0-beta8+56） | `abacus-packages/abacus-develop/build-mpi-lcao/install/bin/abacus` | `7ca5a99e0d68cfb4a65707db…` |
| LTS | `f71921fe8`（v3.10.1） | `abacus-packages/abacus-LTS/build-mpi-lcao/install/bin/abacus` | `51f898a40698200db79bacfd…` |

LCAO smoke 源（`abacus-packages/smoke-sources/lcao-*`）使用 Paimon v1.2
`abacus-pp-orb` submodule（`f4711b7`）的 PP/ORB 配对（Si→`PP/Si.upf`+
`ORB/Si_gga_7au_100Ry_2s2p1d.orb`，Fe→`PP/Fe_ONCV_PBE-1.2.upf`+
`ORB/Fe_gga_7au_100Ry_4s2p2d1f.orb`），`ecutwfc=100` 遵循该仓
`max(PP 推荐, ORB 截断)` 规则；Fe bcc primitive 几何取自 v1.2
`demos/strus/Fe_bcc.cif`。三个源分别为 Si LCAO SCF、Fe LCAO SCF nspin=2、
Si LCAO SCF + `out_mat_hs2=1` + `out_mat_r=1`。矩阵门禁断言 `inputs/OUT.ABACUS/`
下生成了 HR/SR/rR 稀疏矩阵，接受 v1.2/LTS 命名与 v3.11-beta 新命名两套
文件名（见下）。三个 LCAO 门禁新增于
`tests/real_smoke/test_abacus_smoke.py`，环境变量与无输入跳过语义见
`tests/real_smoke/README.md`；无外部输入时精确选择为 `9 skipped, 1352
deselected`（含新增 3 项）。

精确组合命令与结果（`S=/home/james/work/sidereus/workplace/abacus-packages/smoke-sources`，
两轨分别 source 各自 toolchain 的 `install/setup` 后运行）：

```text
develop 轨（ABACUS_FORGE_ABACUS_EXECUTABLE=…/abacus-develop/build-mpi-lcao/install/bin/abacus）：
  9 passed, 1352 deselected in 135.50s
LTS 轨（ABACUS_FORGE_ABACUS_EXECUTABLE=…/abacus-LTS/build-mpi-lcao/install/bin/abacus）：
  1 failed, 8 passed, 1352 deselected in 147.42s
  （失败项：test_typed_relax_machine_execute_and_collect，见下）
```

两条版本兼容发现（属于 ABACUS 版本行为差异，构成 v1.3 版本策略 SPEC 的
必要输入；不是本次修正的 Forge 缺陷）：

1. **develop 重命名 LCAO 稀疏矩阵输出**：v3.11.0-beta8+56 将
   `data-HR-sparse_SPIN*.csr`/`data-SR-sparse_SPIN0.csr`/`data-rR-sparse.csr`
   改名为 `hrs1_nao.csr`/`sr_nao.csr`/`rr.csr`。LTS 轨矩阵门禁以旧名通过，
   develop 轨以新名通过；typed `pyatb-band` handoff 当前只消费旧名契约，
   develop 可执行文件生成的矩阵需要显式改名或 handoff 扩展才能进入该链路。
2. **LTS v3.10.1 relax 不写 `STRU_FINAL`**：cell-relax 收敛后只写
   `STRU_ION_D`/`STRU_NOW.cif`，typed relax collection 因 final-structure
   fact 缺失返回 `partial`（collector 行为正确；develop 轨同输入
   `1 passed`）。LTS 轨 `test_typed_relax_machine_execute_and_collect`
   失败即此发现，不作为 Forge 回归处理；是否扩展 final-structure 候选
   （如 `STRU_NOW.cif`）属于版本策略决策，须独立 SPEC。

离线回归基线更新：`1346 passed, 15 skipped in 147.36s`（无外部输入时
real-smoke 选择为 `9 skipped`）。以上仍只证明进程调用、workspace containment、
原生 parser facts、audit event 与 artifact 引用，不构成科学正确性、NEB 真实
执行或 capability maturity 晋升依据。

## 6. 发布判断与未决条件

- 所有九个 typed capability 继续为 `experimental`；property packs 也继续为
  `experimental`。
- Forge core 的职责仍限于单 operation 的 prepare/modify/execute/collect/
  postprocess/export、事实型观察和 artifact 引用。
- 科学验证与接受判断、跨 operation 编排、重试/续算、资源选择、平台/调度和
  Paimon v3 thin adapter 均在 Forge 外部。
- 当前 clean package、离线契约、architecture、benchmark，以及
  ABACUS（develop/LTS 双版本、PW/LCAO 双基组）/ATST/PyATB real-process smoke
  已形成候选证据；真实 NEB workflow、上层 Paimon v1.2 全链路 parity、LTS
  relax final-structure 兼容决策和 develop 矩阵命名对 `pyatb-band` handoff
  的影响尚未闭环。
- 因此本记录不能宣称 Stage 5“证据齐全”，不能把 capability 改为 `stable`，也
  不能宣称 Forge 已是 Paimon v1.3 stable backend。后续由外部上层提供真实输入、
  benchmark harness 和独立发布决定。
