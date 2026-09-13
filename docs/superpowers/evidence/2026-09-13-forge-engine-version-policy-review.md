# Engine/Version Policy 收敛审查

初审日期：2026-09-13。以下第 1–6 节保留初审快照；用户随后要求“进行收口”，当前状态见第 7 节。初审结论：**方向已收敛，但当前修订稿尚不能作为无歧义的完整开发基线；需先收口下列两项契约问题，并明确 parser 事实分工。** R3 文件名别名、R5 relaxation 标记等独立增量可以进入有界 PLAN。此结论不代表代码实施或发布授权。

审查对象：[Engine/Version Policy SPEC](../specs/2026-09-12-forge-engine-version-policy-design.html)，状态为 Revised draft，当前尚未跟踪。本文仅是审阅证据，不修改或取代规范源。

## 1. 范围和证据基线

实际核对的 HEAD 与 SPEC 所记基线一致：

| 仓库 | HEAD |
| --- | --- |
| abacus-forge | `81c97c1a3feffb117bd4caf618597de011bd73fb` |
| abacus-develop / canonical abacuslite | `94576a80169de36e02e637edc2a0963fba9e1838` |
| app-tools | `ec173fae19ad6d94b7cd4025dbe7a56fef483209` |

按规范层级检索工作区参考资料，重点读取两份上位 SPEC、Forge AGENTS/README/ROADMAP、测试治理、native collection fidelity PLAN、core fidelity 参考调查、Stage 5 evidence、abacus-packages README，以及相关当前代码/测试。跨仓核对 canonical abacuslite 的 core/latestio/legacyio/包元数据与 Paimon 的 BandData、PDOSData、COHP、convergence 消费点。历史 paimon、abacuslab、abacuscopilot、abacustest 等按现有引用链作为参考，不提升为现行规范。

本审查不声称逐行读完工作区所有资料；证据覆盖与本 SPEC 决策直接相关的规范、接口、实现和测试。未运行真实 ABACUS/PyATB、未核验当日 PyPI 发布状态、未测试尚不存在的 backend。PyPI 可用性按 SPEC 留到阶段 1 核验，不作持续事实断言。

## 2. 必须收口的契约问题

### F1：R4 把行为收紧写成了保持现状（高优先级）

SPEC 第 129、148 行称保持 `STRU_FINAL/STRU_FINAL.cif` 严格契约，并排除 `STRU_NOW`、`STRU_ION_D` 自动成为 final；但当前 typed 实现已有不同且明确的行为：

- [relax_results.py](../../../src/abacus_forge/relax_results.py) 的 `_FINAL_STRUCTURE_SUFFIXES` 包含 `STRU_ION_D`、`STRU_NOW`、`STRU_NOW.cif`、`STRU.cif`、`STRU`。
- `_final_structure_candidates` 优先 native final 家族；不存在 native final 时返回旧候选。唯一可解析、contained 的旧候选可以得到 final snapshot 与 `collection=complete`。
- [test_service_status.py](../../../tests/test_service_status.py) 的 `test_relax_collection_supports_native_abacus_final_structure_names` 明确断言单独 `STRU_NOW` / `STRU_NOW.cif` 为 complete；`test_relax_collection_status_uses_factual_output_completeness` 包含 cell-relax + `STRU_ION_D` 为 complete。

这不是未实施能力与目标设计的正常差距：SPEC 同时承诺保持既有语义，却把已存在的兼容行为当作未来扩展。按字面执行会改变 native typed collection 状态，并与既有回归冲突。

建议在 SPEC 明确选择：

1. 保持现有候选和优先级，本批只禁止从轨迹末帧新增 final 来源；或
2. 将 FINAL-only 标记为本批明确的 typed 行为收紧，写出对旧候选、已有调用方及 owning tests 的影响，并确认这一取舍。

两者均可实现，但 PLAN 不能替用户选择。若维持修订稿的 FINAL-only 方向，应如实采用第二种表述。

Stage 5 的 LTS `1 failed + 8 passed` 仍应保留。**仅“缺 STRU_FINAL”不足以解释当前实现为什么 partial**：旧候选歧义、解析错误或其他完整性原因都可能触发。须读取该案例原始 diagnostics，或在后续授权的 fresh smoke 中保留它，再绑定正向断言；本次没有重新判定历史失败的具体根因。

### F2：失败 parser provenance 没有冻结协议中的承载位置（高优先级）

SPEC 第 177 行要求两种路径在 `diagnostics.parser` 记录配置、版本、来源，“失败时记录已知部分”，同时要求不改 v1 schema、沿用 event 规则。第 192 行又规定缺包/版本未知返回 class 3，版本冲突返回 class 2。

