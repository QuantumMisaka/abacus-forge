# ABACUS-Forge 后续开发与实现计划（P0 + 部分 P1）

## Summary

- 目标：基于二次全面审查结论，先完成当前波次最明确、收益最高且风险最低的一组开发项：`P0` 的 `LocalRunner` 前置检查与 Forge 真输出/集成回归测试，再补一个最小范围的 `P1`，把主仓 `forge_adapter` 中已与 Forge 能力重叠的样本输出生成逻辑下沉到 Forge。
- 实施范围：
  - `deps/abacus-forge/` 子模块源码与测试；
  - 必要时最小修改 `src/paimon/forge_adapter.py` 和 `tests/test_forge_adapter.py`；
  - 不扩展到 `prepare_ops/pert_stru`、CI 工作流、phonon/elastic 等更大范围能力。
- 成功标准：
  - `LocalRunner` 在执行前能显式校验可执行文件存在性，并给出清晰失败信息；
  - Forge 自身新增围绕“真实/准真实输出目录”的回归测试，而不只依赖纯 mock 文本；
  - 主仓 validation 路径中原本位于 `forge_adapter.py` 的样本产物生成逻辑，最小范围下沉到 Forge；
  - 相关测试通过，且不引入工作流越界。

## Current State Analysis

### 已确认的代码现状

- `deps/abacus-forge/src/abacus_forge/runner.py`
  - 当前 `LocalRunner.run()` 直接调用 `subprocess.run(...)`。
  - 目前没有执行前的显式可执行文件检查；若找不到二进制，将依赖底层异常。
- `deps/abacus-forge/src/abacus_forge/api.py`
  - 已具备 `prepare/run/collect/export` 主 API。
  - `collect()` 已支持 `inputs_snapshot`、`structure_snapshot`、`final_structure_snapshot` 以及 `band/dos/pdos` 摘要回收。
- `deps/abacus-forge/src/abacus_forge/band_data.py`
  - 已有 `BandData` 与 `write_sample_band_artifacts()`。
- `deps/abacus-forge/src/abacus_forge/dos_data.py`
  - 已有 `DOSData`、`PDOSData` 与 `write_sample_dos_artifacts()`、`write_sample_pdos_artifacts()`。
- `src/paimon/forge_adapter.py`
  - 当前 `_write_mock_analysis_outputs()` 仍在主仓里手工拼装 relax/band/dos/pdos 的样本输出与 `metrics_*.json`。
  - 其中 band/dos/pdos 的样本文件写出，已与 Forge 子模块内部的样本工件辅助函数重叠。
- 测试现状：
  - Forge 子模块已有 `deps/abacus-forge/tests/test_api.py`、`test_cli.py`、`test_input_io.py`、`test_structure.py`。
  - 主仓已有 `tests/test_forge_adapter.py`，当前主要覆盖“单一 Forge 入口”和结果导出映射，仍以 monkeypatch/假对象为主。

### 已确认的审查结论来源

