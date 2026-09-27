# ABACUS-Forge 路线图

本文件记录 `ABACUS-Forge` 的后续规划，用于与当前已实现能力文档分离。
当前可用接口、CLI 示例与 Python API 用法请参阅 [README.md](./README.md)；开发入口与边界请参阅 [AGENTS.md](./AGENTS.md)。

## 当前阶段

2026-09-13 版本政策已[收口并形成实施计划](docs/superpowers/plans/2026-09-13-forge-engine-version-policy.md)；native 兼容增量与离线 Stage 0（含 canonical checkout 四 capability parity 和调用隔离矩阵）已集成 main 并通过门禁，可安装 extra、真实双轨发布证据和 Paimon 迁移仍待后续验收。下列历史记录中的“typed handoff 只认旧名”和“缺 STRU_FINAL 即 partial”归因已校正：显式 handoff 不受旧名白名单限制，Relax 保留既有旧候选兼容；LTS 个案原因待原始 diagnostics 核验，历史运行数字保留。

- Stage 3 已合并：SCF 的 typed Python services 与 Agent-first CLI 共用请求、结果和错误语义，当前 maturity 为 experimental。
- Stage 4 首批已实现：`relax` 与 `cell-relax` 通过四个 typed Python/Agent-first CLI operation（`prepare`、`modify`、`execute`、`collect`）复用同一请求、结果和错误边界；两个 capability 均保持 `experimental` maturity。
- Stage 4 typed MD 基础操作已实现：`md` 通过四个 typed Python/Agent-first CLI operation（`prepare`、`modify`、`execute`、`collect`）复用同一请求、结果和错误边界；另有独立的 typed `postprocess` operation（见下文）；`md` 保持 `experimental` maturity，默认 profile 为 PBE/NVE，专属控制项继续位于 `parameters` map。
- 2026-09-12 已为 typed `scf`、`relax`、`cell-relax` 和 `md` 收紧 calculation-profile 一致性：prepare/modify/已有 INPUT 的 execute/collect 现在按能力名校验，冲突请求在 admission 前返回 `request.schema`，外部 output-only collect 例外保留；`ForgeServices` 兼容 facade 及 legacy API/CLI 行为不变。该校验只表达输入/过程前置条件，不承担科学判断或任务编排，所有 capability 仍为 `experimental`。
- 2026-09-12 typed execute 已保留独立的 `normal_end` 观察：仅从本次 stdout 或新建/实际内容变化的 contained `running_*.log` 归因，记录 workspace-relative source；旧日志、touch-only 或歧义来源不报告，且不改变 execution/scientific 状态。该事实已通过 API/CLI parity、边界回归和全量离线门禁，所有 capability 仍为 `experimental`。
- 2026-09-13 Stage 5 候选证据已绑定当前代码/测试提交，离线门禁为 `1346 passed, 12 skipped`，clean wheel、架构、benchmark，以及隔离 serial-PW ABACUS 的 SCF/cell-relax/MD、PyATB band 和 ATST 2.2.4 process smoke（组合 `6 passed, 1352 deselected in 54.69s`）均归档于 [证据记录](docs/superpowers/evidence/2026-09-13-forge-stage5-evidence.md)；完整 ATST NEB workflow 与 Paimon v1.2 全链路 parity 仍为 `unproven`，不晋升 stable。
- 2026-09-12 已把验证用 ABACUS 迁到工作区持久 `abacus-packages/` 基座（develop `94576a801` 与 LTS `v3.10.1` 双轨，生产级 MPI+LCAO+ELPA 构建，遵循仓内 toolchain），并以 Paimon v1.2 `abacus-pp-orb` 谱系 PP/ORB 新增三个 LCAO real-smoke 门禁（Si SCF、Fe nspin=2、out_mat_hs2/out_mat_r 矩阵生成）。develop 轨 `9 passed`；LTS 轨 `8 passed, 1 failed`。两条版本兼容发现待版本策略 SPEC 裁决：develop 将 LCAO 稀疏矩阵改名为 `hrs1_nao/sr_nao/rr.csr`（typed `pyatb-band` handoff 只认旧名），LTS v3.10.1 relax 不写 `STRU_FINAL`（typed relax collection 为 `partial`）。证据见 [Stage 5 evidence](docs/superpowers/evidence/2026-09-13-forge-stage5-evidence.md) 第 5 节。
- 已形成 `prepare -> modify -> execute -> collect -> export` 的最小执行闭环，`run` 作为兼容别名保留。
- 输入三件套 `INPUT / STRU / KPT` 已具备 Python API，并逐步补齐 CLI 闭环。
- `collect` 已覆盖基础能量、费米能级、带隙、力、应力、压力、virial、relax 结果与关键工件索引。
- typed collection projection 已补齐语法确认的标量单位、`reported`/`derived`/`runtime` kind 和 workspace-contained `source_artifact_id`；不确定的单位/来源保持为空，legacy collection 元数据不变。
- 2026-09-11 已补齐当前 ABACUS 原生 collection fidelity：SCF 识别 `#SCF IS CONVERGED#` 与 `!FINAL_ETOT_IS`（eV）；Relax/cell-relax 识别 `STRU_FINAL`/`STRU_NOW`（含 CIF 及 runner 的 `inputs/OUT.*` 布局），并保留旧 `STRU_ION_D` 兼容名；typed MD 从唯一 contained `running_md.log` 收集原生热力学事实（Ry→eV、K、可选 kbar），包括 runner 的 `inputs/OUT.*` 路径，`MD_dump` 仅作为帧/步数与工件事实；legacy synthetic dump 兼容路径保持不变。
- ABACUS task profile 的 `dft_functional` 默认已显式固定为 `pbe`，调用方参数仍可覆盖。
- Relax collection 返回可用的能量、力/应力/relax parser facts、电子收敛观察和 workspace-relative 最终结构 artifact；`scientific` 保持 `unassessed`，不把观察转换为物理接受结论。
- 输入保真与中立内核收口见 [2026-09-09 PLAN](docs/superpowers/plans/2026-09-09-forge-core-fidelity.md)：原生 STRU 单位、资源/质量与 `Fe1`/`Fe2` 等物种标签保留、周期真空几何、标准化保真、SCF/Relax 事实投影，以及 typed service 与 legacy API 的下层基元共享；[参考证据](docs/superpowers/plans/2026-09-09-forge-core-fidelity-references.md) 记录 Paimon v1.2、abacustest、abacuslab 和 abacuscopilot 的复用与差异。
- `band` / `dos` 单任务输入已对齐 ABACUS NSCF 语义；`run_band_sequence` / `run_dos_sequence` 提供本地 `SCF -> NSCF` 组合入口。
- 2026-09-10 已落地独立的 typed `band.postprocess` / `dos.postprocess` service 与 Agent-first machine routing：两者均为 `experimental`，要求显式非空 source path，返回 facts-only 的 `execution=not_run` envelope、workspace-relative input/output artifacts（sha256/size）并追加一个 operation event；API 与 CLI 在隔离 workspace 中保持事实 parity。
- typed `band`/`dos` postprocess 不等同于既有 `run_band`、`run_dos`、sequence helper 或 `abacus-forge band|dos` task；后者继续保持 legacy task/sequence 语义，不被隐式改写。
- 2026-09-10 已落地独立的实验性 typed `md.postprocess`：只接受调用方明确交接的 exact trajectory，支持 RDF、漂移校正 MSD/扩散、VACF/VDOS、键长和键角五个 canonical mode；返回 trajectory provenance、analysis/data/plot facts、artifact hash/size 和单个 operation event。它不扫描 latest、不转换 `MD_dump`、不隐式执行 MD、collect 或 workflow，也不做科学验收。
- `band` sequence 已支持 `backend="pyatb"`，将 LCAO SCF matrix files 转为 PyATB `Input` 并收集 PyATB band artifacts。
- 2026-09-10 已落地独立的 typed `pyatb-band` handoff capability：仅提供 `prepare`、`execute`、`collect`，成熟度为 `experimental`。prepare 接收显式 workspace-relative STRU、HR、SR、可选 rR、Fermi 能量和 line-mode K 点，默认创建相对链接（可显式选择 copy），生成 `inputs/Input` 与 `inputs/KPT_band`；nspin=1/4 各使用一个 HR，nspin=2 使用两个 HR，rR 仅在供给时写入 route 并记为 `matrix_rr/shared`，nspin=4 的唯一 HR 在 manifest 中记为 `matrix_hr/shared`；execute 只启动一个本地 PyATB 进程；collect 只返回声明输出的 artifact、运行时和 parser facts，`band_gap` 仅为 reported metric，scientific 保持 `unassessed`。
- typed `pyatb-band` 与 legacy `prepare_pyatb_band` / `run_pyatb` / `collect_pyatb` / `run_band_sequence(..., backend="pyatb")` 分开；legacy helper 的 SCF 自动发现和原有兼容行为保持不变。
- 2026-09-10 已落地独立的 typed `export` capability：成熟度为 `experimental`，仅将同一 workspace 内由 `ArtifactRef` 显式指定的单个 operation outcome 序列化为 `forge.export/v1` JSON 文档；API 与 Agent-first machine CLI 共用同一 service，并追加一个 output artifact 与 export event。
- typed `export` 不复制二进制 artifact、不查找 latest、不隐式执行 collect/postprocess、不发布报告、不做科学验证，也不负责 workflow 编排、重试/恢复或平台调度；legacy `export` 保持原行为。
- KPT line-mode 已使用 ABACUS 原生 `kx ky kz npoints [#label]` 格式，并保留旧 `segments` payload 兼容。
- 已初步实现 Forge-level 实验性 property pack：`convergence`、`charge-density`、`spin-density`、`charge-diff`、`elf`、`bader`、`workfunc`、`vacancy`、`bec` 均提供 Python API 与 CLI `prepare|run|post` 入口。
- property pack 目前仍主要依赖 mock/fixture 回归，尚未逐项完成真实 ABACUS 操作/解析验收；`convergence`、`spin-density`、`workfunc`、`charge-diff` 各已有一次本地 serial-PW 操作/解析 smoke（详见 2026-09-11 maturity-gates plan），不自动进入 ABACUS Agent（Paimon）v1.3 稳定能力面。
- `bec` 的真实 serial-PW 试跑已确认当前 legacy pack 缺少 ABACUS 所需的逐结构 `SCF -> restart -> NSCF(gdir=1/2/3)` 阶段输入和原生 polarization 日志解析；按已批准 SPEC，不在 Forge 内补隐式多 operation 编排。本能力继续保持 experimental，待独立 BEC SPEC/PLAN 明确显式阶段交接后再推进。
- property pack 只承担本地输入生成、子目录 runner、cube/文本后处理与 JSON 汇总。
- 当前 Forge 测试基线：`conda run -n paimon python -m pytest -q`。
- 可选 typed SCF、typed Relax/cell-relax 与 typed MD real smoke 均只复制用户提供的 prepared workspace，并通过 machine CLI 分别执行和收集；三者使用各自的环境门禁，未提供真实输入时不产生 release evidence。当前已有本地 serial-PW ABACUS 的 SCF/Relax/cell-relax/MD parser-artifact smoke 证据，但仍不晋升稳定能力或科学结论；legacy SCF smoke 不能替代 typed SCF 证据。
- typed SCF real-smoke 在首次 execute 前校验输入 calculation profile，typed Relax execute/collect 使用长 parent-process 超时；这些都是 release-gate 检查，不改变生产 service 的兼容行为。
- typed MD real-smoke 还在首次 execute 前校验 `calculation=md`，拒绝复制源中已有的 collector-visible MD 生成物，并要求 collect 暴露本次 `running_md.log` 的原生热力学 facts；它只证明 operation/status/event/artifact 与 parser 边界，保持 `scientific=unassessed`，不承担轨迹质量或科学验收。
- 三类 typed real-smoke 在复制后、首次 execute 前统一拒绝其 collector 可消费的既有生成日志（包括 native `inputs/OUT.*` 域路径）；Relax 还拒绝既有最终结构，同时保留普通非生成 handoff。该 freshness 只属于 release-evidence 测试条件，不改变普通 Forge `execute`/`collect` 行为。
- 本批 typed collection metadata 实现 revision 为 `5807af1`；`1209 passed, 5 skipped` 的全量离线门禁及 clean archive/wheel 记录见门禁文档 revision `beed6d1`。
- typed prepare 已支持显式 `pseudo_sources` / `orbital_sources` 资产映射：默认 copy，contained-only relative link，缺失与冲突 fail-closed，并在 typed diagnostics、manifest 和事件中记录来源/目标及哈希 provenance；未映射 STRU 引用保留且不声明完整。

