# Forge 使用指南

本文按实际调用任务组织当前用法。机器字段和持久化语义见[接口与 workspace 参考](reference.md)；`--help` 与能力发现是当前 CLI/schema 的直接来源。

仓库内 NiO 样例的 `INPUT`/`STRU` 来源、SAI 脚本边界及不依赖 ABACUS 的本地 prepare/dry-run 命令见[示例输入说明](../examples/README.md)。

## 选择调用面

Forge 保留多个面向不同消费场景的入口，它们不是可互换的别名：

| 调用面 | 适用场景 | 边界 |
| --- | --- | --- |
| primitive API | 对单个 workspace 执行 `prepare`、输入文件修改、`execute`、`collect`、`export` | 薄操作原语；`run()` 是 `execute()` 的兼容别名。 |
| `UnitSpec` / unit API | 将 band、DOS 等任务拆为显式 SCF、NSCF、PyATB 或后处理单元 | 通过显式 source workdir 交接上游结果；不隐式调度多阶段 workflow。 |
| 单任务 API/CLI | 快速完成一次 `scf`、`relax`、`cell-relax`、`md`、`band` 或 `dos` 任务 | 兼容便利入口；band/DOS 的 legacy task 行为不等于 typed band/DOS capability。 |
| sequence API | 兼容管理本地 SCF→NSCF band 或 DOS 等阶段目录 | 只负责本地 sequence helper；新的可组合入口是显式 unit 操作。 |
| composite/property pack | 使用已存在的本地领域组合接口 | 本地子目录和 runner；不引入 scheduler 或平台编排。Property packs 保持 experimental。 |
| typed operation service / machine CLI | 显式、单次、可审计的请求/结果边界 | 每次调用一个声明支持的 operation；不隐式串联、执行科学判断或选择 latest。 |

typed `prepare` 使用请求中显式的 `pseudo_sources`、`orbital_sources` 与 `asset_mode`；legacy `prepare(...)` 保留按 `pseudo_path` / `orbital_path` 推断资源目录的行为并默认 `link`。不要将 legacy/unit/sequence 调用假定为 typed service 的同一调用链。

## 安装和外部输入

从仓库安装：

```bash
python -m pip install .
```

运行 ABACUS 还要求调用环境能找到 ABACUS executable，以及输入 `STRU` 所引用的赝势和需要的轨道文件。Forge 不提供这些计算引擎或资源文件。`phonon` pack 的可选依赖通过 `python -m pip install '.[phonon]'` 安装。完整依赖列表及包入口见 `pyproject.toml`。

使用仓库源码开发时，可从仓库根目录运行：

```bash
PYTHONPATH=src python -m abacus_forge.cli --help
```

安装后的命令入口为 `abacus-forge`。CLI 选项会随入口有所不同；执行前查阅对应 `<command> --help`。

```bash
abacus-forge --help
```

<a id="cli-workflows"></a>
## CLI 工作流

### 单任务快捷入口

`scf`、`dos` 等单任务命令是 legacy convenience 闭环。示例中的结构、PP/ORB 资源和 ABACUS executable 必须由调用方提供；`dos` 会同时请求 DOS 与 PDOS 输出，磁性示例可按元素传入 `--magmom`：

```bash
PYTHONPATH=src python -m abacus_forge.cli scf runs/Si_scf \
  --structure Si.cif \
  --ensure-pbc \
  --parameter ecutwfc=70 \
  --executable abacus \
  --json

PYTHONPATH=src python -m abacus_forge.cli dos runs/FeO_dos \
  --structure FeO.cif \
  --magmom Fe=3.0 \
  --magmom O=0.5 \
  --executable abacus \
  --output result.json \
  --json
```

### 准备、执行和收集

将结构和计算资源路径替换为本机可用输入。`prepare` 创建工作目录和 ABACUS 输入；检查输入及资源引用后再执行：

```bash
abacus-forge prepare runs/Si_scf \
  --structure path/to/Si.cif \
  --task scf \
  --parameter ecutwfc=70 \
  --kpoint 3 --kpoint 3 --kpoint 1 \
  --pseudo-path path/to/pseudopotentials \
  --orbital-path path/to/orbitals \
  --asset-mode copy
abacus-forge execute runs/Si_scf --executable abacus --mpi 1 --omp 1
abacus-forge collect runs/Si_scf --json
abacus-forge export runs/Si_scf --output result.json
```

`collect` 默认发现 stdout 类输出文件。stdout 被重定向到非标准文件名时，可以传 `--output-log` 或在 Python `collect(..., output_log=...)` 中显式指定。`execute` 与兼容别名 `run` 都可用于已准备的 workspace；原语也可分开使用：

```bash
PYTHONPATH=src python -m abacus_forge.cli execute runs/Si_scf --executable abacus --mpi 32 --omp 1
PYTHONPATH=src python -m abacus_forge.cli run runs/Si_scf --executable abacus --mpi 32 --omp 1
PYTHONPATH=src python -m abacus_forge.cli collect runs/Si_scf --json
PYTHONPATH=src python -m abacus_forge.cli collect runs/Si_scf --output-log outputs/abacus.log --json
PYTHONPATH=src python -m abacus_forge.cli export runs/Si_scf --output result.json
```

