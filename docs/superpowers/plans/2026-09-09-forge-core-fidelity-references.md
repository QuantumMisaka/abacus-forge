# Forge core fidelity: reference evidence

This is supporting evidence for [the implementation plan](2026-09-09-forge-core-fidelity.md), not a separate specification. Inspection uses local checkouts; revisions below do not claim latest upstream status. Reference repositories were not modified or introduced as runtime dependencies.

| Reference | Inspected local HEAD | Relevant implementation | Adopt / avoid |
| --- | --- | --- | --- |
| Paimon v1.2 (`app-tools/toolbox/ABACUS`) | `85e55e6b83b3b1a883d41b7d149c8afa2c223aba` | `utils/stru_read.py:110` `_cell_face_heights`, `_largest_wrapped_gap`, `detect_vacuum_info`; `utils/abacus_structure_io.py:111` `atoms_from_abacus_stru_dict` | Adopt periodic fractional gap × interplanar height and explicit unit conversion. Keep platform adapter and scientific policies outside Forge. |
| Paimon v1.2 | same | `toolkits/structure_prepare_pipeline.py:599` `_native_stru_uses_selected_resources`, native copy at 718, explicit transformed PP/basis write at 733; `tests/test_structure_prepare_pipeline.py:430` | Preserve native source meaning. Resource selection/materialization is explicit; a structure serializer alone does not stage assets. |
| Paimon v1.2 | same | `utils/basic_result_evidence.py:51`, `utils/result_evidence.py:23`, `abacus_collector.py:71` | Adopt separation of facts, metrics, artifacts and provenance; do not inherit the four-metric ceiling or unconditional execution-status projection. |
| abacustest (`abacus-test`) | `1c9acbca026234ba91cdc19bca2f989d19d2ccff` | `abacustest/lib_prepare/stru.py:1329` `read_stru_file`, `:1460` `write_stru_file` | Writer explicitly accepts PP/mass/orbital data; reader omits parsed mass from returned dictionary. Do not copy that lossy round trip. |
| abacustest | same | `abacustest/lib_model/comm.py:864` `get_largest_vacuum_dir` | Cyclic fractional gaps are useful; multiplying by cell-vector lengths instead of face heights is unsuitable for skew cells. |
| abacustest | same | `abacustest/lib_collectdata/resultAbacus.py:10`; `abacustest/lib_collectdata/abacus/abacus.py:138,318,395,429,1187` | Use independent normal-end, convergence, energy, force, stress and relaxation facts as parser references. No typed completeness contract is supplied by this backend. |
| abacuscopilot | `91b945674d9fc183efcd40e1d1a7ce6058566356` | `abacuscopilot/io/stru_file.py:95` `read_stru`, writer at 285 | Species order and explicit resource fields are useful. Writer regenerates masses and fabricates default resource filenames: unsuitable for fidelity-preserving conversion. |
| abacuscopilot | same | `abacuscopilot/postprocessing/scf_tasks.py:22` and `:557` | Specific positive/negative markers provide parser examples; do not copy broad convergence regexes or turn marker presence into collection completeness. |
| abacuslab | `d641692171b37d52b890c7e0acd34b6f4ffdfb06` | `templates/scf_band_template_v2.yaml:127,166,232,241` | Explicit output handoff is useful. Local checkout contains templates/docs, not internal engine implementation; example success output despite missing artifacts is not a completeness reference. |
| ABACUS | `94576a80169de36e02e637edc2a0963fba9e1838` | `source/source_cell/read_atoms_helper.cpp:24,195`; `source/source_cell/print_cell.cpp:128` | Native coordinate/lattice-unit authority: Cartesian uses lat0; Cartesian_au uses Bohr; centered Angstrom modes add offsets; emitted lattice constant is in Bohr. |

## Corrections to the preceding review

- Forge's `Cartesian_au` followed its Cartesian prefix branch, not Direct. The defects were plain Cartesian missing lattice-constant scaling and centered modes losing their offsets.
- Forge's emitted `LATTICE_CONSTANT_UNIT Angstrom` is not a native ABACUS token. Correct output must be checked using native units independently of Forge's own reader.
- Passing baseline tests (593 passed, 3 skipped at `e7a9cc8`) did not cover these semantic defects. Some prior fixtures encoded the same wrong unit convention on both sides.

## Scope retained for later work

Typed prepare asset maps/materialization remain separate: explicit choice and source provenance, path containment, duplicate basenames, absent files and copy/link behavior need one coherent contract. Paimon v1.2's resource pipeline is the relevant reference; Forge must not inherit its Tool/runtime objects. This batch preserves STRU references but does not claim a complete executable-ready typed prepared directory.

