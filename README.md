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
- Engine/Version Policy 的 parser backend、版本来源与双轨验收边界见 [Engine/Version Policy SPEC](./docs/superpowers/specs/2026-09-12-forge-engine-version-policy-design.html)、[实施 PLAN](./docs/superpowers/plans/2026-09-13-forge-engine-version-policy.md) 和 [Stage 0 证据](./docs/superpowers/evidence/2026-09-14-forge-engine-version-policy-stage0.md)。当前 native 默认与 canonical checkout parity 已验证；可安装的 `abacuslite` exact extra、fresh environment 双轨发布和外部迁移仍须单独验收。
- Paimon v1.3 的逐工具迁移状态由工作区中的 `app-tools/toolbox/ABACUS/docs/superpowers/specs/paimon-v1.3-forge-coverage.html` 维护。该矩阵中的 covered/partial 仅表示接口映射与证据边界；运行时旧依赖清零、完整 Agent Benchmark、SAI/平台与生产验收未完成前，不将 Forge 能力页解释为 Paimon v1.3 发布签收。
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
原生 STRU 中的 `Fe1`/`Fe2` 等物种标签会映射为真实元素并在 STRU 往返及轻量结构修改中保留；
无法按规范元素前缀解析的标签会明确失败，标准化不会静默丢弃这类标签。

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
- 原生 ABACUS SCF 的 `!FINAL_ETOT_IS ... eV` 会作为 `total_energy` 事实收集；typed MD 从 contained `running_md.log` 收集原生 Energy/Potential/Kinetic（Ry 转 eV）、Temperature（K）及可用 Pressure（kbar），`MD_dump` 只提供轨迹帧/步数与工件事实
- Typed `collect` 的标量 `MetricRecord` 会在语法和来源已确认时附带单位、`reported`/`derived`/`runtime` kind，以及指向 workspace 内工件的 `source_artifact_id`；无法确认的单位或来源保持为空。这个增强只作用于 typed collection projection，legacy `collect()`、`CollectionResult.to_dict()` 和 `to_envelope()` 的既有元数据保持兼容，也不把事实转成科学接受结论。
- `LocalRunner` 的 `executable`/`launcher` 带目录相对路径，以及 `PATH` 中的相对或空分量，均按调用进程的 cwd 解析；实际进程仍以 workspace 的 `inputs/` 为 cwd 启动，但使用同一解析结果。公开的 `command` 字段（包括 typed `forge-result`）保留调用方传入的原始请求字符串。

### Typed operation service boundary

`ScfServiceSet`、`RelaxServiceSet` 与 `MdServiceSet` 提供 typed SCF、relax、cell-relax 和
MD 路径，交付
execution/collection 事实与 observations；若兼容结果保留 `scientific` 字段，Forge
只写 `unassessed`，不在 Forge 内作科学判定。`ScfExecuteRequest(dry_run=True)` 或
对应的 `RelaxExecuteRequest(dry_run=True)` 才能产生
`execution=skipped`；typed execute 不会根据已有日志（包括 `NORMAL END`）推断跳过，
并且实际执行直接调用本地 runner。底层 `run_many(..., skip_completed=True)` 仍保留
给现有 composite 兼容调用，但属于 legacy helper，不是 typed service 的状态协议。
若本次进程的 stdout 或新建/实际内容变化的 workspace-contained `running_*.log` 含有
ABACUS 正常结束标志，typed execute 还会返回 `normal_end=true` 及其相对来源路径作为
log observation；没有可归因标志时省略该观察，不改变 execution 或 scientific 状态。
四个 ABACUS typed capability 的 `calculation` profile 必须与能力名一致：`prepare` 可以省略该
参数并使用 profile 默认值，但显式冲突会在 admission 前返回 `request.schema`；`modify` 只能重复
当前 profile，不能改写或删除；`execute`/`collect` 遇到已有 `inputs/INPUT` 时要求其 profile
匹配（没有 `INPUT` 的外部 output-only `collect` 仍可用）。这是输入/过程前置条件，不是科学验收；
保留的 `ForgeServices` legacy facade 继续维持历史宽松行为。
SCF/Relax collection 将已解析的数组指标和有效结构快照作为事实 observations。
SCF 收集完整性由非空输出日志、有限总能量和解析情况决定，Relax 还要求有效的
最终结构；收敛标志独立返回。typed collect 只读取 workspace 内的领域文件，
审计事件、claims、锁和 workspace manifest 不进入计算产物列表。
typed MD 的 `collection=complete` 只表示存在唯一、contained 且可读的原生
`running_md.log`（包括 runner 在 `inputs/OUT.*` 下产生的域路径），其中至少有一个完整热力学 block；缺失或歧义日志、
不完整 block 和仅有 `stdout`/`MD_dump` 的输入会保持 `partial` 或 `missing_output`。
legacy `collect()` 继续读取历史 synthetic `MD_dump` 的兼容指标，但 typed MD 的
`md_last_*` 热力学字段只来自原生 `running_md.log`。

