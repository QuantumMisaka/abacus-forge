# ABACUS-Forge（算筹工场）

> 开发入口、开发边界与约束请优先阅读 [AGENTS.md](./AGENTS.md)。项目规划与路线图已拆分到 [ROADMAP.md](./ROADMAP.md)。

**一句话定位：**`ABACUS-Forge` 是面向本机/HPC 环境的轻量级 ABACUS 快捷消费基座，提供 `prepare -> modify -> execute -> collect -> export` 原语，`scf / relax / cell-relax / md / band / dos` 单任务 CLI 闭环，`eos / elastic / vibration / phonon` 本地 composite task pack，以及实验性 `convergence / cube / workfunc / vacancy / bec` 等 property pack，可作为 Python 库或 CLI 使用，同时服务人类研发者和 AI Agent（Codex、OpenCode，以及作为 ADAM-ABACUS 的 Paimon）。其中 typed `md` 仍为实验性能力；`run` 仍作为 `execute` 的兼容别名保留。

## 当前定位

- 面向单个工作目录的输入准备、输入编辑、程序拉起与结果收集。
- 保持轻量边界：不处理 Slurm/Bohrium/DPDispatcher 等调度与平台编排。
- 作为协议与平台无关的 ABACUS 单元操作基座，同时服务人类研发者和 AI Agent（Codex、OpenCode，以及作为 ADAM-ABACUS 的 Paimon）；其他 workflow/agent 通过同一契约消费并自行完成科学判断。
- CLI 提供参数显式、结果结构化的非交互机器路径；可选 TUI 可以基于 Python API 或结构化 CLI envelope 套壳，提供 VASPKIT/AbacusCopilot 风格的人类导航，但 TUI 和数字 Task-ID 不定义核心能力协议。

## 成熟度与文档入口

本 README 描述当前可用实现，不把所有现有 Python API 都承诺为 Paimon v1.3 的最终后端协议。Forge 正在以契约优先方式收敛请求、workspace、结果和 artifact 语义；在此期间，稳定使用应优先采用本文列出的显式 CLI 与核心基元，实验性能力见下文明确标记。

workspace 中的 `meta.json`、`forge-unit.json` 和 `forge-result.json` 是现有兼容文件，继续按既有格式写出；它们不会被 v1 记录替换。需要机器读取操作历史或跨操作 artifact 引用时，应读取新增的 `reports/forge-workspace.json` 及其 `reports/events/*.json` 记录。当前 v1 workspace manifest 的 schema version 是 `forge.workspace/v1`，typed operation event payload 使用 `forge.operation-outcome/v1`，并嵌入未改变的 `forge.result/v1` envelope；`ArtifactRecord.path_rel` 始终指向 workspace 内的相对路径。该记录层是追加式兼容扩展，不改变现有 CLI 命令示例或旧文件消费者。

- 科研用户与调用者：阅读本文、[ROADMAP.md](./ROADMAP.md) 和 CLI `--help`，按成熟度选择能力。
- 人类与 AI 开发者：先阅读 [AGENTS.md](./AGENTS.md)；其中定义边界、测试和开发路由。
- 架构与 Paimon v1.3 迁移规范：先阅读 [契约优先重构 SPEC](./docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html)，再阅读其 [Service/Status 细化 SPEC](./docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html)。
- 实施前的文档先行流程：阅读 [开发治理入口](./docs/superpowers/README.md)。

## 当前已实现能力

### 输入准备

- `prepare(...)` / `abacus-forge prepare`
- 支持从结构文件生成 `INPUT` / `STRU` / `KPT`
- ABACUS task profile 默认显式写入 `dft_functional=pbe`；调用方可通过参数覆盖该默认
- 支持参数覆盖、参数删除、K 点设置、PP/ORB 路径、`copy/link` 资产模式
- 支持简单的按元素共线磁矩初始化