## 近期方向
- 继续增强 CLI 与文档的一致性，确保 README、`--help`、pytest 同步。
- 继续补强 diagnostics 与错误报告的清晰度。
- 在不越过边界的前提下，为更上层 workflow 提供更稳定的输入与 collect 基元。
- 将 `test/sai-nio-forge` 中验证过的 Slurm harness 继续保持在 Forge 外层；Forge 本体只吸收由 trace 暴露出的格式、artifact、diagnostics 补强。
- 继续维护首批 relax/cell-relax 的 prepare、modify、execute、collect；正常结束、电子/离子收敛和解析完整性分别作为观察返回，执行与收集状态沿用冻结契约。
- typed MD 当前交付单工作目录的准备、修改、一次本地执行、原生日志/`MD_dump` 事实收集以及独立 `postprocess`；`running_md.log` 的热力学事实与 `MD_dump` 的帧/步数事实分开投影，legacy synthetic dump 解析保持兼容。MD 后处理仍不负责 trajectory conversion、PDB/TUI、monitor、restart/resume、workflow 编排、调度、导出或科学判断；这些边界保持在 Forge 外。后续批次仍包括 PyATB properties 和更多 property-pack 的真实 smoke。
- 2026-09-10 已落地 experimental `forge.pyatb-manifest/v1`：typed PyATB prepare/collect 提供有限 kind/spin、同 envelope artifact id、哈希/大小与 missing/unavailable/malformed 事实；nspin=4 handoff 已沿用 `matrix_hr/shared` 映射。2026-09-13 已补齐 typed PyATB band 的真实 machine-process smoke；PyATB properties 和 property/composite 聚合继续 deferred。
- 继续固化 SCF->NSCF artifact handoff 规则，扩展到其他 property family 时仍需独立设计和验证。
- 当前 manifest 已覆盖 nspin=1/2/4 的 HR：nspin=1/4 为 `shared`，nspin=2 按请求顺序为 `up/down`，SR 为 `shared`，供给的 rR 为 `shared`；未供给 rR 时不创建 `matrix_rr` entry。后续若扩展到 PyATB properties、更多布局或真实运行门禁，须在独立 SPEC/PLAN 中增加映射与验证；当前 manifest 不推断这些额外语义。
- 将 property pack 的 mock/fixture 覆盖推进到真实 ABACUS smoke：当前已完成 `convergence`、`spin-density`、`workfunc`、`charge-diff` 的本地 serial-PW 兼容性 smoke；`vacancy` 可继续做独立事实门禁，`bec` 需先完成独立 SPEC/PLAN，不把隐式 SCF→NSCF 编排下沉到 Forge。
- 已落地可选、实验性的 atst-tools NEB engine adapter：以 Forge 的 `prepare -> execute -> postprocess` 单元承接配置、图像执行事实、链路日志和后处理产物；NEB 图像/链路编排及并行执行委托 atst-tools。该能力暂不晋升稳定面；发布前仍须单独通过 atst-tools 安装与版本/API 锁定、干净环境 import/process 验证，以及真实 NEB smoke 门禁。
- 2026-09-09 已用当前 `atst-tools` `2.2.4` 可执行文件完成 Forge machine-CLI 的实际进程契约 smoke（`prepare`、`execute --dry-run`、`postprocess`）及临时 workspace 产物/审计检查；该检查未启动 ABACUS，不构成真实 NEB workflow 证据。
- 2026-09-09 已通过 Forge wheel 在全新 Python 3.13 venv 中的安装/import/console-entry-point 检查，且未安装或导入 `abacus-agent-tools`、`abacustest`、AiiDA 或 `atst-tools`；这只覆盖 Forge 自身的 clean package gate，不替代 ATST 进程隔离与真实 NEB workflow 门禁。
- 2026-09-10 已落地实验性的 `forge.property-manifest/v1` legacy diagnostics projection：`charge-density`、`spin-density` 和 `charge-diff` post 记录明确选中的 cube source、派生 cube、metrics report 以及 missing/escaped/unavailable 事实；artifact id、哈希和大小复用同一结果的 artifact projection。该增量不新增 typed property capability，不做目录扫描、科学验收、workflow 编排或调度。
- cube family 的 potential/ELF/Bader 输出、更多 property 语义、跨 operation 聚合和真实运行证据仍须各自独立 SPEC/PLAN，不从当前 manifest 推断。
- 在独立仓内重建可复现的真实 ABACUS/PyATB smoke 证据，不依赖已结项 PAIMON 的外部 trace 目录；2026-09-13 已将 Paimon v1.2 历史 HR/SR/rR/STRU source 绑定到 typed machine-process harness，在隔离临时 workspace 完成 `prepare -> execute -> collect`（PyATB 1.1.2，exit 0，产出 `band_info.dat`、`band_up.dat`、`band_dn.dat`、`band.pdf`），这只证明输入/进程兼容性，不构成科学验证或稳定晋级证据；typed `pyatb-band` 继续保持 experimental。

