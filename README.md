# ABACUS-Forge（算筹工场）

> 开发入口、开发边界与约束请优先阅读 [AGENTS.md](./AGENTS.md)。项目规划与路线图已拆分到 [ROADMAP.md](./ROADMAP.md)。

**一句话定位：**`ABACUS-Forge` 是面向本机/HPC 环境的轻量级 ABACUS 执行基座，提供 `prepare -> modify -> execute -> collect -> export` 原语，`scf / relax / cell-relax / md / band / dos` 单任务 CLI 闭环，`eos / elastic / vibration / phonon` 本地 composite task pack，以及实验性 `convergence / cube / workfunc / vacancy / bec` 等 property pack，可作为 Python 库或 CLI 使用。`run` 仍作为 `execute` 的兼容别名保留。

## 当前定位

- 面向单个工作目录的输入准备、输入编辑、程序拉起与结果收集。
- 保持轻量边界：不处理 Slurm/Bohrium/DPDispatcher 等调度与平台编排。
- 作为协议与平台无关的科学计算内核，同时被 ABACUS Agent（Paimon）v1.3 适配层、其他 workflow/agent 和独立 CLI 用户消费。
- CLI 优先保持非交互式、参数显式与结果结构化；TUI 和数字 Task-ID 不定义核心能力协议。

## 当前已实现能力

### 输入准备

- `prepare(...)` / `abacus-forge prepare`
- 支持从结构文件生成 `INPUT` / `STRU` / `KPT`
- 支持参数覆盖、参数删除、K 点设置、PP/ORB 路径、`copy/link` 资产模式
- 支持简单的按元素共线磁矩初始化

### 输入编辑

- `modify_input(...)` / `abacus-forge modify-input`
- `modify_stru(...)` / `abacus-forge modify-stru`
- `modify_kpt(...)` / `abacus-forge modify-kpt`
- 输入三件套 `INPUT / STRU / KPT` 均已具备 Python API 与 CLI 闭环

### 运行与收集

- `execute(...)` / `abacus-forge execute`
- `run(...)` / `abacus-forge run` 兼容别名
- `collect(...)` / `abacus-forge collect`
- `export(...)` / `abacus-forge export`
- 已支持基础能量、费米能级、带隙、力、应力、压力、virial、relax 结果与关键工件索引收集

### 原子 unit API

- `UnitSpec`
- `prepare_unit(...)`
- `modify_unit(...)`
- `execute_unit(...)`
- `collect_unit(...)`
- CLI 入口为 `abacus-forge prepare|modify|execute|collect --task ... --unit ...`
- `band` / `dos` 这类多阶段物理任务被拆成 `scf`、`nscf`、`pyatb` 或 `postprocess` 等可独立运行单元
- 下游单元通过显式 `--source-workdir` 读取上游产物，不在 Forge 内部隐藏调度完整 workflow

### 单任务闭环

- `run_scf(...)` / `abacus-forge scf`
- `run_relax(...)` / `abacus-forge relax`
- `run_band(...)` / `abacus-forge band`
- `run_dos(...)` / `abacus-forge dos`
- `run_cell_relax(...)` / `abacus-forge cell-relax`
- `run_md(...)` / `abacus-forge md`
- `dos` task 会在同一个任务中同时启用 DOS 与 PDOS 输出
- `band` task 需要显式提供 line-mode K 点路径，不隐式生成高对称路径
- `band` / `dos` 的单任务 `prepare` 生成 ABACUS NSCF 输入；推荐用 unit CLI 显式组合 SCF 与 NSCF
- 所有单任务支持 `--dry-run`，只准备 workspace 并返回命令预览

### 本地 sequence API

- `run_band_sequence(...)`：本地组合 `SCF -> NSCF band -> collect`
- `run_band_sequence(..., backend="pyatb")`：本地组合 `SCF(out_mat_r/out_mat_hs2) -> PyATB Input -> pyatb -> collect_pyatb`
- `run_dos_sequence(...)`：本地组合 `SCF -> NSCF DOS/PDOS -> collect/postprocess`
- `prepare_pyatb_band(...)` / `run_pyatb(...)` / `collect_pyatb(...)` 可作为独立 PyATB 原语使用
- sequence API 只作为兼容 helper 管理本地子目录；新的可组合入口是 `prepare_unit / execute_unit / collect_unit`