Typed ABACUS collect 默认使用 Forge native parser。需要显式试用内部可选的
`abacuslite` parser 时，在 service 实例或 machine CLI 上逐次指定配置；它只影响
`collect`，不会修改 request JSON/schema、进程环境或 legacy `collect()`：

```python
services = ScfServiceSet.default(
    workspace_root="runs",
    parser_backend="abacuslite",
    output_version="v3.11.0-beta8+56",
)
outcome = services.collect.collect(request)
```

```bash
PYTHONPATH=src python -m abacus_forge.cli operation collect \
  --stdin --parser-backend abacuslite --output-version v3.11.0-beta8+56
```

`output_version` 只接受已支持的 producer 版本映射（例如 `v3.10.1`、裸
`v3.9.0` 和 `v3.11.0-beta8+56`）。缺少可选包、唯一 contained running log 无版本或
日志版本不受支持时，typed collect 返回既有 `precondition.missing`；无效配置和版本冲突
返回 `request.invalid`。无唯一非空主 running log 时不调用可选 parser，沿用已有收集状态。

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
workspace 的显式 `STRU`、HR、SR 文件、可选 rR 文件、Fermi 能量和 line-mode K 点；默认以
workspace 内的相对链接完成 handoff，`handoff_mode="copy"` 可改为独立复制。绝对路径、
跨 workspace 来源、隐式 SCF 目录扫描和从日志推导 Fermi 能量均不属于 typed 面。

准备会生成 `inputs/STRU`、`inputs/pyatb_sources/<basename>`、`inputs/Input` 和
`inputs/KPT_band`，并在结果 diagnostics/manifest 中记录角色、来源与目标相对路径及
SHA-256。`nspin` 支持 1、2 和 4：nspin=1/4 各需一个 HR 文件，nspin=2 需要两个 HR 文件，
三种模式均共用一个 SR 文件；nspin=4 的单个 HR 在 manifest 中记为
`matrix_hr/shared`；rR 只有在请求提供时才生成 `rR_route` 并记为
`matrix_rr/shared`，省略或传入 `null` 时不生成该 route 或 manifest entry。其他 PyATB property 尚未进入此 capability。执行只通过本地 runner
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

`abacuscopilot` 的 library-family 选择器属于上层人类 UX；Forge core 不维护全局家族
配置，也不扫描目录或猜测文件名。人类/Agent 或可选 TUI 可以先把选定家族解析成上述
显式元素映射，再交给 typed `prepare`，从而保留可审计的资产来源而不扩大 Forge 边界。

## Agent-first CLI

