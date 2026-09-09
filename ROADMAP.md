# ABACUS-Forge 路线图

本文件记录 `ABACUS-Forge` 的后续规划，用于与当前已实现能力文档分离。
当前可用接口、CLI 示例与 Python API 用法请参阅 [README.md](./README.md)；开发入口与边界请参阅 [AGENTS.md](./AGENTS.md)。

## 当前阶段
- Stage 3 已合并：SCF 的 typed Python services 与 Agent-first CLI 共用请求、结果和错误语义，当前 maturity 为 experimental。
- Stage 4 首批已实现：`relax` 与 `cell-relax` 通过四个 typed Python/Agent-first CLI operation（`prepare`、`modify`、`execute`、`collect`）复用同一请求、结果和错误边界；两个 capability 均保持 `experimental` maturity。
- 已形成 `prepare -> modify -> execute -> collect -> export` 的最小执行闭环，`run` 作为兼容别名保留。
- 输入三件套 `INPUT / STRU / KPT` 已具备 Python API，并逐步补齐 CLI 闭环。
- `collect` 已覆盖基础能量、费米能级、带隙、力、应力、压力、virial、relax 结果与关键工件索引。
- ABACUS task profile 的 `dft_functional` 默认已显式固定为 `pbe`，调用方参数仍可覆盖。
- Relax collection 返回可用的能量、力/应力/relax parser facts、电子收敛观察和 workspace-relative 最终结构 artifact；`scientific` 保持 `unassessed`，不把观察转换为物理接受结论。
- `band` / `dos` 单任务输入已对齐 ABACUS NSCF 语义；`run_band_sequence` / `run_dos_sequence` 提供本地 `SCF -> NSCF` 组合入口。
- `band` sequence 已支持 `backend="pyatb"`，将 LCAO SCF matrix files 转为 PyATB `Input` 并收集 PyATB band artifacts。
- KPT line-mode 已使用 ABACUS 原生 `kx ky kz npoints [#label]` 格式，并保留旧 `segments` payload 兼容。
- 已初步实现 Forge-level 实验性 property pack：`convergence`、`charge-density`、`spin-density`、`charge-diff`、`elf`、`bader`、`workfunc`、`vacancy`、`bec` 均提供 Python API 与 CLI `prepare|run|post` 入口。
- property pack 目前仅完成 mock/fixture 回归，未经逐项真实 ABACUS 操作/解析验收；不自动进入 ABACUS Agent（Paimon）v1.3 稳定能力面。
- property pack 只承担本地输入生成、子目录 runner、cube/文本后处理与 JSON 汇总。
- 当前 Forge 测试基线：`conda run -n paimon python -m pytest -q`。
- 可选 typed Relax real smoke 只复制用户提供的 prepared workspace，并通过 machine CLI 分别执行和收集；未提供真实输入时不产生 release evidence。

## 近期方向
- 输入保真与 typed collect/core 收口按 [2026-09-09 PLAN](docs/superpowers/plans/2026-09-09-forge-core-fidelity.md) 推进；[参考证据](docs/superpowers/plans/2026-09-09-forge-core-fidelity-references.md) 记录 Paimon v1.2、abacustest、abacuslab 和 abacuscopilot 的复用与差异。
- 后续单独收敛 typed prepare 的 PP/ORB 映射和资产搬运：明确来源、覆盖优先级、copy/link、路径包含性、重名与缺失诊断；保留 STRU 引用不等于自动备齐计算资产。
- 继续增强 CLI 与文档的一致性，确保 README、`--help`、pytest 同步。
- 继续补强 diagnostics 与错误报告的清晰度。
- 在不越过边界的前提下，为更上层 workflow 提供更稳定的输入与 collect 基元。
- 将 `test/sai-nio-forge` 中验证过的 Slurm harness 继续保持在 Forge 外层；Forge 本体只吸收由 trace 暴露出的格式、artifact、diagnostics 补强。
- 继续维护首批 relax/cell-relax 的 prepare、modify、execute、collect；正常结束、电子/离子收敛和解析完整性分别作为观察返回，执行与收集状态沿用冻结契约。
- Stage 4 首批之外仍待交付 typed MD、独立 `postprocess`/`export` operation、PyATB engine boundary，以及更多 property-pack 的真实 smoke；这些批次不由本次 relax/cell-relax 交付代替。
- 固化 SCF->NSCF artifact handoff 规则：电荷、矩阵、最终结构、DOS/PyATB 后处理所需文件要有明确 manifest，而不是只依赖目录名约定。
- 扩展 PyATB artifact schema：区分 spin up/down band data、band PDF/PNG、`band_info.dat` 指标和 PyATB `Out/input.json`，并把 spin-polarized shared overlap matrix 场景纳入回归。
- 将 property pack 的 mock/fixture 覆盖推进到真实 ABACUS smoke：优先顺序为 `convergence -> spin-density/charge-diff -> workfunc -> vacancy -> bec`。
- 已落地可选、实验性的 atst-tools NEB engine adapter：以 Forge 的 `prepare -> execute -> postprocess` 单元承接配置、图像执行事实、链路日志和后处理产物；NEB 图像/链路编排及并行执行委托 atst-tools。该能力暂不晋升稳定面；发布前仍须单独通过 atst-tools 安装与版本/API 锁定、干净环境 import/process 验证，以及真实 NEB smoke 门禁。
- 2026-09-09 已用当前 `atst-tools` `2.2.4` 可执行文件完成 Forge machine-CLI 的实际进程契约 smoke（`prepare`、`execute --dry-run`、`postprocess`）及临时 workspace 产物/审计检查；该检查未启动 ABACUS，不构成真实 NEB workflow 证据。
- 2026-09-09 已通过 Forge wheel 在全新 Python 3.13 venv 中的安装/import/console-entry-point 检查，且未安装或导入 `abacus-agent-tools`、`abacustest`、AiiDA 或 `atst-tools`；这只覆盖 Forge 自身的 clean package gate，不替代 ATST 进程隔离与真实 NEB workflow 门禁。
- 为 cube family 补齐更严格的 artifact manifest：明确 charge cube、spin cube、potential cube、ELF cube、Bader 输出和后处理派生产物的来源。
- 在独立仓内重建可复现的真实 ABACUS/PyATB smoke 证据，不依赖已结项 PAIMON 的外部 trace 目录。

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
- atst-tools 只作为可选 NEB engine adapter：其图像/链路编排与执行语义由 atst-tools 负责，Forge 不把它变成核心依赖，也不承接 Slurm/站点启动或上层编排。
- 不在 Forge core 中引入平台化 UI 或任务管理逻辑；本地 TUI 若实现，只作为 Python API/结构化 CLI envelope 之上的可选薄壳。
- 新增 property pack 不自动进入 PAIMON v1.3 能力面；进入 Agent/协议适配层前需要另行评估契约、用户体验与真实运行门禁。
