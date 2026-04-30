# ABACUS-Forge 路线图

本文件记录 `ABACUS-Forge` 的后续规划，用于与当前已实现能力文档分离。
当前可用接口、CLI 示例与 Python API 用法请参阅 [README.md](./README.md)；开发入口与边界请参阅 [AGENTS.md](./AGENTS.md)。

## 当前阶段
- 已形成 `prepare -> modify -> run -> collect -> export` 的最小执行闭环。
- 输入三件套 `INPUT / STRU / KPT` 已具备 Python API，并逐步补齐 CLI 闭环。
- `collect` 已覆盖基础能量、费米能级、带隙、力、应力、压力、virial、relax 结果与关键工件索引。

## 近期方向
- 继续增强 CLI 与文档的一致性，确保 README、`--help`、pytest 同步。
- 继续补强 diagnostics 与错误报告的清晰度。
- 在不越过边界的前提下，为更上层 workflow 提供更稳定的输入与 collect 基元。

## 中期方向
- 进一步补齐更多 ABACUS 输出指标解析。
- 评估与 `aiida-abacus` 的薄边界对接点，但不把 AiiDA 语义下沉到 Forge。
- 在保持单工作目录原子语义的前提下优化本地执行体验。

## 明确延后项
- `phonon` / `elastic` 等厚工作流不在 Forge 当前阶段直接实现。
- Slurm、Bohrium、DPDispatcher 等调度与平台能力不下沉到 Forge。
- 不在 Forge 中引入平台化 UI 或任务管理逻辑。
