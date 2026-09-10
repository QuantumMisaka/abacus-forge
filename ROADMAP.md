# ABACUS-Forge 路线图

本文件记录 `ABACUS-Forge` 的后续规划，用于与当前已实现能力文档分离。
当前可用接口、CLI 示例与 Python API 用法请参阅 [README.md](./README.md)；开发入口与边界请参阅 [AGENTS.md](./AGENTS.md)。

## 当前阶段
- Stage 3 已合并：SCF 的 typed Python services 与 Agent-first CLI 共用请求、结果和错误语义，当前 maturity 为 experimental。
- Stage 4 首批已实现：`relax` 与 `cell-relax` 通过四个 typed Python/Agent-first CLI operation（`prepare`、`modify`、`execute`、`collect`）复用同一请求、结果和错误边界；两个 capability 均保持 `experimental` maturity。
- Stage 4 typed MD 首批已实现：`md` 通过四个 typed Python/Agent-first CLI operation（`prepare`、`modify`、`execute`、`collect`）复用同一请求、结果和错误边界；`md` 保持 `experimental` maturity，默认 profile 为 PBE/NVE，专属控制项继续位于 `parameters` map。
- 已形成 `prepare -> modify -> execute -> collect -> export` 的最小执行闭环，`run` 作为兼容别名保留。
- 输入三件套 `INPUT / STRU / KPT` 已具备 Python API，并逐步补齐 CLI 闭环。
- `collect` 已覆盖基础能量、费米能级、带隙、力、应力、压力、virial、relax 结果与关键工件索引。
- ABACUS task profile 的 `dft_functional` 默认已显式固定为 `pbe`，调用方参数仍可覆盖。
- Relax collection 返回可用的能量、力/应力/relax parser facts、电子收敛观察和 workspace-relative 最终结构 artifact；`scientific` 保持 `unassessed`，不把观察转换为物理接受结论。
- 输入保真与中立内核收口见 [2026-09-09 PLAN](docs/superpowers/plans/2026-09-09-forge-core-fidelity.md)：原生 STRU 单位与资源/质量保留、周期真空几何、标准化保真、SCF/Relax 事实投影，以及 typed service 与 legacy API 的下层基元共享；[参考证据](docs/superpowers/plans/2026-09-09-forge-core-fidelity-references.md) 记录 Paimon v1.2、abacustest、abacuslab 和 abacuscopilot 的复用与差异。
- `band` / `dos` 单任务输入已对齐 ABACUS NSCF 语义；`run_band_sequence` / `run_dos_sequence` 提供本地 `SCF -> NSCF` 组合入口。
- 2026-09-10 已落地独立的 typed `band.postprocess` / `dos.postprocess` service 与 Agent-first machine routing：两者均为 `experimental`，要求显式非空 source path，返回 facts-only 的 `execution=not_run` envelope、workspace-relative input/output artifacts（sha256/size）并追加一个 operation event；API 与 CLI 在隔离 workspace 中保持事实 parity。
- typed `band`/`dos` postprocess 不等同于既有 `run_band`、`run_dos`、sequence helper 或 `abacus-forge band|dos` task；后者继续保持 legacy task/sequence 语义，不被隐式改写。
- `band` sequence 已支持 `backend="pyatb"`，将 LCAO SCF matrix files 转为 PyATB `Input` 并收集 PyATB band artifacts。
- 2026-09-10 已落地独立的 typed `pyatb-band` handoff capability：仅提供 `prepare`、`execute`、`collect`，成熟度为 `experimental`。prepare 接收显式 workspace-relative STRU、HR、SR、rR、Fermi 能量和 line-mode K 点，默认创建相对链接（可显式选择 copy），生成 `inputs/Input` 与 `inputs/KPT_band`；execute 只启动一个本地 PyATB 进程；collect 只返回声明输出的 artifact、运行时和 parser facts，`band_gap` 仅为 reported metric，scientific 保持 `unassessed`。
- typed `pyatb-band` 与 legacy `prepare_pyatb_band` / `run_pyatb` / `collect_pyatb` / `run_band_sequence(..., backend="pyatb")` 分开；legacy helper 的 SCF 自动发现和原有兼容行为保持不变。
- KPT line-mode 已使用 ABACUS 原生 `kx ky kz npoints [#label]` 格式，并保留旧 `segments` payload 兼容。
- 已初步实现 Forge-level 实验性 property pack：`convergence`、`charge-density`、`spin-density`、`charge-diff`、`elf`、`bader`、`workfunc`、`vacancy`、`bec` 均提供 Python API 与 CLI `prepare|run|post` 入口。
- property pack 目前仅完成 mock/fixture 回归，未经逐项真实 ABACUS 操作/解析验收；不自动进入 ABACUS Agent（Paimon）v1.3 稳定能力面。
- property pack 只承担本地输入生成、子目录 runner、cube/文本后处理与 JSON 汇总。
- 当前 Forge 测试基线：`conda run -n paimon python -m pytest -q`。
- 可选 typed Relax real smoke 只复制用户提供的 prepared workspace，并通过 machine CLI 分别执行和收集；未提供真实输入时不产生 release evidence。
- typed prepare 已支持显式 `pseudo_sources` / `orbital_sources` 资产映射：默认 copy，contained-only relative link，缺失与冲突 fail-closed，并在 typed diagnostics、manifest 和事件中记录来源/目标及哈希 provenance；未映射 STRU 引用保留且不声明完整。