### 本地 composite task pack

- `abacus-forge eos prepare|run|post`
- `abacus-forge elastic prepare|run|post`
- `abacus-forge vibration prepare|run|post`
- `abacus-forge phonon prepare|run|post`
- composite pack 只管理本地子目录和本地 runner；不生成 Slurm/Bohrium/DPDispatcher 配置
- `phonon` 的 phonopy 能力是可选依赖：`pip install "abacus-forge[phonon]"`

### 本地 property pack

> **成熟度：实验性。** 以下能力已具备 API/CLI 和 mock/fixture 回归，但尚未逐项完成真实 ABACUS 计算验收；不应视为 PAIMON v1.3 已稳定暴露的能力。

- `abacus-forge convergence prepare|run|post`
- `abacus-forge charge-density prepare|run|post`
- `abacus-forge spin-density prepare|run|post`
- `abacus-forge charge-diff prepare|run|post`
- `abacus-forge elf prepare|run|post`
- `abacus-forge bader prepare|run|post`
- `abacus-forge workfunc prepare|run|post`
- `abacus-forge vacancy prepare|run|post`
- `abacus-forge bec prepare|run|post`
- property pack 从 `abacus-test CLI` 与 `ABACUS-agent-tools` 的底层能力拆解而来，只承接输入生成、本地子目录执行、cube/文本后处理和 JSON 结果汇总；不承接 Bohrium/dflow/Slurm 编排。
- `bader post` 只调用本机已有 `bader` 可执行文件；缺失时返回 diagnostics，不自动安装外部程序。

## 安装与运行方式

### 开发态

```bash
# 在 abacus-forge 仓库根目录
PYTHONPATH=src python -m abacus_forge.cli --help
```

### 安装后

```bash
abacus-forge --help
```

## CLI 快速上手

### 1. 直接运行一个 SCF 任务

```bash
PYTHONPATH=src python -m abacus_forge.cli scf runs/Si_scf \
  --structure Si.cif \
  --ensure-pbc \
  --parameter ecutwfc=70 \
  --executable abacus \
  --json
```

### 2. 直接运行一个 DOS+PDOS 任务

```bash
PYTHONPATH=src python -m abacus_forge.cli dos runs/FeO_dos \
  --structure FeO.cif \
  --magmom Fe=3.0 \
  --magmom O=0.5 \
  --executable abacus \
  --output result.json \
  --json
```

### 3. 准备一个工作目录

```bash
PYTHONPATH=src python -m abacus_forge.cli prepare runs/Si_scf \
  --structure Si.cif \
  --task scf \
  --parameter ecutwfc=70 \
  --kpoint 3 --kpoint 3 --kpoint 1
```

### 4. 对 INPUT 做轻量编辑

```bash
PYTHONPATH=src python -m abacus_forge.cli modify-input runs/Si_scf/inputs/INPUT \
  --output runs/Si_scf/inputs/INPUT.modified \
  --set calculation=relax \
  --set force_thr=1e-4 \
  --remove smearing_sigma
```

### 5. 对 STRU 做磁矩编辑

```bash
PYTHONPATH=src python -m abacus_forge.cli modify-stru FeO.cif \
  --output STRU \
  --magmom Fe=3.0 \
  --magmom O=0.5 \
  --afm
```

也可以做结构级轻量变换：

```bash
PYTHONPATH=src python -m abacus_forge.cli modify-stru STRU \
  --output STRU.super \
  --structure-format stru \
  --supercell 2 2 1 \
  --vacancy-index 3
```

### 6. 对 KPT 做 mesh 编辑

```bash
PYTHONPATH=src python -m abacus_forge.cli modify-kpt runs/Si_scf/inputs/KPT \
  --output runs/Si_scf/inputs/KPT.modified \
  --mode mesh \
  --mesh 6 6 1 \
  --shifts 1 1 1
```

### 7. 对 KPT 做 line 编辑

```bash
PYTHONPATH=src python -m abacus_forge.cli modify-kpt KPT.line \
  --output KPT.line.modified \
  --mode line \
  --segments 20 \
  --point 0,0,0:Gamma \
  --point 0.5,0,0:X
```