Axis-swap Cartesian orientation, full centered-coordinate support, advanced per-atom STRU extras, broader MD/PyATB/property algorithms and upstream release verification are not closed by this batch.


<a id="integration-review-20261019"></a>
## 2026-10-19：面向集成基座的参考复核

用户本轮明确：将 `abacustools` 纳入参考，重点是构建可供 ABACUS 用户与 Agent
共同消费的集成基座。此节记录参考归属、既有规范复核和下一步建议，不新增公共
API，不把 Draft 改为 Approved，也不引入新运行时依赖。此前快照保持原样。

### 已有 SPEC / PLAN 如何承接

- [09-01 契约优先 SPEC](../specs/2026-09-01-forge-contract-first-rearchitecture-design.html)
  与 [09-02 Service/Status SPEC](../specs/2026-09-02-forge-service-status-migration-design.html)
  已将 Forge 定位为人类与 Agent 共用的独立基座。平台价值应体现在统一请求、
  单元操作、事实结果、错误、产物和安装消费上；Paimon 是其中一个消费者。
  科学方法的成熟实现可以迁入或由外部引擎提供，不能因“集成”重新发明其算法。
- [10-13 整理 SPEC](../specs/2026-10-13-forge-repository-consolidation-design.md)
  要求共享中立内核且保留兼容差异。typed / legacy / task-pack 现有入口不应被
  一次性重写；旧 pack 存在也不授权新增 typed workflow 编排。
- [Engine/Version PLAN](2026-09-13-forge-engine-version-policy.md) 继续管理
  native / optional parser 与 develop/LTS 兼容。1.2.0 rebind 已有独立证据，
  不再列作待发包；真实双轨 matrix 仍未完成。