`prepare`、`execute`、`collect` 和 `export` 不会因在 shell 中依次调用而变成一个 typed machine operation。

### 单文件编辑

`modify-input`、`modify-stru` 和 `modify-kpt` 分别编辑一个输入文件或结构载荷。例如：

```bash
abacus-forge modify-input runs/Si_scf/inputs/INPUT \
  --output runs/Si_scf/inputs/INPUT.modified \
  --set calculation=relax --set force_thr=1e-4 \
  --remove smearing_sigma

abacus-forge modify-kpt runs/Si_scf/inputs/KPT \
  --output runs/Si_scf/inputs/KPT.modified \
  --mode mesh --mesh 6 6 1 --shifts 1 1 1
```

`modify-stru` 可设置按元素共线磁矩，也支持超胞和 vacancy 等单载荷变换；运行 `abacus-forge modify-stru --help` 查看可用选项。对已准备 workspace 执行单元级编辑可用 `modify <workspace> --task ... --unit ...`，它可组合 INPUT、KPT 和结构轻量修改，但仍只作用于调用方指定的 workspace/unit。

例如，`modify-stru` 可以从 CIF 初始化 Fe/O 磁矩和反铁磁排列，也可以对已有 STRU 构造超胞并删除一个原子：

```bash
PYTHONPATH=src python -m abacus_forge.cli modify-stru FeO.cif \
  --output STRU --magmom Fe=3.0 --magmom O=0.5 --afm

PYTHONPATH=src python -m abacus_forge.cli modify-stru STRU \
  --output STRU.super --structure-format stru \
  --supercell 2 2 1 --vacancy-index 3
```

KPT line mode 示例及其 ABACUS 原生格式说明：

```bash
PYTHONPATH=src python -m abacus_forge.cli modify-kpt KPT.line \
  --output KPT.line.modified --mode line --segments 20 \
  --point 0,0,0:Gamma --point 0.5,0,0:X
```

生成的 line-mode `KPT` 第二行为高对称点数量，每个点行为 `kx ky kz npoints [#label]`。旧 `segments` payload 仍兼容；没有显式提供 `npoints` 时，除最后一点外使用 `segments`，最后一点使用 `1`。

若 workspace 已准备好，可以一次编辑指定 unit 的 INPUT、KPT 和结构：

```bash
PYTHONPATH=src python -m abacus_forge.cli modify runs/Fe_cell_relax \
  --task cell-relax \
  --set force_thr=1e-4 --remove smearing_sigma \
  --kpt-mode mesh --mesh 5 5 1 --shifts 1 1 0 \
  --magmom Fe=3.0 --afm --json
```

### 显式交接多阶段计算

Forge 不提供 `relax-band-dos` 一键 workflow。上层工作流或 shell 可显式创建各阶段 workspace，并把前一阶段目录交给下一单元：

