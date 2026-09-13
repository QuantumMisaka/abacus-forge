# Engine/Version Policy 分阶段实施计划

**Goal:** 保持 native 默认和既有 typed collection 行为，先交付版本兼容增量，再验证可选 abacuslite 后端。

**Spec:** [Engine/Version Policy](../specs/2026-09-12-forge-engine-version-policy-design.html)，2026-09-13 收口版本。

**Authorization:** 用户在系统性审查后要求“进行收口”并以本 SPEC 推进 PLAN 与 subagent-driven development。本轮已在隔离分支执行 A 与离线 B；真实计算、可安装 extra、双轨发布和外部迁移仍不在本轮授权结果内。

**Architecture:** 复用 collection 来源选择、共同事实提取与 typed 投影；只替换主日志电子标量/力/应力读取层。配置置于 service 实例，CLI 调用同一 service；error schema、final 候选、legacy surface 和 workspace 审计保持原契约。

**Verification:** 默认离线 owning tests、API/CLI parity、schema/admission/event 回归；真实双轨与 extra 安装是分阶段显式验收。

## 当前实施状态（2026-09-13）

本轮实现保留 native 默认，未修改 v1 request JSON、workspace schema、错误 envelope 字段、final-structure 候选或 legacy `collect()`。实现证据绑定当前隔离分支 `codex/forge-engine-version-policy`；原始工作树在分派前已有的 SPEC/PLAN/evidence/ROADMAP/README 修改不计入下面的代码包。

### 字段责任表

| 责任层 | 当前实现与字段 | 缺失/来源边界 |
| --- | --- | --- |
| 共同来源与事实 | contained 日志选择、INPUT/结构快照、final 候选、artifact/time/report/band/DOS/MD_dump、版本标记、SCF/relax 计数、收敛/normal-end、`band_gap`/`nelec`/`volume` 等非后端数值 | 沿用现有来源选择与 contained 规则；不因 optional parser 缺值切换来源 |
| 可替换主日志数值 | `total_energy`、`fermi_energy`、`force(s)`、`stress(es)`；abacuslite 通过 `legacyio`/`latestio` 局部函数读取，native 路径保留原 reader | optional 路径不运行 native 数值 registry/force/stress reader；缺值保持缺失 |
| 共同派生与 typed 投影 | `energy_per_atom`、压力/压力序列、virial、单位、来源与 derived kind | 从已选 backend 事实推导；不补零、不把 MD 总能与电子 total energy 混合 |

### A. Native 兼容增量

- [x] 新 CSR 名称 `hrs1_nao.csr`/`hrs2_nao.csr`/`sr_nao.csr`/`rr.csr` 与旧名兼容；nspin=1/4 shared、nspin=2 HR up/down、可选 rR 的回归已加入 `tests/test_pyatb.py`/manifest tests。
- [x] `STEP OF RELAXATION : N` 已纳入 relax step 解析；缺标记仍省略且不改变状态。
- [x] final-structure 选择实现未改动，既有唯一旧候选、native final 优先、歧义/不可解析规则继续由 owning tests 锁定；未把轨迹末帧升级为 final。
- [x] 离线 owning 回归已执行；[ ] 获授权的真实两轨 PyATB/relax/cell-relax 证据仍待补齐。
- [x] README/ROADMAP 已补充当前能力与历史归因状态；历史失败数字保留。

### B. 阶段 0：离线 backend 接入

- [x] 共同/后端/派生字段责任已落在本计划并由 collector 白名单与 native-reader guard 回归约束。
- [x] `ScfServiceSet`、`RelaxServiceSet`、`MdServiceSet` 构造器与 default 工厂接受 keyword-only `parser_backend="native"`、`output_version=None`；配置只在 collect admission 消费，legacy facade 保持旧路径。
- [x] CLI `operation collect` 透传配置；非 collect 或非 ABACUS collect capability 在读取/dispatch 前返回 `request.invalid`；request JSON/schema 保持不变。
- [x] 版本正规化覆盖 `v3.10.1`、裸 `v3.9.0`、3.9 develop `.x`/预发布与 `v3.11.0-beta8+56`；import 延迟到合法 collect admission 后，禁止 calculator/global switch/executable 探测。
- [x] 错误顺序的离线回归覆盖无效配置、caller/log 冲突、unsupported log、optional 缺包、无主日志不 dispatch、缺值不 fallback，以及 API/CLI 的既有 error schema/exit 映射。
- [x] canonical checkout 的四 capability 完整/截断/非收敛/缺辅助文件/output-only/歧义/越界/重复调用 parity、同进程交替版本与并发只读验证已在 `tests/benchmark/test_abacuslite_canonical_parity.py` 固化；指定 checkout 的 15 项 benchmark 通过。
- [x] 当前 owning suites、architecture/contracts/workspace 与默认离线全量回归已通过；真实 parser package/双轨 parity 仍是未完成证据项。

### C/D

阶段 1 的 exact installable package、fresh extra、native/abacuslite 四 capability 双轨矩阵以及 Paimon 工具矩阵/运行时依赖清零仍未执行；它们不由本轮离线通过推断完成。

## A. Native 兼容增量

