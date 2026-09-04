# ABACUS-Forge 路线图

本文件记录 `ABACUS-Forge` 的后续规划，用于与当前已实现能力文档分离。
当前可用接口、CLI 示例与 Python API 用法请参阅 [README.md](./README.md)；开发入口与边界请参阅 [AGENTS.md](./AGENTS.md)。

## 当前阶段
- 已形成 `prepare -> modify -> execute -> collect -> export` 的最小执行闭环，`run` 作为兼容别名保留。
- 输入三件套 `INPUT / STRU / KPT` 已具备 Python API，并逐步补齐 CLI 闭环。
- `collect` 已覆盖基础能量、费米能级、带隙、力、应力、压力、virial、relax 结果与关键工件索引。
- `band` / `dos` 单任务输入已对齐 ABACUS NSCF 语义；`run_band_sequence` / `run_dos_sequence` 提供本地 `SCF -> NSCF` 组合入口。
- `band` sequence 已支持 `backend="pyatb"`，将 LCAO SCF matrix files 转为 PyATB `Input` 并收集 PyATB band artifacts。
- KPT line-mode 已使用 ABACUS 原生 `kx ky kz npoints [#label]` 格式，并保留旧 `segments` payload 兼容。
- 已初步实现 Forge-level 实验性 property pack：`convergence`、`charge-density`、`spin-density`、`charge-diff`、`elf`、`bader`、`workfunc`、`vacancy`、`bec` 均提供 Python API 与 CLI `prepare|run|post` 入口。
- property pack 目前仅完成 mock/fixture 回归，未经逐项真实 ABACUS 操作/解析验收；不自动进入 ABACUS Agent（Paimon）v1.3 稳定能力面。
- property pack 只承担本地输入生成、子目录 runner、cube/文本后处理与 JSON 汇总。
- 当前 Forge 测试基线：`conda run -n paimon python -m pytest -q`。

## 近期方向
- 继续增强 CLI 与文档的一致性，确保 README、`--help`、pytest 同步。
- 继续补强 diagnostics 与错误报告的清晰度。
- 在不越过边界的前提下，为更上层 workflow 提供更稳定的输入与 collect 基元。
- 将 `test/sai-nio-forge` 中验证过的 Slurm harness 继续保持在 Forge 外层；Forge 本体只吸收由 trace 暴露出的格式、artifact、diagnostics 补强。
- 优先补齐 relax/cell-relax 完成态语义：`normal_end=true` 但未达到收敛阈值时应在 metrics 中区分 `abacus_normal_end`、`converged` 与 `status`。
- 固化 SCF->NSCF artifact handoff 规则：电荷、矩阵、最终结构、DOS/PyATB 后处理所需文件要有明确 manifest，而不是只依赖目录名约定。
- 扩展 PyATB artifact schema：区分 spin up/down band data、band PDF/PNG、`band_info.dat` 指标和 PyATB `Out/input.json`，并把 spin-polarized shared overlap matrix 场景纳入回归。
- 将 property pack 的 mock/fixture 覆盖推进到真实 ABACUS smoke：优先顺序为 `convergence -> spin-density/charge-diff -> workfunc -> vacancy -> bec`。
- 为 cube family 补齐更严格的 artifact manifest：明确 charge cube、spin cube、potential cube、ELF cube、Bader 输出和后处理派生产物的来源。
- 在独立仓内重建可复现的真实 ABACUS/PyATB smoke 证据，不依赖已结项 PAIMON 的外部 trace 目录。

## 中期方向
- 进一步补齐更多 ABACUS 输出指标解析。
- 完善面向 PAIMON v1.3 与其他上层编排器的薄 adapter 契约，但不把协议、平台或编排器对象语义下沉到 Forge。
- 在保持单工作目录原子语义的前提下优化本地执行体验。
- 当 property pack 经过真实 smoke 后，再由上层 adapter/workflow 选择成熟 Forge API 进行编排；Forge 本体仍不承接 provenance 存储、站点策略或恢复式工作流。

## 工程清理触发点
- Stage 3 的 Agent-first CLI 门禁加入源码 AST forbidden-import 检查，防止 Forge 运行时重新依赖 AiiDA、ATP/MCP、平台调度或 legacy 工具包。
- Stage 4 开始前按 SPEC 将首个 SCF `ForgeServices` facade 收敛为 per-operation protocol；届时把 `artifact_refs` 归一到单一注入点。
- 下次实质修改 workspace admission 接口时，先扫描外部使用，再收敛仅作兼容入口的 `claim_v1_operation` 别名。
- Stage 5 在全新干净环境执行安装与 import 验证，作为解除 `abacus-agent-tools`、`abacustest` 等 legacy 运行时依赖的发布门禁。

## 明确延后项
- `phonon` / `elastic` 等厚工作流只保留本地 pack，不扩展为平台工作流。
- Slurm、Bohrium、DPDispatcher 等调度与平台能力不下沉到 Forge。
- 不在 Forge core 中引入平台化 UI 或任务管理逻辑；本地 TUI 若实现，只作为 Python API/结构化 CLI envelope 之上的可选薄壳。
- 新增 property pack 不自动进入 PAIMON v1.3 能力面；进入 Agent/协议适配层前需要另行评估契约、用户体验与真实运行门禁。
