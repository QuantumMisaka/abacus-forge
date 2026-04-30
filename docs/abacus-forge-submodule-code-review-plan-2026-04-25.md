# ABACUS-Forge Submodule 细致代码审查计划

## Summary

- 目标：围绕 `.trae/documents/abacus-forge-review.md` 的审查框架，以及 `docs/README.md`、`docs/architecture.md`、`docs/contracts.md`、`docs/development.md`、`docs/packages.md`、`docs/paimon-spirit.md`、`docs/brainstorm/index.html` 的主线约束，对 `deps/abacus-forge` 开展一次以“边界合规 + 能力成熟度 + 集成适配性 + 文档真实性”为核心的细致代码审查。
- 交付形态：以正式报告为主，执行阶段在 `docs/develop/` 新增一份 Forge 子项目专项评审文档，同时在对话中给出高优先级 findings 摘要。
- 审查结论口径：不把“有一些代码/样本”直接等同于“能力闭合”；统一区分 `已实现`、`有自动化保护`、`有 mock 闭环`、`有真实链路证据`。
- 范围边界：主审对象是 `deps/abacus-forge/`；`src/paimon/forge_adapter.py`、`src/paimon/aiida_sai.py`、`src/paimon/execution.py`、相关测试与 develop 文档作为集成和事实证据读取，不把主仓/AiiDA 层本身当作本次主审代码对象。

## Current State Analysis

### 已确认的仓库事实

- `deps/abacus-forge/` 当前是一个小型 Python 子项目，实际源码仅包含：
  - `src/abacus_forge/api.py`
  - `src/abacus_forge/runner.py`
  - `src/abacus_forge/workspace.py`
  - `src/abacus_forge/result.py`
  - `src/abacus_forge/cli.py`
  - `tests/test_api.py`
  - `tests/test_cli.py`
  - `README.md`
  - `AGENTS.md`
  - `pyproject.toml`
- 当前实现形态偏“最小基元库”：
  - `prepare()` 只生成最小 `INPUT/KPT/STRU` 与 `meta.json`。
  - `run()` 只走 `LocalRunner` 本地进程执行。
  - `collect()` 主要解析 `stdout.log/stderr.log` 和少量 `band/dos/pdos` 文件摘要。
  - `export()` 只做 JSON 序列化与落盘。
- 主仓默认执行入口 `src/paimon/execution.py` 目前通过 `src/paimon/forge_adapter.py` 统一调用 Forge，符合“主仓唯一 Forge 薄入口”的文档口径。
- 当前真实 AiiDA 叙事主要位于 `src/paimon/aiida_sai.py`，Forge 在主仓中更多承担 mock/local primitives 与 `retrieved -> workspace -> collect/export` 归一化角色。

### 已确认的主线约束

- `docs/architecture.md`、`docs/packages.md`、`docs/paimon-spirit.md` 明确要求 Forge 只承接执行基座职责，不得吸入协议、前端、AiiDA provenance 语义。
- `docs/development.md` 明确当前波次重点是“职责边界收口 + 稳态化”，不是扩模板或新增主接口。
- `docs/brainstorm/index.html` 的 `#18` 裁决明确两点需要同时纳入审查判据：
  - 不接受任务级厚封装成为未来主契约。
  - 也不能把 Forge 简化为仅有 `prepare / submit / poll / collect / export` 的空壳，仍需审视其是否具备必要的领域单元能力落点。
- `.trae/documents/abacus-forge-review.md` 已预先规定了正式评审文档的结构、比较口径、P0/P1/P2 路线和最小验证动作。
- `repo/abacus-test/` 在本仓库内真实存在，因此本次审查可以做“Forge 源码 vs `abacus-test` 源码”的直接细致对比，而不再局限于仓库内历史分析文档。

### 当前可直接复用的证据

- Forge 自身定位与边界：
  - `deps/abacus-forge/README.md`
  - `deps/abacus-forge/AGENTS.md`
- Forge 实现锚点：
  - `deps/abacus-forge/src/abacus_forge/api.py`
  - `deps/abacus-forge/src/abacus_forge/runner.py`
  - `deps/abacus-forge/src/abacus_forge/workspace.py`
  - `deps/abacus-forge/src/abacus_forge/result.py`
  - `deps/abacus-forge/src/abacus_forge/cli.py`
- Forge 与主仓/AiiDA 集成证据：
  - `src/paimon/forge_adapter.py`
  - `src/paimon/aiida_sai.py`
  - `src/paimon/execution.py`
- 当前过程文档证据：
  - `docs/develop/legacy-to-forge-capability-map.md`
  - `docs/develop/practice-informed-status-review-and-next-plan.md`
  - `docs/develop/current-progress-and-next-steps.md`
  - `docs/develop/forge-aiida-frontend-capability-matrix.md`
  - `docs/develop/verification-matrix.md`