```bash
PYTHONPATH=src python -m abacus_forge.cli prepare runs/nio/cell-relax \
  --task cell-relax --structure NiO.STRU --structure-format stru
PYTHONPATH=src python -m abacus_forge.cli execute runs/nio/cell-relax --task cell-relax --executable abacus
PYTHONPATH=src python -m abacus_forge.cli collect runs/nio/cell-relax --task cell-relax --json

PYTHONPATH=src python -m abacus_forge.cli prepare runs/nio/band-scf \
  --task band --unit scf --structure NiO.STRU --structure-format stru
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

Python API 通过 `UnitSpec`、`prepare_unit`、`modify_unit`、`execute_unit` 和 `collect_unit` 暴露这些边界。`run_band_sequence(...)` 与 `run_dos_sequence(...)` 仍是本地兼容 helper；PyATB 能带 sequence 通过 `backend="pyatb"` 选择。sequence helper 保留现有本地目录和产物交接行为。

<a id="composite-and-property-packs"></a>
### Composite 与 property pack

CLI 提供本地 `eos`、`elastic`、`vibration` 和 `phonon` composite 命令，每个 pack 有 `prepare|run|post` 操作。`phonon` 需要可选依赖 `phonopy`。这些 pack 使用本地子目录和本地 runner，不会生成 Slurm、Bohrium 或 DPDispatcher 配置。拟合数据不足时，`elastic post` 会将结果明确标为 `unavailable`。

`convergence`、`charge-density`、`spin-density`、`charge-diff`、`elf`、`bader`、`workfunc`、`vacancy` 和 `bec` property pack 暴露本地 `prepare|run|post` 命令。它们均为实验性能力：大多数仅有 mock/fixture 证据；`convergence`、`spin-density`、`workfunc` 和 `charge-diff` 各有一次本地 serial-PW 操作与解析 smoke。这些证据不能将它们提升为稳定产品能力，也不构成科学验收。legacy `bec` pack 保持 fixture/legacy 形态，不会被下方独立的原生 typed polarization/BEC 路径数值替换。`bader post` 只调用本机已安装的 `bader` executable，不会安装该程序。

以下命令展示 convergence、spin-density 和 workfunc 的不同参数。实际运行前需提供相应 ABACUS 输入/产物以及本机可用的可执行文件：

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

对于 `charge-density`、`spin-density` 和 `charge-diff`，legacy `post` 结果可能带有 `diagnostics.property_manifest`，索引选中的 cube 输入、派生 cube 输出、报告和缺失路径。它只是文件事实索引，不是新的 typed property capability，也不作科学评估。

## Agent-first CLI

机器调用面提供 `operation`、`schema` 和 `capabilities`。每次 `operation` 只执行一个请求；多 operation 的衔接由调用方负责。当前 discovery 列出 `scf`、`relax`、`cell-relax`、`atst-neb`、`md`、`band`、`dos`、`cohp`、`pyatb-band`、`pyatb-cohp`、`polarization`、`bec` 和 `export`。operation 支持范围由 capability 决定：typed band、DOS 和 COHP 仅支持 `postprocess`；typed export 仅支持 `export`；`polarization` 仅支持 `collect`，`bec` 仅支持 `postprocess`；typed PyATB band/COHP 支持 `prepare`、`execute`、`collect`；`md` 支持 `prepare`、`modify`、`execute`、`collect` 和 `postprocess`。每种能力当前的字段和成熟度以 discovery/schema 返回为准。

请求可从文件读取：

```json
{
  "schema_version": "forge.request/v1",
  "operation": "execute",
  "operation_id": "123e4567-e89b-42d3-a456-426614174010",
  "workspace_rel": ".",
  "dry_run": true
}
```

```bash
PYTHONPATH=src python -m abacus_forge.cli operation execute --request request.json
```

也可从 stdin 读取：

```json
{
  "schema_version": "forge.request/v1",
  "operation": "execute",
  "operation_id": "123e4567-e89b-42d3-a456-426614174011",
  "workspace_rel": ".",
  "dry_run": true
}
```

```bash
cat request.json | PYTHONPATH=src python -m abacus_forge.cli operation execute --stdin
```

`capabilities` 和 `schema <capability> <operation>` 返回确定性的 JSON 文档。机器请求字段与结果协议见[机器请求和状态参考](reference.md#machine-request-and-status-protocol)。

### Experimental ATST-NEB machine API

`atst-neb` capability 支持 `prepare`、`execute` 和 `postprocess`；这三个名称构成的是该 capability 自己的 operation 集。Forge 通过外部 `atst` executable 调用 `atst neb make`、`atst run` 和 `atst neb summary/post`，不要求安装或导入 `atst-tools` Python 包。NEB 图像链路编排与并行执行由 atst-tools 负责；后端/模型设置、外层调度和重试，以及科学解释由调用方负责。当前请求形态可用 `abacus-forge schema atst-neb <operation>` 查看。

## Typed Relax operations

`RelaxPrepareRequest`、`RelaxModifyRequest`、`RelaxExecuteRequest` 和 `RelaxCollectRequest` 接受 `capability="relax"` 或 `"cell-relax"`。capability 决定 ABACUS 的 `calculation` profile。每次请求仍只执行一个 operation；调用方在各次调用之间显式传递 workspace。Python prepare 示例：

```python
from abacus_forge import RelaxPrepareRequest, RelaxServiceSet

request = RelaxPrepareRequest(
    operation_id="123e4567-e89b-42d3-a456-426614174012",
    workspace_rel="runs/Si_relax",
    capability="relax",
    structure_path_rel="source.STRU",
    parameters={"calculation": "relax", "ecutwfc": 70},
)
services = RelaxServiceSet.default(workspace_root=".")
outcome = services.prepare.prepare(request)
```

四个 operation 的职责分别是：prepare 写入输入和 provenance；modify 修改 `INPUT` 参数；execute 拉起一次本地 ABACUS process；collect 解析现有输出事实，包括可用的力/应力/relax observations 和最终结构。Typed Relax 的 discovery/schema 当前仍标记为实验性。真实进程 smoke 检查序列化结果、事件和 artifact 行为，不判断物理收敛。typed 与 legacy 的资产差异见[参考说明](reference.md#typed-prepare-assets-and-legacy-assets)。

Machine CLI 的 execute 请求需要显式写出 capability：

```json
{
  "schema_version": "forge.request/v1",
  "operation": "execute",
  "operation_id": "123e4567-e89b-42d3-a456-426614174013",
  "workspace_rel": "runs/Si_cell_relax",
  "capability": "cell-relax",
  "executable": "abacus",
  "mpi_ranks": 1,
  "omp_threads": 1,
  "dry_run": false
}
```

保存为 `request.json` 后只执行这一次 operation：

```bash
PYTHONPATH=src python -m abacus_forge.cli operation execute --request request.json
```

## Typed MD operations

Typed `md` 是实验性能力，提供 `prepare`、`modify`、`execute`、`collect` 和独立的 `postprocess` operation。MD 专用控制项放在 JSON-safe 的 `parameters` map 中：

```python
from abacus_forge import MdPrepareRequest, MdServiceSet