Forge 写出的 line-mode `KPT` 使用 ABACUS 原生格式：第二行为高对称点数量，每个点行为 `kx ky kz npoints [#label]`。旧的 `segments` payload 仍兼容；未显式提供 `npoints` 时，除最后一点外使用 `segments`，最后一点使用 `1`。

### 8. 对已准备 workspace 做 unit 输入编辑

```bash
PYTHONPATH=src python -m abacus_forge.cli modify runs/Fe_cell_relax \
  --task cell-relax \
  --set force_thr=1e-4 \
  --remove smearing_sigma \
  --kpt-mode mesh --mesh 5 5 1 --shifts 1 1 0 \
  --magmom Fe=3.0 --afm \
  --json
```

### 9. 执行与收集

```bash
PYTHONPATH=src python -m abacus_forge.cli execute runs/Si_scf --executable abacus --mpi 32 --omp 1
PYTHONPATH=src python -m abacus_forge.cli run runs/Si_scf --executable abacus --mpi 32 --omp 1
PYTHONPATH=src python -m abacus_forge.cli collect runs/Si_scf --json
PYTHONPATH=src python -m abacus_forge.cli collect runs/Si_scf --output-log outputs/abacus.log --json
PYTHONPATH=src python -m abacus_forge.cli export runs/Si_scf --output result.json
```

`collect` 默认会自动发现 stdout 类输出文件；如果 stdout 被重定向到非标准文件名，也可以通过 `--output-log` 或 `collect(..., output_log=...)` 显式指定。

### 10. 显式组合 cell-relax -> band -> dos

Forge 不提供 `relax-band-dos` 一键 workflow。NiO 这类全流程应由上层 workflow 或 shell 显式串联原子 unit：

```bash
PYTHONPATH=src python -m abacus_forge.cli prepare runs/nio/cell-relax \
  --task cell-relax --structure NiO.STRU --structure-format stru
PYTHONPATH=src python -m abacus_forge.cli execute runs/nio/cell-relax --task cell-relax --executable abacus
PYTHONPATH=src python -m abacus_forge.cli collect runs/nio/cell-relax --task cell-relax --json

PYTHONPATH=src python -m abacus_forge.cli prepare runs/nio/band-scf \
  --task band --unit scf --source-workdir runs/nio/cell-relax
PYTHONPATH=src python -m abacus_forge.cli execute runs/nio/band-scf --task band --unit scf --executable abacus
PYTHONPATH=src python -m abacus_forge.cli collect runs/nio/band-scf --task band --unit scf --json

PYTHONPATH=src python -m abacus_forge.cli prepare runs/nio/band-nscf \
  --task band --unit nscf --source-workdir runs/nio/band-scf \
  --point 0,0,0:G --point 0.5,0,0:X --segments 20
PYTHONPATH=src python -m abacus_forge.cli execute runs/nio/band-nscf --task band --unit nscf --executable abacus
PYTHONPATH=src python -m abacus_forge.cli collect runs/nio/band-nscf --task band --unit nscf --json

PYTHONPATH=src python -m abacus_forge.cli prepare runs/nio/dos-nscf \
  --task dos --unit nscf --source-workdir runs/nio/band-scf
PYTHONPATH=src python -m abacus_forge.cli execute runs/nio/dos-nscf --task dos --unit nscf --executable abacus
PYTHONPATH=src python -m abacus_forge.cli collect runs/nio/dos-nscf --task dos --unit nscf --json
```

### 11. Property pack 示例

```bash
PYTHONPATH=src python -m abacus_forge.cli convergence prepare runs/Si_scf \
  --key ecutwfc --value 60 --value 80 --json
PYTHONPATH=src python -m abacus_forge.cli convergence run runs/Si_scf --executable abacus --json
PYTHONPATH=src python -m abacus_forge.cli convergence post runs/Si_scf --key ecutwfc --json

PYTHONPATH=src python -m abacus_forge.cli spin-density prepare runs/Fe_scf --json
PYTHONPATH=src python -m abacus_forge.cli spin-density post runs/Fe_scf --json

PYTHONPATH=src python -m abacus_forge.cli workfunc prepare runs/slab --vacuum-axis c --dipole-correction --json
PYTHONPATH=src python -m abacus_forge.cli workfunc post runs/slab --vacuum-axis c --json
```