- 自动化保护证据：
  - `deps/abacus-forge/tests/test_api.py`
  - `deps/abacus-forge/tests/test_cli.py`
  - `tests/test_forge_adapter.py`
  - `tests/test_router_and_execution.py`

### 新增的直接源码对照对象

- `repo/abacus-test/` 的同功能对照面已经确认可直接读取，重点包括：
  - 输入准备与结构内核：
    - `repo/abacus-test/abacustest/prepare.py`
    - `repo/abacus-test/abacustest/lib_prepare/abacus.py`
    - `repo/abacus-test/tests/test_prepare_abacus.py`
  - 结果采集与指标抽取：
    - `repo/abacus-test/abacustest/collectdata.py`
    - `repo/abacus-test/abacustest/lib_collectdata/collectdata.py`
    - `repo/abacus-test/abacustest/lib_collectdata/resultAbacus.py`
    - `repo/abacus-test/tests/test_collectdata/test_abacus_collectdata.py`
  - 任务级 band / dos-pdos 能力：
    - `repo/abacus-test/abacustest/lib_model/model_012_band.py`
    - `repo/abacus-test/abacustest/lib_model/model_021_dos_pdos.py`
  - CLI 与工具链入口：
    - `repo/abacus-test/abacustest/main.py`
    - `repo/abacus-test/pyproject.toml`

## Proposed Changes

### 1. 新增正式评审报告

- 文件：`/home/pku-jianghong/liuzhaoqing/work/sidereus/paimon/docs/develop/abacus-forge-submodule-review-2026-04-25.md`
- 变更内容：
  - 按 `.trae/documents/abacus-forge-review.md` 的既定框架落一份正式专项评审报告。
  - 章节固定包含：
    - 项目定位与审查问题
    - 实现现状
    - 与 `abacus-test` 的功能点对比
    - 实现模式对比
    - 按 PAIMON 主线的合规性评估
    - 双角色评估结论
    - 风险点与后续开发路线（P0/P1/P2）
  - 报告中必须显式区分“源码直接证据”和“仓库内过程文档证据”。
  - 报告中新增“同功能源码对照矩阵”小节，至少覆盖：
    - Forge `prepare` vs `abacustest.prepare.PrepareAbacus` / `lib_prepare.abacus`
    - Forge `run` / `LocalRunner` / CLI vs `abacustest` 本地命令组织与 band task 脚本化执行
    - Forge `collect/export` vs `lib_collectdata.RESULT` / `ResultAbacus`
    - Forge 当前 band/dos/pdos 摘要 vs `abacustest` 的 `model_012_band.py` / `model_021_dos_pdos.py`
  - 报告中必须明确声明：本次比较同时使用了仓库内 `repo/abacus-test` 的直接源码证据与既有分析文档/实践记录。
- 为什么：
  - 用户已明确最终产物以正式报告为主。
  - 现有 `.trae/documents/abacus-forge-review.md` 是审查说明文，不是最终对外评审稿。
- 如何做：
  - 先做完整静态审查与证据摘录。
  - 再做一轮“同功能映射”而不是“同文件名映射”的源码对照，避免因为两仓分层方式不同而误判。
  - 再按严重级别归纳 findings，并转写成正式报告中的“结论 + 证据 + 风险 + 建议路线”。
  - 对 `SCF / Relax / Band / DOS` 至少给出“已闭合 / 部分实现 / 未开始”的明确分级，且分级依据绑定到具体文件与测试/文档证据。

### 2. 更新 `docs/README.md` 的 develop 区域导航

- 文件：`/home/pku-jianghong/liuzhaoqing/work/sidereus/paimon/docs/README.md`
- 变更内容：
  - 在 `develop/` 目录地图或“现在做到哪了”一节中加入新评审报告入口。
- 为什么：
  - `docs/README.md` 是文档导航事实源；正式报告落在 `docs/develop/` 后，应可被新开发者和评审者直接发现。
- 如何做：
  - 只补充最小必要一条导航链接与一句功能说明，不重写其它结构。

### 3. 审查执行步骤（不预设代码修复）

