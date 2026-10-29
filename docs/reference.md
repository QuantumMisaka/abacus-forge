# Forge 接口与 workspace 参考

本文记录当前调用面和已实现的 workspace 行为，供 API/CLI 调用者查阅。机器 CLI 的 schema discovery 是请求字段的直接来源：运行 `abacus-forge capabilities`，再运行 `abacus-forge schema <capability> <operation>`。本文不替代有效规范；公共契约以 [契约优先重构 SPEC](superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html) 及 [Service/Status 细化 SPEC](superpowers/specs/2026-09-02-forge-service-status-migration-design.html) 为基线。

## 调用面与状态边界

### Primitive、unit、task 与 sequence

- Primitive API 包括 `prepare`、`modify_input`、`modify_stru`、`modify_kpt`、`execute`、`collect`、`export`。`run` 是 `execute` 的兼容别名。
- `UnitSpec` 与 `prepare_unit`、`modify_unit`、`execute_unit`、`collect_unit` 把一次 ABACUS 工作交给明确的 task/unit。比如 band/DOS 可分为 `scf`、`nscf`、`pyatb` 或 postprocess 单元；下游通过显式 source workdir 取得上游产物。
- 单任务 API/CLI 包括 `run_scf`/`scf`、`run_relax`/`relax`、`run_cell_relax`/`cell-relax`、`run_md`/`md`、`run_band`/`band`、`run_dos`/`dos`。它们是已有便捷闭环，不能据此推断 typed capability 也支持相同操作。单任务 CLI 的 `--dry-run` 只准备 workspace 并返回命令预览。
- `run_band_sequence`、`run_dos_sequence` 是本地兼容 helper；band sequence 的 `backend="pyatb"` 组合 ABACUS LCAO SCF 产物、PyATB 输入、执行和收集。它们负责现有本地目录/阶段语义，不是 typed service 的多操作协议。
- Composite packs：`eos`、`elastic`、`vibration`、`phonon`。Property packs：`convergence`、`charge-density`、`spin-density`、`charge-diff`、`elf`、`bader`、`workfunc`、`vacancy`、`bec`。这些是本地兼容 pack 接口；property packs 保持 experimental。详见[使用指南](guide.md#composite-and-property-packs)。

以上各面会复用部分底层能力，但参数默认值、资产解析和调用行为具有各自兼容契约。调用方应使用目标入口自身的 `--help` 或 Python 签名，不应假设可在入口间机械替换。

### Typed capability 当前覆盖

当前 machine discovery 的 capability 名为 `scf`、`relax`、`cell-relax`、`atst-neb`、`md`、`band`、`dos`、`cohp`、`pyatb-band`、`pyatb-cohp`、`polarization`、`bec`、`export`。具体操作和 maturity 以 `capabilities` 返回的 descriptor 为准；当前已知边界如下：

| Capability | Typed operations | 当前成熟度/边界 |
| --- | --- | --- |
| `scf` | `prepare`, `modify`, `execute`, `collect` | `experimental`。 |
| `relax`, `cell-relax` | `prepare`, `modify`, `execute`, `collect` | discovery/schema 当前为 `experimental`。 |
| `md` | `prepare`, `modify`, `execute`, `collect`, `postprocess` | `experimental`。 |
| `atst-neb` | `prepare`, `execute`, `postprocess` | `experimental`；委托外部 `atst` executable。 |
| `band`, `dos` | `postprocess` | `experimental`；没有 typed band/DOS execute。 |
| `cohp` | `postprocess` | `experimental`；IAO-COHP（`method="iao"`），显式消费同一 workspace 内的已完成 LCAO SCF；不执行 SCF，不含直接 NAO-COHP。 |
| `pyatb-band` | `prepare`, `execute`, `collect` | `experimental`。 |
| `pyatb-cohp` | `prepare`, `execute`, `collect` | `experimental`；direct NAO-COHP，支持 nspin=1/2，显式 k 点与权重。 |
| `polarization` | `collect` | `experimental`；显式原生 Berry 日志、INPUT、STRU。 |
| `bec` | `postprocess` | `experimental`；条件式分支或显式 offsets，请求子集和缺项诊断。 |
| `export` | `export` | `experimental`。 |

Polarization/BEC 的有界实现已获确认，已实现 experimental `polarization/collect`
与 `bec/postprocess`。新能力复用既有通用 prepare/displacement 与单次 execute 原语，
不编排 SCF/NSCF 多阶段工作流，也不替换 legacy BEC pack 的数值行为。安装态
已通过 MgO 的 O_x 单列实算与有限位移/网格敏感性检查；不代表全张量或全面收敛，
见[真实验证记录](superpowers/evidence/2026-10-21-forge-installed-bec-validation.md)。

Typed outcome 报告 `execution`、`collection` 和 `scientific` 等正交状态。Forge 的 `scientific` 字段保持 `unassessed`；运行 smoke、解析出数值或成功写 artifact 都不自动产生科学验收结论，也不会晋级成熟度。

## Machine request and status protocol

machine CLI 的统一入口为：

```text
abacus-forge operation <operation> --request FILE
abacus-forge operation <operation> --stdin
abacus-forge capabilities
abacus-forge schema <capability> <operation>
abacus-forge capability-contracts
abacus-forge capability-contracts <capability>
```

源码开发态可使用 `PYTHONPATH=src python -m abacus_forge.cli`。路径按两级解析：CLI 的 `workspace_rel` 相对调用进程 cwd（作为 service 的 `workspace_root`）解析；`structure_path_rel`、`trajectory_path_rel`、source paths 等 operation 路径再相对解析后的 workspace 根目录解析。例如 `workspace_rel="runs/Si_relax"` 与 `structure_path_rel="source.STRU"` 指向 `runs/Si_relax/source.STRU`。CLI 不提示或推断科学结论，也不负责任务链编排、重试、调度或平台提交。

`capability-contracts` 是 Phase A 只读 registry。无参数返回
`forge.capability-contracts/v1`；指定 capability 返回
`forge.capability-contract/v1`。当前 registry 仅含 SCF reference contract，
明确不表示其他 capability 已完成 canonical output/maturity 契约建设。

请求 envelope 使用 `schema_version="forge.request/v1"`。operation-specific 字段以 `schema` discovery 为准；每个 operation 请求携带 operation id。`capability` 用于区分 capability-specific operation，不能只根据通用 operation 名推断服务。尤其 `band`、`dos` 必须显式声明相应 capability 且只能 postprocess；typed `export` 也必须声明 `capability="export"`。

默认 `operation` 输出一个 JSON outcome/error envelope。`--pretty` 只改变 JSON 空白；`--format text` 是同一 envelope 的文字投影。退出码类别为 `0` 无执行失败、`2` 请求或路径错误、`3` 前置条件缺失、`4` 进程已启动但执行失败、`5` 持久化或内部错误。当前 stderr 留给受控诊断，默认路径无诊断文本。具体错误码、字段校验和 schema 可能由 capability 自身扩展，须以当前 discovery 为准。

Typed operation 直接调用本地 runner 或对指定产物进行单次处理。typed execute 不根据已有日志（包括 `NORMAL END`）推断跳过；`dry_run=true` 才会产生 skipped execution。legacy `run_many(..., skip_completed=True)` 继续保留给既有 composite 兼容调用，不是 typed 状态协议。

## Typed prepare assets and legacy assets

### Typed prepare

Typed prepare 的 `pseudo_sources` 和 `orbital_sources` 是调用方显式提供的按元素映射；`asset_mode` 为 `copy` 或 `link`，默认 `copy`。映射只作用于明确列出的元素。没有映射的 STRU 引用保留原样，Forge 不因此声明资源集合完整。

相对 source path 按 operation workspace root 解析；显式来源也可为绝对路径。`link` 只允许 workspace 内来源，并写 workspace-relative link。缺失来源、不合规后缀或 basename 冲突，以及不安全/不允许的 link 会 fail-closed，不留下部分资源。diagnostics、显式映射对应的 `forge-unit.json` 信息和事件记录可记录 source/target 与 SHA-256 provenance。

### Legacy prepare

legacy `prepare(...)` 继续接受 `pseudo_path` 和 `orbital_path` 目录推断，默认使用 `link`。这与 typed prepare 的显式来源映射、默认 `copy` 有意不同；需要旧行为的消费者应继续使用 legacy API。

### 结构与输入生成

`prepare(...)` 生成 `INPUT`、`STRU`、`KPT`，接受参数覆盖/删除、K 点、资源路径和 `copy/link` 模式，并可按元素设置简单共线磁矩。ABACUS profile 默认显式写出 `dft_functional=pbe`，可由调用方覆盖。

STRU 归一化支持 `Direct`、`Cartesian`、`Cartesian_angstrom`、`Cartesian_au`；居中坐标和未知坐标模式会报错。写出的晶格使用 ABACUS 原生 Bohr 单位，旧 Forge Angstrom 单位扩展仍可读取。归一化保留已有资源引用和质量。原胞/常规胞转换保留元素资源引用及同元素一致的质量和共线磁矩；同元素原子质量/磁矩不一致或存在移动约束时会拒绝，避免静默丢失信息。`Fe1`/`Fe2` 等物种标签在可按规范元素前缀解析时会在往返及轻量结构修改中保留；不可解析标签明确失败。

### INPUT calculation profile

四种 typed ABACUS capability `scf`、`relax`、`cell-relax`、`md` 的 `calculation` profile 必须与 capability 对应。prepare 可省略 `calculation` 并使用 profile 默认；显式冲突在 admission 前返回 `request.schema`。modify 只能重复当前 profile，不能改写或删除。execute/collect 在 `inputs/INPUT` 存在时要求 profile 匹配；没有该文件的外部 output-only collect 仍可用。保留的 `ForgeServices` legacy facade 维持历史宽松行为。这些规则是输入/过程前置条件，不是科学验收。

## Execution and collection facts

`execute` 只在指定 workspace 内调用一次本地进程；不自动 prepare、collect 或分析科学结果。`LocalRunner` 在 `inputs/` 下启动 ABACUS。`executable`/`launcher` 中带目录的相对路径，以及 PATH 中的相对或空分量，都按调用进程 cwd 解析；typed `forge-result` 的公开 `command` 字段保留调用方传入的原始字符串。

若本次进程 stdout 或新建/内容实际变化的 workspace-contained `running_*.log` 包含 ABACUS 正常结束标志，typed execute 可返回 `normal_end=true` 和相对来源路径的 log observation；没有可归因标志时不返回该 observation。它不改变 execution 或 scientific 状态。

`collect` 读取 workspace 输出并返回标准化事实。当前解析范围包括能量、费米能级、带隙、力、应力、压力、virial、relax 结果和关键工件索引。原生 ABACUS SCF 行 `!FINAL_ETOT_IS ... eV` 可作为 `total_energy` 事实。typed SCF/Relax collection 可返回解析数组指标、有效结构快照以及收敛观察；Relax 完整性还要求有效最终结构，收敛标志独立返回。

Typed 标量 `MetricRecord` 在语法和来源确认时可附带单位、`reported`/`derived`/`runtime` kind 和 workspace 内 source artifact id；不确定的单位或来源保持为空。此投影不改变 legacy `collect()`、`CollectionResult.to_dict()`、`to_envelope()` 元数据，也不作科学判定。

Typed collect 只读取 workspace 内领域文件；audit events、claims、锁和 workspace manifest 不作为计算产物。typed MD 的热力学指标只从 contained 的原生 `running_md.log` 提取：Energy/Potential/Kinetic 从 Ry 转 eV，Temperature 为 K，Pressure（kbar）可选。`MD_dump` 提供轨迹帧/步数和 artifact facts。MD typed collection 为 `complete` 要求唯一、contained、可读的原生日志且至少有一个完整热力学 block；缺失/歧义/不完整日志，以及只有 stdout 或 `MD_dump` 的情况会是 `partial` 或 `missing_output`。Legacy collect 可保留从 synthetic `MD_dump` 读取历史兼容指标。

`collect` 默认使用 Forge native parser。typed ABACUS collect 可在 service 实例或 machine CLI 单次显式指定可选 `abacuslite` parser backend 和受支持的 `output_version`；这只影响 typed collect，不改变请求 schema、进程环境或 legacy collect。可选包缺失、日志版本缺失/不支持会按既有前置条件错误返回；无唯一非空主 running log 时不会调用可选 parser。该 backend 需要已发布的 `abacuslite` 包，安装 `pip install 'abacus-forge[abacuslite]'`（extra 固定已验证版本，当前为 `1.2.2`）；默认安装不包含它。

Python 配置形态如下；`output_version` 只接受当前支持的 producer 映射，例如 `v3.10.1`、`v3.9.0` 和 `v3.11.0-beta8+56`：

```python
services = ScfServiceSet.default(
    workspace_root="runs",
    parser_backend="abacuslite",
    output_version="v3.11.0-beta8+56",
)
outcome = services.collect.collect(request)
```

machine CLI 可逐次传入 `--parser-backend abacuslite --output-version v3.11.0-beta8+56`。缺少可选包、日志无版本或版本未受支持时返回既有 `precondition.missing`；无效配置或版本冲突返回 `request.invalid`。

```bash
PYTHONPATH=src python -m abacus_forge.cli operation collect \
  --stdin --parser-backend abacuslite --output-version v3.11.0-beta8+56
```

## Typed postprocess and PyATB detail

### Band and DOS

`BandPostprocessRequest` 和 `DosPostprocessRequest` 只作独立 typed `postprocess`。请求需声明 capability 和一个非空的 workspace-relative 源路径列表：band 使用 `source_paths_rel`，DOS 使用 `dos_paths_rel`，另可给 `pdos_path_rel`/`tdos_path_rel`。不存在隐式 collect、export 或上游 operation。

纯进程内解析不声明 execution：成功、部分解析和 parser failure 的 `execution` 为 `not_run`；`collection` 描述 `complete`、`partial` 或 `missing_output`；`scientific` 固定 `unassessed`。结果含 parser facts、input/output artifacts（相对路径、SHA-256、size）和 append-only operation event。每个 admitted outcome 写入 operation report；request/precondition 错误不写该 report。旧的 `run_band`、`run_dos`、sequence helper 与 `abacus-forge band|dos` legacy task/sequence API 维持旧边界。

### ATST NEB

`atst-neb` 的 `execute` 请求中，`check_input=true` 只允许与 `dry_run=true` 一起使用；真实执行使用 `dry_run=false`、`check_input=false`。`postprocess.n_max` 按 ATST 定义表示中间图像数量，不包含两个端点：5 图像链应传 `3`。`execution=completed` 只说明外部进程成功，是否达到 NEB 力收敛阈值需另读 ATST 的 stage 记录；Forge 的 `scientific` 仍为 `unassessed`。

### PyATB band

运行兼容性：Forge 支持显式交接新旧矩阵文件名，但文件内容仍须被所选 PyATB reader 支持。2026-10-19，完整 PyATB `sidereus-adam@5f7e132` 新编译 wheel 与 Forge `be1c0bc` 在 fresh venv 完成指定 develop/LTS Si/LCAO/nspin=1 的 prepare/execute/collect，两轨 band 数组与既有结果一致。候选限定 CPython 3.12、Linux x86_64、glibc ≥ 2.39；未修改共享环境，旧 PyATB 1.1.2 reader 对 develop 新 CSR 的限制仍在。其它 Python/平台、真实 nspin=2/4 及发布需独立验收。见[完整包安装消费证据](superpowers/evidence/2026-10-19-forge-pyatb-installed-consumption.md)。

`pyatb-band` 请求要求结构、HR、SR（可选 rR）、Fermi energy 和 line-mode K 点等由调用方显式提供的 workspace-relative inputs。prepare 默认 link workspace 内来源，`handoff_mode="copy"` 时复制；不接受绝对路径/跨 workspace 来源，不扫描 SCF 目录或从 log 推断 Fermi energy。

`nspin` 支持 1、2、4：1/4 各需要一个 HR 文件，2 需要两个；三者共享一个 SR。nspin=4 的 HR 在 manifest 标为 `matrix_hr/shared`。仅提供 rR 时生成 `rR_route` 并记为 `matrix_rr/shared`。输出包括 `inputs/STRU`、`inputs/pyatb_sources/<basename>`、`inputs/Input`、`inputs/KPT_band`。manifest entry 引用相同 envelope 中的 artifact，记录有限的 kind/spin、source/target、SHA-256；缺失或越界资源进入 `missing` 并带原因，不扫描目录。执行只启动一个本地 PyATB process；收集默认读取 `inputs/Out/Band_Structure/band_info.dat`，也可显式提供 band data/picture paths。可解析 `band_gap` 是 `reported` metric，不表示科学结论。旧 `prepare_pyatb_band`、`run_pyatb`、`collect_pyatb` 和 `run_band_sequence(..., backend="pyatb")` 保留自动 SCF discovery/兼容行为。

```json
{"schema_version":"forge.pyatb-manifest/v1","inputs":[],"outputs":[],"missing":[]}
```

### MD postprocess

`MdPostprocessRequest` 要求显式 trajectory path，可选帧视图 `start`/`end`/`stride`，analysis 名称为 `rdf`、`msd_diffusion`、`vacf_vdos`、`bond_length`、`bond_angle`。参数 `timestep`、`selection`、`elements`、`rmax`、`nbins`、`save_data`、`save_plot` 位于 JSON-safe `parameters`。`msd_diffusion` 和 `vacf_vdos` 要求正 timestep，表示筛选后相邻帧间隔；Forge 不会把 stride 隐式乘入。RDF 需要轨迹帧显式提供周期 cell。`msd`/`vacf`/`bond` 等兼容别名由上层 Paimon adapter 映射，不属于 Forge request。

服务生成 `trajectory_source.json` 和 `analysis.json`，并按 canonical mode 生成确定性数据文件和可选 PNG。解析/绘图失败不会伪造占位 PNG；诊断记录错误，collection 反映缺失产物。未知 XYZ 元素 fail-closed，不使用合成质量。MSD 可用时以 `analysis.json` 为来源返回 `diffusion_coefficient` reported metric。operation 的 `execution=not_run`、`scientific=unassessed`；collection 描述 artifact 完整性。

## Typed export

Typed export 序列化调用方明确引用的同一个 workspace 内既有 operation outcome。`source_artifact_refs` 非空且必须全属于一个已记录 source operation；Forge 读取 immutable event，保留原始 facts，在当前 workspace 写出 JSON output artifact。结果为 `execution=completed`、`collection=complete`、`scientific=unassessed`。

首版仅支持 `format="json"` 与 `overwrite_policy="fail"`。它不复制二进制 artifacts、不扫描 latest、不隐式 collect/postprocess、不发布科学报告，也不做科学验证、编排、重试、恢复或平台调度。replace/merge、archive/binary 和 multi-operation aggregation 不在当前 typed capability 内。legacy `api.export()` 与 CLI `abacus-forge export` 分开保留。

输出文档 `forge.export/v1` 包含显式 source operation 和 artifact 引用，`source_outcome` 保留原始 `forge.operation-outcome/v1`；其中的 `forge.result/v1` envelope 不变：

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
      "status": {"execution": "completed", "scientific": "unassessed", "collection": "complete"},
      "artifacts": [{
        "id": "energy", "path_rel": "outputs/energy.dat", "role": "output",
        "stage": "collect", "availability": "available", "media_type": "text/plain",
        "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "size_bytes": 4
      }],
      "metrics": [], "checks": [], "warnings": [], "diagnostics": {}
    },
    "observations": []
  }
}
```

## Workspace layout and records

推荐每次计算使用独立 workspace：

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

`reports/forge-workspace.json` 是 `forge.workspace/v1` manifest，记录 workspace 相对位置和追加顺序的事件索引。`reports/events/*.json` 是 append-only event，每个保存 event id、operation 名和 `forge.operation-outcome/v1` payload；其中嵌入的 `forge.result/v1` envelope 保持原 schema。`ArtifactRecord.path_rel` 指向 workspace 内相对路径。事件用于审计和跨操作 artifact 引用，索引中的相对路径应在 workspace root 下有效。

旧 `meta.json`、`forge-unit.json` 和 `forge-result.json` 继续作为兼容文件按既有格式写出，不被 v1 event/manifest 替换。Manifest 是可重建 discovery index，event 文件是 immutable audit facts：若 event 已原子写入而 manifest 更新在崩溃时未完成，下一次带 workspace 锁的初始化或追加会扫描有效未索引 event 并确定性补入。Forge 不声称跨多个 event/manifest 文件具有原子提交。

workspace event 是 audit record，不是 mutable last-result 文件；更新不应覆盖既有事件。typed export 读取历史 event 而不改变 source event。typed postprocess 的 source/input 与生成 output 均使用 workspace-relative artifact path，不向 outcome 泄露绝对路径。

## Legacy property manifest

`charge-density`、`spin-density` 和 `charge-diff` 的 legacy post 结果可能附带 `diagnostics.property_manifest`（`forge.property-manifest/v1`）：`inputs` 列出明确选中的 cube source，`outputs` 列出派生 cube 和 metrics report，`missing` 列出缺失、越界或不可读位置。entry 复用同一结果 artifact id、SHA-256 和文件大小。ABACUS 默认 `inputs/OUT.<suffix>/` 仅在文件不存在时作为 canonical expected path；兼容 glob 命中的变体保留实际相对路径。该 manifest 不新增 typed property capability。

```json
{
  "schema_version": "forge.property-manifest/v1",
  "task": "spin-density",
  "inputs": [],
  "outputs": [],
  "missing": []
}
```


## Direct NAO-COHP 与有限能力元数据

`pyatb-cohp` 是独立的 PyATB 薄适配；现有 `cohp/postprocess` 的 IAO 方法不变。
请求字段以 `schema pyatb-cohp prepare`（以及 execute/collect）为准，用法见
[指南](guide.md#direct-nao-cohp)。输入 HR 单位固定 Ry，Fermi energy 和绝对能量窗口为 eV；
输出谱的纵轴无量纲，ICOHP 为 eV。metadata 保留原始/展示符号、能量平移、
零温 `E <= EF` 占据积分、pair convention/factor 和轨道选择事实。collect 校验
identical/disjoint orbital-set pair 语义并拒绝部分重叠；不执行生成的绘图脚本，
也不判断科学可接受性。
当前验证的 PyATB baseline 是 `sidereus-adam@18c9ff6`，包含修复单字母 uppercase
atom label 解析的 PR #1。含 `O` 等元素的 STRU 必须使用该 commit 或等价修复。

`capabilities` 增加顶层 `contracts` map，目前只覆盖 `cohp` 和 `pyatb-cohp` 的
方法、输入和结果语义。operation、字段与默认值仍从现有 descriptor/schema 查询；
该 map 不代表全部能力已完成契约目录建设。

现有 property pack 的 `diagnostics.property_manifest` 继续保持 experimental。
[消费示例](../examples/README.md#property-manifest-consumer) 按 role/origin/source artifact 引用选择
派生 cube，并核验路径、大小和摘要；它没有引入新的 typed operation 或 Paimon 运行时依赖。

## Polarization collection and BEC postprocess

这两个 operation 的实施状态、边界和验收记录见[有界 BEC SPEC](superpowers/specs/2026-10-21-forge-polarization-bec-design.md)
与[实施计划](superpowers/plans/2026-10-21-forge-bec-implementation.md)。请求字段以
`abacus-forge schema polarization collect` 和 `abacus-forge schema bec postprocess` 为准；
本页不复制字段表。`auto` 分支模式要求调用方提供可信的 `max_step_fraction`，并为路径提供
零位移参考；`explicit` 模式要求调用方为使用的每个样本提供整数 branch offsets。请求列可为原子/轴子集，
所以 `requested_complete` 不等于 `full_tensor_complete`。条件连续性只在调用方给定上界成立时适用，
Forge 不据此判断科学可接受性。缺项按列报告，legacy BEC pack 不被新路径数值替换。