request = MdPrepareRequest(
    operation_id="123e4567-e89b-42d3-a456-426614174014",
    workspace_rel="runs/Si_md",
    capability="md",
    structure_path_rel="source.STRU",
    parameters={
        "md_type": "nve", "md_nstep": 100, "md_dt": 1.0,
        "md_tfirst": 300, "md_tlast": 300, "md_dumpfreq": 1,
    },
)
outcome = MdServiceSet.default(workspace_root=".").prepare.prepare(request)
```

默认 profile 使用 PBE 和 NVE；物理参数由调用方选择。Typed collection 在文件可用时返回 `MD_dump` 与原生 `running_md.log` 的事实。原生日志中的 Energy、Potential 和 Kinetic 从 Ry 换算为 eV；Pressure 可以不存在。结果不判断轨迹或物理结果是否可接受。

### Typed MD postprocess

`MdPostprocessRequest` 要求显式的 workspace-relative `trajectory_path_rel`，并指定一个或多个 canonical analysis：`rdf`、`msd_diffusion`、`vacf_vdos`、`bond_length` 或 `bond_angle`。它不扫描寻找轨迹、不转换 `MD_dump`，也不调用 ABACUS。例如：

```json
{
  "schema_version": "forge.request/v1",
  "capability": "md",
  "operation": "postprocess",
  "operation_id": "123e4567-e89b-42d3-a456-426614174150",
  "workspace_rel": "runs/Si_md",
  "trajectory_path_rel": "outputs/md.traj",
  "analysis": ["msd_diffusion", "vacf_vdos"],
  "output_dir_rel": "outputs/md-postprocess",
  "parameters": {"timestep": 1.0, "save_data": true, "save_plot": true}
}
```

```bash
PYTHONPATH=src python -m abacus_forge.cli operation postprocess --request md-postprocess-request.json
```

MSD/VACF 要求正值 `timestep`，表示选定帧视图中相邻帧的时间间隔；不会将 `stride` 隐式乘入。RDF 要求轨迹中明确包含周期 cell。结果描述生成的 artifacts 和解析事实，状态为 `execution=not_run`、`scientific=unassessed`。Python API 使用同一个 service：

```python
from abacus_forge import MdPostprocessRequest, MdPostprocessServiceSet

request = MdPostprocessRequest.from_dict(payload)
result = MdPostprocessServiceSet.default(workspace_root=".").postprocess.postprocess(request)
```

## Typed band/DOS postprocess

Typed band 和 DOS 是实验性的 postprocess-only capability。它们要求调用方明确提供非空的 workspace-relative source path，不会运行 ABACUS，也不会隐式 collect 上游 operation。band 请求示例：

```json
{
  "schema_version": "forge.request/v1",
  "capability": "band",
  "operation": "postprocess",
  "operation_id": "123e4567-e89b-42d3-a456-426614174100",
  "workspace_rel": "runs/Si_band",
  "source_paths_rel": ["inputs/BANDS_1.dat"],
  "output_dir_rel": "outputs/postprocess",
  "plot_emin": -10.0,
  "plot_emax": 10.0,
  "save_data": true,
  "save_plot": true
}
```

```bash
PYTHONPATH=src python -m abacus_forge.cli operation postprocess --request band-request.json
```

DOS 请求使用 `capability="dos"` 和 `dos_paths_rel`，并可选提供 `pdos_path_rel`/`tdos_path_rel`；其他选择项包括 `include_tdos`、`include_pdos`、`pdos_mode` 和 `pdos_atom_indices`。下方给出 DOS+PDOS 读取的真实请求形态，完整 schema 仍以 `schema dos postprocess` 为准。解析成功不等于科学验收；postprocess facts 和 artifacts 作为一次 operation 记录。

```json
{
  "schema_version": "forge.request/v1",
  "capability": "dos",
  "operation": "postprocess",
  "operation_id": "123e4567-e89b-42d3-a456-426614174101",
  "workspace_rel": "runs/FeO_dos",
  "dos_paths_rel": ["inputs/DOS1_smearing.dat"],
  "pdos_path_rel": null,
  "tdos_path_rel": null,
  "output_dir_rel": "outputs/postprocess",
  "include_tdos": true,
  "include_pdos": true,
  "pdos_mode": "species",
  "pdos_atom_indices": [],
  "plot_emin": -10.0,
  "plot_emax": 10.0,
  "save_data": true,
  "save_plot": true,
  "suffix": null
}
```

```bash
cat band-request.json | PYTHONPATH=src python -m abacus_forge.cli operation postprocess --stdin
cat dos-request.json | PYTHONPATH=src python -m abacus_forge.cli operation postprocess --stdin
```

Python API 与 CLI 使用相同 typed service 和 request record：

```python
from abacus_forge import BandPostprocessRequest, PostprocessServiceSet