当前 [contracts.py](../../../src/abacus_forge/contracts.py) 的 `ForgeErrorEnvelope` 只有 error class/message/affected_fields、operation_id、workspace_rel、schema_version，没有 diagnostics；反序列化严格拒绝未知字段。[service_support.py](../../../src/abacus_forge/service_support.py) 的错误路径直接返回该 envelope；正常 `persist` 才追加 OperationOutcome event。上位 Service/Status SPEC 也没有定义带 parser diagnostics 的失败 outcome/event。

因此成功或 partial outcome 可直接携带 `diagnostics.parser`，但 class 2/3/5 错误不能按同一句要求实现而同时保持当前契约。

建议本批保持冻结 schema：将结构化 parser diagnostics 的保证限定到 OperationOutcome（含 partial/missing_output），错误通过现有 `message` / `affected_fields` 返回已知原因；明确 admission 前后以及是否有 event。若必须让错误也携带结构化 provenance，则应显式设计其协议/持久化扩展。

同处需补一张优先级小表：缺日志、截断且无版本、来源歧义、版本未知/冲突分别何时返回 outcome、何时 class 2/3。现在“缺输出沿用 missing_output/partial”和“无版本返回 precondition.missing”同时命中，至少要固定典型重叠案例，避免两入口各自裁决。

## 3. 阶段 0 前需明确的 parser 分工

### F3：全部事实 parity 与禁止混合后端，需要定义共同解析的边界（中优先级）

SPEC 第 204 行要求四 capability 既有公开事实集合均比较，第 192 行禁止合并两引擎事实，但仅画出了“共享事实投影”，尚未列出事实提取由谁负责。

当前 [collectors/abacus.py](../../../src/abacus_forge/collectors/abacus.py) 同时承担能量、收敛标记、力/应力、MD 热力学、time.json 和报告事实等提取。[md_results.py](../../../src/abacus_forge/md_results.py) 的公开 MD 字段和 complete 判定依赖 `native_md_block_complete` 等结果。

canonical abacuslite 的 `latestio.read_abacus_out` 会读取相邻 `eig_occ.txt`，MD 路径还要求 `MD_dump`，并执行轨迹/能量/电子态帧数断言；其底层 `read_energies_from_running_log` 读取电子 `ENERGY Rydberg eV` 表。这里没有 Forge 所需 MD 温度、离子动能、热力学序列与收敛观察的完整同名输出接口。因此不能把 `read_abacus_out` 简单映射为全部现有 collect facts；SPEC 允许调用底层读取函数的方向是正确的。

建议新增简短事实责任表：共同来源发现/元数据/标记与 MD 专属解析，后端可替换的数值解析，及共同单位/状态/产物投影。明确“禁止混合”是禁止两个完整 collector 的隐式 fallback/覆盖拼接，而共同事实提取是否允许、覆盖哪些字段。若坚持全部解析必须仅由 abacuslite 提供，就须把缺失的上游能力列为阶段 0 可行性门槛。

具体内部类名、函数布局和逐字段容差可由 PLAN 固化；哪些事实可共享及失败时能否补值属于本 SPEC 应明确的边界。

## 4. 已经收敛的内容

| 决策 | 核验结果 |
| --- | --- |
| 内部可选 parser，native 默认，collect 优先 | 与 Forge 单元职责和两份上位 SPEC 一致；service 有明确注入位置。 |
| CLI/Python 使用实例级配置，不改进程环境 | 方向可实现，不要求进程隔离，不把计算 engine 字段误作 parser。 |
| 局部版本分发，规避 calculator/global switch | `core.switch_io_backend_version` 的裸 v3.9.0 分支确实不重置全局值；修订稿归因正确。 |
| 撤回 eig_occ.txt 删除阻断项 | `latestio.py` 中 unlink 位于测试清理，读取函数没有该删除行为。 |
| PyATB 双命名，显式角色/顺序优先 | typed prepare 传递显式路径，manifest 按请求 role 覆盖分类；旧名限制位于名称分类，不能据此推断 handoff 拒绝新名。 |
| R5 relaxation 步数 | 当前正则覆盖 RELAX/ION STEPS，缺 STEP OF RELAXATION；增量明确。 |
| 双轨正向预期断言 | 历史失败不改写为通过；实际配置范围、构建偏离和 parser 版本绑定清楚。 |
| canonical 包与分阶段发布 | checkout 试点、已验证 exact pin、native 可独立发布的边界清楚。 |
| Forge 与 Paimon 迁移分别验收 | 当前 Paimon band/PDOS/COHP/convergence 确有旧包调用；覆盖矩阵归 app-tools，依赖解除与 Agent Benchmark 不由 Forge fixture gate 替代。 |

