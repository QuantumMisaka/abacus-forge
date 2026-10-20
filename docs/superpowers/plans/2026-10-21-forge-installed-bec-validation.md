# Forge 安装消费与真实 BEC 接续验证

状态：本轮安装消费、真实 MgO 单列与有限敏感性验证完成，独立审查通过。
用户在本地实现交付后要求继续按 SPEC/PLAN 推进，本计划范围已闭合。
本计划承接 [BEC 实施计划](2026-10-21-forge-bec-implementation.md) 的真实输入验收
和 [消费接续计划](2026-10-21-forge-consumption-followup.md) 的安装包消费缺口。
产品/算法契约仍按 [BEC SPEC](../specs/2026-10-21-forge-polarization-bec-design.md)，
不重做已经通过的完整离线实现任务。

Ruling：前轮“不启动新 ABACUS 计算”是已完成实现轮的边界；本轮按用户继续推进
剩余验收的指令，开展单机、小规模、逐阶段可停止的真实验证。仅使用既有本地
引擎与输入资产；不提交 SAI/云端作业，不发布/推送，不触碰 Paimon 并行工作线。
先完成资源与输入核查，再逐步启动。真实实验结果不能自动晋升 stable。

工作树继续使用 `forge-integration-reference-review`，HEAD f590367 + 前两轮
已审查 dirty 内容。科学事实、包消费、科学收敛分别记账。

### Task 1：候选 wheel 与隔离安装

- [x] 构建当前候选 wheel；新 venv 无 system-site，记录依赖、来源与 wheel 内容。
- [x] installed-only 检查新增模块、schema、CLI 与 owning 回归；不得将 PYTHONPATH
  注入测试子进程伪装安装消费。
- [x] 核对包内容与当前源码一致、pip check、安装态声明范围。

### Task 2：真实计算输入和最小探针

- [x] 选用已有 PP 的小型绝缘材料（优先两原子 MgO），记录固定结构、泛函/PP、
  cutoff/k 网格、自旋、引擎版本与运行环境；比较依据来自原始或官方来源。
- [x] 单进程先跑零位移 SCF 与一个 gdir NSCF，核查 SCF 电荷交接、原生输出、
  正常结束和解析。每次有有限 timeout，失败先诊断，不盲目批量启动。
- [x] 确认实际 collector 能消费原生格式；若暴露产品缺陷，先有回归，再修复并
  更新 wheel，不能用手工修日志替代适配。

### Task 3：真实 BEC 列与敏感性

- [x] 在同一固定晶胞上计算明确原子的 x 位移响应；0/±delta 与三 gdir 齐全。
  调用方脚本组织计算，不把 workflow 放进 Forge core。
- [x] 使用显式 offsets 与有条件 auto 对照；保留原始量子、路径与所用变化界。
  自动连续性为条件式判断，不凭离散样本证明无隐藏绕圈。
- [x] 在资源可承受且探针通过后，比较另一位移幅度和更密 k 网格；完整记录
  实际差异、未收敛或未覆盖事项。不同 PP/泛函文献仅作量级参照，不当严格oracle。
- [x] 成功范围按输出事实界定；一列/一材料/有限敏感性不冒充全张量或全面收敛。

### Task 4：审查与记录

- [x] 审查实算 inputs/logs、安装态结果与源码修复，核对证据链。
- [x] 更新拥有该状态的计划/导航，保留可复现脚本和所需原始输出；报告真实剩余项。

## 分工与恢复

安装 executor 只在 `/home/james/scratch/forge-release-validation-20261021/` 操作；
只读代理分别核查本地资源和科学对照；主控负责实算脚本/运行与规范裁决。
如需源码修复另行明确 ownership，其他 writer 暂停，保留前后失败证据。

## 完成与实验记录

安装态：wheel SHA256 `c70e71a698ea6fc6d697495845e45c8cb9a95876636e54705074ce2967a02180`；
全新 Python 3.12 venv，76 个 Python 文件与源码/安装态逐字节一致，8 文件 520 passed，
`pip check` 通过。未装 PyATB，不能据此宣称新环境原生 COHP 执行通过。