request = BandPostprocessRequest.from_dict(band_payload)
result = PostprocessServiceSet.default(workspace_root=".").band.postprocess(request)
```

## Typed COHP postprocess

Typed `cohp` 是实验性的 postprocess-only capability。W1 只实现 `method="iao"`，要求调用方显式提供已完成 LCAO SCF 的 workspace-relative 目录；Forge 不准备输入、不执行 ABACUS、不判断 SCF 复用，也不做科学验收。

这里的 COHP 是晶体轨道 Hamilton 布居分析，IAO 是从原 NAO 空间构造的轨道表示，
因此当前方法称为 **IAO-COHP**。直接 NAO-COHP 与 IAO-COHP 都可以读取 ABACUS
LCAO 的 H/S 和波函数；区别在轨道表示与键分解，不能仅凭输入文件相同判断方法等价。
当前 typed 接口不接受 `method="nao"` 或 `method="legacy"`，也不提供自动方法切换。
`cohp.meta.json` 中的 `method="IAO-COHP"` 标识结果方法；与外部结果比较前还需
核对单位、spin、单/双序、周期像、展宽与积分约定。

```json
{
  "schema_version": "forge.request/v1",
  "capability": "cohp",
  "operation": "postprocess",
  "operation_id": "123e4567-e89b-42d3-a456-426614174102",
  "workspace_rel": "runs/Si_cohp",
  "method": "iao",
  "scf_dir_rel": "scf",
  "out_dir_rel": null,
  "atom_i_index": 1,
  "atom_j_index": 2,
  "atom_i_orbs": "all",
  "atom_j_orbs": "all",
  "output_dir_rel": "outputs/cohp"
}
```

成功后固定生成 `outputs/cohp/cohp.meta.json`、`cohp_EminusEf.dat`、`cohp.png` 和 `cohp_bond_images.json`，并写入 postprocess report。请求/schema 可能随 W1 演进；最终字段以 `schema cohp postprocess` 为准。

```bash
PYTHONPATH=src python -m abacus_forge.cli operation postprocess --request cohp-request.json
```

## Typed PyATB band handoff

实验性的 typed `pyatb-band` capability 接收调用方已放入目标 workspace 的显式输入。它不会扫描上游 SCF workspace，也不会从日志推断 Fermi energy。其 `prepare`、`execute` 和 `collect` 是三个分开的 operation，与 legacy sequence helper 不同。

```json
{
  "schema_version": "forge.request/v1",
  "capability": "pyatb-band",
  "operation": "prepare",
  "operation_id": "123e4567-e89b-42d3-a456-426614174120",
  "workspace_rel": "runs/Si_pyatb_band",
  "structure_path_rel": "source/STRU",
  "hr_paths_rel": ["source/data-HR-sparse_SPIN0.csr"],
  "sr_path_rel": "source/data-SR-sparse_SPIN0.csr",
  "rr_path_rel": null,
  "fermi_energy": 4.25,
  "line_kpoints": [
    {"coords": [0.0, 0.0, 0.0], "label": "G"},
    {"coords": [0.5, 0.0, 0.0], "label": "X"}
  ],
  "nspin": 1,
  "line_segments": 20,
  "max_kpoint_num": 4000,
  "handoff_mode": "link"
}
```

`rr_path_rel` 可以省略或设为 `null`；只有调用方提供来源时 Forge 才生成 rR route。nspin 为 1 或 4 时各用一个 HR 文件，nspin 为 2 时用两个；三种模式均使用一个 SR 文件。operation 按 `handoff_mode` 链接 workspace 内来源或复制文件。收集读取所声明的输出路径，默认 band info 路径为 `inputs/Out/Band_Structure/band_info.dat`。结果 facts、manifest 和 process evidence 均不代表科学验收或稳定成熟度。

执行与收集是独立请求，调用方需要分别提交；两者不会隐式执行 prepare 或上游 SCF：

```json
{
  "schema_version": "forge.request/v1",
  "capability": "pyatb-band",
  "operation": "execute",
  "operation_id": "123e4567-e89b-42d3-a456-426614174121",
  "workspace_rel": "runs/Si_pyatb_band",
  "executable": "pyatb",
  "mpi_ranks": 1,
  "omp_threads": 1,
  "timeout_seconds": null,
  "dry_run": false
}
```

```json
{
  "schema_version": "forge.request/v1",
  "capability": "pyatb-band",
  "operation": "collect",
  "operation_id": "123e4567-e89b-42d3-a456-426614174122",
  "workspace_rel": "runs/Si_pyatb_band",
  "band_info_path_rel": "inputs/Out/Band_Structure/band_info.dat",
  "band_data_paths_rel": ["inputs/Out/Band_Structure/band.dat"],
  "band_picture_paths_rel": ["inputs/Out/Band_Structure/band.png"]
}
```

三个 operation 可分别使用 `operation prepare|execute|collect --request FILE` 或 `--stdin`。Python API 使用同一 service：

```python
from abacus_forge import PyatbBandPrepareRequest, PyatbBandServiceSet