其他文档精度项：R1“无新增 ase”应解释为不扩大当前默认依赖集合；Forge 当前已直接依赖 ase。ROADMAP、abacus-packages README 和历史 evidence 仍有“typed handoff 只认旧名”等旧归因，后续应加校正说明并指向最终 SPEC，保留原始运行数字。

## 5. 可以推进到哪里

| 工作 | 判断 |
| --- | --- |
| R3 分类别名与显式 handoff 回归、R5 标记解析 | 可单独进入有界实施 PLAN。 |
| R4/R6 final-structure 和 LTS 正向预期门禁 | F1 明确后再定目标断言，不能先把历史原因写死。 |
| 阶段 0 parser 接缝与 fixture parity | F2/F3 明确后可进入 PLAN；先做四 capability 事实责任/样例映射。 |
| 阶段 1 extra 发布 | 尚未满足；实际包版本、安装、parity 和双轨是实施/发布证据，不必提前全做完才允许阶段 0。 |
| Paimon v1.3 迁移交付 | 尚未满足；工具矩阵、运行时依赖清零、Benchmark parity 与生产链路另行验收。 |

不建议重做整份设计。收口上述局部契约后，可按 native 增量、阶段 0、阶段 1 分开计划，避免将跨仓迁移或包发布状态变成所有开发的统一前置条件。

## 6. 当前工作状态验证

采用 verification-before-completion 的当前证据要求，在 Forge HEAD 上实际执行：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  /home/james/apps/miniforge3/envs/paimon/bin/python -m pytest -q \
  -p no:cacheprovider tests/test_service_status.py \
  -k 'relax_collection_supports_native_abacus_final_structure_names or relax_collection_prefers or relax_collection_ambiguous_log_or_final_structure_is_partial'
```

结果：`6 passed, 163 deselected in 3.04s`，exit 0。该结果证明 F1 所述旧候选兼容和优先级确实是当前行为；不证明新 backend、全部回归或双轨真实运行已通过。

初审阶段仅新增本审查记录，未修改目标 SPEC 或生产代码；后续实施证据见第 8、9 节。


## 7. 收口记录（2026-09-13）

用户在初审后明确要求“进行收口”。本次据既有行为兼容和冻结 v1 协议目标修订 SPEC，未修改生产代码：

| 初审发现 | SPEC 中的处置 | 当前状态 |
| --- | --- | --- |
| F1 | R4 与决策 3 明确保留现有候选、native final 优先、旧候选兼容与歧义拒绝；禁止从轨迹新增 final。历史 LTS 原因交由原始 diagnostics/fresh evidence 核定，不再声称缺 FINAL 必然 partial。 | 设计冲突已消解；历史原因仍为实施证据项。 |
| F2 | parser diagnostics 限定 OperationOutcome；错误保持既有 message/affected_fields，无新 error 字段或失败 event。按顺序表明确配置、缺包、缺/歧义日志、版本冲突/缺失和数值缺失的优先级及 admission。 | 设计承载与控制流已明确。 |
| F3 | 增加共同来源/日志事实、可替换电子标量/力/应力、共同派生投影职责表；允许共同解析，禁止完整 collector 拼接或 backend 缺值触发 native 补跑。 | 责任边界已明确；字段表与 parity 留在实施任务。 |

依赖描述已校正：默认已有 ase，不因新后端增加默认 seekpath/abacuslite。补充 [分阶段实施计划](../plans/2026-09-13-forge-engine-version-policy.md)，区分 native 增量、checkout 试点、extra 发布和 Paimon 外部迁移。本记录中的初审代码证据仍适用，因为本轮没有生产代码变更。

当前判断：SPEC 已进入分阶段实施；阶段 0 的 checkout parity 证据见第 9 节。尚未完成的包版本选择、可安装 extra、真实 ABACUS 双轨及 Paimon 迁移仍是明确的实施/发布验收，不由本节证据推断完成。

## 8. 实施分支验证（2026-09-13）

随后按 [实施 PLAN](../plans/2026-09-13-forge-engine-version-policy.md) 在隔离 worktree `codex/forge-engine-version-policy` 推进 A 与离线 B。实现包含 native PyATB 双命名/relax marker 兼容、typed service/CLI parser 配置、版本局部分发、abacuslite optional adapter、共同事实白名单与派生投影；legacy facade、request/schema、final 候选和 workspace 事件边界保持不变。

当前工作态验证（`conda` 环境 `paimon`，canonical benchmark 加入前的实现基线）：

```text
conda run -n paimon python -m pytest -q tests/test_parser_backend.py tests/test_collect_abacus_reference.py tests/test_machine_cli.py tests/test_pyatb.py
192 passed in 4.39s