Stage 3 的 machine surface 以及 Stage 4 首批现已提供 `scf`、`relax`、`cell-relax` 和
成熟度为 `experimental` 的 `md`、`atst-neb`、`pyatb-band`；typed `band`/`dos` 另提供仅用于
`postprocess` 的实验性 capability，typed `export` 提供实验性的 `export` capability 和
`export` operation。它固定暴露三个顶层命令：`operation`
（`scf`、`relax`、`cell-relax` 执行 `prepare`、`modify`、`execute`、`collect`；`md` 还提供独立的 `postprocess`；`atst-neb` 执行 `prepare`、
`execute`、`postprocess`；`pyatb-band` 执行 `prepare`、`execute`、`collect`；`band`、`dos` 执行 `postprocess`；`export` 执行 `export`）、`schema`（读取请求 schema）和
`capabilities`（读取能力发现）。兼容保留的顶层 `--help` 不列出这三个命令；请分别
运行 `operation --help`、`schema --help` 和 `capabilities --help` 查看机器接口。

没有 capability 的 `postprocess` 仍返回 `request.invalid`；typed
band/DOS 请求必须分别声明 `capability="band"`/`"dos"`，typed postprocess/export 必须显式声明
对应 capability。legacy CLI 的默认输出和入口保持不变。

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
capability 为 `scf`、`relax`、`cell-relax`、`atst-neb`、`md`、`band`、`dos`、`pyatb-band`、`export`；`md` 支持
`prepare`、`modify`、`execute`、`collect`、`postprocess`，且 maturity 为 `experimental`；其他 capability
按各自 descriptor 暴露 operation，`band`/`dos` 仅暴露 `postprocess` 且 maturity 为
`experimental`，`pyatb-band` 仅暴露 `prepare`、`execute`、`collect` 且 maturity 为
`experimental`，`export` 仅暴露 `export` 且 maturity 为 `experimental`。默认格式下，
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
这里的三个 operation 是 `atst-neb` capability 自身支持的 operation 集，不是 Forge 全局
operation 集。
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
- `elastic post` 会从计划中的 zero/strain 状态与收集到的 stress 做最小二乘拟合并发布 `elastic_tensor.json`、`elastic_fit.json`；数据不足时明确降级为 `unavailable`
- `phonon` 的 phonopy 能力是可选依赖：`pip install "abacus-forge[phonon]"`

### 本地 property pack

> **成熟度：实验性。** 以下能力仍主要依赖 API/CLI 与 mock/fixture 回归，尚未逐项完成真实 ABACUS 操作/解析验收；`convergence`、`spin-density`、`workfunc`、`charge-diff` 各已有一次本地 serial-PW 操作/解析 smoke，但不应视为 PAIMON v1.3 已稳定暴露的能力。

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

`bec` 当前仍是 fixture/legacy 形态，不能视为已验证的原生端到端流程：ABACUS
对每个结构要求先执行 SCF 生成 restart，再以 `calculation=nscf`、显式
`gdir=1/2/3` 和 `symmetry=-1` 执行 NSCF；当前 Forge 尚未把这些
阶段作为显式、由调用方交接的独立 operation，也尚未将原生
`running_nscf*.log` 的 polarization 事实接入 `post_bec`。这项能力保持
experimental，不进入 Paimon v1.3 稳定面；顺序、重试、artifact handoff 和
科学解释由人类/Agent 负责，待独立 BEC SPEC/PLAN 收敛后再推进。

`charge-density`、`spin-density` 和 `charge-diff` 的 legacy `post` 结果会在
`diagnostics.property_manifest` 中附加 `forge.property-manifest/v1` 文件事实索引：
`inputs` 记录明确选中的 cube source，`outputs` 记录派生 cube 与 metrics report，
`missing` 记录缺失、越界或不可读取的位置。manifest 使用同一结果中的 artifact id、
SHA-256 和大小；ABACUS 默认的 `inputs/OUT.<suffix>/` 只作为没有实际文件时的
canonical expected path，兼容 glob 找到的变体仍保留实际相对路径。该索引不新增 typed
property capability，不做科学验收、workflow 编排、重试或调度；其他 property pack 和
PyATB properties 仍保持实验性/独立推进。typed PyATB band 的真实进程 smoke 只证明
输入、进程、parser 与 artifact/audit 兼容性，证据与边界见
[`tests/real_smoke/README.md`](tests/real_smoke/README.md) 和
[`Stage 5 evidence`](docs/superpowers/evidence/2026-09-13-forge-stage5-evidence.md)。

