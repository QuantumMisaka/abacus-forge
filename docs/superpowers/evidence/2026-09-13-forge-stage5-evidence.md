# Forge Stage 5 evidence record

**状态：** provisional / candidate evidence；不构成稳定能力或 Paimon v1.3
backend 发布决定。

**代码候选提交：** `e32fda1`（包含生产代码归因修复、回归测试，以及已复审的
ATST adapter 死状态清理；后者不改变行为或公共契约）。Stage 5 ATST smoke harness
follow-ups：`c11fc6e`、`7458110`；这些提交仅增加测试/门禁文档，不改变生产代码候选。

**证据文档基线提交：** `87eda1fe6b3e59da73965d4dee92cf2e876d5054`；后续
`5806d1c`、`5930607`、`939f666` 及后续文档校正均不改变候选代码；`e32fda1` 是之后
单独复审的行为保持型 adapter 清理。

**规范源：**
`docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html`
与 `docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html`。

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
1346 passed, 11 skipped in 103.32s (0:01:43)

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
5 skipped, 1352 deselected in 2.40s (without external smoke inputs)
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
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q \
  -p no:cacheprovider --run-real-smoke -m real_smoke tests/real_smoke
5 passed in 51.30s
```

这五项包括 legacy/typed SCF、typed cell-relax、typed MD 和 ATST process smoke；
它们证明的是 Forge 的进程调用、workspace containment、原生 parser facts、
audit event 和 artifact refs。它们不构成科学验证、收敛判断、NEB 真实执行或
稳定能力晋升。`normal_end` 仍只是独立日志 observation，不会被转换为
scientific status；当前归因规则只接受前缀未变的新增后缀 marker，旧 marker 在
截断、同尺寸改写或前缀改写中一律视为歧义并省略。

`atst-tools` 外部仓当前记录为 `main@9318177`、版本 `2.2.4`。在
`atst-dev` 环境用 `/home/james/apps/miniforge3/envs/atst-dev/bin/atst` 运行
`tests/real_smoke/test_atst_smoke.py` 的结果为 `1 passed in 15.14s`；该门禁只
覆盖 `neb make`、`run --dry-run`、`neb summary/post` 的进程/API 与 Forge 产物
containment，不启动 ABACUS。没有提供 ATST executable 时，精确选择为 `1 skipped
in 0.02s`。真实 NEB workflow、版本/API 锁定和环境隔离仍为 `unproven`。Forge
不启动 Slurm，也不复制 atst 的链路编排。

## 5. 发布判断与未决条件

- 所有九个 typed capability 继续为 `experimental`；property packs 也继续为
  `experimental`。
- Forge core 的职责仍限于单 operation 的 prepare/modify/execute/collect/
  postprocess/export、事实型观察和 artifact 引用。
- 科学验证与接受判断、跨 operation 编排、重试/续算、资源选择、平台/调度和
  Paimon v3 thin adapter 均在 Forge 外部。
- 当前 clean package、离线契约、architecture、benchmark，以及 ABACUS/ATST
  real-process smoke 已形成候选证据；PyATB real process、真实 NEB workflow 和
  上层 Paimon v1.2 全链路 parity 尚未齐全。
- 因此本记录不能宣称 Stage 5“证据齐全”，不能把 capability 改为 `stable`，也
  不能宣称 Forge 已是 Paimon v1.3 stable backend。后续由外部上层提供真实输入、
  benchmark harness 和独立发布决定。
