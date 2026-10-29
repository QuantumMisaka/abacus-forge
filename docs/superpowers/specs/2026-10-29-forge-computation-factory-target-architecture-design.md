# Forge “算筹工场”：面向实际消费的后端设计

- 状态：2026-10-29 用户确认收缩方向并授权消融；本修订取代本文件原七层架构与 Phase A–F 框架建设方案。
- Owner：ABACUS-Forge。
- 基础规范：[Contract-First](2026-09-01-forge-contract-first-rearchitecture-design.html)、[Service/Status](2026-09-02-forge-service-status-migration-design.html)、[Engine/Version Policy](2026-09-12-forge-engine-version-policy-design.html)。既有 v1 请求、结果、错误、单 workspace 与事件语义继续有效。
- 实施与验证：[Phase A 收缩记录](../plans/2026-10-29-forge-computation-factory-phase-a.md)、[SCF consumer chain 记录](../plans/2026-10-29-forge-scf-consumer-chain.md)。

## 1. 产品目标与职责

ABACUS-Forge（算筹工场）为人类研发者与 AI Agent 提供可复用的 ABACUS 科学计算 Python API 和非交互 CLI。优先把实际输入、执行、收集和后处理能力交付完整，而不先建设统一所有能力的元数据系统。

| 层次 | 负责的行为 |
| --- | --- |
| Forge | 输入与资产处理、单次引擎调用、解析和独立后处理；返回事实、来源与工件。 |
| 引擎与专业库 | ABACUS、PyATB、ATST、abacuslite 等各自的数值算法、驱动和格式读取；Forge 通过明确接口复用。 |
| 调用方与平台适配 | 选择和组合操作、申请资源、重试、科学判断、ATP Tool、报告与平台发布。 |

复用计算实现与已公开契约，不要求所有 Paimon Tool 都变成一个 Forge capability。Paimon 自有摘要、展示、编排和辅助能力继续由 Paimon 维护。

## 2. 保留已有接口，取消平行框架

能力和请求发现继续使用 `discovery.py`、`request_registry.py`、已有 request 类型，以及 `capabilities` / `schema <capability> <operation>`。结果事实以实际 `OperationOutcome`、metric、artifact 和 observations 为准。

撤回尚未接入运行链的 Phase A `capability_registry.py`、新记录类型及 `capability-contracts` 命令。它们只提供 SCF seed 与自测，重复描述既有事实，并包含未实现的输出、错误的 metric 元数据和不可解析的 schema 引用。消费者改用已有发现接口；不保留另一份声明相同事实的兼容 registry。此次是首次公开发布前、用户明确授权的原型撤回；已交付操作接口的兼容规则仍见 [compatibility](../../compatibility.md)。

后续缺少某项元数据时，在它的实际 owner 中补充，并通过对应消费者验证。当前没有完成全能力输出目录，不把目录完整度设为所有 Tool 的发布前提，也不按固定数量的字段或 evidence booleans 判断能力成熟度。已有 COHP 方法说明、property manifest 与专用结果契约继续保持各自边界。

## 3. 来源记录：记录事实，按需要核对

来源信息沿用现有结果 diagnostics、parser metadata、输入 provenance 和 workspace event，不增加通用 ExecutionIdentity 子系统。

| 使用场景 | 所需来源 |
| --- | --- |
| 执行 | 当前 operation、输入和工件引用、实际启动命令与参数；可获得的引擎和 Forge 版本。 |
| 收集已有输出 | 输出中可识别的生产者版本与源文件、当前解析器及版本；无法得知的原执行环境保留 unknown。 |
| Benchmark、发布或特定复现 | 根据所验证的组合记录候选源码、wheel、镜像、依赖环境和输入；复用已有候选清单和证据。 |

生产者与解析者分别记录。解析历史日志不要求原二进制、容器或 Git checkout，也不把本机版本冒充日志生产者。哈希用于必要的内容完整性、来源绑定或制品核验，不要求每次普通操作重复计算 executable / wheel / SIF hash 或提交 Python lock。

核对只针对操作实际需要的版本、功能或调用方显式要求的约束。现有 parser 的已知版本冲突、格式不支持和缺依赖处理继续有效；来源不全本身不成为新的全局拒绝条件。

## 4. 资源：沿用 GPU/CPU 分工，分开申请与启动

用户确认的现役策略继续保留：ABACUS 计算默认 GPU；独立输入准备、收集和 CPU 后处理按实际成本使用 CPU。资源取决于本次 operation 启动什么，不能仅凭 capability 名称推断。

| 操作 | 集成方式 |
| --- | --- |
| 纯输入准备、结构编辑、日志收集 | 工具自身使用 CPU；生成面向 GPU 的未来 ABACUS 输入不意味着当前申请 GPU。 |
| ABACUS execute | 现役 Paimon profile 保留 GPU 默认与已验证档位；资源与实际 INPUT、可执行程序和启动方式一致。 |
| CPU PyATB / Bader 等独立后处理 | 使用对应 CPU 运行环境；不因前一步是 GPU SCF 而要求 GPU。 |
| ASE/CP、NEB 等含 ABACUS 子计算的操作 | 按驱动及子计算的并行方式传递资源；不将图像并行的 GPU/rank 含义套用到普通 ABACUS。 |