- 读取并审查 `deps/abacus-forge/` 全部源码、CLI、测试和项目元数据。
- 读取并审查 `repo/abacus-test/` 中与 Forge 同功能的关键源码、CLI 与测试，不对整个 `abacus-test` 做无边界泛审。
- 建立明确的“同功能对照矩阵”：
  - `deps/abacus-forge/src/abacus_forge/api.py::prepare`
    vs
    `repo/abacus-test/abacustest/prepare.py`、
    `repo/abacus-test/abacustest/lib_prepare/abacus.py`
  - `deps/abacus-forge/src/abacus_forge/workspace.py`
    vs
    `repo/abacus-test/abacustest/prepare.py` 的输入目录生成与
    `repo/abacus-test/abacustest/lib_prepare/abacus.py` 的 `gen_stru` / `AbacusStru`
  - `deps/abacus-forge/src/abacus_forge/runner.py`
    vs
    `repo/abacus-test/abacustest/lib_model/comm.py` 的 `run_command()`、
    `repo/abacus-test/abacustest/lib_model/model_012_band.py` 的 `PrepBand.run_abacus()`
  - `deps/abacus-forge/src/abacus_forge/api.py::collect/export`、
    `deps/abacus-forge/src/abacus_forge/result.py`
    vs
    `repo/abacus-test/abacustest/lib_collectdata/collectdata.py::RESULT`、
    `repo/abacus-test/abacustest/lib_collectdata/resultAbacus.py`、
    `repo/abacus-test/abacustest/collectdata.py`
  - `deps/abacus-forge/src/abacus_forge/cli.py`
    vs
    `repo/abacus-test/abacustest/main.py`
- 对照以下四类判据输出 findings：
  - 边界守恒：是否仍符合 `prepare/run/collect/export` 基元分层，不吸入协议、AiiDA provenance、前端语义。
  - 能力成熟度：README/brainstorm/过程文档宣称的能力，与当前真实实现之间有哪些闭合项、部分实现项、未开始项。
  - 同功能差距：Forge 相比 `abacus-test` 在输入准备、结构表示、K 点处理、任务脚本生成、结果解析、band/dos/pdos 后处理上的缺口哪些属于“有意收缩”，哪些属于“当前缺口”。
  - 集成适配性：Forge 是否被主仓通过单一薄入口使用；是否存在集成层为便利而替 Forge 私补大量私有语义。
  - 测试与证据充分性：Forge 自测与主仓集成测试是否足以支撑当前文档成熟度表述。
- 审查结论输出规则：
  - 对话中的最终回复以 findings 为先，按严重级别排序。
  - 正式报告则允许先给综述，再给分项证据与路线图。
- 不在计划中预设对 `deps/abacus-forge` 源码本身做任何修复；若执行阶段发现文档与代码事实不一致，优先如实写入评审报告，而不是擅自进入修复任务。

## Assumptions & Decisions

- 决定：最终产物以正式报告为主，同时在对话中给出关键 findings 摘要。
- 决定：本次主审范围是 `deps/abacus-forge/` 子模块本身；主仓和 `aiida-abacus` 仅作为“边界/集成/证据”读取范围。
- 决定：比较 `abacus-test` 时，优先使用 `repo/abacus-test/` 的直接源码证据；既有分析文档和实践记录只作为补充语境，不替代源码事实。
- 决定：采用“文档事实源优先级”口径：
  - P0：`docs/README.md`、`docs/architecture.md`、`docs/contracts.md`、`docs/development.md`、`docs/packages.md`、`docs/paimon-spirit.md`、`docs/brainstorm/index.html`
  - P1/P2：`docs/develop/*.md` 和 `.trae/documents/abacus-forge-review.md`
- 决定：`brainstorm/index.html` 的 `#18` 裁决会作为关键审查判据之一，用来避免把 Forge 审成“厚封装任务壳”或“过度抽空的生命周期空壳”两种偏航方向。
- 假设：当前工作树在 Forge 相关路径上无未提交改动；后续执行若发现意外变更，应立即停止并向用户确认。

## Verification Steps

- 静态核对：
  - 通读 `deps/abacus-forge/` 全部源码、README、AGENTS、测试。
  - 通读 `repo/abacus-test/` 的同功能关键源码、CLI 和针对性测试，不扩散到全部模型/平台能力。
  - 核对 `src/paimon/forge_adapter.py`、`src/paimon/aiida_sai.py`、`src/paimon/execution.py` 的调用与边界关系。
  - 核对 `docs/develop/legacy-to-forge-capability-map.md`、`docs/develop/practice-informed-status-review-and-next-plan.md`、`docs/develop/forge-aiida-frontend-capability-matrix.md` 与当前代码的一致性。
- 只读验证命令：
  - `python -m pytest deps/abacus-forge/tests -q`
  - `python -m pytest tests/test_forge_adapter.py tests/test_router_and_execution.py -q`
  - `python -m pytest repo/abacus-test/tests/test_prepare_abacus.py repo/abacus-test/tests/test_collectdata/test_abacus_collectdata.py -q`
- 报告自检：
  - 每条核心结论都至少绑定一个源码证据和一个主线/过程文档证据。
  - 每条“与 `abacus-test` 的差距”都明确标记为“有意收缩”或“当前缺口”，避免把架构边界误判成缺陷。
  - 每个能力评级都显式标注依据，不以 README 路线图代替已实现事实。
  - 报告中的 P0/P1/P2 路线明确说明“应进入 Forge”还是“必须留在 AiiDA/PAIMON 上层”。
