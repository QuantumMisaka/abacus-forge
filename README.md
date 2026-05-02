# ABACUS-Forge（算筹工场）

> 开发入口、开发边界与约束请优先阅读 [AGENTS.md](./AGENTS.md)。项目规划与路线图已拆分到 [ROADMAP.md](./ROADMAP.md)。

**一句话定位：**`ABACUS-Forge` 是面向本机/HPC 环境的轻量级 ABACUS 执行基座，提供 `prepare -> modify -> run -> collect -> export` 原语，`scf / relax / cell-relax / md / band / dos` 单任务 CLI 闭环，以及 `eos / elastic / vibration / phonon` 本地 composite task pack，可作为 Python 库或 CLI 使用。

## 当前定位
- 面向单个工作目录的输入准备、输入编辑、程序拉起与结果收集。
- 保持轻量边界：不处理 Slurm/Bohrium/DPDispatcher 等调度与平台编排。
- 作为 `PAIMON` 主链中的本地执行基座，被更上层 workflow 或 agent 调用。

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
- `run(...)` / `abacus-forge run`
- `collect(...)` / `abacus-forge collect`
- `export(...)` / `abacus-forge export`
- 已支持基础能量、费米能级、带隙、力、应力、压力、virial、relax 结果与关键工件索引收集

### 单任务闭环
- `run_scf(...)` / `abacus-forge scf`
- `run_relax(...)` / `abacus-forge relax`
- `run_band(...)` / `abacus-forge band`
- `run_dos(...)` / `abacus-forge dos`
- `run_cell_relax(...)` / `abacus-forge cell-relax`
- `run_md(...)` / `abacus-forge md`
- `dos` task 会在同一个任务中同时启用 DOS 与 PDOS 输出
- `band` task 需要显式提供 line-mode K 点路径，不隐式生成高对称路径
- 所有单任务支持 `--dry-run`，只准备 workspace 并返回命令预览

### 本地 composite task pack
- `abacus-forge eos prepare|run|post`
- `abacus-forge elastic prepare|run|post`
- `abacus-forge vibration prepare|run|post`
- `abacus-forge phonon prepare|run|post`
- composite pack 只管理本地子目录和本地 runner；不生成 Slurm/Bohrium/DPDispatcher 配置
- `phonon` 的 phonopy 能力是可选依赖：`pip install "abacus-forge[phonon]"`

## 安装与运行方式

### 开发态
```bash
cd deps/abacus-forge
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

### 8. 运行与收集
```bash
PYTHONPATH=src python -m abacus_forge.cli run runs/Si_scf --executable abacus --mpi 32 --omp 1
PYTHONPATH=src python -m abacus_forge.cli collect runs/Si_scf --json
PYTHONPATH=src python -m abacus_forge.cli collect runs/Si_scf --output-log outputs/abacus.log --json
PYTHONPATH=src python -m abacus_forge.cli export runs/Si_scf --output result.json
```

`collect` 默认会自动发现 stdout 类输出文件；如果 stdout 被重定向到非标准文件名，也可以通过 `--output-log` 或 `collect(..., output_log=...)` 显式指定。

## 作为 Python 库使用
```python
from abacus_forge.api import collect, prepare
from abacus_forge.modify import modify_input, modify_kpt, modify_stru
from abacus_forge.runner import LocalRunner
from abacus_forge.tasks import run_dos, run_scf

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

task_result = run_scf("runs/Si_task", structure="Si.cif", executable="abacus")
dos_result = run_dos("runs/FeO_dos", structure="FeO.cif", executable="abacus")
print(task_result.status, dos_result.metrics.get("dos_family_summary"))
```

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
- 不在本层实现 phonon / elastic 等厚工作流

## 贡献
- 小步提交，保持边界清晰
- 为解析器和 CLI 补充可复现测试
- 开发前先阅读 [AGENTS.md](./AGENTS.md)