```text
操作默认值 + 调用方显式选择
          ↓
Paimon / 站点适配器申请资源
          ↓
实际分配 + 引擎启动参数 → Forge 执行 → 退出与资源观察
```

Paimon/站点适配器继续负责 `resAlloc`、partition/QOS、GPU 档位、分配与绑定。通用库不固化 SAI 的 CPU/GPU 比例、固定档位上限或 Slurm 参数。独立本地调用可使用调用方已有的资源，不要求经过平台分配服务。

Forge runner 复用当前 MPI/OMP、timeout、命令和环境传递能力。新增 GPU 数、设备绑定或实际分配信息，应随具体执行适配接入并验证；暂不发布脱离运行消费者的 ResourceSpec。通用资源表示需要覆盖零 GPU 的 CPU 操作；这不改变现役 Paimon 的 ABACUS GPU 准入，也不授权自动 CPU 降级。本次不增加新的资源调度实现。

当前 SCF execute 裁决：只按 SCF 消费者暴露站点 `launcher` 与 `env_overrides`，并分别记录 requested command 与 resolved command；无法解析可执行文件时 resolved launch 保持 unknown。无 KPT 的 SCF execute 只有在 INPUT 提供 `gamma_only` 或 1/3 个 finite positive `kspacing` token 时才可 admission。这些扩展不进入 Relax/MD execute 契约；后续实际消费者需要时另行裁决。

资源请求、实际分配和实际启动三者分别记录，未知观测不写成零。MPI ranks 与 GPU 数由引擎和启动方式映射，不设置通用一比一规则。发生 OOM、超时或非零退出时，Forge 返回有来源的事实；外层决定升档、重新申请和重试。整个作业被平台杀死时，终态记录由外部执行管理层补充，不要求进程内必然落盘。

先贯通单节点 ABACUS GPU 与独立 CPU 后处理，再按实际需要接 ASE/CP、NEB；多节点扩展随启动能力和真实验证推进。

## 5. 目录、输出与诊断按消费者补齐

**目录放置。** 先复用调用方已有 project parent 和路径解析，向 Forge 提供明确 workspace。只有可复用的路径解析、冲突检查确实缺失时才抽取小型 helper。不预建 ProjectContext / WorkspaceAllocator / ProjectManifest 框架、固定 role 枚举或跨 workspace 的第二套审计索引。既有路径 containment 和 append-only event 继续保护实际工件交接。

**输出映射。** Paimon 中声明来自 Forge 的输出核对实际工件、单位、来源和缺失语义，允许显式重命名与有依据的派生。摘要、报告及平台输出由 Paimon 自有契约定义。多个操作的组合属于调用方；不要求全部 Tool 输出是 Forge canonical outputs 的子集，不自动生成整套 Tool。

**诊断。** 复用已有错误 envelope、运行退出事实、observations 和 diagnostics。遇到真实消费缺口再补稳定字段，不另建 collector registry、封闭的全局 diagnostic 枚举或恢复动作语言。平台特有信息由 adapter 解释为有来源的事实；Forge 不直接读取 ATP/Slurm 传输协议。数据保真、有效 JSON 与既有错误类别仍需验证。

## 6. 迁移与相称验证

以最新 Paimon v2 基线为需求来源，逐能力移植实际缺口。2026-10-29 读取的 `app-tools/main@38c0f9073` 为 toolbox `1.2.84`；`app-tools-forge-latest-main-sync@7cd73eeb3` 是对应规划工作树，不是已通过替代验收的新运行候选。旧 `1.2.76` Forge-route candidate 和历史 Benchmark 证据按其原身份保留。

近期先完成一条 SCF 输入→执行→收集→Paimon 消费链，按实际需要补目录放置、资源交接和输出映射；再扩展 Relax/MD、CPU 后处理和驱动。完整替代仍需解除旧依赖并在相应 ABACUS Agent Benchmark 上同等或更好，不能由离线测试或删除 import 推定。

验证强度随变更及所声称的结果选择：

- 契约或消费者改变，检查实际请求、结果与交接；真实错误用邻近回归保护。
- 仅收缩未消费的元数据原型，比较保留接口及相关离线行为；不为删设计新增真实计算。
- 安装、引擎启动或打包边界改变，补对应安装态或真实运行证据；相关输入未变时复用已有证据。
- 在完整迁移或发布验收处汇总候选和适用证据，不要求每个小切片重跑全套 Benchmark、冻结全部哈希或重复 SAI 计算。

本修订不批准旧 Contract System M1–M4，不替换专用科学方法设计，也不新增发布、平台上传或生产运行授权。后续实现按具体缺口推进，不以完成一套预设架构层级作为交付目标。