STRU 归一化保留已有赝势/轨道引用和质量，写出 ABACUS 原生 Bohr 晶格单位；旧
Forge 的 Angstrom 单位扩展仍可读取。支持 `Direct`、`Cartesian`、
`Cartesian_angstrom`、`Cartesian_au`；居中坐标模式和未知模式会明确报错。
周期真空识别使用分数坐标周期间隙和晶格面间距，支持跨周期边界的薄层与斜晶胞。
原胞/常规胞转换保留各元素的资源引用，以及同一元素内一致的质量和共线磁矩；
同元素原子的质量或磁矩不同、或带移动约束时，当前标准化会明确拒绝，避免静默丢失信息。

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

### Typed operation service boundary

`ScfServiceSet`、`RelaxServiceSet` 与 `MdServiceSet` 提供 typed SCF、relax、cell-relax 和
MD 路径，交付
execution/collection 事实与 observations；若兼容结果保留 `scientific` 字段，Forge
只写 `unassessed`，不在 Forge 内作科学判定。`ScfExecuteRequest(dry_run=True)` 或
对应的 `RelaxExecuteRequest(dry_run=True)` 才能产生
`execution=skipped`；typed execute 不会根据已有日志（包括 `NORMAL END`）推断跳过，
并且实际执行直接调用本地 runner。底层 `run_many(..., skip_completed=True)` 仍保留
给现有 composite 兼容调用，但属于 legacy helper，不是 typed service 的状态协议。
SCF/Relax collection 将已解析的数组指标和有效结构快照作为事实 observations。
SCF 收集完整性由非空输出日志、有限总能量和解析情况决定，Relax 还要求有效的
最终结构；收敛标志独立返回。typed collect 只读取 workspace 内的领域文件，
审计事件、claims、锁和 workspace manifest 不进入计算产物列表。

`BandPostprocessRequest` 与 `DosPostprocessRequest` 提供独立的 typed band/DOS
`postprocess` service。它们的成熟度为 `experimental`，要求调用方显式声明一个非空的
workspace-relative source path 列表；不会隐式执行 `collect`、`export` 或上游 operation。
纯进程内解析不声明执行事实：成功、部分解析和 parser failure 的
`execution` 均为 `not_run`，`collection` 反映 `complete`、`partial` 或
`missing_output`，`scientific` 始终为 `unassessed`。结果只交付 parser facts、相对
artifact（input/output、sha256、size）和一个追加式 operation event。这里的 typed
postprocess 与下文已有的 `run_band`、`run_dos`、`run_band_sequence`、
`run_dos_sequence` 以及 `abacus-forge band|dos` legacy task/sequence API 是不同边界；
后者继续保持原有 task/sequence 语义，不被隐式改写为 typed service。

`PyatbBandPrepareRequest`、`PyatbBandExecuteRequest` 与
`PyatbBandCollectRequest` 提供独立的实验性 `pyatb-band` capability。它只暴露
`prepare`、`execute`、`collect` 三个 operation：prepare 接收调用方已经放入同一
workspace 的显式 `STRU`、HR、SR、rR 文件、Fermi 能量和 line-mode K 点；默认以
workspace 内的相对链接完成 handoff，`handoff_mode="copy"` 可改为独立复制。绝对路径、
跨 workspace 来源、隐式 SCF 目录扫描和从日志推导 Fermi 能量均不属于 typed 面。

准备会生成 `inputs/STRU`、`inputs/pyatb_sources/<basename>`、`inputs/Input` 和
`inputs/KPT_band`，并在结果 diagnostics/manifest 中记录角色、来源与目标相对路径及
SHA-256。`nspin` 当前只支持 1 或 2；spin-2 需要两个 HR 文件，共用一个 SR 文件，
并且其他 PyATB property 与 nspin 4 尚未进入此 capability。执行只通过本地 runner
启动一个 PyATB 进程；收集读取默认的
`inputs/Out/Band_Structure/band_info.dat`，也可显式列出 band data/picture 路径，返回
artifact、运行时和 parser facts。可解析的 `band_gap` 只是 `reported` metric，
`scientific` 永远为 `unassessed`，不表示科学接受结论。

