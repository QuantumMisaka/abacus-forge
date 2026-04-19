# ABACUS-Forge（算筹工场）

> **开发约束与架构禁区提示**：关于本项目在 PAIMON 架构中的核心接口抽象原则与开发禁区（如禁止引入的包与处理的逻辑），请在开发前严格查阅 [AGENTS.md](./AGENTS.md)。

**一句话定位：**ABACUS-Forge 是一个面向本机/HPC 环境的 **ABACUS 执行基座**，提供“输入准备 → 计算拉起 → 结果采集/分析”的标准化能力。同时以 Python 库形式，基于 `aiida-abacus` 插件嵌入 AiiDA 等工作流系统。

## 开发目标与参考
- **开发目标**：一个面向本机/HPC 环境的 **ABACUS 执行基座**，提供“输入准备 → 计算拉起 → 结果采集/分析”的标准化能力。同时以 Python 库形式，基于 `aiida-abacus` 插件嵌入 AiiDA 等工作流系统。
- **开发重要参考**：`abacus-test` 库已有实现。

## 边界与约束
- **更基础、更轻量**：基于 `abacus-test` 开发更轻量级的执行基座。
- **不依赖云服务**：不依赖 Bohrium, DPDispatcher 等服务。
- **服务场景**：仅服务于本机终端快速使用，以及通过 `import` 等方式接入到 `aiida-abacus` 中。
- **生态集成**：基于 AiiDA 生态调用 workflow 完成 ABACUS 计算模拟任务。

## 适用场景
- 在服务器上快速把结构文件转成 ABACUS 输入目录（INPUT/KPT/STRU + PP/ORB 组织）
- 单个 ABACUS 任务（SCF/relax/cell-relax/MD/NSCF 等）的启动和结果提取
- 声子谱、弹性模量等复杂任务的集成工作流（prepare/run/post）
- 作为 Python 库嵌入到 AiiDA、ASE、或自研 workflow 中，作为统一的 ABACUS 执行与解析底座

## 核心能力（规划接口）
### 1) 输入准备（prepare）
- 结构输入：`cif` / `POSCAR` / `STRU`
- 生成：`INPUT` / `KPT` / `STRU` 及 PP/ORB 文件组织（copy/link 策略可配置）
- 参数注入：以“模板 + 覆盖”的方式生成输入（便于批量与可复现）

### 2) 本机执行（run）
- 统一 Runner 抽象（默认 `LocalRunner`：`mpirun` + `OMP_NUM_THREADS`）
- 资源参数显式化：MPI ranks / OpenMP threads / 绑定策略（按需扩展）
- 清晰失败模式：输入错误、运行时错误、未收敛、输出不完整等，均以结构化状态返回

### 3) 结果采集与分析（collect/analyze）
- 结构化指标：收敛、能量、力、应力、费米能级、带隙（按可用性返回）
- 工件索引：自动记录关键输出文件路径（log、OUT.*、BANDS、PDOS、cube 等）
- 可选导出：`result.json` / `metrics.json` / 图像或表格文件（按工作流提供）

### 4) 复杂任务的集成工作流（workflows：prepare → run → post）
重点案例：
- `phonon`：位移超胞生成 → 批量力计算 → phonopy 后处理 → 频散/声子 DOS/关键诊断
- `elastic`：应变集合生成 → 批量应力计算 → 拟合弹性张量 → 模量与派生量输出
- 要求：集成工作流需要的输入准备，计算和结果分析应当解耦，且集成工作流搭建应直接基于已有单元模块。在单元模块开发完成前，不开发集成工作流。

## 非目标（明确不做）
- 不内置 Bohrium, DPDispatcher 的提交/追踪/下载能力
- 不提供平台化 Web UI（可产出 HTML/图片作为工件，但不做服务端平台）
- 不做“智能选参/专家系统”（这属于上层 Agent 或 workflow 策略层）

## 快速上手（CLI 示例，待实现）
> 下列命令为目标接口示例，最终以 `--help` 为准。

```bash
# 1) 从结构文件准备输入
abacus-forge prepare --stru Si.cif --job scf --pp /path/to/pp --orb /path/to/orb -o runs/Si_scf

# 2) 运行（本机 mpirun）
abacus-forge run runs/Si_scf --mpi 32 --omp 1

# 3) 收集结果（输出 JSON + 关键文件索引）
abacus-forge collect runs/Si_scf --json > result.json

# 4) 集成工作流的终端调用：待设计
```

## 作为 Python 库使用（示例，待实现）
```python
from abacus_forge import Workspace, LocalRunner
from abacus_forge.workflows import elastic

ws = Workspace("runs/Si_elastic")
runner = LocalRunner(mpi=32, omp=1)

result = elastic.run(structure="Si.cif", workspace=ws, runner=runner)
print(result.metrics)
```

## 目录规范与 provenance（建议）
每次运行建议生成一个可追溯目录，例如：
```
runs/<run_id>/
  meta.json
  inputs/
  outputs/
  reports/   # json/csv/png 等可选工件
```

## 路线图（建议）
- **v0.1**：workspace/元数据 + prepare/run/collect（scf/relax）+ CLI 雏形
- **v0.2**：elastic 工作流（prepare/run/post）+ 更完整的失败模式与测试集
- **v0.3**：phonon 工作流（prepare/run/post）+ 本机并行执行策略优化

## 贡献与协作
欢迎 issue/PR。建议提交内容遵循：
- 小步提交、清晰变更说明
- 为解析器/工作流补充可复现的测试用例（golden outputs）

---

### Repository description（用于 GitHub Description）
> **ABACUS execution substrate for local/HPC**: prepare → run → collect/analyze, with built-in phonon/elastic workflows and a Python API for AiiDA-style workflow integration.