## 作为 Python 库使用

```python
from abacus_forge.api import UnitModifySpec, UnitSpec, collect, collect_unit, execute_unit, modify_unit, prepare, prepare_unit
from abacus_forge.composite import prepare_convergence, post_convergence, prepare_workfunc, post_workfunc
from abacus_forge.cube import CubeData, subtract_cubes
from abacus_forge.modify import modify_input, modify_kpt, modify_stru
from abacus_forge.runner import LocalRunner
from abacus_forge.tasks import run_band_sequence, run_dos, run_dos_sequence, run_scf

workspace = prepare(
    "runs/Si_scf",
    structure="Si.cif",
    task="scf",
    parameters={"ecutwfc": 70},
    kpoints=[3, 3, 1],
)

modify_input(workspace.inputs_dir / "INPUT", updates={"force_thr": "1e-4"})
modify_kpt(workspace.inputs_dir / "KPT", mesh=[6, 6, 1], shifts=[1, 1, 1])
modify_stru(workspace.inputs_dir / "STRU", destination=workspace.inputs_dir / "STRU.modified")

result = collect(workspace, output_log="outputs/abacus.log")
print(result.status)

prepared = prepare_unit(UnitSpec(task="band", unit="scf", workdir="runs/NiO_band_scf", structure="NiO.STRU", structure_format="stru"))
modified = modify_unit(UnitModifySpec(task="band", unit="scf", workdir=prepared.workspace.root, input_updates={"scf_thr": "1e-8"}))
executed = execute_unit(UnitSpec(task="band", unit="scf", workdir=prepared.workspace.root, executable="abacus"))
collected = collect_unit(UnitSpec(task="band", unit="scf", workdir=prepared.workspace.root))

task_result = run_scf("runs/Si_task", structure="Si.cif", executable="abacus")
dos_result = run_dos("runs/FeO_dos", structure="FeO.cif", executable="abacus")
print(task_result.status, dos_result.metrics.get("dos_family_summary"))

band_sequence = run_band_sequence(
    "runs/Si_band_sequence",
    structure="Si.cif",
    executable="abacus",
    backend="nscf",
    line_kpoints=[
        {"coords": [0, 0, 0], "npoints": 20, "label": "Gamma"},
        {"coords": [0.5, 0, 0], "npoints": 1, "label": "X"},
    ],
)
pyatb_band_sequence = run_band_sequence(
    "runs/NiO_band_pyatb",
    structure="NiO.STRU",
    executable="abacus",
    pyatb_executable="pyatb",
    backend="pyatb",
    parameters={"basis_type": "lcao"},
    line_kpoints=[
        {"coords": [0, 0, 0], "npoints": 20, "label": "Gamma"},
        {"coords": [0.5, 0, 0], "npoints": 1, "label": "X"},
    ],
)
dos_sequence = run_dos_sequence("runs/FeO_dos_sequence", structure="FeO.cif", executable="abacus")

conv_plan = prepare_convergence("runs/Si_scf", key="ecutwfc", values=["60", "80"])
conv_result = post_convergence("runs/Si_scf", key="ecutwfc")
workfunc_plan = prepare_workfunc("runs/slab", vacuum_axis="c", dipole_correction=True)
workfunc_result = post_workfunc("runs/slab", vacuum_axis="c")
```

`LocalRunner` 在 `inputs/` 目录下直接执行 ABACUS 可执行文件，不默认注入 `--input-dir` 等非 ABACUS 参数。
PyATB 不是必装依赖；缺少 `pyatb` 可执行文件或 ABACUS LCAO matrix files 时，PyATB collect/sequence 会返回明确 diagnostics。

## 目录约定

推荐每次运行生成独立工作目录：

```text
runs/<run_id>/
  inputs/
  outputs/
  reports/
```

## 非目标

- 不内置云平台提交、追踪、下载能力
- 不引入 AiiDA 语义或工作流编排语义到 Forge 核心
- 对于 phonon / elastic 等厚工作流，其实现必须基于解耦的单元模块，且其输入/计算/输出必须可解耦

## 贡献

- 小步提交，保持边界清晰
- 为解析器和 CLI 补充可复现测试
- 开发前先阅读 [AGENTS.md](./AGENTS.md)