该 typed 面与下文保留的 `prepare_pyatb_band(...)`、`run_pyatb(...)`、
`collect_pyatb(...)` 及 `run_band_sequence(..., backend="pyatb")` legacy helper
分开；后者继续保留自动 SCF discovery 和原有兼容行为。

该阶段的 typed service 已通过下方 Agent-first CLI 的 machine surface 暴露；当前
`app-tools` 中的 Paimon v1.2 仍是既有发布面，不在 Forge 中复制。
typed service 与旧 API 共用 `preparation.py`、`collection.py` 和 INPUT 编辑基元；
路径、错误及事件持久化由 `service_support.py` 提供通用支持。旧 API 保留原有
task/sequence 分发与兼容记录，不再是 typed service 的底层依赖。

typed prepare 可通过 `pseudo_sources` 与 `orbital_sources` 显式提供按元素映射，
并以 `asset_mode=copy|link` 控制搬运方式。相对来源路径按 operation workspace 根目录
解析，绝对路径也可作为显式来源；默认 `copy`，`link` 仅允许 workspace 内来源并写入
相对链接。缺失来源、后缀或 basename 冲突、以及不安全或不允许的链接均 fail-closed，
不会留下部分资产；结果 diagnostics、`forge-unit.json`（仅显式映射）和事件记录包含
来源/目标及 SHA-256 provenance。映射只对列出的元素生效，未映射的 STRU 引用保留，
但 Forge 不声明资产集合因此完整。

legacy `prepare(...)` 仍保留原有 `pseudo_path` / `orbital_path` 目录推断，默认使用
`link`；需要该兼容行为时继续使用 legacy API。

## Agent-first CLI

Stage 3 的 machine surface 以及 Stage 4 首批现已提供 `scf`、`relax`、`cell-relax` 和
成熟度为 `experimental` 的 `md`、`atst-neb`、`pyatb-band`；typed `band`/`dos` 另提供仅用于
`postprocess` 的实验性 capability。它固定暴露三个顶层命令：`operation`
（`scf`、`relax`、`cell-relax`、`md` 执行 `prepare`、`modify`、`execute`、`collect`；`atst-neb` 执行 `prepare`、
`execute`、`postprocess`；`pyatb-band` 执行 `prepare`、`execute`、`collect`；`band`、`dos` 执行 `postprocess`）、`schema`（读取请求 schema）和
`capabilities`（读取能力发现）。兼容保留的顶层 `--help` 不列出这三个命令；请分别
运行 `operation --help`、`schema --help` 和 `capabilities --help` 查看机器接口。

没有 capability 的 `postprocess` 以及 `export` 仍返回 `request.invalid`；typed
band/DOS 请求必须分别声明 `capability="band"`/`"dos"`。legacy CLI 的默认输出和入口
保持不变。

请求可以来自文件：

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

也可以从 stdin 传入请求：

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

`capabilities` 和 `schema <capability> <operation>` 返回确定性的 JSON 文档；当前发现的
capability 为 `scf`、`relax`、`cell-relax`、`atst-neb`、`md`、`pyatb-band`、`band`、`dos`；`md` 仅支持
`prepare`、`modify`、`execute`、`collect`，且 maturity 为 `experimental`；其他 capability
按各自 descriptor 暴露 operation，`band`/`dos` 仅暴露 `postprocess` 且 maturity 为
`experimental`，`pyatb-band` 仅暴露 `prepare`、`execute`、`collect` 且 maturity 为
`experimental`。默认格式下，
`operation` 在 stdout 输出恰好一个完整的 JSON outcome/error envelope，其中包含错误消息与
结果 diagnostics；stderr 仅保留给受控诊断，当前覆盖路径为空。退出码分别为
`0`（无执行失败）、
`2`（请求或路径错误）、`3`（前置条件缺失）、`4`（进程已启动但执行失败）和 `5`（持久化
或内部错误）。`--pretty` 只改变 JSON 空白，`--format text` 是同一 envelope 的文字
投影。