## 中期方向
- 进一步补齐更多 ABACUS 输出指标解析。
- 完善面向 PAIMON v1.3 与其他上层编排器的薄 adapter 契约，但不把协议、平台或编排器对象语义下沉到 Forge。
- 在保持单工作目录原子语义的前提下优化本地执行体验。
- 当 property pack 经过真实 smoke 后，再由上层 adapter/workflow 选择成熟 Forge API 进行编排；Forge 本体仍不承接 provenance 存储、站点策略或恢复式工作流。

## 工程清理触发点
- Stage 3 已交付源码 AST forbidden-import 门禁、per-operation protocol 与 artifact_refs 单点构造；新增能力复用这些边界。
- 下次实质修改 workspace admission 接口时，先扫描外部使用，再收敛仅作兼容入口的 `claim_v1_operation` 别名。
- Stage 5 在全新干净环境执行安装与 import 验证，作为解除 `abacus-agent-tools`、`abacustest` 等 legacy 运行时依赖的发布门禁。

## 明确延后项
- `phonon` / `elastic` 等厚工作流只保留本地 pack，不扩展为平台工作流。2026-09-28 起 `elastic post` 可由已收集 strain/stress 拟合弹性张量与工程模量，但仍不接管调度或平台编排。
- Slurm、Bohrium、DPDispatcher 等调度与平台能力不下沉到 Forge。
- typed `export` 已作为独立实验性 operation 落地；本 capability 不把 postprocess 结果隐式导出，也不改写 legacy export。replace/merge、binary/archive 和多 operation 聚合仍需单独设计和验证。
- PyATB properties 和 property/composite 聚合仍需单独设计和验证；nspin=4 handoff 已支持，typed `pyatb-band` band process smoke 已有证据，但现有 PyATB sequence/helper 不构成该 capability 的替代实现，真实 NEB workflow 也仍未验证。
- workflow/orchestration、monitor、重试/恢复和科学判断由 Forge 外部的调用方负责；typed postprocess 只返回 parser facts，不生成 band gap/acceptance 等科学结论。
- atst-tools 只作为可选 NEB engine adapter：其图像/链路编排与执行语义由 atst-tools 负责，Forge 不把它变成核心依赖，也不承接 Slurm/站点启动或上层编排。
- 不在 Forge core 中引入平台化 UI 或任务管理逻辑；本地 TUI 若实现，只作为 Python API/结构化 CLI envelope 之上的可选薄壳。
- 新增 property pack 不自动进入 PAIMON v1.3 能力面；进入 Agent/协议适配层前需要另行评估契约、用户体验与真实运行门禁。