最小 manifest 形态如下（具体 entry 会带同一结果的 artifact 事实）：

```json
{
  "schema_version": "forge.property-manifest/v1",
  "task": "spin-density",
  "inputs": [],
  "outputs": [],
  "missing": []
}
```

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

## Typed export（experimental）

typed `export` 将一个调用方明确引用的、同一 workspace 内既有 operation outcome
序列化为一个新的 `forge.export/v1` JSON 文档。它不是“寻找最近结果”的快捷方式：
`source_artifact_refs` 必须非空，且所有 ref 必须属于同一个已记录的 source operation。
Forge 只读取该 operation 的 immutable event，保留 source outcome 的原始 facts，并在
当前 workspace 写出一个新的 output artifact；`execution=completed`、
`collection=complete`，`scientific=unassessed`。

完整的 typed request 示例：

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

将请求保存为 `export-request.json` 后，机器路径可以从文件或 stdin 调用：

```bash
PYTHONPATH=src python -m abacus_forge.cli operation export --request export-request.json
cat export-request.json | PYTHONPATH=src python -m abacus_forge.cli operation export --stdin
```

Python API 与 machine CLI 使用同一个 typed service：

```python
from abacus_forge import ExportRequest, ExportServiceSet

request = ExportRequest.from_dict(payload)
result = ExportServiceSet.default(workspace_root=".").export.export(request)
```

输出文档的 wire shape 固定如下；`source_outcome` 是未改变的
`forge.operation-outcome/v1` payload（其内部 envelope 仍为 `forge.result/v1`）：

```json
{
  "schema_version": "forge.export/v1",
  "source_operation_id": "123e4567-e89b-42d3-a456-426614174131",
  "source_artifact_refs": [
    {"operation_id": "123e4567-e89b-42d3-a456-426614174131", "artifact_id": "energy"}
  ],
  "source_outcome": {
    "schema_version": "forge.operation-outcome/v1",
    "operation_id": "123e4567-e89b-42d3-a456-426614174131",
    "envelope": {
      "schema_version": "forge.result/v1",
      "operation": "collect",
      "workspace_rel": ".",
      "status": {
        "execution": "completed",
        "scientific": "unassessed",
        "collection": "complete"
      },
      "artifacts": [
        {
          "id": "energy",
          "path_rel": "outputs/energy.dat",
          "role": "output",
          "stage": "collect",
          "availability": "available",
          "media_type": "text/plain",
          "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "size_bytes": 4
        }
      ],
      "metrics": [],
      "checks": [],
      "warnings": [],
      "diagnostics": {}
    },
    "observations": []
  }
}
```

typed export 只序列化显式引用的历史 outcome JSON：不复制二进制 artifact，不扫描或
选择 latest，不隐式执行 `collect`/`postprocess`，不发布报告，不做科学验证，也不负责
任务编排、重试、恢复或平台调度。首版仅支持 `format="json"` 与
`overwrite_policy="fail"`；replace/merge、binary/archive 和多 operation 聚合需要另立
设计。旧的 `api.export()` 与顶层 `abacus-forge export` 仍保持原有兼容行为，和该 typed
capability 分开使用。

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

`rr_path_rel` 是可选字段；请求可省略或显式传入 `null`。只有调用方确实提供 rR
文件时，Forge 才会交接该文件并在生成的 `Input` 与 manifest 中记录对应事实。

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

该 capability 已有离线 fixture/mock、API/CLI parity 以及本地输入/进程兼容性证据，仍保持
`experimental`；本仓库不以此文档声称科学验证或稳定晋级。

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