相对路径均以调用进程的当前工作目录（cwd）为 workspace root；CLI 不提示、不猜测科学
结论，也不负责多操作编排、重试、调度或平台提交。科学判断、workflow/orchestration
和 scheduling 由调用方负责。

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

### 实验性 ATST-NEB machine API

机器调用可使用 `abacus-forge operation <prepare|execute|postprocess> --request FILE`
或 `--stdin`，并在请求中声明 `"capability": "atst-neb"`。也可用
`abacus-forge capabilities` 和 `abacus-forge schema atst-neb <operation>` 查询契约。
该 capability 通过外部 `atst` 可执行文件调用 `atst neb make`、`atst run` 和
`atst neb summary/post`；Forge 本身不要求安装或导入 `atst-tools` Python 包。
NEB 图像/链路编排与并行执行由 atst-tools 负责；外层任务调度、重试以及科学结果判定由调用方负责，
Forge 只忠实执行单个 prepare/execute/postprocess 操作并返回结构化 envelope。ATST 后端和模型
（包括 DeePMD）由 atst-tools 与调用方配置；Forge 不选择、安装、配置或科学评估这些后端。

### 本地 composite task pack

- `abacus-forge eos prepare|run|post`
- `abacus-forge elastic prepare|run|post`
- `abacus-forge vibration prepare|run|post`
- `abacus-forge phonon prepare|run|post`
- composite pack 只管理本地子目录和本地 runner；不生成 Slurm/Bohrium/DPDispatcher 配置
- `phonon` 的 phonopy 能力是可选依赖：`pip install "abacus-forge[phonon]"`

### 本地 property pack

> **成熟度：实验性。** 以下能力已具备 API/CLI 和 mock/fixture 回归，但尚未逐项完成真实 ABACUS 操作/解析验收；不应视为 PAIMON v1.3 已稳定暴露的能力。

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

## Typed band/DOS postprocess（experimental）

Band 和 DOS 请求都必须携带 `schema_version`、合法的 lowercase UUIDv4
`operation_id`、`workspace_rel` 和 `operation="postprocess"`。source 只能写成该
workspace 内的显式相对路径；Band 的 `source_paths_rel`、DOS 的 `dos_paths_rel` 都必须
非空。以下是可直接交给 machine CLI 的完整请求示例：

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

将上述 JSON 分别保存为 `band-request.json` 或 `dos-request.json` 后，可通过 stdin
执行单个 operation：

```bash
cat band-request.json | PYTHONPATH=src python -m abacus_forge.cli operation postprocess --stdin
cat dos-request.json | PYTHONPATH=src python -m abacus_forge.cli operation postprocess --stdin
```

Python API 使用同一 typed service 集合和请求记录：

```python
from abacus_forge import BandPostprocessRequest, PostprocessServiceSet

request = BandPostprocessRequest.from_dict(band_payload)
result = PostprocessServiceSet.default(workspace_root=".").band.postprocess(request)
```

直接 service 调用和上述 subprocess CLI 返回等价的 typed envelope facts（只需对不同
operation-id 与隔离 workspace root 做 parity normalization）。每次成功或 admitted
parser outcome 只追加一个 `reports/events/<operation_id>-postprocess.json`；每个 admitted
`OperationOutcome` 固定写入 `reports/postprocess/<operation_id>.json`，request 或
precondition 错误不写该 report。生成文件和 OperationOutcome report 都是
workspace-relative output artifact，source 是 input artifact。结果不泄露绝对路径，不生成
band gap、acceptance 或其它科学判断；缺失 source、路径碰撞和审计保留路径会按既有
request/precondition/error 语义返回。

## Typed PyATB band handoff（experimental）

typed `pyatb-band` 请求使用与其他 machine operation 相同的
`forge.request/v1` envelope。所有 `*_path_rel` 都相对于请求的目标 workspace；调用方应先
把上游产物 materialize 到该 workspace，再调用 Forge。下面的 prepare 请求只声明一个
最小的 spin-1 handoff：

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
  "rr_path_rel": "source/data-rR-sparse.csr",
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