职责文件：`src/abacus_forge/pyatb_manifest.py`（名称分类）、`collectors/abacus.py`（步数标记）、`tests/test_pyatb_manifest.py`、`tests/test_pyatb_typed.py`、`tests/test_collect_abacus_reference.py`、`tests/test_service_status.py`，以及 `tests/real_smoke/` 的 owning gate。

- [x] 为新 CSR 名称和 nspin=1/2/4 显式角色/请求顺序建立回归；只在复现断点处修改，不增加 rename/白名单。
- [x] 为 `STEP OF RELAXATION : N` 建立失败回归并补解析；无标记仍省略，不改变状态。
- [x] 保留唯一旧 final 候选、native final 优先、歧义/不可解析/越界测试。LTS 历史原因仍绑定原始 diagnostics/fresh evidence，未把缺 STRU_FINAL 当作原因。
- [x] 跑上述离线 owning tests；[ ] 真实计算获授权后，以两轨实际矩阵进入 typed PyATB prepare/execute/collect，保留具体 nspin 与输入身份。relax/cell-relax 分别记录。
- [x] 更新 README/ROADMAP 的当前能力说明和历史归因；旧失败数字保留，以新增证据校正解释。此增量不等待 abacuslite 发布包。

## B. 阶段 0：离线 backend 接入与可行性验收

职责文件：`src/abacus_forge/collection.py`、`collectors/abacus.py`、新增内部 backend 模块（具体命名由实施者决定）、`services.py`、`machine_cli.py`；必要时调整 `collection_results.py`、`md_results.py` 的内部诊断消费，公共语义保持。相关测试位于现有 collect、service、MD、machine CLI 和 architecture owning suites。

- [x] 从当前公开 metrics/observations 提取字段责任表，落在本 PLAN 与 owning parity tests：每项字段的共同/后端责任、来源、单位、末步选择和缺失语义均按 SPEC 固化；不让两个完整 collector 合并结果。
- [x] 先以窄行为证据抽取共同来源和共同解析，证明 native 基线行为保持。backend 失败不作为 stdout 来源切换条件；沿用原始来源条件。
- [x] 为三类 ServiceSet 构造/default 工厂增加 keyword-only `parser_backend`、`output_version`，保存于实例并仅在 collect admission 验证；legacy facade 不启用。CLI 仅作配置传递和适用 operation 检查。
- [x] 实现纯版本正规化/分发，用 SPEC 覆盖的版本样例固定映射；后端 import 延迟到合法 collect admission 后。仅调用局部读取函数，禁止 calculator/global switch 和 executable 探测。
- [x] 为配置、版本、错误顺序、admission/event、actual_backend null 和缺值不 fallback 建立离线行为回归；API/CLI 继续使用既有 envelope/schema。
- [x] 使用 canonical 指定 commit checkout，通过四 capability 的完整、截断、非收敛、缺辅助文件、output-only、歧义、越界与重复调用 fixture，证明实际 abacuslite 后端字段 parity；命令与结果写入 evidence。
- [x] 验证同进程交替版本、并发 workspace、只读领域文件与 append-only 审计；底层 reader 路径不要求 `eig_occ.txt` 或 `MD_dump`。
- [x] 运行 owning suites、`tests/test_architecture.py`、`tests/test_contracts.py`、`tests/test_workspace.py` 与默认离线全量回归；canonical parity 另以显式 `--run-benchmark` 门禁执行，未放宽既有事实集合。

验收时使用仓库约定环境：`conda run -n paimon python -m pytest ... -q`；新测试文件的最终名称由实施者记录，不能将尚未创建的用例写成已通过。

## C. 阶段 1：可选包与双轨发布证据

依赖 B 验收完成。职责文件：`pyproject.toml`、包安装/architecture owning tests、`tests/real_smoke/`、README 与新的候选 evidence。

- [ ] 核验当时实际可安装的 canonical 发布包，选择已验证的 exact pin；源码 checkout 可用不代表 extra 已交付。
- [ ] 默认 clean wheel 保持现有依赖集合；extra 在 fresh venv 执行四 capability fixture collect，验证显式选择与缺包失败。
- [ ] 显式复跑 native/abacuslite × LTS/develop × 四 capability 同源 parity；记录实际 PW/LCAO、nspin、源码版本、完整 executable hash、构建偏离、输入身份、命令与输出。未运行组合不得宣布支持。
- [ ] 发布候选必须满足对应矩阵，不能用 skip/xfail 代替已知限制的正向断言；发布动作另按实际授权执行。

## D. 外部迁移交接

Paimon 工具覆盖矩阵、旧依赖清零、Agent Benchmark 与生产 E2E 由 `app-tools/toolbox/ABACUS` 维护，本计划只引用 SPEC 的 owner 和边界。它们不成为 A/B 的前置条件；未验收不得宣称 Paimon v1.3 迁移完成。

## 回退与验收边界

可选 backend 未通过时继续以 native 为默认，不提交自动 fallback；调用方可使用新 operation ID 显式选择 native。已写 admission/event 不删除或改写。若可行性调查要求改变公共事实、final 候选或 error schema，先回到 SPEC；内部模块布局、fixture 和容差细化由实施者依据证据完成。

当前已完成 A 与离线 B 的代码、回归和默认离线门禁；C 的可安装 extra/双轨证据与 D 的外部迁移仍未执行，不能由本轮通过推断为已交付。