Relax discovery 和 schema 当前保持 `experimental`；默认离线门禁仍覆盖 mock/fixture 与
machine/API parity。可选的 `real_smoke` 会在复制的用户准备 workspace 上验证
execute/collect 的序列化 outcome、事件和 artifact，但不作物理收敛判断；当前候选已用本地
serial-PW ABACUS 运行并通过 typed SCF、Relax/cell-relax 和 MD 的 process/parser/artifact
smoke（详见候选 [maturity-gates plan](docs/superpowers/plans/2026-09-11-forge-maturity-gates-integration.md)）。
其中 typed SCF machine-path smoke 与 typed Relax smoke 都通过 machine CLI，legacy SCF API
smoke 不能替代前者。真实 smoke 证据也不自动提升 maturity。typed SCF smoke 还会在首次执行前确认复制 workspace 的
`inputs/INPUT` 声明 `calculation=scf`；typed Relax 的执行和收集使用同一长 parent-process
超时预算。`collect` 的 `scientific` 始终为 `unassessed`，缺少输出或解析不完整只反映
collection 状态。

可选的 typed MD real-smoke 也只通过 machine CLI，在复制的用户准备 workspace 上执行一次
`md` 的 `execute` 与 `collect`。它要求 `inputs/INPUT` 声明 `calculation=md`，并核对
`running_md.log` 的原生热力学 parser facts、状态、事件、manifest 和 contained artifact；
`MD_dump` 事实作为独立投影保留。该门禁不判断轨迹质量、温度/能量物理正确性、收敛或任务
编排；缺少 `ABACUS_FORGE_MD_SMOKE_WORKSPACE` 或共享 executable 时只 skip，错误输入则
fail。用于 smoke 的源 workspace 还必须没有 collector 可见位置下既有的
`running_md.log`/`MD_dump`（包括 `inputs/OUT.*` 下的同名生成文件），避免无操作 executable 复用旧结果；显式
`inputs/OUT.*` 中的其它 handoff 资产仍由调用方负责。MD smoke 仍是 experimental 证据，
不改变生产 service 或稳定能力面。

typed SCF 与 typed Relax real-smoke 也要求复制源保持 freshness：门禁会拒绝其
collector 可消费的既有 `running_*.log`（包括 `reports/` 下的运行日志）/fallback
log，Relax 还会拒绝 `STRU_FINAL`、`STRU_FINAL.cif`、`STRU_ION_D`、`STRU_NOW`、
`STRU_NOW.cif`、`STRU.cif` 或 `STRU` 等既有最终结构文件（包括 `inputs/OUT.*` 域路径；
普通 `inputs/` 和 `reports/` 中的非域 handoff/审计文件不受此检查）。这个条件只属于真实运行
证据测试，不改变普通 Forge `execute`/`collect` 对外行为。

typed MD 首批已提供实验性的 `prepare`、`modify`、`execute`、`collect` 和独立
`postprocess` operation。MD 后处理只读取调用方明确交接的 workspace-relative exact
trajectory，不扫描目录、不查找 latest、不自动转换 `MD_dump`，也不隐式启动 ABACUS 或
串联 `execute`/`collect`。上文的 typed band/DOS postprocess、typed `pyatb-band` handoff
和通用 typed `export` 都是彼此独立的实验性能力，不扩展为 MD 或其它 task 的隐式后处理；
PyATB properties 和更多真实 property-pack smoke 仍待后续交付。监控、workflow 编排、
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
可用时返回 `MD_dump` 与 `running_md.log` 中的解析事实、指标和 artifact 引用，不判断
轨迹或物理结果是否可接受。`running_md.log` 的 Energy/Potential/Kinetic 按 ABACUS
原生 Ry 单位转换为 eV；没有 Pressure 列是合法的可选事实。通用 typed export 不会隐式
读取或改写 MD 产物。monitor、workflow 编排、
restart/resume、调度以及科学判断由 Forge 外部的人类或 Agent 负责。

## Typed MD postprocess（experimental）

`MdPostprocessRequest` 要求一个显式的 `trajectory_path_rel`，并支持五个 canonical
分析名称：`rdf`、`msd_diffusion`、`vacf_vdos`、`bond_length`、`bond_angle`。请求还可用
`start`/`end`/`stride` 选择帧，以及在 JSON-safe `parameters` 中提供
`timestep`、`selection`、`elements`、`rmax`、`nbins`、`save_data`、`save_plot`。
`msd_diffusion` 和 `vacf_vdos` 要求正的 `timestep`，其含义是采样帧视图中相邻帧的时间间隔；
Forge 不会把 `stride` 静默乘入该值。RDF 需要轨迹帧提供显式周期 cell。
`msd`、`vacf`、`bond` 等兼容别名只由上层 Paimon adapter 映射，不进入 Forge request。