执行和收集仍是两个独立 operation，不依赖数字 Task-ID，也不隐式执行 prepare 或
上游 SCF：

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

保存后可分别通过 `operation prepare|execute|collect --request FILE`（或 `--stdin`）
调用；Python API 使用同一 service：

```python
from abacus_forge import (
    PyatbBandPrepareRequest,
    PyatbBandServiceSet,
)

services = PyatbBandServiceSet.default(workspace_root=".")
result = services.prepare.prepare(PyatbBandPrepareRequest.from_dict(prepare_payload))
```

该 capability 仅在离线 fixture/mock 与 API/CLI parity 范围内保持
`experimental`；本仓库不以此文档声称真实 PyATB/ABACUS smoke、科学验证或稳定晋级。

成功的 typed `prepare` 与 `collect` 结果会在同一 `forge.result/v1` envelope 的
`diagnostics.pyatb_manifest` 中提供稳定文件语义。每个 present entry 的 `artifact_id`
都指向同一 envelope 的 artifact；`kind`/`spin` 使用有限枚举。malformed 但真实可读的
文件仍是 output artifact，不可访问、越界或缺失的文件进入 `missing` 并带原因。manifest
不自动扫描目录、不提供 export，也不做科学验证；任务编排、平台调度和科学结论由调用方负责。

```json
{"schema_version":"forge.pyatb-manifest/v1","inputs":[],"outputs":[],"missing":[]}
```

## Typed Relax operations

`RelaxPrepareRequest`、`RelaxModifyRequest`、`RelaxExecuteRequest` 和
`RelaxCollectRequest` 是带显式 `capability` 的四个 typed 请求。`capability` 只能是
`relax` 或 `cell-relax`；它决定对应 ABACUS `calculation` profile，但不会隐式串联
多个 operation。每次 machine CLI 调用只执行一个请求，调用方负责在阶段之间传递
workspace。

```python
from abacus_forge import RelaxPrepareRequest

request = RelaxPrepareRequest(
    operation_id="123e4567-e89b-42d3-a456-426614174012",
    workspace_rel="runs/Si_relax",
    capability="relax",
    structure_path_rel="source.STRU",
    parameters={"calculation": "relax", "ecutwfc": 70},
)
```

四个 operation 的边界和输出事实如下：

| operation | typed request | phase boundary and factual result |
| --- | --- | --- |
| `prepare` | `RelaxPrepareRequest` | 将结构和参数写入一个 `relax`/`cell-relax` workspace；返回输入与 provenance artifact。 |
| `modify` | `RelaxModifyRequest` | 只编辑已准备 workspace 的 `INPUT` 参数；返回修改前后 snapshot。 |
| `execute` | `RelaxExecuteRequest` | 只拉起一次本地 ABACUS process；返回 execution、returncode、runtime log artifact。 |
| `collect` | `RelaxCollectRequest` | 只解析现有输出；返回能量、可用力/应力/relax 指标、电子收敛观察，以及 workspace-relative 最终结构 artifact。 |

Machine 请求必须带显式 capability，例如：

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

将上述 JSON 作为 `request.json` 后执行单个 machine operation：

```bash
PYTHONPATH=src python -m abacus_forge.cli operation execute --request request.json
```

Relax discovery 和 schema 当前保持 `experimental`；只有 mock/fixture 与离线
machine/API parity 已验证。可选的 `real_smoke` 会在复制的用户准备 workspace 上验证
execute/collect 的序列化 outcome、事件和 artifact，但不作物理收敛判断；没有真实证据
时不应提升 maturity。`collect` 的 `scientific` 始终为 `unassessed`，缺少输出或解析
不完整只反映 collection 状态。

