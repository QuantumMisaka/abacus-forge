# ABACUS-Forge 路线图

本文件记录 `ABACUS-Forge` 的后续规划，用于与当前已实现能力文档分离。
当前可用接口、CLI 示例与 Python API 用法请参阅 [README.md](./README.md)；开发入口与边界请参阅 [AGENTS.md](./AGENTS.md)。

## 当前阶段
- 已形成 `prepare -> modify -> run -> collect -> export` 的最小执行闭环。
- 输入三件套 `INPUT / STRU / KPT` 已具备 Python API，并逐步补齐 CLI 闭环。
- `collect` 已覆盖基础能量、费米能级、带隙、力、应力、压力、virial、relax 结果与关键工件索引。
- `band` / `dos` 单任务输入已对齐 ABACUS NSCF 语义；`run_band_sequence` / `run_dos_sequence` 提供本地 `SCF -> NSCF` 组合入口。
- `band` sequence 已支持 `backend="pyatb"`，将 LCAO SCF matrix files 转为 PyATB `Input` 并收集 PyATB band artifacts。
- KPT line-mode 已使用 ABACUS 原生 `kx ky kz npoints [#label]` 格式，并保留旧 `segments` payload 兼容。
- 已初步放开首批模板外的 Forge-level property pack：`convergence`、`charge-density`、`spin-density`、`charge-diff`、`elf`、`bader`、`workfunc`、`vacancy`、`bec` 均提供 Python API 与 CLI `prepare|run|post` 入口。
- property pack 只承担本地输入生成、子目录 runner、cube/文本后处理与 JSON 汇总；不改变 PAIMON 主仓 `scf/relax/band/dos` 稳定模板范围。
- 当前 Forge 测试基线：`PYTHONNOUSERSITE=1 conda run -n paimon python -m pytest deps/abacus-forge/tests -q`。
- SAI NiO trace smoke 已落在 `test/sai-nio-forge/20260509133012`：ABACUS LTS 单 GPU 完成 `cell-relax -> DOS(SCF/NSCF)` 与 Band SCF，PyATB CPU 后处理完成并收集 `band_info.dat` / `band_up.dat` / `band_dn.dat` / `band.pdf`。

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

## 中期方向
- 进一步补齐更多 ABACUS 输出指标解析。
- 评估与 `aiida-abacus` 的薄边界对接点，但不把 AiiDA 语义下沉到 Forge。
- 在保持单工作目录原子语义的前提下优化本地执行体验。
- 当 property pack 经过真实 smoke 后，再由 `aiida-abacus` 选择成熟 Forge API 装配成 AiiDA DAG；Forge 本体仍不承接 Group/provenance/站点策略。

## 明确延后项
- `phonon` / `elastic` 等厚工作流只保留本地 pack，不扩展为平台工作流。
- Slurm、Bohrium、DPDispatcher 等调度与平台能力不下沉到 Forge。
- 不在 Forge 中引入平台化 UI 或任务管理逻辑。
- 新增 property pack 不自动进入 PAIMON 主仓首批 IntentSpec/task template；进入协议层前需要另行评估契约、AiiDA DAG 和真实运行门禁。