- [abacus-forge-second-round-audit-report-2026-04-28.md](file:///home/pku-jianghong/liuzhaoqing/work/sidereus/paimon/docs/develop/abacus-forge-second-round-audit-report-2026-04-28.md)
  - `AF-03`：缺乏执行文件存在性检查；
  - `P0`：补齐 `LocalRunner` 前置检查逻辑；
  - `P0`：在主仓 `tests/` 中增加对 `deps/abacus-forge` 真输出的集成回归测试；
  - `P1`：将 `forge_adapter.py` 中残留的 Mock 解析/样本逻辑尽量下沉到 Forge。
- [abacus-forge-submodule-review-2026-04-25.md](file:///home/pku-jianghong/liuzhaoqing/work/sidereus/paimon/docs/develop/abacus-forge-submodule-review-2026-04-25.md)
  - Forge 应优先增强稳定原语与可复用单元，而不是继续让主仓长期承担私有 helper。

### 本轮范围决策

- 用户已确认本轮范围为：`P0 + 部分 P1`。
- 用户已确认若涉及主仓改动，可“按需最小改”。
- 用户已确认优先选择的 `P1` 方向是：下沉主仓逻辑，而不是先做 `prepare_ops/pert_stru`。

## Proposed Changes

### 1. 在 `LocalRunner` 中增加前置可执行文件检查

- 文件：
  - `deps/abacus-forge/src/abacus_forge/runner.py`
  - `deps/abacus-forge/tests/test_api.py`
- 变更内容：
  - 在 `LocalRunner.run()` 调用 `subprocess.run()` 前，显式校验 `self.executable` 是否可执行：
    - 若是绝对/相对路径，直接检查文件存在且可执行；
    - 若是命令名，使用 `shutil.which()` 解析；
    - 解析失败时，抛出清晰的 `FileNotFoundError`，错误信息中带上原始 `executable`。
- 为什么：
  - 对应二次审查报告 `AF-03` 与 `P0` 收尾项。
  - 该变化不改变 Forge 的职责边界，只把底层失败从“隐式系统异常”提升为“显式前置校验”。
- 如何做：
  - 在 `runner.py` 中新增私有辅助方法，例如 `_resolve_executable()`；
  - 保持 `build_command()` 的参数组织逻辑不变；
  - 不引入新的 runner 抽象，不改 `RunResult` 契约；
  - 在 `test_api.py` 中新增“缺失 executable 时抛出清晰异常”的测试。

### 2. 增加 Forge 真输出/准真实输出回归测试

- 文件：
  - `deps/abacus-forge/tests/test_api.py`
  - `deps/abacus-forge/tests/test_cli.py`
  - `tests/test_forge_adapter.py`
- 变更内容：
  - 在 Forge 子模块测试中增加“准真实输出目录”级回归测试，覆盖：
    - `stdout.log` + `stderr.log` + `OUT.ABACUS/time.json`；
    - `STRU_ION_D` 的 final structure 回收；
    - `BANDS_*.dat`、`DOS*_smearing.dat`、`PDOS/TDOS` 的 artifacts/summary 回收；
    - executable 检查与正常运行路径共存。
  - 在主仓 `tests/test_forge_adapter.py` 中增加一个最小真实集成测试：
    - 尽量不 monkeypatch Forge 的 `collect/export`；
    - 验证 `forge_adapter.collect_workspace_results()` 能对 Forge 真实 `CollectionResult` 做正确映射。
- 为什么：
  - 对应二次审查报告中的 `P0` 收尾项；
  - 当前 Forge 测试已不全是极简 mock，但主仓侧对“真实 Forge 结果对象”的直接回归仍偏薄。
- 如何做：
  - 复用 Forge 现有 `Workspace`、`prepare()`、`collect()`、`BandData/DOSData` 样本能力；
  - 不引入大型 golden 数据集，仅使用当前仓内可快速构造的准真实输出；
  - 主仓测试尽量在既有 `tests/test_forge_adapter.py` 中扩展，避免无谓新增测试壳。

### 3. 将主仓中的样本输出生成逻辑最小范围下沉到 Forge

- 文件：
  - 新增 `deps/abacus-forge/src/abacus_forge/sample_outputs.py`
  - 可能更新 `deps/abacus-forge/src/abacus_forge/__init__.py`（仅当需要导出）
  - `src/paimon/forge_adapter.py`
  - `deps/abacus-forge/tests/test_api.py`
  - `tests/test_forge_adapter.py`
- 变更内容：
  - 在 Forge 子模块中新增一个内部样本输出辅助模块，用来统一生成：
    - relax 场景下的 `OUT.ABACUS/STRU_ION_D` 与 `metrics_relax.json`；
    - band/dos/pdos 场景下的样本工件与 `metrics_band.json` / `metrics_dos.json` / `metrics_pdos.json`；
    - 该模块内部直接复用 `band_data.py` 与 `dos_data.py` 已有的样本写出函数。
  - 主仓 `forge_adapter.py` 中的 `_write_mock_analysis_outputs()` 改为优先调用 Forge 新模块，而不是继续在主仓内手写样本工件生成。
- 为什么：
  - 这是当前最适合本轮的 `P1`：
    - 已与 Forge 现有样本工件能力高度重叠；
    - 主仓改动面小；
    - 能直接降低“Forge 缺口长期由主仓私有 helper 承担”的风险。
  - 该下沉仍属于执行基座内部的样本/验证辅助，不会把 AiiDA 或协议层逻辑引入 Forge。
- 如何做：
  - 新模块只接收单工作区与简单任务标志，不接入 `BuilderSpec`、AiiDA、协议语义；
  - 任务判定、one-shot/NiO 等上层场景判断仍保留在 `forge_adapter.py`，避免把主仓业务判断下沉到 Forge；
  - Forge 负责“如何在一个工作区里写出样本输出”，主仓继续负责“什么时候、为何触发这些样本输出”。

### 4. 本轮明确不做的项

- 不实现 `prepare_ops.py` 与 `pert_stru`；
- 不新增 `.github/workflows` CI 配置；
- 不扩展到 `phonon` / `elastic` / `eos`；
- 不重构 `forge_adapter.py` 中与 `BuilderSpec`、NiO one-shot 判定、主仓交付语义相关的上层逻辑；
- 不修改 `docs/` 主线文档，除非实现结果要求最小同步说明。

## Assumptions & Decisions

- 决定：本轮开发批次固定为 `P0 + 部分 P1`，不继续扩张范围。
- 决定：选择的 `P1` 是“下沉主仓样本输出生成逻辑”，不选 `prepare_ops/pert_stru`。
- 决定：主仓只做最小必要改动，优先把可复用的文件/工件生成逻辑下沉，保留主仓场景判断。
- 决定：`LocalRunner` 在 executable 缺失时直接抛出清晰异常，而不是返回伪造的失败 `RunResult`。
- 决定：本轮测试重点是“准真实输出目录回归”，而不是引入更大体量的 golden 数据集。
- 假设：当前 `deps/abacus-forge` 与主仓相关路径没有新的未预期并发修改；若实施时发现意外变更，应立即停止并向用户确认。

## Verification Steps

- 代码级验证：
  - 确认 `deps/abacus-forge/src/abacus_forge/runner.py` 新增 executable 前置检查逻辑；
  - 确认主仓 `src/paimon/forge_adapter.py` 不再手写大段 band/dos/pdos 样本工件生成代码，而是复用 Forge 内部辅助模块；
  - 确认新增 Forge 辅助模块未吸入 `BuilderSpec`、AiiDA、MCP/ATP 等上层语义。
- 测试验证：
  - `python -m pytest deps/abacus-forge/tests -q`
  - `python -m pytest tests/test_forge_adapter.py -q`
  - 如主仓执行链受影响，再补跑：
    - `python -m pytest tests/test_router_and_execution.py -q`
- 行为验证：
  - 缺失 executable 时，`LocalRunner` 失败信息中包含原始命令名；
  - 构造带 `time.json`、`STRU_ION_D`、`BANDS_*.dat`、`DOS*_smearing.dat`、`PDOS/TDOS` 的工作区后，Forge `collect()` 能稳定回收指标与 artifacts；
  - 主仓 `collect_workspace_results()` 对 Forge 真实结果对象的导出路径与 artifact 映射保持兼容。
- 边界自检：
  - Forge 新增模块仅处理单工作区样本输出生成；
  - NiO one-shot、builder 输入解释、主仓验证路径决策仍留在 `src/paimon/forge_adapter.py`。