typed MD 首批已提供实验性的四个 typed operation，但只覆盖输入准备、修改、一次本地执行
和事实收集；本批次不提供 MD 专用 trajectory 转换、monitor、restart/resume 或独立
`postprocess`/`export`。上文的 typed band/DOS postprocess 和 typed `pyatb-band` handoff
都是独立的实验性能力，不扩展为 MD 或其它 task 的隐式后处理；typed `export`、PyATB
properties 和更多真实 property-pack smoke 仍待后续交付。监控、workflow 编排、
恢复/重试、调度和科学判断由 Forge 外部的人类或 Agent 负责；Stage 5 的 legacy 依赖
解除与稳定发布门禁也尚未完成。

## Typed MD operations

`MdPrepareRequest`、`MdModifyRequest`、`MdExecuteRequest` 和 `MdCollectRequest` 提供
实验性的 `md` capability。它们只支持 typed `prepare`、`modify`、`execute`、`collect`，
沿用通用请求字段；MD 专属控制项继续放在 JSON-safe 的 `parameters` map 中，例如：

```python
from abacus_forge import MdPrepareRequest

request = MdPrepareRequest(
    operation_id="123e4567-e89b-42d3-a456-426614174014",
    workspace_rel="runs/Si_md",
    capability="md",
    structure_path_rel="source.STRU",
    parameters={
        "md_type": "nve",
        "md_nstep": 100,
        "md_dt": 1.0,
        "md_tfirst": 300,
        "md_tlast": 300,
        "md_dumpfreq": 1,
    },
)
```

默认 profile 使用 PBE 与 NVE；调用方或 Agent 负责选择和覆盖物理参数。`collect` 只在
可用时返回 `MD_dump` 与日志中的解析事实、指标和 artifact 引用，不判断轨迹或物理结果
是否可接受。本批次不包含 MD 专用 trajectory 转换或独立 `postprocess`/`export`；后者
仍可在后续 Forge operation 批次交付。monitor、workflow 编排、restart/resume、调度以及
科学判断由 Forge 外部的人类或 Agent 负责。

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
    forge-workspace.json
    events/
      <event-id>-<operation>.json
    postprocess/
      <operation-id>.json
```

`reports/forge-workspace.json` 保存 workspace 相对位置和按发生顺序追加的事件索引；每个 typed operation 事件文件保存事件 ID、操作名和 `forge.operation-outcome/v1` payload，其中嵌入未改变的 `forge.result/v1` envelope。事件记录用于审计和跨操作发现，事件索引中的 `path_rel` 可在 workspace 根目录下解析并应保持有效。已有的根目录 `meta.json` 以及 unit/结果 API 产生的 `forge-unit.json`、`forge-result.json` 仍是兼容输出。typed band/DOS postprocess 与 typed `pyatb-band` handoff 已落地但仍为 `experimental`，其离线测试和 API/CLI parity 不等同于真实 ABACUS 科学结果或稳定发布保证；typed `export`、PyATB properties、property/composite 聚合和其它 capability-specific 真实操作/解析验收仍不属于本批次。

事件文件是不可变审计事实；manifest 是可重建的发现索引。若事件文件已原子写入而 manifest 更新在崩溃中未完成，下一次带 workspace 锁的 manifest 初始化或追加会扫描并确定性地补入有效未索引事件。该机制不声称跨事件文件与 manifest 的多文件原子性。

## 非目标

- 不内置云平台提交、追踪、下载能力
- 不引入 AiiDA 语义或工作流编排语义到 Forge 核心
- 对于 phonon / elastic 等厚工作流，其实现必须基于解耦的单元模块，且其输入/计算/输出必须可解耦
- typed `export`、PyATB properties、nspin 4、property/composite 聚合不在本批次
- 调度、workflow/orchestration、重试/恢复和科学判断由 Forge 外部的调用方负责

## 贡献

- 小步提交，保持边界清晰
- 为解析器和 CLI 补充可复现测试
- 开发前先阅读 [AGENTS.md](./AGENTS.md)；涉及公共契约、workspace、CLI 协议或 Paimon 适配时，先按 [开发治理入口](./docs/superpowers/README.md) 生成或阅读对应 SPEC/PLAN
