# abacuslite 插件维护位置与独立分发设计

状态：历史设计讨论与跨仓迁移候选方案，2026-10-16 更新。用户已批准建立 `QuantumMisaka/abacuslite` 独立源码仓库并推进首轮包建设；完整跨仓迁移与正式 PyPI 发行尚未完成。

独立包现行设计与执行记录已迁至 [abacuslite 设计](https://github.com/QuantumMisaka/abacuslite/blob/main/docs/design.md) 和 [首轮实施记录](https://github.com/QuantumMisaka/abacuslite/blob/main/docs/superpowers/plans/2026-10-16-standalone-bootstrap.md)。本文保留前期证据、方案比较及 Forge 消费边界；包内实现约定以新仓规范源为准，不在两仓同步编辑。

首轮源码已交付至新仓 `main`，实现提交 `e984c44`。[包 CI](https://github.com/QuantumMisaka/abacuslite/actions/runs/38855256056) 的 Python 3.10/3.12 环境均通过 wheel 与 sdist 重建安装验证，每组 97 通过、11 跳过；跳过包括 9 个真实引擎用例及 2 个上游占位用例。本地已安装候选包的 Forge parity 为 15 通过，ATST profile/input 检查为 32 通过。消费检查只调整 scratch 测试副本的夹具位置或显式 vendored import；未修改消费者生产代码，不能据此宣布跨仓迁移或真实引擎验收完成。

## 已定方向与待确认项

已确定独立 `QuantumMisaka/abacuslite` 源码仓库与 Python 包；不再将源码维护位置列为待决事项。首轮采用保留公开 import 的抽取、通用补丁归并、只读解析和实例级 reader 隔离，候选版本为 `1.1.0rc1`。

仍待明确 ABACUS interfaces/CI 中“parser”的具体边界；推荐薄兼容适配与引擎集成测试，不复制另一套生产解析实现。本文后续比较属于决策历史，跨仓接入章节仍是候选方案；不能视为 ABACUS 上游已接受迁移或生产依赖已经切换。

本设计只调整源码维护与分发方向。Forge 的 native 默认、optional parser、事实和审计边界保持现行约定；“共同依赖”不等于本次把 Forge 改成强制依赖或默认改用 abacuslite。若要改变默认后端，另行决策。

## 当前证据与启动基线

| 对象 | 2026-10-16 核对结果 |
| --- | --- |
| ABACUS develop | `4b92455cab1b1a51e8534b7eb869798ae1241b1b`；已 fetch，并更新本地隔离检出 `abacus-develop-abacuslite-review`。原 develop 的未提交 toolchain 改动保留。 |
| abacuslite 源码 | `interfaces/ASE_interface`；与上一轮验证的 `8ae37fcd6cb9043a4a0c7ebde2c062d97f393bdb` 相比，该目录及 ASE CI 无差异。新引擎提交涉及 DOS 输出，不据此宣称真实集成仍已验证。 |
| ATST main | `45d8c78de8a605c127cd4c36742d0c9525a0a6b6`，2.2.8；本地检出与远端相同。 |
| ATST 副本基线 | `70f7ed69b5677c447afdc78e05240e93da660e66`；本地通用语义补丁见其 PATCHES.md。 |
| 版本与分发 | 上游 pyproject 声明 `abacuslite==1.0.0`；本次 PyPI JSON 查询返回 404，不等于项目名已保留或保证可注册。 |
| 已执行验证 | 上游 I/O、K 点测试 34 通过、2 跳过；ATST profile/重排/多帧测试 61 通过；wheel、sdist 构建成功；wheel 安装后 socket/版本解析测试 12 通过。环境 Python 3.12、ASE 3.29.0；未覆盖声明的全部依赖版本，未执行真实 ABACUS 集成。 |
| 包装缺口 | 本次构建的 wheel、sdist 均无许可证文件，sdist 无现有测试所需夹具；源码安装成功不能代替发布产物验收。 |

本轮保留日志与产物在 `/home/james/scratch/abacuslite-publishing-audit-20261016-25in2e6b/`。它们是本地调查证据；实施时将必要、可公开的证据和回归夹具整理进入选定的 abacuslite 项目，不让测试依赖该绝对路径。

执行开始时重新检查远端、发布状态和相关 diff。若仅无关文件更新，可复用对应代码不变的测试证据；若改变解析器、引擎格式或依赖，补跑受影响检查。版本与提交用于识别交付物，不以固定旧提交阻止正常演进。

## 维护权与职责

无论源码选址，abacuslite 都有明确的主要编辑、issue、版本及发行入口。保留原作者、许可证、来源提交和必要历史；不把归并工作改写为全新原创项目。个人维护的项目作为 ABACUS 社区正式入口，需要通过上游 PR 与维护者协调；用户支持个人维护不等于上游已接受删除或重定向原入口。

| 所有者 | 承担 | 不承担 |
| --- | --- | --- |
| abacuslite | ASE FileIO/socket calculator、profile、INPUT/STRU/KPT、日志/轨迹/电子态读取、通用 K 点工具、兼容性与发行 | ATST 工作流、Forge schema、调度器、ATP/MCP、ABACUS 二进制安装 |
| ABACUS | 引擎输出契约、当前引擎与插件的真实集成测试、输入与测试资产 | 长期维护另一份可编辑的插件生产源码 |
| ATST | NEB/MD/恒电势等工作流、配置与任务层适配、消费者回归 | 长期独立修改同一解析实现 |
| Forge | 选择 parser、投影事实、单位/缺失/状态与审计、consumer parity | 实例化 calculator 来完成 output-only collect、修改上游全局 I/O 开关 |

上游迁移未合入期间保留来源与差异台账，明确一次修复的主要提交入口及移植去向，避免自动双向同步。只建立“打包镜像仓”不能自行解决补丁分裂；维护位置的选择也不能替代补丁归并与上游协调。

## 维护位置比较与推荐

源码仓库、Python 分发包和维护团队是三个不同维度。独立 PyPI 包不要求独立 GitHub 仓库；同仓源码也不要求 `abacuslite` 运行时依赖 `atst-tools`。PyPI Trusted Publishing 明确支持一个仓库对应多个 PyPI 项目。

| 维度 | A 独立 `QuantumMisaka/abacuslite` | B ATST 仓内独立子项目 | C 维持当前内嵌副本 |
| --- | --- | --- | --- |
| ABACUS/Forge 安装 | 单独安装 abacuslite | 同样单独安装 abacuslite | 直接依赖内部路径会耦合 ATST；现状未建立独立发版 |
| 插件与 ATST 联合改动 | 两个 PR/提交，候选包验证组合 | 同一 PR 可修改双方并运行候选包测试 | 修改方便，但副本与上游差异继续积累 |
| 版本与发布 | 自然对应独立 tag、工作流、变更记录 | 需要独立子包版本、tag 前缀、构建与发布工作流 | 当前包版本与 ATST 发版不能准确表达插件身份 |
| 仓库管理开销 | 新仓库的权限、issue、文档和 CI 配置 | 复用仓库管理，但增加多包 CI 与发布路由 | 短期较少，长期承担副本及差异检查 |
| 通用 ASE 用户与上游贡献入口 | 入口直接，插件职责清晰 | 需要仓内独立导航、组件标签与维护边界 | 容易把通用能力视为 ATST 私有实现 |
| 维护者 | 可由现有维护者维护，无需额外团队 | 同一团队内协作便利 | 当前维护者承担补丁同步 |
| 第三方兼容验证 | 必须执行 ABACUS/ATST/Forge 检查 | 同样必须执行；同仓成功不代表发布包可用 | 当前 vendored 测试不足以证明外部包行为 |

B 是成立的备选，推荐布局为 `atst-tools/packages/abacuslite/{pyproject.toml,src/abacuslite,tests,...}`，ATST 主包仍位于自身 `src/atst_tools`。两个分发包只拥有各自文件；ATST wheel 不再捆绑第二份插件实现。依赖方向始终为 `atst-tools -> abacuslite -> ASE`，Forge 和 ABACUS 可只安装 abacuslite，不带入 ATST 工作流依赖。

ATST 当前内置目录已有独立 pyproject，core 使用包内相对导入，说明子包分发具有结构基础；这不构成该副本已满足首发要求的证据。现行 `.github/workflows/publish-pypi.yml` 只处理 ATST 根项目，绑定 `vX.Y.Z` 与 ATST release preflight。B 仍需新增独立构建目录、发行产物、检查与 PyPI 项目配置；可使用 `abacuslite-vX.Y.Z` 标签避开现有 ATST tag 路由。同仓联合提交不能省略“先验证候选插件、再发布插件、再发布依赖它的 ATST”的顺序。

对当前目标推荐 A，依据是已存在 ABACUS CI、ATST、Forge 三类调用边界，插件还包含通用 ASE FileIO/socket 能力；它的兼容范围与发布原因已不限于 ATST。A 提供直接的通用贡献入口，减少长期将通用补丁当作 ATST 私有补丁管理的倾向。这个判断不意味着 B 会必然产生依赖耦合，也不保证另建仓库就会自动改善同步或稳定性。

A 的实际代价是跨仓修改与额外仓库管理；通过候选 wheel 联合测试、有限稳定导出及独立包版本缓解，不能宣称成本为零。B 更适用于未来插件改动长期主要伴随 ATST、维护者优先减少仓库数量且愿意承担多包发布路由的情形。当前没有统计全部历史协同改动频率，因此不以未经测量的“改动比例”作为结论。

若选 B，可长期使用，无需预设过渡后强制拆仓；保持独立 import、包元数据与测试边界即可保留以后迁移的余地。若选 A，则直接建立独立源，无需先做一次仓内搬迁。两案共同必须完成源码归并、安装包验证、只读解析、消费者导入统一及上游协调；这些成本不能算作独立仓库特有代价。C 不推荐作为通用插件的最终交付模式。

## 仓库结构与插件接口

以下为 A 的推荐结构；B 在 `packages/abacuslite/` 下采用同样的包内结构，GitHub 工作流仍位于 ATST 仓库根目录。首次抽取保留现有模块与可消费符号；模块重排和语义修复分开验证。

```text
abacuslite/
  pyproject.toml
  README.md
  LICENSE
  CHANGELOG.md
  src/abacuslite/
    __init__.py
    core.py
    io/{generalio,legacyio,latestio}.py
    utils/ksampling.py
  tests/{unit,fixtures,integration,packaging}/
  examples/
  docs/
  .github/workflows/
```

`src` 布局便于验证安装物，防止测试从仓库根目录误导入源码。首轮仍保留 `from abacuslite import Abacus, AbacusProfile, AbacusSocketIO` 和消费者使用的 `abacuslite.io.*` 路径。迁出内嵌测试时保留行为覆盖与 fixture，并更新调用入口；不因整理目录而重写 calculator。

“plugin”采用现有 ASE calculator 接口，无需修改 ASE 核心。不在本次承诺兼容历史 `ase-abacus` 的所有命名、私有函数或自动注册机制；新增通用入口只在真实消费者需求明确后设计。ABACUS executable、赝势和轨道仍由调用者显式提供。

纯 I/O 必须可在没有 ABACUS executable 的环境工作；保留 Forge 所需的底层日志函数，不能强制所有解析都经过 calculator 或完整 `read_abacus_out`。

## 源码归并与兼容契约

基线取最新 ABACUS 插件，而非直接发布 ATST 的旧快照。逐项移植并验证 ATST 通用补丁：

- 缺失费米能级容错；在 calculator 结果中保留 `efermi`，恒电势求根仍归 ATST。
- SCF 当前结构帧选择、原子映射、周期性平移、实际 STRU 文件名与损坏帧检查；保留原生 relax/MD 的预期帧语义。
- point-KPT 小数坐标与权重往返修复。
- 保留上游已有 socket、错误诊断、STRU 晶格参数修复及其他最新变更。

明确处理的契约差异：上游已不再于解析时删除 `eig_occ.txt`，ATST 仍删除且有回归要求一次性消费。推荐独立包采用重复读取不修改源文件的契约；ATST 相应测试改成验证重复读取与输入完整性。不能为满足旧断言恢复删除行为，也不能只移除失败测试。变更应附旧行为失败与新行为成功的证据、变更说明。

已确认结构风险：两份现有 core 均用模块级 `__LEGACYIO__` 选择 reader。实施先复现同进程交替版本/多 calculator 的干扰，再做有界修复，保持公开构造与结果接口；calculator 内部应保存自己的选择。兼容 helper 若保留，不得再控制其他已创建实例。Forge 继续使用局部函数引用，避免通过 calculator 或全局切换读取输出。

兼容清单至少覆盖：公开导入、profile/版本格式、输入写入与重排、能量/力/应力/Fermi 的单位和缺失值、LTS/develop reader、SCF/relax/MD 帧行为、重复只读解析、socket 固定胞与可用属性。新功能的支持范围按引擎能力记录，不能把 socket 等新能力泛化为所有 LTS 版本都支持。

## ABACUS interfaces 与 CI 推荐方案

此节依赖尚待确认的“parser”含义。推荐保留 integration harness：使用独立包完成解析，以参考值、结构/单位/缺失值断言和引擎输出夹具检查兼容性。原调用方式确需适配时才加薄 wrapper；现有 `from abacuslite import ...` 可直接延续，不为安装包额外增加一层抽象。

不保留另一套生产解析器或静默回退。单独的少量格式断言可用于暴露引擎格式变化，但不复制完整 parser，也不把受测 parser 的输出本身当作唯一正确性 oracle。

CI 将插件安装改为明确版本的 `pip install`，仍构建并运行当前 PR 的 ABACUS 二进制。保留 SCF、relax、MD、band、magnetic 用例及失败目录；包单测由 abacuslite 项目负责，不能再以运行主仓本地 core.py 冒充已安装包验证。

| 验证线 | 插件来源 | 目的 |
| --- | --- | --- |
| ABACUS PR 常规检查 | constraints 中的已验证发布版本 | 当前引擎与已发布消费者契约兼容 |
| 跨仓候选检查 | 显式指定的候选 wheel 或精确提交 | 输出格式/API 协同变更，在正式发布前验证 |
| 周期兼容检查 | 最新发布版本 | 发现已验证版本与最新插件之间的差异，推动依赖更新 |

候选检查无需正式 PyPI 发布，避免“先发包才能测、先测试才能发包”的循环。候选来源作为受控输入；普通 PR 不拥有发布凭据。只有实际已配置并通过的 CI 才能记为集成完成。

CI 应检查导入包的路径与版本，防止当前目录中的同名旧源码遮蔽已安装包。移除源码副本前保留用例与安装迁移说明；历史 `cd interfaces/ASE_interface && pip install .` 路径的去留在上游 PR 明示，不能保留一个同名旧包继续覆盖新发布包。

## 版本与分发

区分三个身份：abacuslite 发布版本、ABACUS 引擎版本/提交、输出格式兼容范围。插件版本不跟随引擎版本编号；每次发行发布兼容矩阵和已知限制，不能用当前 `1.0.0` 标记不同源码的多个发行物。

首发序号在补丁归并与 API 差异确认后决定。保留既有接口的增量版本可采用 `1.1.0rc1` → `1.1.0`；若存在无法兼容的公共 API 变更，应单独裁决迁移或主版本升级，不预先保证 1.x 完全兼容。

发布 wheel 与 sdist；许可证、作者、项目 URL、版本源和直接依赖完整。sdist 包含运行其测试所需的 fixture；wheel 是否携带测试资产按运行需要确定。验证从 sdist 重建 wheel、在无源码路径与无 system-site-packages 的新环境安装，以及真实消费者共同安装。依赖下限以实际测试确定，不照抄未经验证的 `ase>=3.22.0`；按最低支持版本与当前版本测试，不建立无证据的过宽兼容承诺。

GitHub release 对应源码 tag 与同一组已测试产物；测试完再上传这些产物，不在上传阶段重新构建。推荐 GitHub Actions + PyPI Trusted Publishing。创建远端仓库、配置 PyPI 所有权及真实发布属于实施/外部操作阶段，本次设计讨论不执行。

ATST 迁移时先建立统一 import 入口与外部包行为测试，再统一所有直接副本导入；声明经验证的依赖范围，交付环境用 constraints 固定具体组合。副本过渡期间不得与外部实现混用；退出后删除静默 fallback。

已知外部调用者还包括 Paimon v3：`app-tools-forge/toolbox/ABACUS/utils/abacus_structure_io.py::_import_atst_generalio` 直接导入 ATST 的 vendored 路径。退出副本前必须迁移此调用，并运行对应结构读写与安装消费回归；只验证 ATST/Forge 不足以关闭这项门禁。若其他已发布消费者无法同步升级，ATST 可以暂时保留旧 import 路径的纯转发层，统一委托独立包并注明弃用范围，不保留第二份实现。Paimon v2 生产代码不属于本任务默认写入范围，其升级按 owner 流程处理；不得通过更新其依赖破坏既有生产交付。

Forge 沿用 optional extra 的实际发布版本 exact pin，native 默认不变。修订旧 Engine/Version Policy 中的 canonical 所有者描述与相应 Stage 0 oracle 路径；不能因为新仓库成立，就绕过现有 fresh-extra、parity、双轨发布门禁。

## 实施顺序与可观察验收

以下是设计层阶段与退出条件，不替代批准后的具体实施 PLAN。

| 阶段 | 工作 | 退出条件 |
| --- | --- | --- |
| A 基线与契约 | 复核最新 refs、补丁、调用点（含 Paimon 直接导入）、依赖、现有 tests 与安装路径 | 明确源码归属、兼容表、差异与回归落点 |
| B 独立源码 | 抽取源代码和历史/归属信息，建立包与测试目录 | 公开导入与既有行为保持，wheel/sdist 可安装与测试 |
| C 补丁归并 | 移植通用补丁，修复确认的只读/实例隔离问题 | 原症状回归、上游能力与 ATST 所需行为共同通过 |
| D 候选联合验证 | 本地候选 wheel 验证 ABACUS、ATST、Forge | ABACUS 真实集成、ATST 外部后端、Forge parity；共装环境无副本遮蔽，默认离线测试不依赖集群 |
| E 发行与接入 | 发布已验证版本，更新 ABACUS CI 与消费者依赖 | 干净环境可从索引安装；安装版本与测试产物一致 |
| F 退出副本 | 上游接受接口迁移，ATST 退出 vendored，迁移 Paimon v3 已知调用者，文档改指新源 | 结构读写与安装消费回归通过；无隐式混用；必要的旧路径仅转发；按已验证消费者/依赖配对版本回退 |

ABACUS 格式/API 协同变更用阶段 D 候选通道验证，不要求先完成阶段 E。任何失败保留原日志与来源，区分引擎、插件与消费者责任；不通过降低科学容差或将缺失事实补零使检查通过。

ATST 的真实 NEB/恒电势等验收选择受本次变更影响的现有案例；Forge 按当前测试入口执行包级、四 capability parity 与发布所需双轨真实证据。单测通过不等于科学收敛或完整平台交付。

## 现有规范关系与后续决策

本 Draft 不覆盖已批准规范。若批准，需在 Forge 现行 Engine/Version Policy 中明确更新 canonical 来源及 ATST 维护模式描述；保留该 SPEC 的默认后端、结果语义与验收要求。独立项目实施 PLAN 在设计确认后编写，并明确各仓写入范围、依赖顺序、回退和发布步骤。

当前需用户确定源码选址 A/B 与“parser”职责；其余普通实现选择采用本文推荐。完整设计确认后进入执行规划，不重新询问已经确认的独立分发与共同消费者方向。阶段 A 先收口选址；B 的阶段 B/E 在 ATST 子项目中完成，其余行为与消费者验收要求相同。

独立审阅（2026-10-16）指出退出 ATST 副本前遗漏 Paimon 直接导入者。核对现有调用后已补入阶段 A/F 与消费门禁；审阅不替代用户对 parser 职责与完整设计的确认。

## 依据

- [Forge 当前 Engine/Version Policy](2026-09-12-forge-engine-version-policy-design.html)与[分阶段计划](../plans/2026-09-13-forge-engine-version-policy.md)。
- [ABACUS 插件源码](https://github.com/deepmodeling/abacus-develop/tree/4b92455cab1b1a51e8534b7eb869798ae1241b1b/interfaces/ASE_interface)与[现行 CI](https://github.com/deepmodeling/abacus-develop/blob/4b92455cab1b1a51e8534b7eb869798ae1241b1b/.github/workflows/ase_plugin_test.yml)。
- [ATST 补丁台账](https://github.com/QuantumMisaka/atst-tools/blob/45d8c78de8a605c127cd4c36742d0c9525a0a6b6/src/atst_tools/external/ASE_interface/PATCHES.md)与[后端选择](https://github.com/QuantumMisaka/atst-tools/blob/45d8c78de8a605c127cd4c36742d0c9525a0a6b6/src/atst_tools/calculators/abacuslite_backend.py)。
- [PyPA src 布局说明](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)；[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)。
- [PyPI 多项目仓库的 publisher 支持](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)；[ATST 当前发布工作流](https://github.com/QuantumMisaka/atst-tools/blob/45d8c78de8a605c127cd4c36742d0c9525a0a6b6/.github/workflows/publish-pypi.yml)。