conda run -n paimon python -m pytest tests/test_pyatb_manifest.py tests/test_pyatb_typed.py tests/test_collect_abacus_reference.py tests/test_service_status.py tests/test_machine_cli.py tests/test_contracts.py tests/test_workspace.py tests/test_architecture.py tests/test_parser_backend.py tests/test_pyatb.py -q
749 passed in 29.04s

conda run -n paimon python -m pytest -q
1391 passed, 15 skipped in 123.13s

git diff --check && conda run -n paimon python -m compileall -q src tests
exit 0
```

The focused run includes the typed parser regression for an unexpected reader
`ValueError`; it must propagate for the existing `internal.failure` mapping
instead of being converted into a partial result. The typed PyATB suite also
asserts the new CSR names and explicit nspin 1/2/4 role ordering. These are
offline Forge checks under the repository `paimon` environment.

An independent final review reran the related regression set (`177 passed`) and
reported no blocking finding; `git diff --check` also passed. This review did
not change the Stage 1 or external migration boundary described below.

另以 canonical checkout `abacus-develop/interfaces/ASE_interface/abacuslite` 的指定源码路径探测 `latestio`/`legacyio` 底层 reader：能量 tuple、最终 eV 能量、力帧形状及 stress 单位/符号转换均有适配回归；四 capability parity 与边界矩阵已在第 9 节提升为显式 benchmark 门禁。阶段 1 exact package、真实 ABACUS 双轨发布矩阵及 Paimon 迁移仍按 PLAN 保持未完成，不以 checkout fixture 通过替代。

收口终审（第 7 节记录）：独立文档 reviewer 首轮指出 CLI/Python 配置表述及初审状态标记两处矛盾，修正后复核 SPEC 与 PLAN，结论为“未发现实质阻塞或明确矛盾”。当时仅修改文档，复用第 6 节绑定未变生产代码的 6 项测试证据，未重跑真实计算；第 8 节记录后续实现分支验证。

## 9. Canonical abacuslite Stage 0 parity（2026-09-13）

证据绑定：Forge 隔离分支 `codex/forge-engine-version-policy`，canonical
`abacus-develop` checkout `94576a80169de36e02e637edc2a0963fba9e1838`，源码路径
`interfaces/ASE_interface/abacuslite`。测试直接调用该 checkout 的
`legacyio`/`latestio` 底层 reader 作为 oracle，再调用 Forge 的
`collect_contained(parser_backend="abacuslite")`；没有调用 `read_abacus_out`，因此
不会把 `eig_occ.txt`、`MD_dump` 或轨迹帧一致性提升为 Forge 最小 collect 前置条件。

执行命令：

```bash
conda run -n paimon env \
  ABACUS_FORGE_CANONICAL_ABACUSLITE=/home/james/work/sidereus/workplace/abacus-develop/interfaces/ASE_interface \
  PYTHONPATH=src python -m pytest -q --run-benchmark \
  tests/benchmark/test_abacuslite_canonical_parity.py
```

结果：`15 passed in 1.12s`，exit 0。

矩阵包括：

- `scf`、`relax`、`cell-relax`、`md` 四个 capability，分别对照 v3.10.1
  `legacyio` 与 v3.11.0-beta8+56 `latestio` 的 canonical fixture；比较最终电子能、
  Fermi 能、力/应力最后帧及全帧形状，并核对 stress 的 kbar 单位与符号变换。
- output-only workspace 在没有 `INPUT`、`eig_occ.txt`、`MD_dump` 时仍按底层 reader
  得到同源数值；版本来自 contained running log。
- 截断日志保留已确认的数值事实；非收敛日志保留 numeric parity 并保持
  `unfinished`，没有触发 native fallback。
- 歧义 running logs 和指向 workspace 外部的 symlink 不选择主日志，
  `actual_backend` 保持 null，数值 backend 未被 dispatch。
- 同进程 LTS/develop 交替、两个 workspace 并发执行，`io_backend` 与请求版本逐项
  对齐；两次不同 operation ID 的 typed collect 在只读 INPUT/日志上运行，领域文件
  字节与 mode 不变，reports manifest/events 只追加两条事件。

canonical benchmark 后的回归复核为：focused parser/collector/CLI/PyATB `150 passed
in 3.50s`；owning command `749 passed in 25.26s`；默认全量
`1391 passed, 30 skipped in 107.94s`；`git diff --check` 与 compileall 均通过。

这组证据完成 PLAN 阶段 0 的 canonical checkout parity 与调用隔离门禁；它仍是
源码 checkout 的离线 fixture 验证，不等价于阶段 1 的可安装 exact package、真实
ABACUS native/abacuslite 双轨运行，也不构成 Paimon v1.3 迁移或稳定能力发布判断。