services = PyatbBandServiceSet.default(workspace_root=".")
result = services.prepare.prepare(PyatbBandPrepareRequest.from_dict(prepare_payload))
```

Legacy PyATB primitive 仍可直接调用 `prepare_pyatb_band(...)`、`run_pyatb(...)` 和 `collect_pyatb(...)`；sequence helper 也保留自动 SCF discovery。

## Typed export

Typed export 是实验性能力。它序列化调用方显式引用的、来自同一个 workspace 的历史 operation outcome；不会选择 latest、复制二进制 artifact，或调用 collect/postprocess。引用列表不能为空，且所有引用必须属于同一个已记录的 source operation。

```json
{
  "schema_version": "forge.request/v1",
  "capability": "export",
  "operation": "export",
  "operation_id": "123e4567-e89b-42d3-a456-426614174130",
  "workspace_rel": ".",
  "source_artifact_refs": [
    {"operation_id": "123e4567-e89b-42d3-a456-426614174131", "artifact_id": "energy"}
  ],
  "destination_path_rel": "exports/scf-result.json",
  "format": "json",
  "pretty": true,
  "overwrite_policy": "fail"
}
```

```bash
PYTHONPATH=src python -m abacus_forge.cli operation export --request export-request.json
cat export-request.json | PYTHONPATH=src python -m abacus_forge.cli operation export --stdin
```

该 typed capability 当前仅支持 JSON 和 `overwrite_policy="fail"`。Python API 使用同一 service：

```python
from abacus_forge import ExportRequest, ExportServiceSet

request = ExportRequest.from_dict(payload)
result = ExportServiceSet.default(workspace_root=".").export.export(request)
```

legacy `api.export()` 与顶层 `abacus-forge export` 继续保留原有行为，是独立的调用入口。

## Python API

Python 库还提供低层结构/数据 helper 以及兼容的 task/pack 函数。下面集中展示 primitive、unit、task、sequence 与 property API 的真实调用形式。Typed request 可直接构造，也可调用 `from_dict`；相应 service set 需要显式指定 workspace root。依赖 request 字段或持久化结果语义前，请查阅[typed 请求与状态参考](reference.md#machine-request-and-status-protocol)。

### Primitive 与单元 API

下面示例展示从 primitive 准备输入、逐文件修改并收集结果，以及用 `UnitSpec` 对 band 的 SCF unit 执行 prepare/modify/execute/collect。输入结构和 ABACUS 资源文件需由调用方提供；示例中的 `Si.cif`、`NiO.STRU` 是用户输入路径：

```python
from abacus_forge.api import (
    UnitModifySpec, UnitSpec, collect, collect_unit, execute_unit,
    modify_unit, prepare, prepare_unit,
)
from abacus_forge.cube import CubeData, subtract_cubes
from abacus_forge.modify import modify_input, modify_kpt, modify_stru

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

charge_difference = subtract_cubes("runs/Fe/charge-a.cube", "runs/Fe/charge-b.cube")
charge_difference.write("runs/Fe/charge-difference.cube")

prepared = prepare_unit(UnitSpec(
    task="band", unit="scf", workdir="runs/NiO_band_scf",
    structure="NiO.STRU", structure_format="stru",
))
modified = modify_unit(UnitModifySpec(
    task="band", unit="scf", workdir=prepared.workspace.root,
    input_updates={"scf_thr": "1e-8"},
))
executed = execute_unit(UnitSpec(
    task="band", unit="scf", workdir=prepared.workspace.root,
    executable="abacus",
))
collected = collect_unit(UnitSpec(
    task="band", unit="scf", workdir=prepared.workspace.root,
))
```

### Task、sequence 與 property API

以下兼容 API 保留了 task 闭环、band/DOS 本地 sequence 和 property pack 的 Python 调用方式。`backend="pyatb"` 会使用既有 sequence helper，自动从 ABACUS LCAO SCF workspace 发现其输入；这不同于上文要求显式 workspace-relative 输入的 typed `pyatb-band` capability。

```python
from abacus_forge.composite import (
    post_convergence, post_workfunc, prepare_convergence, prepare_workfunc,
)
from abacus_forge.tasks import (
    run_band_sequence, run_dos, run_dos_sequence, run_scf,
)

task_result = run_scf("runs/Si_task", structure="Si.cif", executable="abacus")
dos_result = run_dos("runs/FeO_dos", structure="FeO.cif", executable="abacus")
print(task_result.status, dos_result.metrics.get("dos_family_summary"))