例如，下面的请求只分析调用方已经放在 `runs/Si_md/outputs/md.traj` 的轨迹：

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

将其保存为 `md-postprocess-request.json` 后执行：

```bash
PYTHONPATH=src python -m abacus_forge.cli operation postprocess --request md-postprocess-request.json
```

Python API 使用同一 service：

```python
from abacus_forge import MdPostprocessRequest, MdPostprocessServiceSet

request = MdPostprocessRequest.from_dict(payload)
result = MdPostprocessServiceSet.default(workspace_root=".").postprocess.postprocess(request)
```

服务始终生成 `trajectory_source.json` 和 `analysis.json`，并按 canonical mode 生成确定性
数据文件及可选 PNG；所有 artifact 都是 workspace-relative 并带 SHA-256/size。绘图导入或
渲染失败时不伪造占位 PNG，只在 diagnostics 记录失败并让 collection 反映缺失产物；未知
XYZ 元素也会 fail-closed，不使用合成质量。MSD 可用时返回 `diffusion_coefficient` reported
metric，source 指向本次生成的 `analysis.json`。返回的
`execution` 固定为 `not_run`、`scientific` 固定为 `unassessed`，`collection` 只描述
`complete`、`partial` 或 `missing_output` 的产物事实。科学验证、轨迹转换/PDB、TUI、
任务编排、监控、调度、重试/恢复和导出均不在此 operation 内。

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

`reports/forge-workspace.json` 保存 workspace 相对位置和按发生顺序追加的事件索引；每个 typed operation 事件文件保存事件 ID、操作名和 `forge.operation-outcome/v1` payload，其中嵌入未改变的 `forge.result/v1` envelope。事件记录用于审计和跨操作发现，事件索引中的 `path_rel` 可在 workspace 根目录下解析并应保持有效。已有的根目录 `meta.json` 以及 unit/结果 API 产生的 `forge-unit.json`、`forge-result.json` 仍是兼容输出。typed band/DOS postprocess、typed `pyatb-band` handoff 与 typed export 已落地但仍为 `experimental`，其离线测试、API/CLI parity 和 PyATB band process smoke 不等同于真实 ABACUS/PyATB 科学结果或稳定发布保证；binary/archive、replace/merge、多 operation 聚合、PyATB properties、property/composite 聚合和其它 capability-specific 真实操作/解析验收仍需独立设计或验证。

事件文件是不可变审计事实；manifest 是可重建的发现索引。若事件文件已原子写入而 manifest 更新在崩溃中未完成，下一次带 workspace 锁的 manifest 初始化或追加会扫描并确定性地补入有效未索引事件。该机制不声称跨事件文件与 manifest 的多文件原子性。typed export 只读取这些历史 event，不改变 source event。

## 非目标

- 不内置云平台提交、追踪、下载能力
- 不引入 AiiDA 语义或工作流编排语义到 Forge 核心
- 对于 phonon / elastic 等厚工作流，其实现必须基于解耦的单元模块，且其输入/计算/输出必须可解耦
- binary/archive 或 replace/merge 形式的 export、多 operation 聚合、PyATB properties、property/composite 聚合不在本批次；nspin=4 handoff 已支持，typed `pyatb-band` 的 band process smoke 已有证据，但 property 计算与真实 NEB workflow 仍需独立推进
- 调度、workflow/orchestration、重试/恢复和科学判断由 Forge 外部的调用方负责

## 贡献

- 小步提交，保持边界清晰
- 为解析器和 CLI 补充可复现测试
- 开发前先阅读 [AGENTS.md](./AGENTS.md)；涉及公共契约、workspace、CLI 协议或 Paimon 适配时，先按 [开发治理入口](./docs/superpowers/README.md) 生成或阅读对应 SPEC/PLAN
