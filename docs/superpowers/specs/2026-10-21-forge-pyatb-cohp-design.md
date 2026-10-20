# Forge 直接 NAO-COHP / PyATB 消费扩展

状态：2026-10-21 用户确认接入必要性并授权按讨论方向推进；本文件固化该有界
实现选择。上位 [Service/Status SPEC](2026-09-02-forge-service-status-migration-design.html)
与 [IAO W1 SPEC](2026-10-15-forge-cohp-postprocess-design.md) 保持有效。
实施计划：[消费接续](../plans/2026-10-21-forge-consumption-followup.md)。

## 方法与职责

新增 experimental capability `pyatb-cohp`，engine `pyatb`，操作为
`prepare / execute / collect`。方法元数据固定 `direct_nao`，population 为
`COHP`；首批不顺带暴露 COOP。既有 `cohp/postprocess` 的 `method=iao`、
算法、默认和输入不变。两者不是同一方法的两个等价后端。

PyATB 从 H(R)/S(R) 重建并对角化 H(k)/S(k)，进行 NAO 轨道块分析。
Forge 不重写收缩、积分或本征求解，不自动运行 SCF，不发现 latest 计算目录，
不选择自旋态、k 网格或科学接受标准。

## 显式请求

沿用 `forge.request/v1`、UUIDv4 operation identity、workspace-relative paths、
严格未知字段拒绝和现有 outcome/error 语义。Python/CLI 调用同一服务。

prepare 明确提供：

- STRU、HR 文件列表、SR、数值轨道文件的 workspace 内路径；
  `nspin=1|2` 对应 1/2 个 HR，nspin=4 不在本切片范围；
- Fermi energy（eV）；HR 单位沿用现有 ABACUS→PyATB handoff 的 Ry，
  SR 无量纲，晶胞长度从 STRU 读取并明确写入 PyATB Input；
- 两个 1-based 原子索引，以及 PyATB 原生轨道 selector（默认 `all`）；
- 显式分数倒空间 k 点和逐点非负有限权重，长度一致且至少一个权重大于零。
  PyATB 负责归一化；不隐式使用 Γ-only/uniform。此选择服务同输入可比性；
- 有限递增的绝对能量窗口（eV）、正的 `de`、`sigma`（eV）；
  默认 `de=0.05`、`sigma=0.15`，`invert=true`、`shift_to_efermi=true`，
  `spin=sum`（nspin=2 可显式 up/down）。窗口至少容纳两个样本。

默认 copy staging，输入必须自足。在专用 Forge workspace 的 `inputs/`
生成 PyATB `Input`、`STRU` 与 contained 矩阵/轨道目录；先完成所有路径与
目标冲突检查再写文件。显式轨道映射需与 STRU 的 NUMERICAL_ORBITAL 对应，
拒绝不明确/重名映射，不让 STRU 中的绝对或逃逸引用进入引擎。
不要求为运行 PyATB 而额外提供不会被使用的 PP 或 rR。

execute 使用现有 LocalRunner 的 executable/MPI/OMP/timeout/dry-run 约定，
每次只运行一个进程。引擎为外部已安装 PyATB，不自动安装；参考功能版本为
`sidereus-adam@5f7e132` 的完整候选包，具体消费证据另记。基础 Forge 安装
不新增 PyATB/native 强制依赖。collect 可处理外部生成的显式文件，不依赖
本地先前 execute/prepare event。

## 产物与防覆盖

PyATB 初始化 COHP 会清理已有 `Out/COHP`。为保护已有结果，本切片的 prepare
不得覆盖已有目标文件；execute 在启动前拒绝已有 `inputs/Out`（包括 symlink）
或其它会使引擎写出 workspace 的路径。不同运行使用调用方提供的新 workspace；
不隐式删除、重试或覆盖源 SCF。dry-run 同样验证准备与路径前提，不启动进程。

固定 output prefix `COHP`。collect 默认显式路径为
`inputs/Out/COHP/COHP.dat` 与 `inputs/Out/COHP/COHP.meta.json`，
允许调用方指定其它 contained 路径。返回实际 spectrum/meta 的 ArtifactRecord，
保留同结果内 metadata 与 spectrum 的关联；不执行生成的绘图脚本。

检查两列 spectrum 的有限性、递增能量、至少两个样本；metadata 为 JSON object，
COHP 方法、符号/单位、EF、轨道/自旋和 occupied_integral 等必要事实须存在且合法。
`metadata.files.spectrum` 必须对应所选 spectrum，不能借此打开未声明路径。
文件缺失为 missing_output/partial；格式非法为 partial 并保留已知文件与诊断；
不能把 PyATB 零返回码或一个有路径的 JSON 当作完整科学结果。

## 数值语义

- 能量轴 eV，是否相对 EF 由 metadata 如实标记；
- spectrum 为 COHP 或 -COHP，PyATB 的谱密度单位为 dimensionless；
- occupied_integral 是离散 `E <= EF` 零温积分，原值和显示值均保留，单位 eV；
  不是有限温占据加权，也不从绘图窗口积分反推；
- pair factor、spin degeneracy、k 权重方式、Gaussian 展宽原样保留；
  Forge method=`direct_nao` 与 PyATB formula=`COHP` 分开表达；
- 不把曲线符号直接解释为化学结论，不声称单对轨道积分等于键解离能。

## 验收

定向测试应先暴露尚无该能力，再覆盖 wire round-trip、schema/CLI/API parity、
显式 k 权重、ORB 对应、路径碰撞/越界、已有输出保护、真实本地子进程的
成功/失败/超时、collect 缺失/非法/符号单位事实和 append-only event。
不引入第二套 runner 或 IAO 算法。

数值接入使用保留的同输入矩阵，将 Forge 调用与同版本 PyATB 直接调用比较，
确认输入、谱与积分约定一致；没有可用引擎时不伪造该结果。与独立 NAO/WFC
实现的比较须另核对重建本征态、k 权重、能量参考及轨道索引。IAO 与 NAO
结果允许因方法不同而不同，跨方法相等不作为门禁。