Ruling：实算选用固定 a=4.24584 Å 的两原子岩盐 MgO 原胞，O（原始 ASE 第 2 原子，prepare 重排后的 STRU/BEC 第 1 原子）沿 x
位移 0/±0.01 Å。使用既有 PBE NC Mg.PD04.PBE.UPF（2 价）与 O.upf（6 价），
PW 80 Ry、nspin=1、固定占据、SCF 4³、Berry NSCF 相应 gdir 加密为 8×4×4，
SCF 阈值 1e-10、对角化阈值 1e-11。单进程单线程，每阶段 timeout 300 秒。
使用 develop 既有引擎；先跑零位移探针，再扩展。若 runtime 可承受，补 ±0.005 Å
与 6³/12×6×6；预设 Zxx 敏感性差异参考阈值 0.1 e，不称科学收敛。
Auto 每步变化界 0.25 量子；显式模式 offsets 从原始连续性独立检查，不能证明隐藏绕圈不存在。
文献/官方结果仅作负号及约 -2 e 的数量级对照，非同 PP/泛函/基组的严格 oracle。
原始/官方参考：[VASP MgO](https://vasp.at/tutorials/latest/electron-phonon/part1/)、
[Posternak et al.](https://arxiv.org/pdf/cond-mat/9702086)、
[ABACUS Berry](https://abacus-rtd.readthedocs.io/en/latest/advanced/elec_properties/Berry_phase.html)。
全部输入、原生日志、charge handoff hashes 与脚本保留在
`/home/james/scratch/forge-real-bec-20261021/`。


探针及首组 12 次引擎执行均正常完成，原生日志 collector 全部成功。
Ruling：敏感性加密采用 SCF 5³ / NSCF 10×5×5，而非预估的 6³/12×6×6；
保留至少一次网格加密对照，控制首轮单列验证成本，不能据此宣称 k 网格收敛。
两种敏感性独立 case 最多并行两个单线程进程，每个 case 内仍顺序执行。
初始验证脚本的正常结束与 SCF 收敛字符串与真实格式不符，已改成
`Total  Time` 和 `#SCF IS CONVERGED#`，保留已成功原始引擎执行，无生产修复。
charge handoff 摘要相同指执行前复制；NSCF 会改写目标 restart，追加执行后
摘要并确认 SCF 源未变。nbands=4 仅含占据态，不用打印的零 gap 证明金属性或
绝缘性；MgO 绝缘性是材料前提，本轮不做独立带隙测量。


首组 installed CLI auto/explicit 与独立 NumPy 中心差分均得 O_x
`[-1.954825926723525, 0, 0] e`。独立 reviewer 从原生日志重算，相差约
9.4e-14 e；36 个 analysis 复制源摘要一致，无阻断发现。
半幅位移已完成，`[-1.954850069282804, 0, 0] e`，与首组 Zxx 差
2.414255927885023e-5 e；三法一致。5³ 网格已完成，`[-1.955397438111305, 0, 0] e`，
与首组 Zxx 差 0.0005715113877799993 e；三法一致。两项差异均低于预设
0.1 e 工程界，能力仍为 experimental/scientific unassessed。
32 次引擎、24 collect、最终三组6次BEC全部成功；生产源码无修改，
最终 wheel/source 字节一致性复核通过。独立终审通过，无阻断发现；状态导航与 guide/reference 已同步。


最终证据：[完整记录](../evidence/2026-10-21-forge-installed-bec-validation.md)。
独立 reviewer 检查全部8个SCF/24个NSCF及归档摘要，从敏感性原生日志重算与
安装态差异均小于2e-13 e。全部检查绑定本轮候选 wheel 和实际 dirty源码；
本轮生产源码未改。文档链接与归档完整性检查通过，`git diff --check` 通过。
实施仍留在原隔离工作树，未提交/合入/推送/发布。本计划不把后续全张量、
更多版本/材料、科学收敛或 Paimon/SAI 验收列为已完成；这些按实际需求另行推进。