- [Stage 5](2026-09-13-forge-stage5-evidence-gates.md) 管 Forge 候选交付证据；
  Paimon 09-29 总体架构 SPEC 与 09-13 migration PLAN 管 M0–M4 / W0–W4。
  W1 补公共基元，W2 接产品链，W3 闭合安装，W4 做对等与平台验收；它们不是
  再造第二套 Forge 框架的理由。上层入口见[跨仓导航](../README.md#跨仓迁移)。
- Contract System / Typed BEC / Property manifest 继续按现有 Draft 状态处理。
  特别是 BEC Draft 的“设计决策 1/2”仍描述 `run_bec` 内串联 SCF 与三次 NSCF、
  自动发现并复制电荷。该旧 pack 方案不能直接成为新的 typed operation 设计；
  实施前必须重新确认阶段 owner、显式产物交接、极化分支、单位和张量公式。

**判断：总体已批准架构支持本轮目标，主要短板是跨层消费与验收闭合。**
“platform”在本轮按可复用的库/CLI 与专业引擎集成面理解；托管服务、调度系统、
统一 workflow 引擎等仍属于新的产品边界，不能由这个词自动获得实施授权。

### 工作区参考角色与快照

下表为本轮本地读取快照，不声称所有 checkout 都是上游最新代码，也不将各自
测试声明视为 Forge 验收。路径相对 `workplace/`；具体源码入口沿用各仓布局。

| 仓库 / 本地提交 | 参考角色 | 进入 Forge 的方式 / 排除项 |
| --- | --- | --- |
| `abacus-develop` / `7b33a94bfb41` | producer 格式、参数、单位与实际输出权威 | 按实际 producer 版本核对原生源码和真实日志；此 checkout 落后远端且有本地 toolchain 属性修改，不能冒充最新 develop。 |
| `abacuslite` / `4cea075cc154` | 独立 ASE calculator / I/O 与 optional parser | 消费已发布包与既有 extra/adapter；共享兼容证据，避免重新维护一套 ASE calculator。 |
| `atst-tools` / `f2870917af09` | NEB/过渡态专业引擎，声明版本 2.3.0 | 用显式文件与进程交接，NEB 内部优化链由 ATST 持有；新版本不能复用旧 2.2.8 smoke 冒充验收。 |
| `pyatb` / `80f7c2d89aaa` | 紧束缚矩阵后处理与专业数值实现 | 扩展既有显式 handoff；不在 Forge 重写 PyATB 算法或引入其上层工作流。 |
| `abacustools` / `af2b49837025` | 新增：输入保真、版本格式、后处理算法与性质流程参考 | 优先查 `io/`、`data/` 和对应测试；调度模板、监控、数据库和 workflow 留在上层评估。不是整包替换 Forge。 |
| `abacus-agent-tools` / `eb239ab1ff37`；`abacus-test` / `5470b0fac343` | Paimon 既有行为、输入默认值与结果兼容 oracle | 抽取底层能力、保留同输入对照；最终目标仍是解除两者的生产运行时依赖，不能用新 adapter 包装旧依赖来宣称迁移完成。 |
| `abacuscopilot` / `5418ebce92c5`；`abacuslab` / `f1e96be43520` | 人类使用场景、模板、局部解析与文件交接参考 | 选择具体行为参考；不继承整套交互状态或 workflow。旧源码缺陷结论仅绑定上表历史快照，不能直接套到新 HEAD。 |
| `app-tools` / `52798406d67d`；`app-tools-forge` / `51423d8094f7` | v2 兼容基线与 v3 实际消费者 | 以 migration PLAN 中实际工具/默认链/下游 artifact 为验收对象；ATP、资源、恢复、报告、科学 policy 归 Paimon。读取时 v3 包含本地 `origin/main`。 |
| `paimon` / `5b5088160ff2` | 已结项 AiiDA 原型，读取时有文档修改 | 仅作历史设计证据，不恢复其运行时与对象协议。 |
| `app-tools-forge/toolbox/ABACUS/deps/abacus-cohp-lcao` / `78b3628aa4bb` | 直接 NAO-block COHP/COOP 实现与 legacy 兼容 oracle | 单独核对方法、能量参考、spin 与周期像口径；不要求不同方法无条件数值相等。 |

### abacustools 首轮参考入口

源：[ahxbcn/abacustools，冻结提交 af2b498](https://github.com/ahxbcn/abacustools/tree/af2b49837025db46046cb68401ba568de55471dd)。
`pyproject.toml` 声明版本 0.0.1、Python >=3.9、LGPL-3.0-or-later；本轮仅纳入参考，
未安装或复制代码。源码调查不构成成熟度认证。

| 能力 | 源码 / 测试入口（相对该仓） | 本项目的具体用法 |
| --- | --- | --- |
| 结构与资产保真 | `io/stru.py`（位于 `src/abacustools/`）、`data/structure_summary.py`；`tests/test_file_stru.py`、`test_file_struinfo.py` | 比较 PP/ORB、磁矩、约束和坐标往返，补 Forge 真正缺失的行为，避免建立第二套结构类型。 |
| 版本解析 | `src/abacustools/data/versions.py`、`data/abacus_result.py`；`tests/test_abacus_versions.py` | 作为 LTS/develop marker 与失败案例的独立对照；版本来源/覆盖优先级仍遵循 Forge SPEC。 |
| 电荷与后处理 | `src/abacustools/data/charge.py`、`grid_files.py`、`cohp.py`、`mayer.py`；`tests/test_cube_precision.py`、`test_cohp.py` | 核对单位、网格精度、spin、格式覆盖；先补已有 operation 的事实与产物缺口。 |
| 极化/BEC/介电/压电/声子 | `src/abacustools/data/polarization.py`、`dielectric.py`、`piezoelectric.py` 与 `commands/workflow/` | 参考物理输入和阶段交接以修订 Draft；流程组织与数值实现分别评估，不将 workflow 文件整体移入 Forge。 |
| Agent 可用性 | `skills/`、CLI 参数与错误；`integrations/abacuslite.py` | 将专业前置条件用于使用文档/上层知识，检查现有 discovery 的不足；不复制菜单或用 stdout 文本取代 v1 envelope。 |

观察到的边界：`main.py` 在解析参数前打印 banner，不能直接等同于 Forge 的单 JSON
stdout 协议；`data/cohp.py::analyze_cohp` 在部分缺失 k 权重情况下推断均匀权重，
不能未经评估迁入 Forge 的事实完整性语义。其 COHP 使用直接 NAO 原子块，不是 IAO。
本轮源码态 `--help` 在 `paimon` 环境因缺少 `rich` 失败，未修改共享环境；测试套件和
真实 ABACUS 未运行，故上述是源码参考结论。

<a id="cohp-provenance-20261019"></a>
### COHP：输入来源相同，方法与迁移决策不同

两条路径都来源于 ABACUS LCAO 的 NAO 表示、H(k)、S(k) 和波函数 C(k)。
“NAO/H/S”描述的是原始数据，不能据此区分或等同后处理方法。

- `abacus-cohp-lcao/src/cohp.py::cal_COHPmatskIJ_e_ij` 直接计算
  `Re[C_i* H_ij C_j]`（COOP 用 S）；`abacustools/data/cohp.py::_pair_value` 与本地
  PyATB `src/pyatb/fermi/cohp.py::cohp_values_one_k` 也走同一类原子轨道块收缩。
  这是方法模式的确认，不是共同代码来源或完整数值等价的证明。
  `absolute H` 指未移能量参考的 H，不是对 H 元素取绝对值。把横轴改成 E−Ef
  与改变 Hamiltonian 的参考是两回事。
- Forge `src/abacus_forge/cohp_iao.py` 在原 NAO 空间内构造最小价层 IAO，冻结
  满足守卫的半芯带，计算 `H_IAO=A†HA`、`T=A†SC`，再按晶格平移分解单键。
  额外使用 S(R) 判断 Bloch 相位符号；这不是不使用 NAO，也不是直接 NAO 分块的别名。
- 决策来源是 Paimon `docs/reports/2026-09-30-cohp-iao-kernel.md`：报告把 IrO2
  dev task 12255 作为起因，记录直接 NAO 分块的能量零点依赖和周期像求和问题，
  以及 13 种投影方案的历史调查。报告还记载 21 个平台 SCF / 61 个键的基准复算。
  本轮核对报告和当前代码，未独立重跑这些数据或复核全部方案，因此这些数字只作为
  历史决策证据，不能升级为本轮科学验收。
- 工程上先在 Paimon v2 提供可选 `iao`，保留默认 `legacy`；Forge
  [10-15 W1 SPEC](../specs/2026-10-15-forge-cohp-postprocess-design.md) 经用户批准，
  选择迁入已有纯 Python 内核，明确只支持 `method=iao`，把 legacy subprocess
  bridge、自动方法选择和科学接受排除在 W1 外。这是有界迁移决定，不是宣告 IAO
  对所有材料都更优或永久取消 NAO 路径。
- Forge 自有证据见[安装消费](../evidence/2026-10-15-forge-cohp-installed-consumption.md)
  与[完整 Si 输入](../evidence/2026-10-15-forge-real-evidence.md)：支持 IAO 迁移等价与
  该输入的后处理；不证明 legacy 数值等价、普适键强排序或完整平台迁移。

既有 IAO 报告还明确：第一 zeta 仅为参考代理、过渡金属外层 p 未纳入、bcc Fe
符号解释未定、k 网格收敛未完成；实现对壳层外赝势、半芯条件、gamma_only=1、
nspin=4/SOC 等拒绝或限制。新增方法前应分别记录基组、Hamiltonian 参考、单/双序、
spin、占据、平移像与积分约定。建议先做同输入的三方方法审计，区分相同方法的
数值 parity 与不同方法的定义差异；不靠更换默认值掩盖差异。

### 建议的推进顺序与验收对象

此处是对既有 owning PLAN 的建议排序，不另设迁移总表，也不授权执行 Draft：

1. **先闭合已有能力的完整消费。** 以 Paimon 当前 W2 工具链为需求清单，Forge
   W1 只补实际公共缺口；同时用独立 Python/CLI 消费证明不依赖 Paimon checkout。
   每个切片串起显式输入、执行/后处理、事实产物和下游读取；错误不能静默回退旧包。
2. **同步完成安装和版本交接。** W3 核对当前 Forge wheel、Paimon ZIP、abacuslite
   1.2.0、ATST 2.3.0 与实际环境；重建适用 lock/receipt，按当前默认路径扩展包消费
   门禁。此前 2.2.8 NEB 和旧 kit 只保留历史证据，不能替代新组合。
3. **用独立参考补真实证据。** Engine/Version 与 Stage 5 按 producer 版本和能力
   补齐适用实算；COHP 先做方法/输入/周期像审计，再决定 legacy bridge 或新增方法。
   运行时断言与科学接受分别记录，不以测试数量或“方向合理”替代方法验证。
4. **按用户需求扩展能力。** 从 abacustools 等仓提取真实用例与算法参照，先完成
   BEC/介电等 Draft 的边界和方法确认，再立实现任务。Contract System 优先说明
   现有 schema/discovery 不能满足的具体问题，不先建完整知识服务阻挡当前迁移。

每个参考采纳项至少回答：谁消费、缺少什么、复用哪个已存在内核/外部包、Forge
负责哪个 operation、依据哪个 producer 版本、用什么真实输入验证、由哪个 PLAN
追踪。这样把能力接成可用接口，而不是按参考仓库的菜单不断新增命令。


2026-10-19 用户进一步确认 NAO-COHP / IAO-COHP 的术语区分；当前实现说明与后续
同输入方法对照由[COHP owning PLAN](2026-10-15-forge-cohp-postprocess.md#已确认的方法口径与后续对照2026-10-19)
维护。`abacus-cohp-lcao` 本身还包含其他投影实验函数；此处“直接 NAO 路径”仅指已检查的
常规 COHP 路径，不概括该仓全部方法，也不概括未检查的外部 COHP 软件。