## 近期方向
- 继续增强 CLI 与文档的一致性，确保 README、`--help`、pytest 同步。
- 继续补强 diagnostics 与错误报告的清晰度。
- 在不越过边界的前提下，为更上层 workflow 提供更稳定的输入与 collect 基元。
- 将 `test/sai-nio-forge` 中验证过的 Slurm harness 继续保持在 Forge 外层；Forge 本体只吸收由 trace 暴露出的格式、artifact、diagnostics 补强。
- 继续维护首批 relax/cell-relax 的 prepare、modify、execute、collect；正常结束、电子/离子收敛和解析完整性分别作为观察返回，执行与收集状态沿用冻结契约。
- typed MD 当前只交付单工作目录的准备、修改、一次本地执行和事实收集；`MD_dump`/日志只作为可用事实返回。本批次尚未交付 MD 专用 trajectory conversion 或独立 `postprocess`/`export`；已交付的 typed band/DOS postprocess 与 typed `pyatb-band` handoff 是彼此独立的实验性 capability 边界。monitor、workflow 编排、restart/resume、调度与科学判断保持在 Forge 外。后续批次仍包括 PyATB properties、nspin 4、typed export 和更多 property-pack 的真实 smoke。
- 2026-09-10 已落地 experimental `forge.pyatb-manifest/v1`：typed PyATB prepare/collect 提供有限 kind/spin、同 envelope artifact id、哈希/大小与 missing/unavailable/malformed 事实；PyATB properties、nspin 4、typed `export` 和 real-smoke 继续 deferred。
- 继续固化 SCF->NSCF artifact handoff 规则，扩展到其他 property family 时仍需独立设计和验证。
- 当前 manifest 已覆盖 nspin=1/2 的 HR（shared 或 up/down）以及 shared SR/rR；后续若扩展到 PyATB properties、nspin 4、更多布局或真实运行门禁，须在独立 SPEC/PLAN 中增加映射与验证；当前 manifest 不推断这些语义。
- 将 property pack 的 mock/fixture 覆盖推进到真实 ABACUS smoke：优先顺序为 `convergence -> spin-density/charge-diff -> workfunc -> vacancy -> bec`。
- 已落地可选、实验性的 atst-tools NEB engine adapter：以 Forge 的 `prepare -> execute -> postprocess` 单元承接配置、图像执行事实、链路日志和后处理产物；NEB 图像/链路编排及并行执行委托 atst-tools。该能力暂不晋升稳定面；发布前仍须单独通过 atst-tools 安装与版本/API 锁定、干净环境 import/process 验证，以及真实 NEB smoke 门禁。
- 2026-09-09 已用当前 `atst-tools` `2.2.4` 可执行文件完成 Forge machine-CLI 的实际进程契约 smoke（`prepare`、`execute --dry-run`、`postprocess`）及临时 workspace 产物/审计检查；该检查未启动 ABACUS，不构成真实 NEB workflow 证据。
- 2026-09-09 已通过 Forge wheel 在全新 Python 3.13 venv 中的安装/import/console-entry-point 检查，且未安装或导入 `abacus-agent-tools`、`abacustest`、AiiDA 或 `atst-tools`；这只覆盖 Forge 自身的 clean package gate，不替代 ATST 进程隔离与真实 NEB workflow 门禁。
- 为 cube family 补齐更严格的 artifact manifest：明确 charge cube、spin cube、potential cube、ELF cube、Bader 输出和后处理派生产物的来源。
- 在独立仓内重建可复现的真实 ABACUS/PyATB smoke 证据，不依赖已结项 PAIMON 的外部 trace 目录；在此之前，typed `pyatb-band` 只保持 experimental，不声称真实运行或科学验证证据。

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
- `phonon` / `elastic` 等厚工作流只保留本地 pack，不扩展为平台工作流。
- Slurm、Bohrium、DPDispatcher 等调度与平台能力不下沉到 Forge。
- typed `export` 仍是独立的后续 operation；本批次不把 postprocess 结果隐式导出或改写为 legacy export。
- PyATB properties、nspin 4、typed `export` 和 property/composite 聚合仍需单独设计和验证；现有 PyATB sequence/helper 不构成 typed `pyatb-band` capability 的替代实现或真实运行证据。
- workflow/orchestration、monitor、重试/恢复和科学判断由 Forge 外部的调用方负责；typed postprocess 只返回 parser facts，不生成 band gap/acceptance 等科学结论。
- atst-tools 只作为可选 NEB engine adapter：其图像/链路编排与执行语义由 atst-tools 负责，Forge 不把它变成核心依赖，也不承接 Slurm/站点启动或上层编排。
- 不在 Forge core 中引入平台化 UI 或任务管理逻辑；本地 TUI 若实现，只作为 Python API/结构化 CLI envelope 之上的可选薄壳。
- 新增 property pack 不自动进入 PAIMON v1.3 能力面；进入 Agent/协议适配层前需要另行评估契约、用户体验与真实运行门禁。
