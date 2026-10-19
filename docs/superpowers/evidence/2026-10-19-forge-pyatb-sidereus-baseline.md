# PyATB sidereus-adam 集成基线与 COHP 差距确认

日期：2026-10-19。用户指定 `QuantumMisaka/pyatb` 的 `sidereus-adam` 为集成基线。

## 本地集成结果

- 基线 `9655a85` 已包含 COHP 权重/配对修正与 Python/C++ 正体积修正；将原 CSR 候选 `cfa5fb1` 无冲突移植为 `d638031`。
- PyATB 本地 `sidereus-adam` 已快进到 `dad27b5`，相对 `misaka/sidereus-adam` 领先两次提交；未推送远端。原 upstream main 保留。
- 完整测试 **47 passed，无 skip**，包含编译分支 C++ 源码的 handedness 回归。Eigen 固定为 `3147391`。
- 既有真实 Si/LCAO/nspin=1 的 develop/LTS 矩阵经 Forge prepare/execute/collect 两轨回放通过，每轨三条事件，band.dat 与原已安装包的 LTS 结果逐字节一致。未重新运行 ABACUS。
- 回放载体使用完整候选 Python 源码及旧安装包的 native extension；分支 C++ 修正另有上述编译测试证据。完整新 wheel 构建及安装消费仍待完成，不能据此宣称已安装旧包的问题已消除。

完整源码审查、绑定、原始测试和探针结果由 PyATB 自己维护：`pyatb/doc/SIDEREUS_CSR_COHP_REVIEW.md` 与 `pyatb/doc/validation/2026-10-19-sidereus-csr-cohp/`（工作区兄弟仓库）。独立 reviewer 复核无集成阻断。

## COHP 结论与推进顺序

对比当前 `abacus-cohp-lcao@78b3628`（参考仓测试 12 passed）：两者均为直接 NAO-block COHP/COOP，PyATB 从 H(R)/S(R) 插值并求本征态，参考仓消费 ABACUS H(k)/S(k)/WFC；不等同 Forge 现有 IAO 方法。

1. sidereus 已有 k 权重、nspin=1 简并及 nspin=2 分通道修正，不应重复移植。
2. 受控探针确认：同一原子内不相交轨道组应有的对称贡献为 1，PyATB 仅给 0.5；`invert=1` 改变数值但 header/metadata/绘图标签未表达符号；恰在能窗下界的态被丢弃。
3. PyATB 尚缺独立于展宽与绘图能窗的占据态离散 ICOHP/ICOOP。两仓 Gaussian sigma 定义和窗口处理也不同，不能直接比较同名参数下的曲线。
4. 先修轨道组因子、符号标注与网格/边界校验；部分重叠轨道组须明确语义或拒绝。再明确占据定义、积分输出契约，补 ICOHP/ICOOP，最后以相同本征态、权重、自旋和单位做真实材料 parity。

参考仓 `docs/validation-summary.md` 已撤回旧处理曲线及定量/性能结论，等待重新生成，不能将 README 案例清单当作当前黄金数据。流式 WFC 优化也不能直接搬到 PyATB 插值求解路径。

本轮仅合入 CSR 支持并确认 COHP 差距，未修改 COHP 算法或 Forge 公共契约；后续 COHP 修复由 PyATB 负责，Forge 保留显式消费边界。