band_sequence = run_band_sequence(
    "runs/Si_band_sequence", structure="Si.cif", executable="abacus",
    backend="nscf",
    line_kpoints=[
        {"coords": [0, 0, 0], "npoints": 20, "label": "Gamma"},
        {"coords": [0.5, 0, 0], "npoints": 1, "label": "X"},
    ],
)
pyatb_band_sequence = run_band_sequence(
    "runs/NiO_band_pyatb", structure="NiO.STRU", executable="abacus",
    pyatb_executable="pyatb", backend="pyatb",
    parameters={"basis_type": "lcao"},
    line_kpoints=[
        {"coords": [0, 0, 0], "npoints": 20, "label": "Gamma"},
        {"coords": [0.5, 0, 0], "npoints": 1, "label": "X"},
    ],
)
dos_sequence = run_dos_sequence(
    "runs/FeO_dos_sequence", structure="FeO.cif", executable="abacus",
)

conv_plan = prepare_convergence("runs/Si_scf", key="ecutwfc", values=["60", "80"])
conv_result = post_convergence("runs/Si_scf", key="ecutwfc")
workfunc_plan = prepare_workfunc("runs/slab", vacuum_axis="c", dipole_correction=True)
workfunc_result = post_workfunc("runs/slab", vacuum_axis="c")
```

`LocalRunner` 在 `inputs/` 目录启动 ABACUS，不默认注入 `--input-dir` 等非 ABACUS 参数。PyATB 不是必装依赖；缺少 `pyatb` executable 或 ABACUS LCAO matrix files 时，PyATB collect/sequence 会返回 diagnostics。`CubeData` 及 `subtract_cubes` 等 helper 也可通过 `abacus_forge.cube` 使用；上方第一段 import 展示了其调用入口。


<a id="direct-nao-cohp"></a>
## 直接 NAO-COHP（experimental）

`pyatb-cohp` 消费已有 ABACUS NAO 矩阵，与 `cohp` 的 IAO 后处理分别发现。
调用方先将 STRU、HR、SR 和 STRU 中列出的所有数值轨道文件放入同一 workspace。
以下 prepare JSON 中的文件名、Fermi energy、原子/轨道选择、能量范围和 k 点需要
替换成当前任务的实际值；这些示例参数不构成收敛设置。

```json
{
  "schema_version": "forge.request/v1",
  "capability": "pyatb-cohp",
  "operation": "prepare",
  "operation_id": "ee80c710-65a3-4a30-8546-439de756d911",
  "workspace_rel": ".",
  "structure_path_rel": "source/STRU",
  "hr_paths_rel": ["source/hrs1_nao.csr"],
  "sr_path_rel": "source/sr_nao.csr",
  "orbital_paths_rel": ["source/Si_gga_7au_100Ry_2s2p1d.orb"],
  "fermi_energy": 6.793680865,
  "atom_i_index": 1,
  "atom_j_index": 2,
  "kpoints": [[0, 0, 0], [0.5, 0, 0]],
  "kpoint_weights": [1, 1],
  "e_range": [-15, 25]
}
```

在 workspace 根目录执行 `abacus-forge operation prepare --request prepare.json`。
prepare 复制输入到新的 `inputs/` 目标，并生成 PyATB `Input`。
`nspin=2` 时显式提供 up/down 两个 HR；不支持 nspin=4。
轨道文件 basename 必须与 STRU 的 NUMERICAL_ORBITAL 一一对应。
HR 为 Ry；Fermi energy 和 `e_range` 为绝对 eV；k 点为分数倒易坐标，权重由 PyATB 归一化。

另建 execute JSON，保留 schema_version/capability/workspace_rel，使用新的 UUID，
设 `operation="execute"`，可指定 `executable` 和 `timeout_seconds`；
以 `abacus-forge operation execute --request execute.json` 启动一个 PyATB 进程。
执行前要求 `inputs/Out` 与本次 stdout/stderr 目标不存在，防止引擎覆盖已有输出。
这要求安装支持 COHP 元数据的 PyATB 候选；Forge 不自动安装引擎。
当前验证基线是 `QuantumMisaka/pyatb:sidereus-adam@18c9ff6`（含 PR #1 的 STRU
parser fix）。含 `O` 这类单字母 uppercase atom label 时必须使用该 commit 或等价
修复；旧 candidate 会在 orbital selection 阶段丢失 O atoms。

collect JSON 同样使用新的 UUID 和 `operation="collect"`，调用
`abacus-forge operation collect --request collect.json`。
默认收集 `inputs/Out/COHP/COHP.dat` 和 `COHP.meta.json`，也可显式指定
`spectrum_path_rel`/`metadata_path_rel`。缺失、格式错误或 metadata/spectrum 引用不一致
不能得到 complete；collect 还要求 PyATB pair convention/factor 与轨道集合一致：
identical selection 为 1，disjoint selection 为 2，部分重叠 fail-closed。科学状态
始终为 unassessed。正常结果含谱 artifact 和 `icohp_raw`/`icohp`（eV）reported
metrics，符号、权重与积分约定见 metadata。

通过 `abacus-forge capabilities` 查询 `contracts`，可区分 IAO 与 direct_nao；
完整字段通过 `abacus-forge schema pyatb-cohp prepare` 查询。

<a id="polarization-and-bec"></a>
## 原生极化事实与 BEC（experimental）

`polarization/collect` 收集一个显式 Berry-phase 日志及对应 INPUT/STRU，
`bec/postprocess` 消费这些事实文件，计算调用方请求的原子/位移方向列。
它们与 legacy `bec prepare|run|post` 分开；后者不会自动获得新的解析和分支逻辑。

准备一个位移、一个 gdir 的 NSCF 输入可复用
[`examples/polarization_stage.py`](../examples/polarization_stage.py) 的 `prepare_stage`。
它使用现有 `modify_stru` 和通用 `prepare`，明确写入 `calculation=nscf`、
`berry_phase=1`、`symmetry=-1`、`init_chg=file` 和 gdir。示例不启动计算：
调用方须先完成**相同位移结构的 SCF**，并将相应电荷文件放到 NSCF 所需位置，
同时提供相容的 PP/ORB 和经过选择的 k 网格。随后可独立调用通用
`execute(workspace, runner=LocalRunner(...))` 或 `abacus-forge execute workspace`；
这只启动一个进程。不能把此 NSCF 阶段交给要求 SCF 输入的 typed `scf/execute`。

已有输出后，在包含所有阶段目录的 workspace 根目录调用 collect。例如：

```json
{
  "schema_version": "forge.request/v1",
  "capability": "polarization",
  "operation": "collect",
  "operation_id": "4c3d172a-86f0-4ba8-9037-53d5f334c2b0",
  "workspace_rel": ".",
  "log_path_rel": "stages/plus-g1/inputs/OUT.ABACUS/running_nscf.log",
  "structure_path_rel": "stages/plus-g1/inputs/STRU",
  "input_path_rel": "stages/plus-g1/inputs/INPUT",
  "output_path_rel": "facts/plus-g1.json"
}
```

`abacus-forge operation collect --request collect.json` 输出标准 JSON envelope，
并写入带来源的 `forge.polarization/v1` artifact。每个阶段使用新的 operation UUID
和输出路径；文件必须处于同一 workspace，已有目标不会覆盖。解析保留三个单位行、
浮点模量与 gdir；gdir 是晶格方向，不是笛卡尔轴。

下面是只请求第一个原子 x 位移响应列的 BEC 请求形状。所有路径必须替换为
前述 collect 的实际事实文件。示例位移和变化上界仅展示格式，不是收敛推荐值。

```json
{
  "schema_version": "forge.request/v1",
  "capability": "bec",
  "operation": "postprocess",
  "operation_id": "d04ac202-65fd-4659-b9ca-5fdb1d7720d5",
  "workspace_rel": ".",
  "branch_mode": "auto",
  "max_step_fraction": 0.25,
  "columns": [{
    "atom_index": 1,
    "direction": "x",
    "samples": [
      {"displacement_angstrom": -0.01, "polarization_paths_rel": ["facts/minus-g1.json", "facts/minus-g2.json", "facts/minus-g3.json"]},
      {"displacement_angstrom": 0.0, "polarization_paths_rel": ["facts/zero-g1.json", "facts/zero-g2.json", "facts/zero-g3.json"]},
      {"displacement_angstrom": 0.01, "polarization_paths_rel": ["facts/plus-g1.json", "facts/plus-g2.json", "facts/plus-g3.json"]}
    ]
  }],
  "output_path_rel": "outputs/bec.json"
}
```

运行 `abacus-forge operation postprocess --request bec.json`。
自动模式的 `max_step_fraction` 必须介于 0 和 0.5 之间，含义是调用方对
**真实相邻极化变化**的可信上界（以该 gdir 量子为单位）。程序不会从小的折叠差值
推断这个条件已成立。路径须含零位移及对称 ±delta，可显式增加中间点；近边界、
缺参考或不满足界限时返回歧义。算法从零参考分别向两侧解缠，保留 offset 轨迹。

使用 `branch_mode="explicit"` 时，每个 sample 增加
`"branch_offsets": {"1": 0, "2": 0, "3": 0}`，数值应为调用方实际指定的整数，
不能照抄零值来假设无需修正；此模式不要求 max_step_fraction 或零位移参考。
两种模式都核验固定晶胞、原子/资源/设置一致性及声明位移，先合成三个 gdir 的
笛卡尔贡献再差分。输出张量单位为 e。

`requested_complete` 表示本次请求的列全部得到结果；`full_tensor_complete`
还要求结构内全部原子的 x/y/z 列。缺列保留 null，独立有效列仍可返回；
缺文件、缺方向或分支歧义会阻止本次请求被标成完整。科学状态始终 unassessed。
除源格式合成测试外，安装态已跑通真实 MgO 的 O_x 单列、半幅位移与一次 K 网格
加密对照，见[真实验证记录](superpowers/evidence/2026-10-21-forge-installed-bec-validation.md)。
该结果不代表完整张量、声学求和规则或全面收敛。请求中的 atom_index 以实际采集的
STRU/fact 原子顺序为准；prepare 可能重排输入的 species 顺序。
